# Architecture Decision Log

This log records meaningful architectural and product decisions. New entries must include a date, status, context, and decision.

## 2026-07-22 - Private repository during MVP

Status: Superseded

The repository begins private because the MVP may include implementation details related to private data sources and licensed content. Repository privacy does not permit secrets or runtime data to be committed.

Superseded by the 2026-08-04 public-repository decision below.

## 2026-07-22 - Markdown specification in Git is canonical

Status: Accepted

`docs/project-spec.md` is the canonical product and technical specification. Product behavior changes require a corresponding specification update.

## 2026-07-22 - Two-file terminology architecture

Status: Accepted

Shared Ethplorer analytics terminology and project-specific X Signal Finder terminology are maintained separately. Task 005A moved them without merging or redefining terms to `knowledge/terminology/shared-analytics.md` and `knowledge/terminology/x-signal.md`. Definitions must not be synchronized or changed silently.

## 2026-07-22 - Manual local execution for the first MVP stage

Status: Accepted

The pipeline will initially be started manually once or twice per day. A platform-independent Python entry point is required.

## 2026-07-22 - GitHub Actions deferred

Status: Accepted

CI-based scheduling or execution is outside the current MVP stage. No GitHub Actions workflows are created in this bootstrap.

## 2026-07-22 - Telegram deferred

Status: Accepted

Telegram delivery, buttons, and webhooks are outside the current MVP stage.

## 2026-07-22 - Managed PostgreSQL planned for operational storage

Status: Accepted

A managed PostgreSQL service such as Supabase is the intended operational source of truth. The provider and schema are not selected or implemented in this bootstrap.

Superseded by the 2026-07-23 decision below.

## 2026-07-22 - Git excludes raw operational X content

Status: Accepted

Git is not an operational data store. Raw X content, runtime databases, and private or licensed runtime exports must not be committed.

## 2026-07-22 - Python is the cross-platform runtime

Status: Accepted

Python 3.11 or newer is the main runtime. Platform-specific scripts may be optional helpers but cannot be the sole execution path.

## 2026-07-22 - Publication remains manual

Status: Accepted

Every draft requires human review, and a human must publish it. Automatic publication requires an explicit future specification and architecture decision change.

## 2026-07-23 - Supabase selected as the initial managed PostgreSQL provider

Status: Accepted

Supabase is the initial managed PostgreSQL provider for the MVP. The application connects with a protected standard PostgreSQL connection string from `DATABASE_URL` through `psycopg`. It does not depend on the Supabase Python SDK, anon keys, authenticated roles, service-role keys, or provider-specific UUID extensions. The storage layer remains compatible with other standard PostgreSQL providers.

PostgreSQL is the operational source of truth. GitHub remains separate from operational data and must not contain raw X content, runtime databases, dumps, or operational exports. Database secrets exist only in local or deployment environment configuration.

Schema changes use explicit, deterministic, checksum-tracked migrations. Normal pipeline execution never creates or migrates the database automatically. Operational tables use Row Level Security without anonymous or authenticated public policies.

## 2026-07-23 - Canonical implementation roadmap and MVP stage boundary

Status: Accepted

`docs/roadmap.md` is the canonical implementation sequence and progress record. `docs/project-spec.md` remains the canonical product and technical requirements specification.

Stages 0 through 7 constitute the MVP. Stage 8 is post-MVP. Reordering or bypassing a stage requires an explicit accepted decision. A stage is completed only after its task-specific validation passes.

## 2026-08-04 - Public repository during MVP

Status: Accepted

The repository remains public during the MVP. Public visibility does not authorize committing credentials, `.env` files, raw operational X content, runtime database data, database dumps, private or licensed exports, or confidential internal documents.

Public documentation and synthetic fixtures must remain safe for unrestricted distribution. Operational data continues to live in PostgreSQL, and secrets continue to exist only in ignored local or deployment environment configuration.

## 2026-08-05 - X API access spike constrained-go

Status: Accepted

Live OAuth 2.0 PKCE authorization and refresh succeeded. The reverse chronological home endpoint returned multiple HTTP 200 pages, repeated page one consistently, exposed rate-limit metadata, and reached an in-memory checkpoint without duplicate Post IDs. The direct `@Ethplorer` mentions endpoint also returned HTTP 200 under Aleksandr user context, so separate Ethplorer authorization is not required to call the endpoint in the tested configuration. Its empty result did not exercise mentions pagination or establish content completeness, access to protected content, or Owned Read pricing.

