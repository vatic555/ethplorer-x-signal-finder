"""Cross-platform command-line interface."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime, timezone
import json
import sys
from uuid import uuid4

import psycopg

from x_signal_finder import __version__
from x_signal_finder.collector import (
    CollectionError,
    fetch_source,
    record_failed_source_attempt,
    save_source_collection,
    source_key_for,
)
from x_signal_finder.config import (
    ConfigurationError,
    load_database_config,
    redact_secrets,
)
from x_signal_finder.db.checks import inspect_database
from x_signal_finder.db.connection import connect_database
from x_signal_finder.db.migrations import (
    MigrationError,
    apply_migrations,
    default_migrations_directory,
    discover_migrations,
)
from x_signal_finder.db.repository import StorageRepository
from x_signal_finder.x_api.client import XApiClient, XApiRequestError
from x_signal_finder.x_api.config import (
    XApiConfigurationError,
    load_x_api_config,
    persist_refresh_token,
)
from x_signal_finder.x_api.oauth import (
    OAuthFlowError,
    authorize_with_local_callback,
    refresh_access_token,
)
from x_signal_finder.x_api.probe import run_probe


STATUS_MESSAGE = (
    "Durable PostgreSQL storage foundation is implemented. "
    "The X API access spike is complete with a constrained-go decision. "
    "The bounded Task 004A X collector is complete and Stage 3 remains in progress. "
    "LLM integration is not implemented."
)


def build_parser() -> argparse.ArgumentParser:
    """Build and return the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="x-signal-finder",
        description="Ethplorer X Signal Finder project CLI.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "status",
        help="Show implementation status without external API calls.",
    )
    database = subparsers.add_parser(
        "db",
        help="Inspect and explicitly manage PostgreSQL storage.",
    )
    database_subparsers = database.add_subparsers(dest="db_command")
    database_subparsers.add_parser(
        "doctor",
        help="Run read-only configuration, connection, schema, and RLS checks.",
    )
    database_subparsers.add_parser(
        "migrate",
        help="Apply pending checksum-verified migrations.",
    )
    database_subparsers.add_parser(
        "status",
        help="Show connection and migration status without row contents.",
    )
    database_subparsers.add_parser(
        "smoke-test",
        help="Exercise repository operations and roll back all synthetic data.",
    )
    x_api = subparsers.add_parser(
        "x-api",
        help="Run isolated, read-only X API access-spike diagnostics.",
    )
    x_api_subparsers = x_api.add_subparsers(dest="x_api_command")
    probe = x_api_subparsers.add_parser(
        "probe",
        help="Probe one timeline endpoint using an environment-provided token.",
    )
    probe.add_argument("source", choices=("home", "mentions"))
    probe.add_argument("--user-id")
    probe.add_argument("--max-pages", type=int, default=2)
    probe.add_argument("--max-results", type=int, default=100)
    probe.add_argument("--checkpoint-id")
    probe.add_argument(
        "--repeat-first-page",
        action="store_true",
        help="Repeat page one to compare IDs; this consumes an extra request.",
    )
    oauth_probe = x_api_subparsers.add_parser(
        "oauth-probe",
        help=(
            "Run one-time OAuth 2.0 PKCE authorization, validate refresh, and "
            "probe without persisting tokens or responses."
        ),
    )
    oauth_probe.add_argument(
        "--source",
        choices=("home", "mentions", "both"),
        default="home",
    )
    oauth_probe.add_argument("--home-user-id")
    oauth_probe.add_argument("--ethplorer-user-id")
    oauth_probe.add_argument("--max-pages", type=int, default=2)
    oauth_probe.add_argument("--max-results", type=int, default=100)
    oauth_probe.add_argument("--checkpoint-id")
    oauth_probe.add_argument("--repeat-first-page", action="store_true")
    x_api_subparsers.add_parser(
        "oauth-setup",
        help="Authorize once and store only the refresh token in local .env.",
    )
    collect = subparsers.add_parser(
        "collect",
        help="Run the bounded Task 004A X collector and persist to PostgreSQL.",
    )
    collect.add_argument(
        "--source",
        choices=("home", "mentions", "both"),
        default="both",
    )
    collect.add_argument("--max-pages", type=int, default=1)
    collect.add_argument("--max-results", type=int, default=20)
    return parser


