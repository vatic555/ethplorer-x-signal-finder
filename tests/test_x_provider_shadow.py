from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path

import pytest

from x_signal_finder.x_provider_shadow import (
    NormalizedPost,
    NormalizedReference,
    ProviderPage,
    ProviderRun,
    SearchTask,
    ShadowSpikeError,
    TwitterApiIoProvider,
    build_direct_id_cost_plan,
    build_discovery_cost_plan,
    compare_direct_id_lookup,
    compare_provider,
    direct_id_selection_summary,
    fetch_official_benchmark,
    fetch_stored_official_benchmark,
    normalize_official_post,
    normalize_socialdata_post,
    normalize_twitterapi_io_post,
    plan_search_tasks,
    plan_official_page_size,
    run_search_provider,
    select_direct_id_benchmark,
)
from x_signal_finder.x_api.client import HttpResponse, XApiRequestError


NOW = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)


def _post(
    post_id: str,
    *,
    provider="official_x",
    author="alice",
    post_type="original",
    text="complete text",
    referenced_post_id=None,
    referenced_context=None,
    media=(),
) -> NormalizedPost:
    return NormalizedPost(
        post_id=post_id,
        author=author,
        author_id="10",
        created_at=NOW,
        text=text,
        post_type=post_type,
        conversation_id=post_id,
        referenced_post_id=referenced_post_id,
        referenced_context=referenced_context,
        media_metadata=media,
        provider=provider,
    )


def test_normalize_official_post_preserves_long_text_context_and_media() -> None:
    post = {
        "id": "100",
        "author_id": "10",
        "created_at": "2026-08-14T12:00:00Z",
        "text": "fallback",
        "note_tweet": {"text": "x" * 400},
        "conversation_id": "90",
        "referenced_tweets": [{"type": "quoted", "id": "99"}],
        "attachments": {"media_keys": ["m1"]},
    }
    normalized = normalize_official_post(
        post,
        users_by_id={
            "10": {"username": "alice"},
            "11": {"username": "bob"},
        },
        expanded_posts_by_id={
            "99": {
                "id": "99",
                "author_id": "11",
                "created_at": "2026-08-14T11:00:00Z",
                "text": "quoted text",
            }
        },
        media_by_key={"m1": {"media_key": "m1", "type": "photo", "url": "u"}},
    )

    assert normalized.text == "x" * 400
    assert normalized.post_type == "quote"
    assert normalized.referenced_post_id == "99"
    assert normalized.referenced_context is not None
    assert normalized.referenced_context.text == "quoted text"
    assert normalized.media_metadata == ({"media_key": "m1", "type": "photo", "url": "u"},)
    assert "x" * 20 not in repr(normalized)


def test_normalize_twitterapi_io_post_preserves_quote_context() -> None:
    normalized = normalize_twitterapi_io_post(
        {
            "id": "100",
            "text": "comment",
            "createdAt": "Fri Aug 14 12:00:00 +0000 2026",
            "conversationId": "100",
            "author": {"id": "10", "userName": "alice"},
            "quoted_tweet": {
                "id": "99",
                "text": "quoted text",
                "createdAt": "Fri Aug 14 11:00:00 +0000 2026",
                "author": {"id": "11", "userName": "bob"},
            },
        }
    )

    assert normalized.post_type == "quote"
    assert normalized.referenced_post_id == "99"
    assert normalized.referenced_context is not None
    assert normalized.referenced_context.author == "bob"


def test_normalize_socialdata_post_uses_full_text_and_reply_id() -> None:
    normalized = normalize_socialdata_post(
        {
            "id_str": "100",
            "text": None,
            "full_text": "full reply",
            "tweet_created_at": "2026-08-14T12:00:00.000000Z",
            "in_reply_to_status_id_str": "99",
            "user": {"id_str": "10", "screen_name": "alice"},
            "extended_entities": {
                "media": [{"type": "photo", "media_url_https": "u"}]
            },
        }
    )

    assert normalized.text == "full reply"
    assert normalized.post_type == "reply"
    assert normalized.referenced_post_id == "99"
    assert normalized.media_metadata == ({"media_url_https": "u", "type": "photo"},)


