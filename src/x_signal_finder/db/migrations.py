"""Deterministic, checksum-verified PostgreSQL migrations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Iterable

import psycopg


_MIGRATION_NAME = re.compile(r"^(?P<version>\d+)_(?P<name>[a-z0-9_]+)\.sql$")


class MigrationError(RuntimeError):
    """Raised when migration discovery or validation fails."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    filename: str
    checksum: str
    sql: str


@dataclass(frozen=True)
class MigrationStatus:
    current_version: int | None
    pending: tuple[Migration, ...]
    applied_versions: tuple[int, ...]


def default_migrations_directory() -> Path:
    """Locate the repository migration directory."""
    candidates = (
        Path.cwd() / "migrations",
        Path(__file__).resolve().parents[3] / "migrations",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def discover_migrations(directory: str | Path) -> tuple[Migration, ...]:
    """Read valid migration files, rejecting duplicate versions."""
    directory = Path(directory)
    migrations: list[Migration] = []
    versions: dict[int, str] = {}
    for path in directory.glob("*.sql"):
        match = _MIGRATION_NAME.fullmatch(path.name)
        if not match:
            continue
        version = int(match.group("version"))
        if version in versions:
            raise MigrationError(
                f"Duplicate migration version {version}: "
                f"{versions[version]} and {path.name}."
            )
        sql = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        versions[version] = path.name
        migrations.append(
            Migration(
                version=version,
                name=match.group("name"),
                filename=path.name,
                checksum=checksum,
                sql=sql,
            )
        )
    return tuple(sorted(migrations, key=lambda migration: migration.version))


def validate_applied_migrations(
    migrations: Iterable[Migration],
    applied: dict[int, tuple[str, str]],
) -> None:
    """Fail if an applied file is missing locally or its checksum changed."""
    local = {migration.version: migration for migration in migrations}
    for version, (name, checksum) in applied.items():
        migration = local.get(version)
        if migration is None:
            raise MigrationError(
                f"Applied migration version {version} ({name}) is missing locally."
            )
        if migration.filename != name:
            raise MigrationError(
                f"File name mismatch for applied migration {version}: "
                f"database has {name}, local file is {migration.filename}."
            )
        if migration.checksum != checksum:
            raise MigrationError(
                f"Checksum mismatch for applied migration {version} "
                f"({migration.filename})."
            )


def ensure_migration_table(connection: psycopg.Connection) -> None:
    """Create migration metadata storage in its own explicit transaction."""
    with connection.transaction():
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version bigint PRIMARY KEY,
                name text NOT NULL,
                checksum text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )


def read_applied_migrations(
    connection: psycopg.Connection,
) -> dict[int, tuple[str, str]]:
    """Read applied migration names and checksums."""
    rows = connection.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
    ).fetchall()
    return {int(version): (str(name), str(checksum)) for version, name, checksum in rows}


def get_migration_status(
    connection: psycopg.Connection,
    migrations: Iterable[Migration],
) -> MigrationStatus:
    """Validate migration history and return current/pending versions."""
    migration_list = tuple(migrations)
    ensure_migration_table(connection)
    applied = read_applied_migrations(connection)
    connection.rollback()
    validate_applied_migrations(migration_list, applied)
    pending = tuple(
        migration
        for migration in migration_list
        if migration.version not in applied
    )
    versions = tuple(sorted(applied))
    return MigrationStatus(
        current_version=versions[-1] if versions else None,
        pending=pending,
        applied_versions=versions,
    )


def apply_migrations(
    connection: psycopg.Connection,
    migrations: Iterable[Migration],
) -> tuple[int, ...]:
    """Apply pending migrations one at a time in explicit transactions."""
    migration_list = tuple(migrations)
    ensure_migration_table(connection)
    applied = read_applied_migrations(connection)
    connection.rollback()
    validate_applied_migrations(migration_list, applied)

    newly_applied: list[int] = []
    for migration in migration_list:
        if migration.version in applied:
            continue
        with connection.transaction():
            connection.execute(migration.sql)
            connection.execute(
                """
                INSERT INTO schema_migrations (version, name, checksum)
                VALUES (%s, %s, %s)
                """,
                (migration.version, migration.filename, migration.checksum),
            )
        newly_applied.append(migration.version)
    return tuple(newly_applied)