Stage 3 may proceed only as the separate planned Task 004 and must treat the Stage 2 result as `constrained-go`. The collector must use independent source checkpoints, paginate to a safe stopping condition, refuse checkpoint advancement on partial errors or incomplete pagination, warn about possible history-window truncation, track usage and cost, and support X Content revalidation and deletion obligations. Stage 2 does not approve automatic publication, scheduling, schema changes, or any other deferred capability.

## 2026-08-06 - Task 004A bounded collector baseline

Status: Accepted

Task 004A validates the shortest operational path from X API through the Python CLI to the existing PostgreSQL schema. It adds no migration and no dependency. The command is manually invoked, defaults to one page and 20 Posts per source, excludes simple home reposts in both the API request and application mapping, and uses `post_id` upserts for deduplication. Home and mentions maintain independent `sync_state` rows.

Only the OAuth refresh token is stored in the ignored local `.env`. Access tokens remain in memory. A successful refresh-token rotation is persisted before collection begins so a later API or database failure does not lose the usable refresh credential.

The first bounded run establishes a current baseline even when older history is available and records `initial_history_not_backfilled`. This is an explicit Task 004A viability tradeoff, not a claim of historical completeness. After a checkpoint exists, incomplete pagination, response-level partial errors, missing pagination metadata, or duplicate Post IDs prevent checkpoint advancement. Full historical recovery, automatic retention and deletion handling, and the rest of Stage 3 hardening remain deferred.

## 2026-08-06 - Task 004B content completeness and manual review views

Status: Accepted

Long-form Post content uses `note_tweet.text` when available and falls back to `text`. The original X fields remain at the top level of `raw_json`; returned referenced Post context and matching media metadata are added only under `_expanded`, and collector-derived provenance is added under `_collector`. Missing expansions are recorded when useful but are nonfatal and never cause an additional X request or a media download.

Versioned migration 002 adds security-invoker PostgreSQL views for Post review, stored home-author statistics, and manual unfollow candidates. Their keyword and low-information reply flags are coarse review heuristics, not AI relevance decisions, rejection actions, or account changes. The explicit bounded `--refresh-existing` mode omits `since_id`, anchors its window at the stored checkpoint with documented `until_id`, upserts the returned window, preserves first-seen values and workflow state, and does not write `sync_state`. Stage 3 remains In Progress, and Stage 4 is not started.

## 2026-08-06 - Task 004C incremental completeness and cost guardrails

Status: Accepted

Forward incremental collection paginates each source from its stored checkpoint until `next_token` disappears or an explicit safety guard stops collection. Home and mentions remain independent and run in that order. Page, global primary-Post, estimated-cost, partial-response, malformed-content, and terminal-request conditions make the affected source incomplete, preserve fetched data and estimated usage, prevent checkpoint advancement, and produce a non-zero CLI result.

Estimated X usage counts distinct Post IDs returned in primary `data` and expanded `includes.tweets` within each source. The configurable unit estimate defaults to $0.005. The cost guard controls whether another page is requested and is not a billing cap, so one-page and expansion overshoot is expected. Actual cost remains a Developer Console observation.

Successful-response usage is committed separately before Post upsert. This preserves a best-effort paid-fetch record if a later database write fails without creating a second event. Retries are bounded and restricted to connection failures, timeouts, HTTP 500, 502, 503, 504, and short HTTP 429 waits. Manual execution, forward collection, and safe warnings are part of the MVP. Historical backfill, automatic missed-window recovery, and compliance revalidation or deletion automation remain deferred.

## 2026-08-07 - Explicit manual baseline acceptance

Status: Accepted

An operator may explicitly accept the newest collected point from the current incomplete source run as a new forward baseline when the MVP intentionally declines to pay for the older remaining window. The action is PostgreSQL-only, requires a source, run ID, and `--confirm-skip-older-posts`, and never calls X, creates Posts, deletes Posts, or creates a collection run or usage event.