def test_plan_search_tasks_groups_only_active_benchmark_authors() -> None:
    benchmark = tuple(
        _post(str(index), author="alice" if index < 8 else "bob")
        for index in range(14)
    ) + (_post("case-duplicate", author="ALICE"),)
    tasks = plan_search_tasks(
        benchmark,
        start=NOW - timedelta(hours=24),
        end=NOW,
    )

    assert {author for task in tasks for author in task.authors} == {"alice", "bob"}
    assert len(tasks) == 2


class _FakeProvider:
    name = "twitterapi_io"
    unit_cost_usd = Decimal("0.00015")

    def __init__(self, *, has_more=False):
        self._has_more = has_more
        self.calls = 0

    def search(self, task: SearchTask):
        self.calls += 1
        return ProviderPage(
            posts=(_post(str(self.calls), provider="twitterapi_io"),),
            raw_payload={"tweets": []},
            has_more=self._has_more,
        )


def test_provider_run_requires_approved_preflight_before_request(tmp_path) -> None:
    provider = _FakeProvider()
    with pytest.raises(ShadowSpikeError, match="approval is missing"):
        run_search_provider(
            provider,
            benchmark=(_post("1"),),
            start=NOW - timedelta(hours=24),
            end=NOW,
            spend_limit_usd=Decimal("0.10"),
            artifact_dir=tmp_path,
        )

    assert provider.calls == 0


def test_twitterapi_balance_includes_trial_bonus_credits(monkeypatch) -> None:
    monkeypatch.setattr(
        "x_signal_finder.x_provider_shadow._request_json",
        lambda **kwargs: (
            200,
            {"recharge_credits": 0, "total_bonus_credits": 10000},
        ),
    )

    assert TwitterApiIoProvider("key").balance_usd() == Decimal("0.1")


def test_twitterapi_overflow_splits_both_time_halves_and_dedupes(tmp_path) -> None:
    class Provider:
        name = "twitterapi_io"
        unit_cost_usd = Decimal("0.00015")

        def __init__(self):
            self.tasks = []

        def search(self, task):
            self.tasks.append(task)
            duration = int((task.end - task.start).total_seconds())
            if duration > 60:
                return ProviderPage(
                    posts=(_post("parent", provider=self.name),),
                    raw_payload={"window": duration},
                    has_more=True,
                    possible_incomplete=True,
                )
            suffix = "left" if task.end <= NOW - timedelta(seconds=60) else "right"
            return ProviderPage(
                posts=(
                    _post(suffix, provider=self.name),
                    _post("duplicate", provider=self.name),
                ),
                raw_payload={"window": suffix},
                has_more=False,
            )

    provider = Provider()
    benchmark = (_post("1"),)
    start = NOW - timedelta(seconds=120)
    plan = build_discovery_cost_plan(
        provider="twitterapi_io",
        benchmark=benchmark,
        start=start,
        end=NOW,
        hard_cap_usd=Decimal("0.10"),
        minimum_twitter_slice_seconds=60,
    )
    result = run_search_provider(
        provider,
        benchmark=benchmark,
        start=start,
        end=NOW,
        spend_limit_usd=Decimal("0.10"),
        artifact_dir=tmp_path,
        approved_plan_sha256=plan.plan_sha256,
        minimum_twitter_slice_seconds=60,
    )

    assert result.status == "complete"
    assert result.requests == 3
    assert len(provider.tasks) == 3
    assert {(task.start, task.end) for task in provider.tasks[1:]} == {
        (start, NOW - timedelta(seconds=60)),
        (NOW - timedelta(seconds=60), NOW),
    }
    assert {post.post_id for post in result.posts} == {
        "parent",
        "left",
        "right",
        "duplicate",
    }
    assert "canonical_post_id_duplicates_removed" in result.warnings


def test_twitterapi_overflow_at_minimum_slice_stops_without_loop(tmp_path) -> None:
    provider = _FakeProvider(has_more=True)
    benchmark = (_post("1"),)
    start = NOW - timedelta(seconds=60)
    plan = build_discovery_cost_plan(
        provider="twitterapi_io",
        benchmark=benchmark,
        start=start,
        end=NOW,
        hard_cap_usd=Decimal("0.10"),
        minimum_twitter_slice_seconds=60,
    )
    result = run_search_provider(
        provider,
        benchmark=benchmark,
        start=start,
        end=NOW,
        spend_limit_usd=Decimal("0.10"),
        artifact_dir=tmp_path,
        approved_plan_sha256=plan.plan_sha256,
        minimum_twitter_slice_seconds=60,
    )

    assert result.status == "incomplete_due_to_minimum_time_slice"
    assert result.requests == 1
    assert provider.calls == 1


