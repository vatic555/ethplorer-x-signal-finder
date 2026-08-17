from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from x_signal_finder.knowledge import (
    ASSET_COLUMNS,
    VOCABULARY_COLUMNS,
    normalize_article_url,
    validate_knowledge,
)


def _knowledge_root(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge"
    for directory in (
        "terminology",
        "sources/ethplorer",
        "sources/binplorer",
        "sources/analytics",
        "sources/other",
        "sources/posts",
        "prefilter",
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# Knowledge\n", encoding="utf-8")
    (root / "source_documents.md").write_text("# Sources\n", encoding="utf-8")
    (root / "review_summary.md").write_text("# Review summary\n", encoding="utf-8")
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
    (root / "prefilter/README.md").write_text(
        "# Prefilter vocabulary\n", encoding="utf-8"
    )
    (root / "prefilter/vocabulary.csv").write_text(
        ",".join(VOCABULARY_COLUMNS) + "\n", encoding="utf-8"
    )
    return root


def _add_source(
    root: Path,
    *,
    source_id: str = "synthetic-source",
    review_status: str = "pending",
    filename: str = "synthetic.md",
    include_title: bool = True,
    confirms: bool = True,
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
            confirms = {['Synthetic validation claim'] if confirms else []!r}
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
    source_url: str | None = None,
) -> None:
    article_body = body or ("Synthetic article paragraph. " * 30)
    source_url_line = f'source_url = "{source_url}"\n' if source_url else ""
    (root / "sources/posts" / filename).write_text(
        dedent(
            f"""\
            +++
            source_id = "{source_id}"
            title = "{title}"
            source_type = "{source_type}"
            products = []
            networks = []
            {source_url_line}approved_provenance = "Synthetic canonical article fixture"
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


def _add_vocabulary(
    root: Path,
    *,
    trigger_id: str = "synthetic-trigger",
    term: str = "synthetic phrase",
    match_type: str = "phrase",
    category: str = "capability",
    role: str = "positive_trigger",
    strength: str = "strong",
    asset_ids: str = "synthetic-asset",
    source_ids: str = "synthetic-source",
    exact_basis: str = "",
    review_status: str = "candidate",
) -> None:
    row = (
        trigger_id,
        term,
        match_type,
        category,
        role,
        strength,
        "synthetic-product",
        "synthetic-network",
        asset_ids,
        source_ids,
        "yes" if source_ids else "no",
        "0",
        "0",
        exact_basis,
        review_status,
        "Synthetic validation row",
    )
    path = root / "prefilter/vocabulary.csv"
    with path.open("a", encoding="utf-8", newline="") as handle:
        import csv

        csv.writer(handle).writerow(row)


def test_repository_knowledge_structure_is_valid() -> None:
    result = validate_knowledge()

    assert result.valid
    assert result.source_count == 17
    assert result.asset_count == 11
    assert result.route_count == 12
    assert result.vocabulary_count == 76


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


def test_reviewed_source_with_supported_claim_passes(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root, review_status="reviewed")

    assert validate_knowledge(root).valid


def test_reviewed_source_without_supported_claim_fails(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root, review_status="reviewed", confirms=False)

    result = validate_knowledge(root)

    assert any("reviewed source must confirm" in error for error in result.errors)


def test_canonical_article_url_maps_to_one_source(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_article(root, source_url="https://ethplorer.io/posts/synthetic")

    result = validate_knowledge(root)

    assert result.valid
    assert result.route_count == 1


def test_duplicate_canonical_article_url_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_article(root, source_url="https://ethplorer.io/posts/synthetic")
    _add_article(
        root,
        filename="other.md",
        source_id="ethplorer.article.other",
        title="Other Article",
        heading="Other Article",
        body="Other substantive source paragraph. " * 30,
        source_url="http://www.ethplorer.io/posts/synthetic/?campaign=test#top",
    )

    result = validate_knowledge(root)

    assert any("duplicate canonical article URL" in error for error in result.errors)


def test_article_route_normalization_preserves_identity() -> None:
    expected = "https://ethplorer.io/posts/example_article"

    assert normalize_article_url(
        "http://www.ethplorer.io/posts/example_article/?utm_source=x#section"
    ) == expected
    assert normalize_article_url(expected) == expected
    assert normalize_article_url("https://ethplorer.io/address/example_article") is None


def test_duplicate_vocabulary_trigger_id_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root)
    _add_asset(root)
    _add_vocabulary(root)
    _add_vocabulary(root, term="another phrase")

    result = validate_knowledge(root)

    assert any("duplicate trigger_id synthetic-trigger" in error for error in result.errors)


def test_normalized_duplicate_vocabulary_term_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root)
    _add_asset(root)
    _add_vocabulary(root, trigger_id="one", term="Wallet   Portfolio")
    _add_vocabulary(root, trigger_id="two", term=" wallet portfolio ")

    result = validate_knowledge(root)

    assert any("normalized duplicate term" in error for error in result.errors)


def test_invalid_vocabulary_match_type_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root)
    _add_asset(root)
    _add_vocabulary(root, match_type="regex")

    assert any(
        "invalid match_type regex" in error
        for error in validate_knowledge(root).errors
    )


def test_invalid_vocabulary_category_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root)
    _add_asset(root)
    _add_vocabulary(root, category="generic_keyword")

    assert any(
        "invalid category generic_keyword" in error
        for error in validate_knowledge(root).errors
    )


def test_invalid_vocabulary_role_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root)
    _add_asset(root)
    _add_vocabulary(root, role="hard_reject")

    assert any(
        "invalid role hard_reject" in error
        for error in validate_knowledge(root).errors
    )


def test_invalid_vocabulary_review_status_is_rejected(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root)
    _add_asset(root)
    _add_vocabulary(root, review_status="approved")

    assert any(
        "invalid review_status approved" in error
        for error in validate_knowledge(root).errors
    )


def test_vocabulary_asset_reference_must_exist(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root)
    _add_vocabulary(root, asset_ids="missing-asset")

    assert any(
        "unknown asset_id missing-asset" in error
        for error in validate_knowledge(root).errors
    )


def test_vocabulary_static_source_reference_must_exist(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_vocabulary(root, asset_ids="", source_ids="missing-source")

    assert any(
        "unknown static_source_id missing-source" in error
        for error in validate_knowledge(root).errors
    )


def test_reviewed_capability_trigger_requires_reviewed_evidence(
    tmp_path: Path,
) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root, review_status="pending")
    _add_asset(root, review_status="pending")
    _add_vocabulary(root, review_status="reviewed")

    result = validate_knowledge(root)

    assert any("reviewed trigger requires reviewed static evidence" in error for error in result.errors)


def test_exact_article_basis_requires_a_canonical_route(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)
    _add_source(root)
    _add_asset(root)
    _add_vocabulary(root, exact_basis="synthetic-source")

    assert any(
        "exact article source has no canonical route" in error
        for error in validate_knowledge(root).errors
    )


def test_repository_vocabulary_excludes_historical_numeric_triggers() -> None:
    vocabulary = (
        Path(__file__).parents[1] / "knowledge/prefilter/vocabulary.csv"
    ).read_text(encoding="utf-8")

    for historical_value in ("$342B", "$426B", "$189B", "$116.5B", "58%", "66%"):
        assert historical_value not in vocabulary


def test_offline_validation_reports_no_external_dependencies(tmp_path: Path) -> None:
    root = _knowledge_root(tmp_path)

    payload = validate_knowledge(root).as_dict()

    assert payload["network_requests"] == 0
    assert payload["llm_calls"] == 0
