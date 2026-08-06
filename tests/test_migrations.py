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


def test_content_review_migration_contains_bounded_manual_review_views() -> None:
    sql = (
        Path(__file__).parents[1] / "migrations" / "002_content_review_views.sql"
    ).read_text(encoding="utf-8")

    assert "CREATE VIEW public.posts_review" in sql
    assert "CREATE VIEW public.author_source_stats" in sql
    assert "CREATE VIEW public.author_unfollow_candidates" in sql
    assert "https://x.com/i/web/status/" in sql
    assert "full_text_source" in sql
    assert "referenced_post_text" in sql
    assert "media_types" in sql
    assert "low_information_reply_candidate" in sql
    assert "estimated_stored_post_cost_usd" in sql
    assert "observed_posts >= 20 OR observation_span_days >= 7" in sql
    assert "blockchain_keyword_matches = 0" in sql
    assert "DELETE" not in sql.upper()
    assert "UPDATE" not in sql.upper()