def test_socialdata_traverses_cursor_and_blocks_repeated_cursor(tmp_path) -> None:
    class Provider:
        name = "socialdata"
        unit_cost_usd = Decimal("0.0002")

        def __init__(self):
            self.tasks = []

        def search(self, task):
            self.tasks.append(task)
            if task.cursor is None:
                return ProviderPage(
                    posts=(
                        _post("100", provider=self.name),
                        _post("99", provider=self.name),
                    ),
                    raw_payload={"page": 1},
                    has_more=True,
                    next_cursor="cursor-1",
                    possible_incomplete=True,
                )
            return ProviderPage(
                posts=(
                    _post("99", provider=self.name),
                    _post("98", provider=self.name),
                ),
                raw_payload={"page": 2},
                has_more=True,
                next_cursor="cursor-1",
                possible_incomplete=True,
            )

    provider = Provider()
    benchmark = (_post("1"),)
    plan = build_discovery_cost_plan(
        provider="socialdata",
        benchmark=benchmark,
        start=NOW - timedelta(hours=1),
        end=NOW,
        hard_cap_usd=Decimal("0.10"),
    )
    result = run_search_provider(
        provider,
        benchmark=benchmark,
        start=NOW - timedelta(hours=1),
        end=NOW,
        spend_limit_usd=Decimal("0.10"),
        artifact_dir=tmp_path,
        approved_plan_sha256=plan.plan_sha256,
    )

    assert result.status == "incomplete_due_to_repeated_cursor"
    assert result.requests == 2
    assert provider.tasks[1].cursor == "cursor-1"
    assert {post.post_id for post in result.posts} == {"100", "99", "98"}
    assert "canonical_post_id_duplicates_removed" in result.warnings


def test_socialdata_uses_max_id_fallback_when_cursor_is_absent(tmp_path) -> None:
    class Provider:
        name = "socialdata"
        unit_cost_usd = Decimal("0.0002")

        def __init__(self):
            self.tasks = []

        def search(self, task):
            self.tasks.append(task)
            if task.max_id is None:
                return ProviderPage(
                    posts=(_post("100", provider=self.name),),
                    raw_payload={"page": 1},
                    has_more=True,
                    continuation_max_id="99",
                    possible_incomplete=True,
                )
            return ProviderPage(
                posts=(_post("98", provider=self.name),),
                raw_payload={"page": 2},
                has_more=False,
            )

    provider = Provider()
    benchmark = (_post("1"),)
    plan = build_discovery_cost_plan(
        provider="socialdata",
        benchmark=benchmark,
        start=NOW - timedelta(hours=1),
        end=NOW,
        hard_cap_usd=Decimal("0.10"),
    )
    result = run_search_provider(
        provider,
        benchmark=benchmark,
        start=NOW - timedelta(hours=1),
        end=NOW,
        spend_limit_usd=Decimal("0.10"),
        artifact_dir=tmp_path,
        approved_plan_sha256=plan.plan_sha256,
    )

    assert result.status == "complete"
    assert result.requests == 2
    assert provider.tasks[1].max_id == "99"
    assert "socialdata_max_id_fallback_used" in result.warnings


def test_socialdata_blocks_repeated_max_id_without_loop(tmp_path) -> None:
    class Provider:
        name = "socialdata"
        unit_cost_usd = Decimal("0.0002")

        def __init__(self):
            self.calls = 0

        def search(self, task):
            self.calls += 1
            return ProviderPage(
                posts=(_post(str(100 - self.calls), provider=self.name),),
                raw_payload={"call": self.calls},
                has_more=True,
                continuation_max_id="90",
                possible_incomplete=True,
            )

    provider = Provider()
    benchmark = (_post("1"),)
    plan = build_discovery_cost_plan(
        provider="socialdata",
        benchmark=benchmark,
        start=NOW - timedelta(hours=1),
        end=NOW,
        hard_cap_usd=Decimal("0.10"),
    )
    result = run_search_provider(
        provider,
        benchmark=benchmark,
        start=NOW - timedelta(hours=1),
        end=NOW,
        spend_limit_usd=Decimal("0.10"),
        artifact_dir=tmp_path,
        approved_plan_sha256=plan.plan_sha256,
    )

    assert result.status == "incomplete_due_to_repeated_max_id"
    assert result.requests == 2
    assert provider.calls == 2


