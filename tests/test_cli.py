from contextlib import nullcontext
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest

import x_signal_finder.cli as cli_module
from x_signal_finder.cli import build_parser, main
from x_signal_finder.collector import FetchedSource, source_key_for
from x_signal_finder.x_api.client import XApiRequestError


def test_database_subcommands_parse() -> None:
    parser = build_parser()

    for subcommand in ("doctor", "migrate", "status", "smoke-test"):
        args = parser.parse_args(["db", subcommand])
        assert args.command == "db"
        assert args.db_command == subcommand


def test_project_status_does_not_require_database(capsys) -> None:
    result = main(["status"])

    assert result == 0
    output = capsys.readouterr().out
    assert "PostgreSQL storage foundation is implemented" in output
    assert "access spike is complete with a constrained-go decision" in output
    assert "Stage 3 collection is complete" in output
    assert "Task 005A Git-backed knowledge architecture" in output
    assert "Task 005C first-party X corpus sync are implemented" in output


def test_knowledge_validate_is_offline_and_valid(capsys) -> None:
    result = main(["knowledge", "validate"])

    assert result == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "valid"
    assert report["source_count"] == 17
    assert report["asset_count"] == 0
    assert report["network_requests"] == 0
    assert report["llm_calls"] == 0


def test_x_api_subcommands_parse() -> None:
    parser = build_parser()

    args = parser.parse_args(["x-api", "probe", "home", "--user-id", "123"])
    assert args.command == "x-api"
    assert args.x_api_command == "probe"
    assert args.source == "home"

    oauth_setup = parser.parse_args(["x-api", "oauth-setup"])
    assert oauth_setup.x_api_command == "oauth-setup"


def test_collect_defaults_are_bounded() -> None:
    args = build_parser().parse_args(["collect", "--source", "home"])

    assert args.command == "collect"
    assert args.max_pages == 5
    assert args.max_results == 100
    assert str(args.max_estimated_cost_usd) == "1.00"
    assert args.max_primary_posts_total is None
    assert args.max_attempts == 3
    assert args.max_retry_wait_seconds == 60
    assert args.refresh_existing is False


def test_collect_refresh_existing_requires_explicit_flag() -> None:
    args = build_parser().parse_args(
        ["collect", "--source", "home", "--refresh-existing"]
    )

    assert args.refresh_existing is True


def test_accept_baseline_cli_requires_explicit_confirmation_flag() -> None:
    args = build_parser().parse_args(
        [
            "collect",
            "accept-baseline",
            "--source",
            "home",
            "--run-id",
            "00000000-0000-0000-0000-000000000123",
        ]
    )

    assert args.collect_action == "accept-baseline"
    assert args.confirm_skip_older_posts is False


def test_collect_rejects_invalid_shared_page_size_before_external_calls(capsys) -> None:
    result = main(["collect", "--source", "both", "--max-results", "1"])

    assert result == 2
    assert "max_results for mentions" in capsys.readouterr().err


