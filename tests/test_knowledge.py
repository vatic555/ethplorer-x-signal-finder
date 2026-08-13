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
        "sources/posts",
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


def _add_article(
    root: Path,
    *,
    filename: str = "synthetic-article.md",
    source_id: str = "ethplorer.article.synthetic",
    source_type: str = "ethplorer_article",
    title: str = "Synthetic Ethplorer Article",
    heading: str = "Synthetic Ethplorer Article",
    body: str | None = None,
) -> None:
    article_body = body or ("Synthetic article paragraph. " * 30)
    (root / "sources/posts" / filename).write_text(
        dedent(
            f"""\
            +++
            source_id = "{source_id}"
            title = "{title}"
            source_type = "{source_type}"
            products = []
            networks = []
            approved_provenance = "Synthetic canonical article fixture"
            review_status = "pending"
            confirms = []
            limitations = []
            +++

            # {heading}

            {article_body}
            """
        ),
        encoding="utf-8",
    )


def test_repository_knowledge_structure_is_valid() -> None:
    result = validate_knowledge()

    assert result.valid
    assert result.source_count == 17
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


def test_duplicate_source_body_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root, source_id="synthetic-source-one", filename="one.md")
    _add_source(root, source_id="synthetic-source-two", filename="two.md")

    result = validate_knowledge(root)

    assert any("duplicate source body matches" in error for error in result.errors)


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


def test_invalid_optional_source_file_sha256_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root)
    source = root / "sources/ethplorer/synthetic.md"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            'review_status = "pending"',
            'source_file_sha256 = "not-a-sha256"\nreview_status = "pending"',
        ),
        encoding="utf-8",
    )

    result = validate_knowledge(root)

    assert any("source_file_sha256 must be 64 lowercase hex" in error for error in result.errors)


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


def test_canonical_posts_require_ethplorer_article_type(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_article(root, source_type="article")

    result = validate_knowledge(root)

    assert any(
        "sources/posts requires source_type ethplorer_article" in error
        for error in result.errors
    )


def test_canonical_article_title_must_match_preserved_h1(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_article(root, heading="Different Existing Heading")

    result = validate_knowledge(root)

    assert any("metadata title must match the existing H1" in error for error in result.errors)


def test_short_canonical_article_is_rejected_as_possible_truncation(
    tmp_path: Path,
) -> None:
    root = _knowledge_root(tmp_path)
    _add_article(root, body="Too short.")

    result = validate_knowledge(root)

    assert any("appears empty or unexpectedly truncated" in error for error in result.errors)


def test_unclosed_article_fence_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    body = ("Article content. " * 35) + "\n\n```text\nunclosed"
    _add_article(root, body=body)

    result = validate_knowledge(root)

    assert any("unclosed fenced Markdown block" in error for error in result.errors)


def test_source_site_routes_and_article_image_references_are_preserved(
    tmp_path: Path,
) -> None:
    root = _knowledge_root(tmp_path)
    body = ("Article content. " * 35) + "\n\n[Part 2](/posts/part-2)\n\n![](image.png)"
    _add_article(root, body=body)

    assert validate_knowledge(root).valid


def test_missing_managed_article_image_asset_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    body = (
        ("Article content. " * 35)
        + "\n\n![Chart](assets/chart.jpg)"
    )
    _add_article(root, body=body)

    result = validate_knowledge(root)

    assert any("broken local image asset" in error for error in result.errors)


def test_present_managed_article_image_asset_passes(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    body = (
        ("Article content. " * 35)
        + "\n\n![Chart](assets/chart.jpg)"
    )
    _add_article(root, body=body)
    asset = root / "sources/posts/assets/chart.jpg"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"synthetic-image")

    assert validate_knowledge(root).valid
