"""Cross-platform command-line interface."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal
import json
import sys
from uuid import uuid4
from uuid import UUID

import psycopg

from x_signal_finder import __version__
from x_signal_finder.baseline import (
    BaselineAcceptanceError,
    accept_baseline_candidate,
    inspect_baseline_candidate,
)
from x_signal_finder.collector import (
    CollectionError,
    fetch_source,
    record_failed_source_attempt,
    record_source_usage,
    save_source_collection,
    source_key_for,
    source_minimum_page_size,
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
from x_signal_finder.first_party_x import (
    ACCOUNTS as FIRST_PARTY_ACCOUNTS,
    FirstPartyXError,
    fetch_first_party_source,
    record_first_party_usage,
    record_inventory_usage,
    save_first_party_source,
    source_key_for as first_party_source_key_for,
)
from x_signal_finder.knowledge import validate_knowledge
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
from x_signal_finder.x_provider_shadow import (
    ShadowSpikeError,
    run_shadow_spike,
)


STATUS_MESSAGE = (
    "Durable PostgreSQL storage foundation is implemented. "
    "The X API access spike is complete with a constrained-go decision. "
    "Stage 3 collection is complete. "
    "Task 005A Git-backed knowledge architecture and Task 005C first-party "
    "X corpus sync are implemented; "
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
    knowledge = subparsers.add_parser(
        "knowledge",
        help="Validate the local Git-backed knowledge base.",
    )
    knowledge_subparsers = knowledge.add_subparsers(dest="knowledge_command")
    knowledge_subparsers.add_parser(
        "validate",
        help="Run offline knowledge structure and reference validation.",
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
        help="Run the bounded Stage 3 X collector and persist to PostgreSQL.",
    )
    collect.add_argument(
        "collect_action",
        nargs="?",
        choices=("accept-baseline",),
        help="Explicitly accept an incomplete run as a new source baseline.",
    )
    collect.add_argument(
        "--source",
        choices=("home", "mentions", "both"),
        default="both",
    )
    collect.add_argument("--max-pages", type=int, default=5)
    collect.add_argument("--max-results", type=int, default=100)
    collect.add_argument(
        "--max-estimated-cost-usd",
        type=Decimal,
        default=Decimal("1.00"),
        help="Stop before another page once estimated run cost reaches this guard.",
    )
    collect.add_argument(
        "--max-primary-posts-total",
        type=int,
        default=None,
        help="Optional primary Post limit shared by all requested sources.",
    )
    collect.add_argument("--max-attempts", type=int, default=3)
    collect.add_argument("--max-retry-wait-seconds", type=float, default=60)
    collect.add_argument(
        "--run-id",
        help="Incomplete collection run to inspect or accept as a baseline.",
    )
    collect.add_argument(
        "--confirm-skip-older-posts",
        action="store_true",
        help="Confirm that older Posts may be skipped when accepting a baseline.",
    )
    collect.add_argument(
        "--refresh-existing",
        action="store_true",
        help=(
            "Use one explicit bounded window ending at the stored checkpoint, "
            "omit since_id, and refresh Post content without changing the "
            "operational checkpoint."
        ),
    )
    first_party = subparsers.add_parser(
        "first-party-x",
        help="Synchronize the PostgreSQL first-party Ethplorer/Binplorer X corpus.",
    )
    first_party_subparsers = first_party.add_subparsers(dest="first_party_command")
    first_party_sync = first_party_subparsers.add_parser(
        "sync",
        help="Run a complete historical or incremental read-only corpus sync.",
    )
    first_party_sync.add_argument(
        "--source",
        choices=("ethplorer", "binplorer", "both"),
        default="both",
    )
    first_party_sync.add_argument("--max-pages", type=int, default=5)
    first_party_sync.add_argument(
        "--max-estimated-cost-usd",
        type=Decimal,
        default=Decimal("1.00"),
        help="Stop before another request once estimated run cost reaches this guard.",
    )
    first_party_sync.add_argument("--max-attempts", type=int, default=3)
    first_party_sync.add_argument(
        "--max-retry-wait-seconds",
        type=float,
        default=60,
    )
    shadow = subparsers.add_parser(
        "x-provider-shadow",
        help=(
            "Run the isolated read-only Task 004D Official X and third-party "
            "quality comparison without database writes."
        ),
    )
    shadow_subparsers = shadow.add_subparsers(dest="shadow_command")
    shadow_run = shadow_subparsers.add_parser(
        "run",
        help="Run one approximately 24-hour provider shadow comparison.",
    )
    shadow_run.add_argument("--hours", type=int, default=24)
    shadow_run.add_argument(
        "--max-provider-spend-usd",
        type=Decimal,
        default=Decimal("0.10"),
        help="Hard ceiling per third-party provider; cannot exceed $0.10.",
    )
    shadow_run.add_argument("--max-official-pages", type=int, default=20)
    shadow_run.add_argument(
        "--output-root",
        default="data/runtime/x-provider-shadow",
        help="Ignored local directory for raw temporary responses and safe summary.",
    )
    shadow_run.add_argument(
        "--window-end",
        help="Optional fixed ISO-8601 UTC end time for a reproducible window.",
    )
    shadow_run.add_argument(
        "--official-benchmark-source",
        choices=("api", "stored"),
        default="api",
        help=(
            "Use a fresh Official X API window or the latest already-collected "
            "x_home_timeline window in PostgreSQL (read-only)."
        ),
    )
    shadow_run.add_argument(
        "--provider",
        action="append",
        choices=("twitterapi_io", "socialdata"),
        dest="shadow_providers",
        help="Limit a run to one provider; repeat to select both.",
    )
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


def _run_accept_baseline(args: argparse.Namespace) -> int:
    if args.source not in {"home", "mentions"}:
        raise BaselineAcceptanceError(
            "accept-baseline requires exactly one source: home or mentions."
        )
    if not args.run_id:
        raise BaselineAcceptanceError("accept-baseline requires --run-id.")
    try:
        run_id = UUID(args.run_id)
    except ValueError as error:
        raise BaselineAcceptanceError("--run-id must be a valid UUID.") from error

    database_config = load_database_config()
    accepted_at = datetime.now(timezone.utc)
    with connect_database(database_config) as connection:
        repository = StorageRepository(connection)
        with connection.transaction():
            candidate = inspect_baseline_candidate(
                repository=repository,
                run_id=run_id,
                source=args.source,
            )
        if candidate["status"] == "already_accepted":
            print(json.dumps(candidate, indent=2, sort_keys=True))
            return 0
        if not args.confirm_skip_older_posts:
            print(json.dumps(candidate, indent=2, sort_keys=True))
            return 1
        with connection.transaction():
            result = accept_baseline_candidate(
                repository=repository,
                candidate=candidate,
                accepted_at=accepted_at,
                run_id=run_id,
            )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _run_collect(args: argparse.Namespace) -> int:
    if args.max_pages < 1:
        raise ValueError("max_pages must be at least 1")
    if args.source in {"mentions", "both"} and args.max_results < 5:
        raise ValueError("max_results for mentions must be between 5 and 100")
    if not 1 <= args.max_results <= 100:
        raise ValueError("max_results must be between 1 and 100")
    if args.max_estimated_cost_usd <= 0:
        raise ValueError("max_estimated_cost_usd must be positive")
    if (
        args.max_primary_posts_total is not None
        and args.max_primary_posts_total < 1
    ):
        raise ValueError("max_primary_posts_total must be at least 1")
    if args.max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if args.max_retry_wait_seconds < 0:
        raise ValueError("max_retry_wait_seconds must not be negative")

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
    source_reports: list[dict[str, object]] = []
    run_primary_posts = 0
    run_expanded_posts = 0
    run_distinct_resources = 0
    run_estimated_cost = Decimal("0")

    with connect_database(database_config) as connection:
        repository = StorageRepository(connection)
        with connection.transaction():
            repository.create_run(
                run_id=run_id,
                started_at=started_at,
                trigger_type=(
                    "manual_x_refresh"
                    if args.refresh_existing
                    else "manual_x_collection"
                ),
                application_version=__version__,
                metadata={
                    "source": args.source,
                    "max_pages": args.max_pages,
                    "max_results": args.max_results,
                    "max_estimated_cost_usd": format(
                        args.max_estimated_cost_usd, "f"
                    ),
                    "max_primary_posts_total": args.max_primary_posts_total,
                    "max_attempts": args.max_attempts,
                    "max_retry_wait_seconds": args.max_retry_wait_seconds,
                    "task": "004C",
                    "refresh_existing": args.refresh_existing,
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
            remaining_primary = (
                None
                if args.max_primary_posts_total is None
                else args.max_primary_posts_total - run_primary_posts
            )
            if (
                remaining_primary is not None
                and remaining_primary < source_minimum_page_size(source)
            ):
                failure = _failed_source_diagnostic(
                    source=source,
                    error_category="not_requested_due_to_primary_post_limit",
                    details={
                        "checkpoint_before": checkpoint_before,
                        "checkpoint_after": checkpoint_before,
                        "completion_state": "incomplete",
                        "primary_posts_received": 0,
                        "expanded_posts_received": 0,
                        "distinct_post_resources_received": 0,
                        "unit_cost_usd": format(
                            x_config.post_read_unit_cost_usd, "f"
                        ),
                        "estimated_x_cost_usd": "0.000",
                    },
                )
                failures.append(failure)
                source_reports.append(failure)
                continue
            if run_estimated_cost >= args.max_estimated_cost_usd:
                failure = _failed_source_diagnostic(
                    source=source,
                    error_category="not_requested_due_to_cost_guard",
                    details={
                        "checkpoint_before": checkpoint_before,
                        "checkpoint_after": checkpoint_before,
                        "completion_state": "incomplete",
                        "primary_posts_received": 0,
                        "expanded_posts_received": 0,
                        "distinct_post_resources_received": 0,
                        "unit_cost_usd": format(
                            x_config.post_read_unit_cost_usd, "f"
                        ),
                        "estimated_x_cost_usd": "0.000",
                    },
                )
                failures.append(failure)
                source_reports.append(failure)
                continue
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
                    refresh_existing=args.refresh_existing,
                    max_primary_posts_total=remaining_primary,
                    max_estimated_cost_usd=args.max_estimated_cost_usd,
                    estimated_cost_before_usd=run_estimated_cost,
                    unit_cost_usd=x_config.post_read_unit_cost_usd,
                    max_attempts=args.max_attempts,
                    max_retry_wait_seconds=args.max_retry_wait_seconds,
                    previous_successful_at=(
                        previous_state.get("last_successful_at")
                        if previous_state
                        else None
                    ),
                )
            except XApiRequestError as error:
                failure = _failed_source_diagnostic(
                    source=source,
                    error_category=error.category,
                    details={
                        "http_result": error.status,
                        "rate_limits": error.rate_limits,
                        "completion_state": "incomplete",
                        "primary_posts_received": 0,
                        "expanded_posts_received": 0,
                        "distinct_post_resources_received": 0,
                        "unit_cost_usd": format(
                            x_config.post_read_unit_cost_usd, "f"
                        ),
                        "estimated_x_cost_usd": "0.000",
                    },
                )
                if not args.refresh_existing:
                    try:
                        with connection.transaction():
                            record_failed_source_attempt(
                                repository=repository,
                                source=source,
                                previous_state=previous_state,
                                attempted_at=collected_at,
                                warning_code=error.category,
                            )
                    except Exception:
                        failure["sync_failure_recorded"] = False
                failures.append(failure)
                source_reports.append(failure)
                continue
            except CollectionError:
                failure = _failed_source_diagnostic(
                    source=source,
                    error_category="unexpected_post_shape",
                )
                if not args.refresh_existing:
                    try:
                        with connection.transaction():
                            record_failed_source_attempt(
                                repository=repository,
                                source=source,
                                previous_state=previous_state,
                                attempted_at=collected_at,
                                warning_code="unexpected_post_shape",
                            )
                    except Exception:
                        failure["sync_failure_recorded"] = False
                failures.append(failure)
                source_reports.append(failure)
                continue

            run_primary_posts += fetched.fetched_posts
            run_expanded_posts += fetched.expanded_posts_received
            run_distinct_resources += fetched.distinct_post_resources_received
            run_estimated_cost += fetched.estimated_cost_usd

            usage_recorded = False
            try:
                with connection.transaction():
                    record_source_usage(
                        repository=repository,
                        fetched=fetched,
                        run_id=run_id,
                        usage_event_id=uuid4(),
                        collected_at=collected_at,
                    )
                usage_recorded = True
            except Exception:
                fetched = fetched.with_warning("usage_recording_failed")

            try:
                with connection.transaction():
                    summary = save_source_collection(
                        repository=repository,
                        fetched=fetched,
                        previous_state=previous_state,
                        run_id=run_id,
                        collected_at=collected_at,
                        max_pages=args.max_pages,
                        max_results=args.max_results,
                    )
            except Exception:
                sync_failure_recorded = None if args.refresh_existing else True
                if not args.refresh_existing:
                    try:
                        with connection.transaction():
                            record_failed_source_attempt(
                                repository=repository,
                                source=source,
                                previous_state=previous_state,
                                attempted_at=collected_at,
                                warning_code="database_write_failed",
                            )
                    except Exception:
                        sync_failure_recorded = False
                failures.append(
                    _failed_source_diagnostic(
                        source=source,
                        error_category="database_write_failed",
                        details={
                            "checkpoint_before": checkpoint_before,
                            "checkpoint_after": checkpoint_before,
                            "completion_state": "incomplete",
                            "primary_posts_received": fetched.fetched_posts,
                            "expanded_posts_received": (
                                fetched.expanded_posts_received
                            ),
                            "distinct_post_resources_received": (
                                fetched.distinct_post_resources_received
                            ),
                            "unit_cost_usd": format(fetched.unit_cost_usd, "f"),
                            "estimated_x_cost_usd": format(
                                fetched.estimated_cost_usd, "f"
                            ),
                            "usage_recorded": usage_recorded,
                            "sync_failure_recorded": sync_failure_recorded,
                        },
                    )
                )
                source_reports.append(failures[-1])
                continue
            summaries.append(summary)
            diagnostic = summary.safe_diagnostic()
            diagnostic["usage_recorded"] = usage_recorded
            if fetched.terminal_error_category:
                diagnostic["errors"] = [
                    {
                        "error_category": fetched.terminal_error_category,
                        "http_result": fetched.terminal_http_status,
                        "rate_limits": dict(fetched.terminal_rate_limits or {}),
                    }
                ]
            source_reports.append(diagnostic)

        warning_count = sum(len(summary.warnings) for summary in summaries) + len(failures)
        fetched_count = sum(summary.fetched_posts for summary in summaries)
        new_count = sum(summary.new_posts for summary in summaries)
        rejected_count = sum(summary.reposts_excluded for summary in summaries)
        finished_at = datetime.now(timezone.utc)
        incomplete = bool(failures) or any(
            summary.has_blocking_warning for summary in summaries
        )
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
            completed_with_warnings = incomplete or bool(warning_count)
            run_status = (
                "incomplete" if incomplete else (
                    "completed_with_warnings" if completed_with_warnings else "completed"
                )
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
        "sources": source_reports,
        "usage": {
            "primary_posts_received": run_primary_posts,
            "expanded_posts_received": run_expanded_posts,
            "distinct_post_resources_received": run_distinct_resources,
            "unit_cost_usd": format(x_config.post_read_unit_cost_usd, "f"),
            "estimated_x_cost_usd": format(run_estimated_cost, "f"),
            "reported_cost_usd": None,
        },
        "errors": failures,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    blocking_warning = any(summary.has_blocking_warning for summary in summaries)
    return 1 if failures or blocking_warning else 0


def _run_first_party_x_sync(args: argparse.Namespace) -> int:
    if args.max_pages < 1:
        raise ValueError("max_pages must be at least 1")
    if args.max_estimated_cost_usd <= 0:
        raise ValueError("max_estimated_cost_usd must be positive")
    if args.max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if args.max_retry_wait_seconds < 0:
        raise ValueError("max_retry_wait_seconds must not be negative")

    database_config = load_database_config()
    x_config = load_x_api_config()
    x_config.require_collector_setup()

    requested_sources = (
        ("ethplorer", "binplorer")
        if args.source == "both"
        else (args.source,)
    )
    inventory_reference_total = sum(
        FIRST_PARTY_ACCOUNTS[source].inventory_reference
        for source in requested_sources
    )
    print(
        json.dumps(
            {
                "preflight": {
                    "source": args.source,
                    "sources": list(requested_sources),
                    "previous_inventory_primary_posts": inventory_reference_total,
                    "inventory_primary_post_cost_estimate_usd": format(
                        inventory_reference_total
                        * x_config.post_read_unit_cost_usd,
                        "f",
                    ),
                    "max_pages_per_source": args.max_pages,
                    "max_estimated_cost_usd": format(
                        args.max_estimated_cost_usd,
                        "f",
                    ),
                    "note": (
                        "Inventory counts are references, not a completeness promise; "
                        "direct reference completion may add Post resources."
                    ),
                }
            },
            indent=2,
            sort_keys=True,
        )
    )

    refreshed = refresh_access_token(
        client_id=x_config.client_id,
        refresh_token=x_config.refresh_token,
    )
    persist_refresh_token(refreshed.refresh_token)
    client = XApiClient(
        token=refreshed.access_token,
        base_url=x_config.base_url,
    )

    run_id = uuid4()
    started_at = datetime.now(timezone.utc)
    summaries = []
    failures: list[dict[str, object]] = []
    reports: list[dict[str, object]] = []
    run_estimated_cost = Decimal("0")
    run_estimated_post_cost = Decimal("0")
    run_estimated_user_cost = Decimal("0")
    run_estimated_media_cost = Decimal("0")
    run_requests = 0
    run_primary_post_resources = 0
    run_expanded_post_resources = 0
    run_reference_completion_post_resources = 0
    run_distinct_post_resources = 0
    run_expansion_user_resources = 0
    run_inventory_user_resources = 0
    run_media_resources = 0
    inventory_counts: dict[str, int | None] = {}
    inventory_report: dict[str, object] = {
        "requested": False,
        "request_count": 0,
        "user_resources": 0,
        "estimated_x_cost_usd": "0",
        "estimated_user_cost_usd": "0",
        "reported_cost_usd": None,
        "warnings": [],
    }

    with connect_database(database_config) as connection:
        repository = StorageRepository(connection)
        with connection.transaction():
            repository.create_run(
                run_id=run_id,
                started_at=started_at,
                trigger_type="manual_first_party_x_sync",
                application_version=__version__,
                metadata={
                    "source": args.source,
                    "max_pages": args.max_pages,
                    "max_estimated_cost_usd": format(
                        args.max_estimated_cost_usd,
                        "f",
                    ),
                    "max_attempts": args.max_attempts,
                    "max_retry_wait_seconds": args.max_retry_wait_seconds,
                    "task": "005C",
                },
            )

        states: dict[str, dict[str, object] | None] = {}
        for source in requested_sources:
            with connection.transaction():
                states[source] = repository.get_sync_state(
                    first_party_source_key_for(source)
                )

        initial_sources = tuple(
            source
            for source in requested_sources
            if not states[source]
            or states[source].get("checkpoint_value") is None
        )
        inventory_user_cost = x_config.user_read_unit_cost_usd * len(initial_sources)
        if initial_sources and inventory_user_cost < args.max_estimated_cost_usd:
            inventory_report["requested"] = True
            try:
                inventory_page = client.get_user_inventory(
                    tuple(FIRST_PARTY_ACCOUNTS[source].user_id for source in initial_sources)
                )
                run_requests += 1
                for source in initial_sources:
                    user_id = FIRST_PARTY_ACCOUNTS[source].user_id
                    snapshot = inventory_page.users_by_id.get(user_id)
                    inventory_counts[source] = (
                        snapshot.tweet_count if snapshot is not None else None
                    )
                if inventory_page.partial_error_count:
                    inventory_report["warnings"] = ["inventory_partial_errors_present"]
                with connection.transaction():
                    inventory_cost = record_inventory_usage(
                        repository=repository,
                        run_id=run_id,
                        usage_event_id=uuid4(),
                        collected_at=datetime.now(timezone.utc),
                        request_count=1,
                        user_count=len(inventory_page.users_by_id),
                        unit_cost_usd=x_config.user_read_unit_cost_usd,
                        inventory_counts={
                            source: inventory_counts.get(source)
                            for source in initial_sources
                        },
                    )
                run_estimated_cost += inventory_cost
                run_estimated_user_cost += inventory_cost
                run_inventory_user_resources += len(inventory_page.users_by_id)
                inventory_report.update(
                    {
                        "request_count": 1,
                        "user_resources": len(inventory_page.users_by_id),
                        "estimated_x_cost_usd": format(inventory_cost, "f"),
                        "estimated_user_cost_usd": format(inventory_cost, "f"),
                        "counts": {
                            source: inventory_counts.get(source)
                            for source in initial_sources
                        },
                    }
                )
            except XApiRequestError as error:
                run_requests += 1
                inventory_report.update(
                    {
                        "request_count": 1,
                        "warnings": ["inventory_lookup_failed"],
                        "error": error.safe_diagnostic(),
                    }
                )
        elif initial_sources:
            inventory_report["warnings"] = ["inventory_lookup_skipped_by_cost_guard"]

        for source in requested_sources:
            previous_state = states[source]
            checkpoint_before = (
                str(previous_state["checkpoint_value"])
                if previous_state
                and previous_state.get("checkpoint_value") is not None
                else None
            )
            if run_estimated_cost >= args.max_estimated_cost_usd:
                failure = {
                    "source": source,
                    "source_key": first_party_source_key_for(source),
                    "completion_state": "incomplete",
                    "checkpoint_before": checkpoint_before,
                    "checkpoint_after": checkpoint_before,
                    "error_category": "not_requested_due_to_cost_guard",
                    "warnings": ["cost_guard_reached"],
                }
                failures.append(failure)
                reports.append(failure)
                continue

            collected_at = datetime.now(timezone.utc)
            try:
                fetched = fetch_first_party_source(
                    client=client,
                    source=source,
                    run_id=run_id,
                    collected_at=collected_at,
                    checkpoint_before=checkpoint_before,
                    max_pages=args.max_pages,
                    max_estimated_cost_usd=args.max_estimated_cost_usd,
                    estimated_cost_before_usd=run_estimated_cost,
                    post_unit_cost_usd=x_config.post_read_unit_cost_usd,
                    user_unit_cost_usd=x_config.user_read_unit_cost_usd,
                    media_unit_cost_usd=x_config.media_read_unit_cost_usd,
                    inventory_tweet_count=inventory_counts.get(source),
                    max_attempts=args.max_attempts,
                    max_retry_wait_seconds=args.max_retry_wait_seconds,
                )
            except XApiRequestError as error:
                failure = {
                    "source": source,
                    "source_key": first_party_source_key_for(source),
                    "completion_state": "incomplete",
                    "checkpoint_before": checkpoint_before,
                    "checkpoint_after": checkpoint_before,
                    "error_category": error.category,
                    "http_result": error.status,
                    "rate_limits": error.rate_limits,
                    "warnings": ["request_failed"],
                }
                metadata = dict(
                    previous_state.get("checkpoint_metadata") or {}
                ) if previous_state else {}
                metadata["last_attempt_status"] = "failed"
                metadata["last_attempt_error_category"] = error.category
                try:
                    with connection.transaction():
                        repository.update_sync_state(
                            source_key=first_party_source_key_for(source),
                            checkpoint_value=checkpoint_before,
                            checkpoint_metadata=metadata,
                            last_attempt_at=collected_at,
                            last_successful_at=(
                                previous_state.get("last_successful_at")
                                if previous_state
                                else None
                            ),
                            last_successful_run_id=(
                                previous_state.get("last_successful_run_id")
                                if previous_state
                                else None
                            ),
                            last_warning_code=error.category,
                            updated_at=collected_at,
                        )
                except Exception:
                    failure["sync_failure_recorded"] = False
                failures.append(failure)
                reports.append(failure)
                continue
            except FirstPartyXError as error:
                failure = {
                    "source": source,
                    "source_key": first_party_source_key_for(source),
                    "completion_state": "incomplete",
                    "checkpoint_before": checkpoint_before,
                    "checkpoint_after": checkpoint_before,
                    "error_category": "first_party_content_error",
                    "warnings": [str(error)],
                }
                failures.append(failure)
                reports.append(failure)
                continue

            run_requests += fetched.requests_count
            run_estimated_cost += fetched.estimated_cost_usd
            run_estimated_post_cost += fetched.estimated_post_cost_usd
            run_estimated_user_cost += fetched.estimated_user_cost_usd
            run_estimated_media_cost += fetched.estimated_media_cost_usd
            run_primary_post_resources += fetched.primary_post_resources_received
            run_expanded_post_resources += fetched.expanded_posts_received
            run_reference_completion_post_resources += (
                fetched.reference_completion_posts_received
            )
            run_distinct_post_resources += fetched.distinct_post_resources_received
            run_expansion_user_resources += fetched.user_resources_received
            run_media_resources += fetched.media_resources_received
            usage_recorded = False
            try:
                with connection.transaction():
                    record_first_party_usage(
                        repository=repository,
                        fetched=fetched,
                        run_id=run_id,
                        usage_event_id=uuid4(),
                        collected_at=collected_at,
                    )
                usage_recorded = True
            except Exception:
                fetched = fetched.with_warning("usage_recording_failed")

            try:
                with connection.transaction():
                    summary = save_first_party_source(
                        repository=repository,
                        fetched=fetched,
                        previous_state=previous_state,
                        run_id=run_id,
                        collected_at=collected_at,
                        max_pages=args.max_pages,
                    )
            except Exception:
                failure = {
                    "source": source,
                    "source_key": first_party_source_key_for(source),
                    "completion_state": "incomplete",
                    "checkpoint_before": checkpoint_before,
                    "checkpoint_after": checkpoint_before,
                    "error_category": "database_write_failed",
                    "usage_recorded": usage_recorded,
                    "primary_posts_received": fetched.primary_posts_received,
                    "estimated_x_cost_usd": format(fetched.estimated_cost_usd, "f"),
                    "warnings": ["database_write_failed"],
                }
                failures.append(failure)
                reports.append(failure)
                continue
            summaries.append(summary)
            diagnostic = summary.safe_diagnostic()
            diagnostic["usage_recorded"] = usage_recorded
            if fetched.terminal_error_category:
                diagnostic["errors"] = [
                    {
                        "error_category": fetched.terminal_error_category,
                        "http_result": fetched.terminal_http_status,
                    }
                ]
            reports.append(diagnostic)

        warning_count = (
            sum(len(summary.warnings) for summary in summaries)
            + len(failures)
            + len(inventory_report.get("warnings", []))
        )
        incomplete = bool(failures) or any(
            summary.has_blocking_warning for summary in summaries
        )
        finished_at = datetime.now(timezone.utc)
        if failures and not summaries:
            run_status = "failed"
            with connection.transaction():
                repository.fail_run(
                    run_id=run_id,
                    finished_at=finished_at,
                    error_summary=f"{len(failures)} first-party source sync(s) failed",
                    warning_count=warning_count,
                )
        else:
            run_status = "incomplete" if incomplete else (
                "completed_with_warnings" if warning_count else "completed"
            )
            with connection.transaction():
                repository.complete_run(
                    run_id=run_id,
                    finished_at=finished_at,
                    completed_with_warnings=incomplete or bool(warning_count),
                    fetched_posts_count=sum(
                        summary.primary_posts_received for summary in summaries
                    ),
                    new_posts_count=sum(summary.new_posts for summary in summaries),
                    warning_count=warning_count,
                    error_summary=(
                        f"{len(failures)} first-party source sync(s) failed"
                        if failures
                        else None
                    ),
                )

    print(
        json.dumps(
            {
                "run_id": str(run_id),
                "status": run_status,
                "inventory": inventory_report,
                "sources": reports,
                "usage": {
                    "requests_count": run_requests,
                    "primary_post_resources": run_primary_post_resources,
                    "expanded_post_resources": run_expanded_post_resources,
                    "reference_completion_post_resources": (
                        run_reference_completion_post_resources
                    ),
                    "distinct_post_resources": run_distinct_post_resources,
                    "expansion_user_resources": run_expansion_user_resources,
                    "inventory_user_resources": run_inventory_user_resources,
                    "media_resources": run_media_resources,
                    "estimated_post_cost_usd": format(
                        run_estimated_post_cost, "f"
                    ),
                    "estimated_user_cost_usd": format(
                        run_estimated_user_cost, "f"
                    ),
                    "estimated_media_cost_usd": format(
                        run_estimated_media_cost, "f"
                    ),
                    "estimated_total_cost_usd": format(run_estimated_cost, "f"),
                    "reported_cost_usd": None,
                },
                "errors": failures,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if incomplete else 0


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
    if args.command == "knowledge":
        if args.knowledge_command is None:
            parser.parse_args(["knowledge", "--help"])
            return 0
        result = validate_knowledge()
        print(result.to_json())
        return 0 if result.valid else 1
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
            if args.collect_action == "accept-baseline":
                return _run_accept_baseline(args)
            return _run_collect(args)
        except (
            BaselineAcceptanceError,
            ConfigurationError,
            XApiConfigurationError,
            OAuthFlowError,
            ValueError,
        ) as error:
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
    if args.command == "first-party-x":
        if args.first_party_command is None:
            parser.parse_args(["first-party-x", "--help"])
            return 0
        try:
            return _run_first_party_x_sync(args)
        except (
            ConfigurationError,
            XApiConfigurationError,
            OAuthFlowError,
            FirstPartyXError,
            ValueError,
        ) as error:
            safe_error = redact_secrets(str(error))
            print(f"First-party X sync failed: {safe_error}", file=sys.stderr)
            return 2
        except psycopg.OperationalError:
            print(
                "First-party X sync failed: PostgreSQL connection unavailable. "
                "Check DATABASE_URL, network access, and SSL settings.",
                file=sys.stderr,
            )
            return 1
        except Exception as error:
            safe_error = redact_secrets(error)
            print(
                f"First-party X sync failed: {type(error).__name__}: {safe_error}",
                file=sys.stderr,
            )
            return 1
    if args.command == "x-provider-shadow":
        if args.shadow_command is None:
            parser.parse_args(["x-provider-shadow", "--help"])
            return 0
        try:
            summary = run_shadow_spike(
                hours=args.hours,
                max_provider_spend_usd=args.max_provider_spend_usd,
                max_official_pages=args.max_official_pages,
                output_root=args.output_root,
                window_end=args.window_end,
                official_benchmark_source=args.official_benchmark_source,
                provider_names=(
                    tuple(args.shadow_providers)
                    if args.shadow_providers
                    else ("twitterapi_io", "socialdata")
                ),
            )
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0 if all(
                provider["status"] == "complete"
                for provider in summary["providers"]
            ) else 1
        except (
            ShadowSpikeError,
            XApiConfigurationError,
            OAuthFlowError,
            ValueError,
        ) as error:
            safe_error = redact_secrets(str(error))
            print(f"X provider shadow spike failed: {safe_error}", file=sys.stderr)
            return 2
        except Exception as error:
            safe_error = redact_secrets(error)
            print(
                f"X provider shadow spike failed: {type(error).__name__}: {safe_error}",
                file=sys.stderr,
            )
            return 1

    parser.print_help()
    return 0