Acceptance is limited to a completed-with-warnings collection run with one matching incomplete source usage record, a recognized blocking reason, valid newest Post evidence, and a current matching incomplete `sync_state`. The audit record retains the source run, previous and accepted checkpoints, incomplete reason, primary and saved Post counts, acceptance time, provenance, and an explicit `older_window_may_have_been_skipped=true` marker. The source run metadata and later checkpoint metadata preserve the acceptance record. This is a deliberate forward-MVP baseline, not historical completeness or recovery.

## 2026-08-07 - Git-backed knowledge source of truth and evidence contract

Status: Accepted

For the MVP, reviewed files under `knowledge/` are the source of truth for static reviewed knowledge. PostgreSQL remains the operational source of truth but does not store canonical static knowledge. No knowledge migration, embeddings, vector database, semantic search, crawler, or runtime LLM integration is introduced by Task 005A. A later database or index may be derived from Git but cannot silently become canonical.

Public or explicitly approved source documents live under `knowledge/sources/` and use stable source IDs plus TOML front matter for identity, provenance, scope, review status, supported claims, and limitations. The compact asset catalog is the structured capability layer. Every capability must reference existing source IDs, and a reviewed capability must have at least one reviewed supporting source. A URL or product positioning alone is not evidence.

The shared analytics and X Signal Finder terminology documents remain separate and retain their existing ownership and provenance. The public repository must not contain full private, internal, confidential, or licensed source text. Task 005A creates the architecture, import template, and offline validation. Its later inventory amendment registers the user-supplied canonical Ethplorer article archive without extracting capabilities; evidence-backed capability extraction remains reserved for Task 005B.

## 2026-08-10 - Three knowledge source classes

Status: Accepted

Knowledge inputs are separated into static reviewed knowledge, first-party editorial corpus, and dynamic analytical evidence. Static reviewed knowledge includes product articles, documentation, terminology, capabilities, and limitations; reviewed Git content is its MVP source of truth and the only class that may directly support a capability record.

The future first-party editorial corpus contains historical Ethplorer and Binplorer X Posts and replies. It may support style, reaction-pattern analysis, and prior public positioning, but cannot silently prove a product capability, limitation, current fact, or supported network. Its importer and compliant storage are not implemented by Task 005A.

Dynamic analytical evidence, especially `ethereum-top-addresses-pipeline`, remains in its own repository and is not copied into static knowledge. A future adapter must request the latest appropriate snapshot or comparison on demand and preserve the as-of date, comparison dates, metric name, scope, and source provenance for every value. Missing provenance or temporal scope leaves a claim unresolved. Task 005A records these future contracts only and does not implement either adapter.

## 2026-08-13 - Canonical Ethplorer article archive

Status: Accepted

The 12 current Ethplorer Markdown articles remain in `knowledge/sources/posts/`, which is their canonical repository location. They are not moved into product directories merely to match an earlier illustrative layout. Their stable source identities and provenance are preserved.

Task 005A inventories each article with a stable source ID, `source_type = ethplorer_article`, approved provenance, and `pending` review status. This source type is static reviewed knowledge and must not be confused with the future first-party X editorial corpus. The offline validator checks metadata, H1 integrity, substantial body presence, fenced-block closure, and duplicate bodies using comparison-only whitespace folding without fetching links or media.

Capability, limitation, topic, product, network, and asset-catalog extraction is not performed by this amendment and remains Task 005B work.

## 2026-08-13 - Meaning-preserving article normalization

Status: Accepted

The Git knowledge corpus is a reliable machine-readable evidence layer, not a forensic CMS archive. Imported article bodies do not need to remain byte-for-byte identical. Stable source identity, provenance, claims, historical facts, and substantive meaning remain mandatory.

Meaning-preserving normalization may remove trailing whitespace, redundant blank lines, and export artifacts; repair broken Markdown, headings, lists, tables, image references, captions, and unambiguous internal links; or add section structure without changing meaning. It may not restyle claims, silently update facts, prices, limits, dates, or capabilities, add absent information, change substantive meaning, or present inference as a source claim.

The validator checks metadata and semantic or structural usability rather than byte identity. Duplicate comparison may normalize whitespace. The 12 articles are not bulk-reformatted by this correction; Task 005B may normalize only where machine readability improves or an actual artifact is repaired.

## 2026-08-13 - Verified DOCX-to-Markdown article imports

Status: Accepted

