# Unified Prefilter Vocabulary

This directory contains a reviewed derivative routing vocabulary for a future cheap deterministic prefilter. It is not the canonical knowledge base and it does not execute relevance decisions.

Canonical capability authority remains the reviewed Markdown sources and `knowledge/assets_catalog.csv`. First-party X contributes real authored wording, audience language, recurring interests, and exact article-link provenance, but it cannot establish a capability. Historical article values are excluded from triggers.

## Vocabulary contract

`vocabulary.csv` contains:

- `trigger_id` - stable identifier;
- `term` - exact normalized token, phrase, or entity;
- `match_type` - `token`, `phrase`, or `entity`;
- `category` - the routing purpose of the term;
- `role` - `positive_trigger`, `context_only`, or `negative_context`;
- `strength` - `strong`, `normal`, or `weak`;
- `products`, `networks`, `asset_ids`, and `static_source_ids` - semicolon-separated scope and provenance;
- `static_basis` - `yes` when reviewed static material supports the routing meaning, otherwise `no`;
- `first_party_authored_count` - distinct non-repost first-party Posts containing the term in canonical `first_party_x_posts.text`;
- `referenced_context_count` - distinct available referenced contexts containing the term;
- `exact_article_link_basis` - reviewed source IDs joined through an exact stored resolved article URL when the linked first-party text also contains the term;
- `review_status` - `candidate`, `reviewed`, or `deprecated`;
- `notes` - concise authority, ambiguity, or intended-use guidance.

Counts are a reviewed snapshot of the 378-row local PostgreSQL corpus analysed on 2026-08-17. They support provenance and review but do not determine inclusion or strength. Reposts were inspected for topic interest but excluded from authored-style counts. Unavailable referenced context remains unknown, not irrelevant.

## Intended future semantics

- `strong` is highly specific product, capability, or entity evidence.
- `normal` is useful routing language that needs surrounding context.
- `weak` is a clue that must not pass by itself.
- A `negative_context` term never overrides positive product, capability, integration, or user-problem evidence.
- An unsupported network term alone is not a hard rejection.

Task 005D does not implement matching, scoring, PASS or REJECT actions, database mutation, or LLM processing. Runtime behavior belongs to Task 006.

## Dynamic analytics boundary

Task 005E must read `ethereum-top-addresses-pipeline` on demand and dynamically discover the latest appropriate comparison under `data/reports/comparisons/`. It must not hard-code a dated directory. A matching `summary/*_article_with_conclusion.md` may act as a narrative index, but exact values must be verified against structured files from the same comparison.

Every dynamic evidence package must retain the upstream repository and commit, as-of date, comparison dates, metric name, scope, entity or category, source path, and caveats. Dynamic datasets are not copied into this repository.
