from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from x_signal_finder.knowledge import ASSET_COLUMNS, validate_knowledge


def _knowledge_root(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge"
    for directory in (
        "terminology",
        "sources/ethplorer",
        "sources/binplorer",
        "sources/analytics",
        "sources/other",
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# Knowledge\n", encoding="utf-8")
    (root / "source_documents.md").write_text("# Sources\n", encoding="utf-8")
    (root / "terminology/shared-analytics.md").write_text(
        "# Shared terminology\n", encoding="utf-8"
    )
    (root / "terminology/x-signal.md").write_text(
        "# Project terminology\n", encoding="utf-8"
    )
    (root / "sources/_source-template.md").write_text(
        "# Template\n", encoding="utf-8"
    )
    (root / "assets_catalog.csv").write_text(
        ",".join(ASSET_COLUMNS) + "\n", encoding="utf-8"
    )
    return root


def _add_source(
    root: Path,
    *,
    source_id: str = "synthetic-source",
    review_status: str = "pending",
    filename: str = "synthetic.md",
    include_title: bool = True,
) -> None:
    title = 'title = "Synthetic source"\n' if include_title else ""
    (root / "sources/ethplorer" / filename).write_text(
        dedent(
            f"""\
            +++
            source_id = "{source_id}"
            {title}source_type = "article"
            products = []
            networks = []
            source_url = "https://example.invalid/source"
            review_status = "{review_status}"
            confirms = ["Synthetic validation claim"]
            limitations = []
            +++

            # Synthetic Source

            Synthetic content used only by offline tests.
            """
        ),
        encoding="utf-8",
    )


def _add_asset(
    root: Path,
    *,
    asset_id: str = "synthetic-asset",
    source_id: str = "synthetic-source",
    review_status: str = "pending",
) -> None:
    row = (
        asset_id,
        "Synthetic asset",
        "synthetic",
        "synthetic-product",
        "",
        "",
        "A synthetic test question",
        "Anything outside the fixture",
        "Offline validation only",
        source_id,
        review_status,
        "2026-08-07",
    )
    (root / "assets_catalog.csv").write_text(
        ",".join(ASSET_COLUMNS) + "\n" + ",".join(row) + "\n",
        encoding="utf-8",
    )


def test_repository_knowledge_structure_is_valid() -> None:
    result = validate_knowledge()

    assert result.valid
    assert result.source_count == 0
    assert result.asset_count == 0


def test_valid_pending_source_and_asset_pass(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root)
    _add_asset(root)

    result = validate_knowledge(root)

    assert result.valid
    assert result.source_count == 1
    assert result.asset_count == 1


def test_duplicate_source_id_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root)
    _add_source(root, filename="duplicate.md")

    result = validate_knowledge(root)

    assert any("duplicate source_id synthetic-source" in error for error in result.errors)


def test_missing_source_metadata_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root, include_title=False)

    result = validate_knowledge(root)

    assert any("missing required metadata field title" in error for error in result.errors)


def test_invalid_review_status_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root, review_status="approved")

    result = validate_knowledge(root)

    assert any("review_status must be pending, reviewed, or deprecated" in error for error in result.errors)


def test_unknown_asset_source_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_asset(root, source_id="missing-source")

    result = validate_knowledge(root)

    assert any("unknown source_id missing-source" in error for error in result.errors)


def test_reviewed_asset_requires_reviewed_source(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root, review_status="pending")
    _add_asset(root, review_status="reviewed")

    result = validate_knowledge(root)

    assert any("requires at least one reviewed source" in error for error in result.errors)


def test_reviewed_asset_with_reviewed_source_passes(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root, review_status="reviewed")
    _add_asset(root, review_status="reviewed")

    assert validate_knowledge(root).valid


def test_duplicate_asset_id_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root)
    _add_asset(root)
    catalog = root / "assets_catalog.csv"
    lines = catalog.read_text(encoding="utf-8").splitlines()
    catalog.write_text("\n".join([*lines, lines[1]]) + "\n", encoding="utf-8")

    result = validate_knowledge(root)

    assert any("duplicate asset_id synthetic-asset" in error for error in result.errors)


def test_broken_local_markdown_reference_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    (root / "README.md").write_text(
        "# Knowledge\n\n[Missing](sources/missing.md)\n", encoding="utf-8"
    )

    result = validate_knowledge(root)

    assert any("broken local reference sources/missing.md" in error for error in result.errors)