def test_direct_id_selection_and_fixture_comparison_are_offline() -> None:
    fixture = json.loads(
        Path("tests/fixtures/provider_direct_id.json").read_text(encoding="utf-8")
    )

    def convert(item, provider):
        context = (
            NormalizedReference(
                item["referenced_post_id"], "context_author", NOW, "context", ()
            )
            if item["referenced_context"]
            else None
        )
        return _post(
            item["post_id"],
            provider=provider,
            author=item["author"],
            post_type=item["post_type"],
            text=item["text"],
            referenced_post_id=item["referenced_post_id"],
            referenced_context=context,
            media=({"type": "photo"},) if item["media"] else (),
        )

    benchmark = tuple(convert(item, "official_x") for item in fixture["benchmark"])
    provider_posts = tuple(
        convert(item, "twitterapi_io") for item in fixture["provider_result"]
    )
    selected = select_direct_id_benchmark(benchmark, limit=4)
    selection = direct_id_selection_summary(selected)
    plan = build_direct_id_cost_plan(
        provider="twitterapi_io",
        benchmark=selected,
        hard_cap_usd=Decimal("0.02"),
    )
    report = compare_direct_id_lookup(
        selected,
        ProviderRun(
            provider="twitterapi_io",
            status="complete",
            posts=provider_posts,
            requests=0,
            pagination_gaps=0,
            estimated_spend_usd=Decimal("0"),
            actual_spend_usd=Decimal("0"),
            warnings=("offline_fixture",),
        ),
    )

    assert selection["selected_post_ids"] == 4
    assert selection["long_posts"] == 1
    assert selection["replies"] == 1
    assert selection["quotes"] == 1
    assert selection["with_referenced_context"] == 2
    assert selection["with_media"] == 2
    assert plan.estimated_requests == 1
    assert plan.expected_billable_resources == 4
    assert plan.fits_hard_cap is True
    assert report["available_ids"] == 3
    assert report["unavailable_ids"] == 1
    assert report["comparison"]["full_text"]["exact_matches"] == 2
    assert report["comparison"]["long_posts"]["exact_text"] == 1
    assert report["comparison"]["post_type"]["accuracy_pct"] == 100.0
    assert report["comparison"]["referenced_context"]["coverage_pct"] == 50.0
    assert report["comparison"]["media"]["coverage_pct"] == 50.0


def test_official_page_size_shrinks_at_budget_boundary() -> None:
    assert plan_official_page_size(
        remaining_budget_usd=Decimal("0.31"),
        requested_page_size=100,
        worst_case_cost_per_primary_usd=Decimal("0.10"),
    ) == 3