def _load_migrations():
    return discover_migrations(default_migrations_directory())


def _print_table_summary(prefix: str, values: frozenset[str]) -> None:
    rendered = ", ".join(sorted(values)) if values else "none"
    print(f"{prefix}: {rendered}")


def _run_db_status(*, doctor: bool) -> int:
    config = load_database_config()
    if doctor:
        print("Configuration: available")
    migrations = _load_migrations()
    with connect_database(config) as connection:
        inspection = inspect_database(connection, migrations)
    print("Connection: available")
    if doctor:
        print(f"PostgreSQL version: {inspection.postgres_version}")
    current = (
        str(inspection.current_migration_version)
        if inspection.current_migration_version is not None
        else "none"
    )
    print(f"Current migration version: {current}")
    print(f"Pending migrations: {inspection.pending_migration_count}")
    _print_table_summary("Missing required tables", inspection.missing_tables)
    if doctor:
        _print_table_summary(
            "Operational tables missing RLS",
            inspection.rls_missing_tables,
        )
        healthy = not inspection.missing_tables and not inspection.rls_missing_tables
        print(f"Doctor result: {'healthy' if healthy else 'attention required'}")
        return 0 if healthy else 1
    return 0


def _run_db_migrate() -> int:
    config = load_database_config()
    migrations = _load_migrations()
    with connect_database(config) as connection:
        applied = apply_migrations(connection, migrations)
    if applied:
        print("Applied migrations: " + ", ".join(str(version) for version in applied))
    else:
        print("Applied migrations: none (database is up to date)")
    return 0


