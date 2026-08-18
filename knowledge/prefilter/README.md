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
- A `context_only` trigger can never create a future PASS by itself.
- Multiple `context_only` triggers together are also insufficient. `Ethereum + USDT + stablecoin + whale` contains useful context but no positive routing reason.
- A future PASS requires at least one meaningful `positive_trigger`, such as a product, capability, user problem, user intent, analytics concept, infrastructure need, BizDev or integration need, or explicit Ethplorer or Binplorer relevance.
- A `negative_context` term lowers confidence when meaningful positive evidence is absent. It is not authoritative and is never an automatic or hard rejection.
- Strong positive evidence takes precedence over negative context. `Solana + Ethereum + address monitoring API` remains eligible for downstream analysis because it contains a specific supported need.
- Negative-only language such as `Solana technical analysis RSI price prediction` has no meaningful project trigger and is an obvious future reject candidate.
- Generic stablecoin, token-entity, DeFi, network, or market context cannot become sufficient merely by appearing in combination.
- An unsupported network term alone is not a hard rejection.

Task 005D.1 documents these semantics but does not implement matching, scoring, PASS, REJECT, or UNCERTAIN actions, database mutation, or LLM processing. Runtime behavior belongs to Task 006.

## Precision boundary

Reviewed knowledge records what a source says. Vocabulary records only what is useful for routing incoming Posts. A documented capability phrase may therefore be contextual or negative routing evidence without changing the reviewed source or capability catalog.

Task 005D.1 demotes broad annotation, market, and chart language that would create obvious false positives. `address tags` remains a positive specific capability phrase, while broad `tags and notes`, `private tags`, `trade volume`, `market cap`, and `candlestick chart` are context only. `moving average` is retained as reviewed historical evidence but acts as trader-oriented negative context. Generic standalone `on-chain` and `exchange integration` are omitted.

The compact initial negative vocabulary covers Solana context and common trader analysis, signal, execution, derivatives, and education language. These terms help identify likely trader-only Posts only when positive project evidence is absent. It is not a complete unsupported-network or trading blacklist.

## Dynamic analytics boundary

Task 005E must read `ethereum-top-addresses-pipeline` on demand and dynamically discover the latest appropriate comparison under `data/reports/comparisons/`. It must not hard-code a dated directory. A matching `summary/*_article_with_conclusion.md` may act as a narrative index, but exact values must be verified against structured files from the same comparison.

Every dynamic evidence package must retain the upstream repository and commit, as-of date, comparison dates, metric name, scope, entity or category, source path, and caveats. Dynamic datasets are not copied into this repository.
