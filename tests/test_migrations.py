from pathlib import Path

import pytest

from x_signal_finder.db.migrations import (
    MigrationError,
    discover_migrations,
    validate_applied_migrations,
)


def test_migrations_are_discovered_in_numeric_order(tmp_path: Path) -> None:
    (tmp_path / "010_later.sql").write_text("SELECT 10;\n", encoding="utf-8")
    (tmp_path / "002_earlier.sql").write_text("SELECT 2;\n", encoding="utf-8")
    (tmp_path / "README.sql").write_text("ignored\n", encoding="utf-8")

    migrations = discover_migrations(tmp_path)

    assert [migration.version for migration in migrations] == [2, 10]
    assert [migration.filename for migration in migrations] == [
        "002_earlier.sql",
        "010_later.sql",
    ]


def test_duplicate_migration_versions_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "001_first.sql").write_text("SELECT 1;\n", encoding="utf-8")
    (tmp_path / "001_duplicate.sql").write_text("SELECT 2;\n", encoding="utf-8")

    with pytest.raises(MigrationError, match="Duplicate migration version 1"):
        discover_migrations(tmp_path)


def test_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "001_initial.sql").write_text("SELECT 1;\n", encoding="utf-8")
    migration = discover_migrations(tmp_path)[0]

    with pytest.raises(MigrationError, match="Checksum mismatch"):
        validate_applied_migrations(
            (migration,),
            {1: ("001_initial.sql", "not-the-current-checksum")},
        )


def test_missing_applied_migration_is_rejected() -> None:
    with pytest.raises(MigrationError, match="missing locally"):
        validate_applied_migrations((), {1: ("001_missing.sql", "checksum")})