def _run_db_smoke_test() -> int:
    config = load_database_config()
    now = datetime.now(timezone.utc)
    run_id = uuid4()
    signal_id = uuid4()
    opportunity_id = uuid4()
    review_id = uuid4()
    usage_event_id = uuid4()
    suffix = uuid4().hex
    post_id = f"synthetic-smoke-post-{suffix}"
    source_key = f"synthetic-smoke-source-{suffix}"

    with connect_database(config) as connection:
        repository = StorageRepository(connection)
        with connection.transaction(force_rollback=True):
            repository.create_run(
                run_id=run_id,
                started_at=now,
                trigger_type="smoke_test",
                application_version=__version__,
                metadata={"synthetic": True},
            )
            repository.upsert_posts(
                [
                    {
                        "post_id": post_id,
                        "author_id": "synthetic-author",
                        "author_username": "synthetic_user",
                        "created_at": now,
                        "conversation_id": post_id,
                        "post_type": "synthetic",
                        "source_key": source_key,
                        "text": "Synthetic smoke-test content.",
                        "raw_json": {"synthetic": True},
                        "first_seen_run_id": run_id,
                        "last_seen_run_id": run_id,
                        "first_collected_at": now,
                        "last_collected_at": now,
                        "processing_status": "synthetic",
                        "availability_status": "available",
                    }
                ]
            )
            repository.create_signal(
                {
                    "signal_id": signal_id,
                    "created_at": now,
                    "updated_at": now,
                    "first_run_id": run_id,
                    "title": "Synthetic smoke-test Signal",
                    "summary": "Synthetic storage validation only.",
                    "topic": "synthetic",
                    "status": "synthetic",
                    "gate_decision": "accepted",
                    "gate_reason": "Synthetic storage validation only.",
                    "evidence": [{"synthetic": True}],
                }
            )
            repository.attach_posts_to_signal(
                signal_id=signal_id,
                posts=[(post_id, "synthetic_evidence")],
                added_at=now,
            )
            repository.create_opportunity(
                {
                    "opportunity_id": opportunity_id,
                    "signal_id": signal_id,
                    "created_at": now,
                    "updated_at": now,
                    "opportunity_type": "reply",
                    "information_gap": "Synthetic gap.",
                    "audience_benefit": "Synthetic validation.",
                    "natural_relevance_reason": "Synthetic storage test.",
                    "recommended_action": "reply",
                    "gate_snapshot": {"decision": "accepted", "synthetic": True},
                    "review_status": "pending",
                }
            )
            repository.add_human_review(
                {
                    "review_id": review_id,
                    "opportunity_id": opportunity_id,
                    "reviewer": "synthetic-reviewer",
                    "decision": "deferred",
                    "reason": "Synthetic rollback validation.",
                    "created_at": now,
                }
            )
            repository.record_usage_event(
                {
                    "usage_event_id": usage_event_id,
                    "run_id": run_id,
                    "provider": "synthetic",
                    "operation": "smoke_test",
                    "request_count": 0,
                    "created_at": now,
                }
            )
            repository.update_sync_state(
                source_key=source_key,
                checkpoint_value="synthetic-checkpoint",
                checkpoint_metadata={"synthetic": True},
                last_attempt_at=now,
                last_successful_at=now,
                last_successful_run_id=run_id,
                last_warning_code=None,
                updated_at=now,
            )
            state = repository.get_sync_state(source_key)
            if state is None or state["checkpoint_value"] != "synthetic-checkpoint":
                raise RuntimeError("Synthetic sync state could not be read back.")

        remaining = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM runs WHERE run_id = %s)
              + (SELECT count(*) FROM posts WHERE post_id = %s)
              + (SELECT count(*) FROM signals WHERE signal_id = %s)
              + (SELECT count(*) FROM signal_posts WHERE signal_id = %s)
              + (SELECT count(*) FROM opportunities WHERE opportunity_id = %s)
              + (SELECT count(*) FROM human_reviews WHERE review_id = %s)
              + (SELECT count(*) FROM usage_events WHERE usage_event_id = %s)
              + (SELECT count(*) FROM sync_state WHERE source_key = %s)
            """,
            (
                run_id,
                post_id,
                signal_id,
                signal_id,
                opportunity_id,
                review_id,
                usage_event_id,
                source_key,
            ),
        ).fetchone()[0]
        connection.rollback()
        if remaining != 0:
            raise RuntimeError("Smoke-test rollback verification failed.")
    print("Smoke test: passed; all synthetic changes were rolled back")
    return 0


def _run_db_command(command: str) -> int:
    if command == "doctor":
        return _run_db_status(doctor=True)
    if command == "migrate":
        return _run_db_migrate()
    if command == "status":
        return _run_db_status(doctor=False)
    if command == "smoke-test":
        return _run_db_smoke_test()
    raise ValueError(f"Unknown database command: {command}")


def _print_probe(summary) -> None:
    print(json.dumps(summary.safe_diagnostic(), indent=2, sort_keys=True))


def _run_x_api_probe(args: argparse.Namespace) -> int:
    config = load_x_api_config()
    user_id = config.user_id_for(args.source, args.user_id)
    client = XApiClient(token=config.token_for(args.source), base_url=config.base_url)
    summary = run_probe(
        client=client,
        source=args.source,
        user_id=user_id,
        max_pages=args.max_pages,
        max_results=args.max_results,
        checkpoint_id=args.checkpoint_id,
        repeat_first_page=args.repeat_first_page,
    )
    _print_probe(summary)
    return 0


def _run_oauth_probe(args: argparse.Namespace) -> int:
    config = load_x_api_config()
    config.require_oauth_setup()
    tokens = authorize_with_local_callback(
        client_id=config.client_id,
        redirect_uri=config.redirect_uri,
    )
    print("OAuth 2.0 PKCE authorization and refresh: succeeded")

    sources = ("home", "mentions") if args.source == "both" else (args.source,)
    for source in sources:
        explicit_id = (
            args.home_user_id if source == "home" else args.ethplorer_user_id
        )
        user_id = config.user_id_for(source, explicit_id)
        summary = run_probe(
            client=XApiClient(token=tokens.access_token, base_url=config.base_url),
            source=source,
            user_id=user_id,
            max_pages=args.max_pages,
            max_results=args.max_results,
            checkpoint_id=args.checkpoint_id,
            repeat_first_page=args.repeat_first_page,
        )
        _print_probe(summary)
    print("OAuth tokens and API responses were not persisted.")
    return 0


def _run_oauth_setup() -> int:
    config = load_x_api_config()
    config.require_oauth_setup()
    tokens = authorize_with_local_callback(
        client_id=config.client_id,
        redirect_uri=config.redirect_uri,
    )
    persist_refresh_token(tokens.refresh_token)
    print("OAuth setup: succeeded; refresh token stored in local .env")
    print("Access token: held in memory only and discarded")
    return 0


def _run_x_api_command(args: argparse.Namespace) -> int:
    if args.x_api_command == "probe":
        return _run_x_api_probe(args)
    if args.x_api_command == "oauth-probe":
        return _run_oauth_probe(args)
    if args.x_api_command == "oauth-setup":
        return _run_oauth_setup()
    raise ValueError(f"Unknown X API command: {args.x_api_command}")


def _failed_source_diagnostic(
    *,
    source: str,
    error_category: str,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    diagnostic: dict[str, object] = {
        "source": source,
        "source_key": source_key_for(source),
        "error_category": error_category,
    }
    diagnostic.update(details or {})
    return diagnostic


def _run_collect(args: argparse.Namespace) -> int:
    if args.max_pages < 1:
        raise ValueError("max_pages must be at least 1")
    if args.source in {"mentions", "both"} and args.max_results < 5:
        raise ValueError("max_results for mentions must be between 5 and 100")
    if not 1 <= args.max_results <= 100:
        raise ValueError("max_results must be between 1 and 100")

    database_config = load_database_config()
    x_config = load_x_api_config()
    x_config.require_collector_setup()
    refreshed = refresh_access_token(
        client_id=x_config.client_id,
        refresh_token=x_config.refresh_token,
    )
    persist_refresh_token(refreshed.refresh_token)

    run_id = uuid4()
    started_at = datetime.now(timezone.utc)
    requested_sources = (
        ("home", "mentions") if args.source == "both" else (args.source,)
    )
    user_ids = {
        source: x_config.user_id_for(source) for source in requested_sources
    }
    summaries = []
    failures: list[dict[str, object]] = []

    with connect_database(database_config) as connection:
        repository = StorageRepository(connection)
        with connection.transaction():
            repository.create_run(
                run_id=run_id,
                started_at=started_at,
                trigger_type="manual_x_collection",
                application_version=__version__,
                metadata={
                    "source": args.source,
                    "max_pages": args.max_pages,
                    "max_results": args.max_results,
                    "task": "004A",
                },
            )

        for source in requested_sources:
            source_key = source_key_for(source)
            with connection.transaction():
                previous_state = repository.get_sync_state(source_key)
            checkpoint_before = (
                str(previous_state["checkpoint_value"])
                if previous_state and previous_state.get("checkpoint_value") is not None
                else None
            )
            collected_at = datetime.now(timezone.utc)
            try:
                fetched = fetch_source(
                    client=XApiClient(
                        token=refreshed.access_token,
                        base_url=x_config.base_url,
                    ),
                    source=source,
                    user_id=user_ids[source],
                    run_id=run_id,
                    collected_at=collected_at,
                    checkpoint_before=checkpoint_before,
                    max_pages=args.max_pages,
                    max_results=args.max_results,
                )
            except XApiRequestError as error:
                failure = _failed_source_diagnostic(
                    source=source,
                    error_category=error.category,
                    details={
                        "http_result": error.status,
                        "rate_limits": error.rate_limits,
                    },
                )
                with connection.transaction():
                    record_failed_source_attempt(
                        repository=repository,
                        source=source,
                        previous_state=previous_state,
                        attempted_at=collected_at,
                        warning_code=error.category,
                    )
                failures.append(failure)
                continue
            except CollectionError:
                failure = _failed_source_diagnostic(
                    source=source,
                    error_category="unexpected_post_shape",
                )
                with connection.transaction():
                    record_failed_source_attempt(
                        repository=repository,
                        source=source,
                        previous_state=previous_state,
                        attempted_at=collected_at,
                        warning_code="unexpected_post_shape",
                    )
                failures.append(failure)
                continue

            try:
                with connection.transaction():
                    summary = save_source_collection(
                        repository=repository,
                        fetched=fetched,
                        previous_state=previous_state,
                        run_id=run_id,
                        usage_event_id=uuid4(),
                        collected_at=collected_at,
                        max_pages=args.max_pages,
                        max_results=args.max_results,
                    )
            except Exception:
                with connection.transaction():
                    record_failed_source_attempt(
                        repository=repository,
                        source=source,
                        previous_state=previous_state,
                        attempted_at=collected_at,
                        warning_code="database_write_failed",
                    )
                failures.append(
                    _failed_source_diagnostic(
                        source=source,
                        error_category="database_write_failed",
                    )
                )
                continue
            summaries.append(summary)

        warning_count = sum(len(summary.warnings) for summary in summaries) + len(
            failures
        )
        fetched_count = sum(summary.fetched_posts for summary in summaries)
        new_count = sum(summary.new_posts for summary in summaries)
        rejected_count = sum(summary.reposts_excluded for summary in summaries)
        finished_at = datetime.now(timezone.utc)
        if failures and not summaries:
            run_status = "failed"
            with connection.transaction():
                repository.fail_run(
                    run_id=run_id,
                    finished_at=finished_at,
                    error_summary=f"{len(failures)} source collection(s) failed",
                    warning_count=warning_count,
                )
        else:
            completed_with_warnings = bool(failures) or bool(warning_count)
            run_status = (
                "completed_with_warnings" if completed_with_warnings else "completed"
            )
            with connection.transaction():
                repository.complete_run(
                    run_id=run_id,
                    finished_at=finished_at,
                    completed_with_warnings=completed_with_warnings,
                    fetched_posts_count=fetched_count,
                    new_posts_count=new_count,
                    rejected_posts_count=rejected_count,
                    warning_count=warning_count,
                    error_summary=(
                        f"{len(failures)} source collection(s) failed"
                        if failures
                        else None
                    ),
                )

    report = {
        "run_id": str(run_id),
        "status": run_status,
        "sources": [summary.safe_diagnostic() for summary in summaries],
        "errors": failures,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    blocking_warning = any(summary.has_blocking_warning for summary in summaries)
    return 1 if failures or blocking_warning else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "status":
        print(STATUS_MESSAGE)
        return 0
    if args.command == "db":
        if args.db_command is None:
            parser.parse_args(["db", "--help"])
            return 0
        try:
            return _run_db_command(args.db_command)
        except (ConfigurationError, MigrationError) as error:
            if args.db_command in {"doctor", "status"}:
                print("Connection: unavailable", file=sys.stderr)
            print(f"Database command failed: {redact_secrets(error)}", file=sys.stderr)
            return 2
        except psycopg.OperationalError:
            if args.db_command in {"doctor", "status"}:
                print("Connection: unavailable", file=sys.stderr)
            print(
                "Database command failed: PostgreSQL connection unavailable. "
                "Check DATABASE_URL, network access, and SSL settings.",
                file=sys.stderr,
            )
            return 1
        except Exception as error:
            if args.db_command in {"doctor", "status"}:
                print("Connection: unavailable", file=sys.stderr)
            safe_error = redact_secrets(error)
            print(
                f"Database command failed: {type(error).__name__}: {safe_error}",
                file=sys.stderr,
            )
            return 1
    if args.command == "x-api":
        if args.x_api_command is None:
            parser.parse_args(["x-api", "--help"])
            return 0
        try:
            return _run_x_api_command(args)
        except XApiRequestError as error:
            print(
                json.dumps(error.safe_diagnostic(), indent=2, sort_keys=True),
                file=sys.stderr,
            )
            return 1
        except (XApiConfigurationError, OAuthFlowError, ValueError) as error:
            print(f"X API probe failed: {error}", file=sys.stderr)
            return 2
    if args.command == "collect":
        try:
            return _run_collect(args)
        except (ConfigurationError, XApiConfigurationError, OAuthFlowError, ValueError) as error:
            safe_error = redact_secrets(str(error))
            print(f"Collection failed: {safe_error}", file=sys.stderr)
            return 2
        except psycopg.OperationalError:
            print(
                "Collection failed: PostgreSQL connection unavailable. "
                "Check DATABASE_URL, network access, and SSL settings.",
                file=sys.stderr,
            )
            return 1
        except Exception as error:
            safe_error = redact_secrets(error)
            print(
                f"Collection failed: {type(error).__name__}: {safe_error}",
                file=sys.stderr,
            )
            return 1

    parser.print_help()
    return 0