Five user-provided DOCX articles are converted into separate `ethplorer_article` Markdown sources in the canonical `knowledge/sources/posts/` directory. The conversion preserves the original filename and SHA-256 digest as provenance metadata, normalizes damaged heading hierarchy and tables, retains hyperlinks and meaningful images, and removes only unambiguous export artifacts. Source claims, historical figures, dates, and capabilities are not updated or promoted during conversion.

Meaningful repeated images are deduplicated into a flat managed namespace directly under `knowledge/sources/posts/assets/`; article references use `assets/<filename>` without dated import subdirectories. A repeated two-pixel Q&A divider is excluded as decoration. Offline validation requires managed `assets/` image references to resolve to non-empty files.

The input DOCX files and their temporary `Delete/` staging directory are removed after visual, structural, source-token coverage, knowledge-validator, and default-test checks pass. Capability extraction remains Task 005B work, and the converted sources retain `pending` status.

## 2026-08-14 - Deferred provider-independent X ingestion boundary

Status: Accepted

Task 004D records a future ingestion-cost optimization and does not authorize implementation. Task 005B, Task 006 and its LLM relevance work, the Opportunity pipeline, and a working MVP/pilot remain higher priority. Stage 3 stays Completed, and Official X remains the production source until an explicit later task changes that decision.

Future X providers must terminate behind provider adapters that emit a stable internal Normalized Post contract. Preliminary provider identifiers are `official_x`, `twitterapi_io`, and `socialdata`, selected manually through `X_DATA_PROVIDER`. Automatic cheapest-provider selection is rejected. Hidden fallback to paid Official X is also rejected; any Official X benchmark, enrichment, or fallback must be explicitly requested and cost-controlled.

The current `x_home_timeline` and future `x_followset` are distinct logical sources. Deduplication must use canonical X `post_id`. Provider-specific cursors may supplement progress tracking but cannot be the only portable checkpoint or leak into downstream relevance, Signal, or Opportunity contracts.

The first future evaluation must be a same-period shadow run of approximately 24 hours across Official X, TwitterAPI.io, and SocialData, not a retrospective benchmark. Official X remains production during the test, and third-party reads must not affect operational checkpoints. Evaluation covers Post-ID recall, missing and extra Posts, complete and long text, Post types, referenced context, author and timestamp integrity, media metadata, duplicates, pagination gaps, latency, and actual cost. Initial acceptance may tolerate approximately 90-95% aggregate recall only when losses are not systematic, while requiring complete text for every received Post, stable canonical IDs, no systematic loss of long Posts, quotes, or replies, and materially lower cost. Relevant-Post recall becomes the more important criterion after Task 006 supplies real relevance decisions.

No adapter, provider purchase, shadow run, scheduling, collector change, fallback, or checkpoint migration is part of this decision record.

## 2026-08-14 - Permanent first-party X editorial corpus

Status: Accepted

By explicit owner decision, Task 005C is performed during Stage 4 before final unified vocabulary or prefilter work. Task 005B static capability review remains separate, Stage 4 remains In Progress, and Task 006 does not begin.

Actual Ethplorer and Binplorer Posts retrieved from X form one continuously updated first-party editorial corpus in PostgreSQL. Historical and future Posts use the same `first_party_x_posts` table and source-specific incremental checkpoints. The corpus is separate from incoming `posts`, Git-backed static evidence, generated drafts, and dynamic analytical evidence. Actual X text is authoritative. The corpus may later inform vocabulary, style, reaction patterns, topic interest, and prior public positioning, but it cannot establish a current capability, supported network, price, API limit, limitation, analytical metric, or numerical fact.

All original, reply, quote, and repost Posts are retained. Long text uses `note_tweet.text` when available. An ordered child table preserves every direct referenced relationship and explicitly distinguishes available from unavailable context. A bounded, deduplicated Post Lookup pass may complete only directly referenced IDs and never recursively crawls thread history. Returned media metadata is retained without downloading media.

The implementation reuses read-only OAuth, `runs`, `usage_events`, and `sync_state`. Ethplorer and Binplorer checkpoints advance independently only after their primary timeline pagination reaches an X-provided end without a blocking guard or persistence failure. Resource-level partial errors remain warnings and preserve explicit unavailable context; they do not make an exhausted primary timeline window incomplete. Estimated Post and User Read prices remain configurable, and `reported_cost` stays NULL until external reconciliation.

