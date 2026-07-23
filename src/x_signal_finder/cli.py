"""Cross-platform command-line interface."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime, timezone
import sys
from uuid import uuid4

import psycopg

from x_signal_finder import __version__
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


STATUS_MESSAGE = (
    "Durable PostgreSQL storage foundation is implemented. "
    "X collection and LLM integration are not implemented."
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

    parser.print_help()
    return 0