def test_x_api_probe_without_credentials_fails_before_network(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    for name in (
        "X_ACCESS_TOKEN",
        "X_BEARER_TOKEN",
        "X_HOME_USER_ID",
        "X_ETHPLORER_USER_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    result = main(["x-api", "probe", "home", "--user-id", "123"])

    assert result == 2
    assert "X_ACCESS_TOKEN" in capsys.readouterr().err


class _FakeCollectConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def transaction(self):
        return nullcontext()


class _FakeCollectRepository:
    def __init__(self):
        self.states = {
            "x_home_timeline": {"checkpoint_value": "100"},
            "x_ethplorer_mentions": {"checkpoint_value": "200"},
        }
        self.usage = []
        self.sync_updates = []

    def create_run(self, **values):
        self.run = values

    def get_sync_state(self, source_key):
        return self.states.get(source_key)

    def get_existing_post_ids(self, post_ids):
        return frozenset()

    def upsert_posts(self, posts):
        self.posts = list(posts)

    def update_sync_state(self, **values):
        self.sync_updates.append(values)

    def record_usage_event(self, event):
        self.usage.append(event)

    def complete_run(self, **values):
        self.completed = values

    def fail_run(self, **values):
        self.failed = values


def _fetched(source, *, primary=0):
    checkpoint = "100" if source == "home" else "200"
    return FetchedSource(
        source=source,
        source_key=source_key_for(source),
        endpoint=f"/{source}",
        requests_count=1,
        fetched_posts=primary,
        expanded_posts_received=0,
        distinct_post_resources_received=primary,
        reposts_excluded=0,
        records=(),
        newest_post_id=checkpoint,
        oldest_post_id=checkpoint,
        checkpoint_before=checkpoint,
        checkpoint_candidate=checkpoint,
        checkpoint_can_advance=True,
        refresh_existing=False,
        completion_state="complete",
        unit_cost_usd=Decimal("0.005"),
        estimated_cost_usd=Decimal("0.005") * primary,
        warnings=(),
    )


def _patch_collect_runtime(monkeypatch, fetch):
    repository = _FakeCollectRepository()
    config = SimpleNamespace(
        client_id="synthetic-client",
        refresh_token="synthetic-refresh",
        base_url="https://example.invalid",
        post_read_unit_cost_usd=Decimal("0.005"),
        require_collector_setup=lambda: None,
        user_id_for=lambda source: "123",
    )
    monkeypatch.setattr(cli_module, "load_database_config", lambda: object())
    monkeypatch.setattr(cli_module, "load_x_api_config", lambda: config)
    monkeypatch.setattr(
        cli_module,
        "refresh_access_token",
        lambda **values: SimpleNamespace(
            access_token="synthetic-access", refresh_token="synthetic-refresh-2"
        ),
    )
    monkeypatch.setattr(cli_module, "persist_refresh_token", lambda token: None)
    monkeypatch.setattr(
        cli_module, "connect_database", lambda config: _FakeCollectConnection()
    )
    monkeypatch.setattr(cli_module, "StorageRepository", lambda connection: repository)
    monkeypatch.setattr(cli_module, "fetch_source", fetch)
    return repository


def test_primary_post_limit_is_global_for_both_sources(
    monkeypatch, capsys
) -> None:
    called = []

    def fetch(**values):
        called.append(values["source"])
        return _fetched(values["source"], primary=20)

    _patch_collect_runtime(monkeypatch, fetch)
    result = main(
        [
            "collect",
            "--source",
            "both",
            "--max-primary-posts-total",
            "20",
        ]
    )
    report = json.loads(capsys.readouterr().out)

    assert result == 1
    assert called == ["home"]
    assert len(report["sources"]) == 2
    assert report["usage"]["primary_posts_received"] == 20
    assert report["sources"][1]["error_category"] == (
        "not_requested_due_to_primary_post_limit"
    )


def test_home_failure_does_not_prevent_mentions_collection(
    monkeypatch, capsys
) -> None:
    called = []

    def fetch(**values):
        source = values["source"]
        called.append(source)
        if source == "home":
            raise XApiRequestError(
                status=503,
                category="api_error",
                endpoint="/home",
            )
        return _fetched("mentions")

    _patch_collect_runtime(monkeypatch, fetch)
    result = main(["collect", "--source", "both"])
    report = json.loads(capsys.readouterr().out)

    assert result == 1
    assert called == ["home", "mentions"]
    assert any(source["source"] == "mentions" for source in report["sources"])


def test_cost_guard_skips_mentions_once_without_duplicate_report(
    monkeypatch, capsys
) -> None:
    called = []

    def fetch(**values):
        called.append(values["source"])
        return _fetched(values["source"], primary=272)

    _patch_collect_runtime(monkeypatch, fetch)
    result = main(["collect", "--source", "both", "--max-estimated-cost-usd", "1"])
    report = json.loads(capsys.readouterr().out)

    assert result == 1
    assert called == ["home"]
    assert len(report["sources"]) == 2
    assert report["sources"][1]["error_category"] == (
        "not_requested_due_to_cost_guard"
    )


def test_accept_baseline_dry_run_never_loads_x_or_updates_checkpoint(
    monkeypatch, capsys
) -> None:
    repository = _FakeCollectRepository()
    candidate = {
        "action": "accept_baseline",
        "status": "confirmation_required",
        "source": "home",
        "source_key": "x_home_timeline",
        "source_run_id": "00000000-0000-0000-0000-000000000123",
        "previous_checkpoint": "100",
        "accepted_checkpoint": "300",
        "incomplete_reasons": ["cost_guard_reached"],
        "older_window_may_have_been_skipped": True,
        "primary_posts_received": 194,
        "saved_posts": 152,
        "checkpoint_provenance": "usage_metadata.newest_post_id",
    }
    monkeypatch.setattr(cli_module, "load_database_config", lambda: object())
    monkeypatch.setattr(
        cli_module, "connect_database", lambda config: _FakeCollectConnection()
    )
    monkeypatch.setattr(cli_module, "StorageRepository", lambda connection: repository)
    monkeypatch.setattr(
        cli_module, "inspect_baseline_candidate", lambda **values: candidate
    )
    monkeypatch.setattr(
        cli_module,
        "load_x_api_config",
        lambda: pytest.fail("accept-baseline must not load X configuration"),
    )

    result = main(
        [
            "collect",
            "accept-baseline",
            "--source",
            "home",
            "--run-id",
            candidate["source_run_id"],
        ]
    )
    report = json.loads(capsys.readouterr().out)

    assert result == 1
    assert report["status"] == "confirmation_required"
    assert repository.sync_updates == []