Migration 003 creates `first_party_x_posts` and `first_party_x_post_references`, enables RLS on both, and leaves old applied migrations unchanged. Raw corpus content remains operational PostgreSQL data and must not be committed to the public repository. Task 005C adds no keywords, LLM processing, style extraction, dynamic analytics adapter, X write access, scheduling, or publication.

## 2026-08-14 - First-party X corpus accounting and downstream read correction

Status: Accepted

First-party usage accounting distinguishes distinct primary, expanded, reference-completion, and total Post resources, expansion or lookup User resources, inventory User resources, Media resources, and request count. Configurable standard estimates cover Post, User, and Media Reads separately. The first-party cost guard uses their conservative estimated total. Existing Task 005C records are not retroactively reconstructed because the earlier implementation did not persist every class needed for a reliable correction; `reported_cost` remains NULL until external reconciliation.

`first_party_x_posts.text` is the canonical downstream editorial-analysis field and continues to prefer `note_tweet.text` over normal `text`. Original text and raw JSON are not rewritten. Downstream URL reads resolve already stored entities as `unwound_url`, then `expanded_url`, then `url`, without redirect crawling or another X request. Unavailable direct context remains unavailable rather than irrelevant and may retain only a safe resource-specific category, never a raw error body.

The X Developer Console balance of USD 5.12 observed on 2026-08-14 is a forward reconciliation baseline only. It does not establish Task 005C actual cost because no reliable immediately-before balance was recorded. Future explicitly approved live validations should keep before and after balances and observed delta separate from internal estimates.

## 2026-08-14 - Owner-authorized early Task 004D shadow spike

Status: Accepted

The owner explicitly authorizes the bounded Task 004D provider quality and cost spike now, before Task 005B and Task 006. This supersedes only the activation timing in the earlier deferred-provider decision. The work must reach an evidence-backed result without reopening Stage 3, changing the Official X production collector, or establishing a production provider choice. Task 005B and then Task 006 remain the next MVP work after the spike.

The spike may add an isolated read-only provider contract and local CLI for `official_x`, `twitterapi_io`, and `socialdata`. It may read one approximately 24-hour Official X home-timeline benchmark and search only the benchmark's active authors through the two third-party providers. Third-party results and raw responses remain under ignored local runtime storage. The spike must not write `posts`, `sync_state`, the first-party corpus, usage tables, or any other database state.

Each third-party provider has a hard trial-spend ceiling of $0.10. Credit exhaustion produces `incomplete_due_to_credit` and is not automatically a quality failure. Results are compared by canonical X `post_id`, normalized fields, recall, content fidelity, context and media coverage, pagination risk, requests, and spend. Provider-specific cursors remain diagnostic only and cannot become canonical checkpoints.

SocialData grouped Search Query Monitors followed by webhook delivery into the future Normalized Post boundary are recorded only as a later optimization experiment if the shadow result supports it. No monitor, webhook, scheduler, polling replacement, keyword pre-filter, or per-account monitor fleet is implemented now. A future monitor experiment must group followed authors and preserve broad collection so the project's own relevance model, not provider keywords, makes relevance decisions.

## 2026-08-14 - Task 004D accepts no production provider

Status: Accepted

A fresh Official X benchmark request returned HTTP 402, so the bounded spike reused the latest already-collected 24-hour `x_home_timeline` window read-only. This is a documented deviation from the preferred fresh shadow and limits the conclusion. PostgreSQL counts and the `sync_state` fingerprint were identical before and after.

TwitterAPI.io ended `incomplete_due_to_credit` after $0.09975 actual spend and SocialData ended `incomplete_due_to_budget` after a conservative $0.0966 estimate. Neither run met the 90-95% recall and 100% full-text acceptance conditions. Because both runs were incomplete and exposed large pagination gaps, the result does not establish that either provider is intrinsically low quality.

No third-party provider is accepted for production. Official X remains the explicit production source. Provider switching, fallback, scheduling, monitoring, and webhooks remain unimplemented. The SocialData grouped Search Query Monitor idea remains deferred and is not promoted by this evidence. Current MVP work returns to Task 005B and then Task 006.
