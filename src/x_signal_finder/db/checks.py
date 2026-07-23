"""Read-only PostgreSQL health and schema inspection."""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from x_signal_finder.db.migrations import Migration, validate_applied_migrations


REQUIRED_TABLES = frozenset(
    {
        "schema_migrations",
        "runs",
        "posts",
        "signals",
        "signal_posts",
        "opportunities",
        "human_reviews",
        "usage_events",
        "sync_state",
    }
)
OPERATIONAL_TABLES = REQUIRED_TABLES - {"schema_migrations"}


@dataclass(frozen=True)
class DatabaseInspection:
    postgres_version: str
    current_migration_version: int | None
    pending_migration_count: int
    present_tables: frozenset[str]
    rls_enabled_tables: frozenset[str]

    @property
    def missing_tables(self) -> frozenset[str]:
        return REQUIRED_TABLES - self.present_tables

    @property
    def rls_missing_tables(self) -> frozenset[str]:
        return OPERATIONAL_TABLES - self.rls_enabled_tables


def inspect_database(
    connection: psycopg.Connection,
    migrations: tuple[Migration, ...],
) -> DatabaseInspection:
    """Inspect PostgreSQL without creating or changing any database object."""
    version = str(connection.execute("SHOW server_version").fetchone()[0])
    rows = connection.execute(
        """
        SELECT tablename
        FROM pg_catalog.pg_tables
        WHERE schemaname = current_schema()
        """
    ).fetchall()
    present = frozenset(str(row[0]) for row in rows)

    applied: dict[int, tuple[str, str]] = {}
    if "schema_migrations" in present:
        migration_rows = connection.execute(
            """
            SELECT version, name, checksum
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()
        applied = {
            int(version_number): (str(name), str(checksum))
            for version_number, name, checksum in migration_rows
        }
        validate_applied_migrations(migrations, applied)

    rls_rows = connection.execute(
        """
        SELECT c.relname
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema()
          AND c.relkind = 'r'
          AND c.relrowsecurity
        """
    ).fetchall()
    rls_enabled = frozenset(str(row[0]) for row in rls_rows)
    connection.rollback()
    current = max(applied) if applied else None
    pending = sum(
        migration.version not in applied
        for migration in migrations
    )
    return DatabaseInspection(
        postgres_version=version,
        current_migration_version=current,
        pending_migration_count=pending,
        present_tables=present & REQUIRED_TABLES,
        rls_enabled_tables=rls_enabled & REQUIRED_TABLES,
    )