def test_official_partial_402_keeps_page_and_partial_summary(
    monkeypatch, tmp_path
) -> None:
    payload = {
        "data": [
            {
                "id": "100",
                "author_id": "10",
                "created_at": "2026-08-14T12:00:00Z",
                "conversation_id": "100",
                "text": "Synthetic benchmark Post.",
            }
        ],
        "includes": {"users": [{"id": "10", "username": "alice"}]},
        "meta": {
            "result_count": 1,
            "newest_id": "100",
            "oldest_id": "100",
            "next_token": "more",
        },
    }

    class Config:
        client_id = "client"
        refresh_token = "refresh"
        base_url = "https://example.invalid"

        def require_collector_setup(self):
            return None

        def user_id_for(self, source):
            assert source == "home"
            return "1"

    class Tokens:
        access_token = "access"
        refresh_token = "rotated"

    class Client:
        def __init__(self, **kwargs):
            self.calls = 0

        def _get(self, endpoint, params):
            self.calls += 1
            if self.calls == 1:
                return (
                    HttpResponse(
                        status=200,
                        headers={},
                        body=json.dumps(payload).encode("utf-8"),
                    ),
                    0.1,
                )
            raise XApiRequestError(
                status=402,
                category="api_error",
                endpoint=endpoint,
            )

    monkeypatch.setattr(
        "x_signal_finder.x_provider_shadow.load_x_api_config", lambda: Config()
    )
    monkeypatch.setattr(
        "x_signal_finder.x_provider_shadow.refresh_access_token",
        lambda **kwargs: Tokens(),
    )
    monkeypatch.setattr(
        "x_signal_finder.x_provider_shadow.persist_refresh_token", lambda value: None
    )
    monkeypatch.setattr("x_signal_finder.x_provider_shadow.XApiClient", Client)

    result = fetch_official_benchmark(
        start=NOW - timedelta(hours=24),
        end=NOW,
        max_pages=3,
        artifact_dir=tmp_path,
        approved_max_spend_usd=Decimal("1.00"),
        worst_case_cost_per_primary_usd=Decimal("0.10"),
        max_results_per_page=10,
    )

    assert result.status == "incomplete_due_to_credit"
    assert result.requests == 1
    assert (tmp_path / "official_x" / "response-0001.json").is_file()
    partial = json.loads(
        (tmp_path / "official_x" / "partial-summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert partial["successful_pages"] == 1
    assert partial["attempted_requests"] == 2
    assert partial["terminal_http_status"] == 402
    assert partial["raw_pages_durable"] is True


def test_compare_provider_reports_recall_text_type_context_and_media() -> None:
    context = NormalizedReference("90", "bob", NOW, "context", ())
    benchmark = (
        _post("1", text="x" * 300, media=({"type": "photo"},)),
        _post(
            "2",
            post_type="reply",
            referenced_post_id="90",
            referenced_context=context,
        ),
        _post("3", post_type="quote", referenced_post_id="80"),
    )
    provider_posts = (
        _post("1", provider="socialdata", text="x" * 299),
        _post(
            "2",
            provider="socialdata",
            post_type="original",
            referenced_post_id=None,
        ),
        _post("4", provider="socialdata"),
        _post("4", provider="socialdata"),
    )
    report = compare_provider(
        benchmark,
        ProviderRun(
            provider="socialdata",
            status="complete",
            posts=provider_posts,
            requests=1,
            pagination_gaps=0,
            estimated_spend_usd=Decimal("0.0008"),
            actual_spend_usd=None,
            warnings=(),
        ),
    )

    assert report["matched_benchmark_ids"] == 2
    assert report["missing_benchmark_ids"] == 1
    assert report["extra_ids"] == 1
    assert report["recall_pct"] == 66.67
    assert report["full_text"]["exact_pct"] == 50.0
    assert report["long_posts"]["truncated_or_mismatched"] == 1
    assert report["post_type"]["accuracy_pct"] == 50.0
    assert report["duplicates"] == 1


def test_stored_official_benchmark_is_read_only(monkeypatch) -> None:
    class Cursor:
        def __init__(self):
            self.query_count = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, statement, parameters=None):
            assert statement.lstrip().upper().startswith("SELECT")
            self.query_count += 1

        def fetchone(self):
            return (NOW,)

        def fetchall(self):
            return [
                (
                    "100",
                    "10",
                    "alice",
                    NOW,
                    "full stored text",
                    "quote",
                    "100",
                    "99",
                    {
                        "_expanded": {
                            "referenced_post": {
                                "id": "99",
                                "created_at": "2026-08-14T11:00:00Z",
                                "text": "quoted text",
                            },
                            "referenced_post_author": {"username": "bob"},
                            "media": [{"type": "photo", "url": "u"}],
                        }
                    },
                )
            ]

    class Connection:
        def __init__(self):
            self.cursor_value = Cursor()
            self.rollback_called = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def cursor(self):
            return self.cursor_value

        def rollback(self):
            self.rollback_called = True

    connection = Connection()
    monkeypatch.setattr(
        "x_signal_finder.x_provider_shadow.load_database_config", lambda: object()
    )
    monkeypatch.setattr(
        "x_signal_finder.x_provider_shadow.connect_database", lambda config: connection
    )

    result, start, end = fetch_stored_official_benchmark(hours=24)

    assert start == NOW - timedelta(hours=24)
    assert end == NOW
    assert result.requests == 0
    assert result.posts[0].referenced_context is not None
    assert result.posts[0].media_metadata == ({"type": "photo", "url": "u"},)
    assert connection.rollback_called is True
