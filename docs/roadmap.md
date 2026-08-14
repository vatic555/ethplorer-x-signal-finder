# Ethplorer X Signal Finder - Implementation Roadmap

Status: Canonical implementation sequence and progress record

## Current Position

- Stage 0 - Repository Bootstrap - Completed
- Stage 1 - Durable Storage Foundation - Completed
- Stage 2 - X API Access Spike - Completed
- Stage 3 - X Collection Pipeline - Completed
- Stage 4 - Minimum Knowledge Base - In Progress
- Current task - Task 005B - Ethplorer Knowledge Import - Planned, awaiting its explicit task specification
- Last completed task - Task 004D - X Provider Shadow Quality Spike
- Local PostgreSQL implementation is ready
- Real Supabase migration and database validation are complete
- Task 003 documentation review, diagnostic probe, live OAuth, endpoint, pagination, refresh, and checkpoint validation are complete
- Stage 2 decision - `constrained-go`; Stage 3 has started with the bounded Task 004A collector
- Task 004A implementation, synthetic validation, and bounded live X-to-Supabase validation are complete
- Task 004B implementation, migration 002, synthetic validation, and bounded live validation are complete
- Task 004C and Task 004C.1 implementation, synthetic validation, explicit baseline acceptance, and bounded incremental live validation are complete
- Task 004D provider shadow quality and cost spike is Completed; neither incomplete trial met acceptance and Official X remains production
- Task 005A knowledge inventory, Git-backed source contract, catalog evidence linkage, and offline validation are complete
- Task 005C first-party Ethplorer/Binplorer X corpus, migration 003, historical import, and incremental lifecycle validation are complete
- Task 005C.1 corrected first-party resource accounting and downstream read contracts without another X request or schema change

Stage 1 must not be marked Completed until the real Supabase database has been created, migrations have been applied, and database validation has passed.

## MVP Boundary

Stages 0 through 7 constitute the MVP. Stage 7 completes the MVP through a two-week manually operated pilot. The MVP is not complete merely because the code exists.

Pipeline execution remains manually started one or two times per day during the MVP. Publication remains a mandatory human action. Stage 8 is post-MVP. Deferred does not mean rejected.

The MVP covers:

- automatic X collection;
- durable cloud storage;
- relevance filtering;
- Signal clustering;
- Opportunity Gate;
- selective context enrichment;
- knowledge-base matching;
- drafts and action suggestions;
- human review and editing;
- usage and cost accounting;
- a two-week pilot.

Post-MVP work may cover:

- scheduled execution;
- GitHub Actions or another scheduler;
- Telegram delivery;
- dashboards;
- real-time monitoring;
- automatic publication;
- automatic image generation;
- automatic model training;
- Opportunity Score.

## Stage Summary

| Stage | Name | Status | Task | MVP |
|---|---|---|---|---|
| 0 | Repository Bootstrap | Completed | Task 001 | Yes |
| 1 | Durable Storage Foundation | Completed | Task 002 | Yes |
| 2 | X API Access Spike | Completed | Task 003 | Yes |
| 3 | X Collection Pipeline | Completed | Tasks 004A through 004D complete; 004D made no production change | Yes |
| 4 | Minimum Knowledge Base | In Progress | Tasks 005A, 005C, and 005C.1 complete; Task 005B next | Yes |
| 5 | Relevance Filtering and Signal Clustering | Planned | Task 006 | Yes |
| 6 | Opportunity Gate and Context Enrichment | Planned | Task 007 | Yes |
| 7 | Drafts, Human Review and Pilot | Planned | Task 008 | Yes |
| 8 | Scheduling and Delivery Automation | Deferred | Future task | No |

## Stage 0 - Repository Bootstrap

Status: Completed

Established the repository foundation:

- canonical specification;
- decision log;
- AGENTS instructions;
- terminology structure;
- knowledge-base placeholders;
- prompt contracts;
- minimal Python package and CLI;
- Git and environment safety rules.

### Tasks

- Task 001 - Repository Bootstrap - Completed
- Task 001A - Canonical Implementation Roadmap - Completed

### Completion Record

- Final commit: `f9b5abf9abe28f3891c0c1cf1376f9a1b87e8353`
- Commit message: `chore: bootstrap Ethplorer X Signal Finder`
- Roadmap task commit: `671a7cbd1f4990e78e41d4717dada5bde28abf59`
- Roadmap validation summary: canonical roadmap created; linked documents aligned; documentation consistency checks passed.

## Stage 1 - Durable Storage Foundation

Status: Completed

Create the cloud PostgreSQL foundation:

- Supabase as the initial provider;
- standard PostgreSQL access;
- migrations;
- runs, posts, Signals, Opportunities, reviews, usage, and sync state;
- repository API;
- DB CLI;
- tests and transaction-based validation;
- secret redaction.

Current state:

- local schema and implementation are ready;
- default tests pass;
- real Supabase connection is available;
- migration 1 is applied with no pending migrations;
- database structure, RLS, rollback behavior, and connectivity are validated.

### Tasks

- Task 002 - Durable Storage Foundation - Completed

### Completion Record

- Completion date: 2026-07-23
- Final commit: `dda7e417550a8f5a05c88f2277443e07c577fcc0`
- Validation summary: Supabase PostgreSQL 17.6; migration 1 applied; `db doctor` healthy; `db smoke-test` passed with all synthetic changes rolled back; 12 default tests passed with 1 optional integration test skipped; explicit Supabase integration test passed; repeat migration reported no pending work.
- Remaining limitations: No known Task 002 limitations. X collection and later pipeline stages remain unimplemented.

## Stage 2 - X API Access Spike

Status: Completed

Verify the real technical and commercial limits of X before building the collector:

- personal-account authentication;
- home timeline access;
- `@Ethplorer` mentions;
- pagination;
- token refresh;
- response fields;
- rate limits;
- available history;
- storage and retention restrictions;
- expected cost;
- go, constrained-go, or no-go decision.

Current state:

- official X documentation review is complete as of 2026-08-05;
- isolated read-only probe, OAuth 2.0 PKCE helper, synthetic fixtures, and mocked tests are implemented;
- live OAuth 2.0 PKCE authorization and refresh succeeded;
- live home-timeline requests returned HTTP 200, exercised multiple pages, showed no duplicate IDs, repeated page one consistently, and reached an in-memory checkpoint;
- the direct `@Ethplorer` mentions request returned HTTP 200 under Aleksandr user context, demonstrating that separate Ethplorer authorization is not required to call the endpoint in this configuration;
- the mentions response contained no Posts, so mentions pagination could not be observed live;
- decision is `constrained-go` because of bounded history windows, possible partial errors, unobserved mentions pagination, Developer Console billing dependence, and unresolved operational compliance details;
- Stage 3 subsequently started with Task 004A and remains In Progress.

### Tasks

- Task 003 - X API Access Spike - Completed

### Completion Record

- Completion date: 2026-08-05
- Final implementation commit: `d21fb2cd99cab8fa6b37fa465501e90db03ca751`
- Decision: `constrained-go`
- Validation summary: OAuth 2.0 PKCE authorization and refresh succeeded; home and mentions endpoints returned HTTP 200; home pagination, page-repeat consistency, duplicate detection, returned fields, actual rate-limit headers, and in-memory checkpoint reachability were validated; the default test suite passed without external calls; tokens, responses, and Post text were not persisted.
- Remaining limitations: Home is bounded to the documented 3,200-Post or seven-day window, and mentions to 800 Posts. The live mentions result was empty, so its pagination was not exercised. Home responses can contain partial object errors even with HTTP 200. Exact charged usage remains a Developer Console observation. Stage 3 must implement independent safe checkpoints, complete pagination, partial-error failure handling, possible-window-truncation warnings, usage accounting, and an approved retention and deletion process.

## Stage 3 - X Collection Pipeline

Status: Completed

Build reliable automatic collection while keeping execution manually initiated:

- home timeline;
- `@Ethplorer` mentions;
- pagination;
- durable storage;
- post-ID deduplication;
- independent checkpoints;
- safe checkpoint advancement;
- retry and partial-failure protection;
- missed-window warnings;
- collection usage and cost accounting;
- macOS and Windows support.

Current state:

- Task 004C changes collector defaults to five pages, 100 primary Posts per page, a $1 estimated-cost guard, three attempts, and a 60-second maximum retry wait;
- OAuth access tokens are refreshed in memory, and only the rotated refresh token is stored in ignored local `.env`;
- home and mentions use independent `sync_state` keys;
- Post mapping, simple-repost exclusion, upsert deduplication, safe checkpoint updates, minimal usage estimates, and secret-safe summaries are implemented without a schema migration;
- an intentionally bounded first run establishes a current baseline and records that older history was not backfilled;
- complete incremental pagination follows `next_token` until exhaustion or an explicit guard, and incomplete sources preserve Posts and usage without advancing their checkpoint;
- the optional total primary-Post limit is global across home then mentions, while expanded Post resources count only toward estimated cost;
- retry is limited to connection failures, timeouts, HTTP 500, 502, 503, 504, and bounded HTTP 429 waits;
- successful-response usage is committed independently before Post upsert so a later database failure does not erase the paid-fetch estimate;
- home missed-window and mentions truncation-risk warnings are persisted without claiming proven data loss;
- required bounded live home, repeated-home, and mentions runs against X and Supabase passed;
- Task 004B content completeness and review-view implementation is complete;
- long Posts now prefer returned `note_tweet.text`, and returned referenced Post and media metadata are retained under service keys in the original `raw_json`;
- an explicit bounded refresh mode reads the checkpoint only to anchor `until_id`, updates the bounded stored window, and does not change the operational checkpoint;
- migration 002 defines manual Post review, author statistics, and manual unfollow-candidate views;
- automatic missed-window recovery and compliance automation remain deferred.
- explicit manual baseline acceptance can advance a stalled checkpoint from a validated incomplete run without an X request, only after confirmation that older Posts may be skipped.

### Tasks

- Task 004A - Minimal X Collector to PostgreSQL - Completed
- Task 004B - Content Completeness and Review Views - Completed
- Task 004C - Complete Incremental Collection and Cost Guardrails - Completed
- Task 004C.1 - Explicit Baseline Acceptance - Completed
- Task 004D - X Provider Shadow Quality Spike - Completed, non-production exception

### Task 004A Validation Record

- Completion date: 2026-08-06
- Live runs: home baseline, repeated incremental home, and mentions
- Live result: 21 Posts fetched across two home requests, 4 simple reposts excluded, and 17 unique home rows saved; stored types were 13 original Posts, 2 replies, and 2 quote Posts; the mentions request succeeded with zero Posts.
- Deduplication: 17 total Post rows and 17 distinct `post_id` values after the repeated home run; duplicate groups were zero.
- Checkpoints: `x_home_timeline` stored and reused a non-empty checkpoint; `x_ethplorer_mentions` recorded a successful empty collection with no checkpoint value.
- Usage estimate: 2 home requests and 1 mentions request; 21 public Post reads; $0.105 estimated X Post-read cost before Developer Console reconciliation.
- Database validation: PostgreSQL 17.6; migration 1 current; no pending migrations; required tables present; RLS enabled; no new migration created.
- Tests: 42 passed and 3 optional integration tests skipped before live validation.
- Remaining limitations: bounded initial baseline, no historical backfill, no full Stage 3 recovery workflow, no automated X Content revalidation or deletion, and one stored `source_key` value per Post row.

### Task 004B Validation Record

- Completion date: 2026-08-06
- Scope: full long-Post text, returned referenced context, returned media metadata, manual review views, and explicit bounded refresh of existing rows
- Database: migration 002 applied; PostgreSQL 17.6 healthy; migrations 1 and 2 current; no pending migrations; operational-table RLS unchanged; all three views use `security_invoker=true`
- Target Post `2085122221501239463`: stored text increased from 319 to 1,320 characters and exactly matches `note_tweet.text`; quote relationship, referenced Post context, direct URLs, video metadata, and `has_video=true` validated
- Target Post `2085122224563126320`: reply relationship, referenced context, direct URLs, `low_information_reply_candidate=true`, `processing_status=unprocessed`, and no rejection validated
- Refresh integrity: first-seen run and first-collected timestamp were preserved; last-seen values advanced; checkpoint fingerprint was identical before and after; duplicate groups were zero
- Views: `posts_review`, `author_source_stats`, and `author_unfollow_candidates` validated with real and rollback-only synthetic data; 0 authors currently meet the manual unfollow-candidate heuristic
- Live usage: 78 X Post Reads and $0.390 estimated cost across three bounded attempts. The first two attempts exposed current-window drift; the accepted fix anchors refresh at the stored checkpoint with `until_id`, and the final one-page attempt validated both required Posts
- Tests: 58 default tests passed with 4 external tests skipped; 2 PostgreSQL integration tests passed explicitly
- Stage boundary: Stage 3 remains In Progress; Stage 4 and AI processing are not started; no automatic unfollow, X write access, or media download was added

### Task 004C Validation Record

- Implementation: complete forward pagination, independent source outcomes, global primary-Post limit, estimated-cost guard, bounded retry policy, partial-response handling, durable usage-before-upsert behavior, and missed-window warnings are implemented
- Default tests: 77 passed with 4 external tests skipped; no external requests or real retry sleep occurred
- PostgreSQL integration: 2 tests passed explicitly against the configured database
- Database health: PostgreSQL 17.6 healthy; migrations 1 and 2 current; no pending migrations; operational-table RLS intact
- Pre-live data: 49 Post rows, 49 distinct Post IDs, zero duplicates; home checkpoint `2085127387939807652`; mentions checkpoint empty
- Bounded run: 20 primary Posts, 17 expanded Posts, 30 distinct resources, 18 saved Posts after 2 repost exclusions, $0.150 estimate, exit 1 as incomplete, and unchanged home checkpoint
- Full guarded run: 194 primary Posts, 113 expanded Posts, 272 distinct resources, 152 saved Posts including 134 new rows after 42 repost exclusions, $1.360 estimate, and exit 1 after the cost guard; one-page overshoot is within the documented guard semantics
- Source independence: mentions was not requested because home exhausted the run cost guard; its checkpoint remained unchanged
- Post-live data: 201 Post rows, 201 distinct Post IDs, zero duplicates; home and mentions checkpoints unchanged
- Recorded validation usage: 3 HTTP requests, 214 primary Posts, 130 expanded Posts, 302 estimated distinct Post resources, and $1.510 estimated cost across the two permitted live runs; `reported_cost` remains NULL
- Remaining validation: authenticate to X Developer Console and record before/after count, cost, and balance; then run one explicitly approved incremental collection with enough guard headroom to exhaust `next_token` and demonstrate live checkpoint advancement
- Baseline acceptance: the incomplete guarded home run was accepted manually at `2085449523904778414`; the operation made no X request, created no Posts, and preserved all 201 existing rows with 201 distinct IDs and zero duplicates
- Cheap incremental validation: one request from the accepted checkpoint returned 19 primary and 10 expanded Posts, counted 29 distinct resources, saved 13 new rows after 6 repost exclusions, estimated $0.145, and remained incomplete at the explicit one-page limit, so the checkpoint correctly stayed unchanged
- Post-validation data: 214 Post rows, 214 distinct Post IDs, zero duplicates; baseline audit metadata is retained in both `sync_state` and the source run
- Final default tests: 88 passed with 4 external tests skipped; explicit PostgreSQL integration tests: 2 passed
- Stage boundary: Task 004C and Task 004C.1 are complete; Stage 3 is Completed; Stage 4 and AI runtime remain unstarted

### Completion Record

- Completion date: 2026-08-07
- Final implementation commit: `098a163cfd40859ff3088d192462c0c37c923746`
- Validation summary: guarded pagination, incomplete-checkpoint safety, explicit no-request baseline acceptance, and one cheap incremental run from the accepted checkpoint passed; PostgreSQL ended with 214 unique Posts and no duplicate IDs
- Remaining limitations: no historical backfill or automatic missed-window recovery; Developer Console billing was not reconciled; mentions pagination was not observed beyond an empty live response

### Task 004D - Pluggable X Data Providers + Provider Quality Spike

Status: Completed as an owner-authorized non-production exception

The owner explicitly authorized one bounded quality and cost spike before Task 005B and Task 006 and asked that it reach an evidence-backed result now. This supersedes only the earlier activation timing. It does not reopen Stage 3, change its Completed status, alter the production collector, or change Task 005B and Task 006 as the next MVP work.

The future goal is provider-independent X ingestion with an explicit manual configuration switch among preliminary providers:

```text
X_DATA_PROVIDER=official_x
X_DATA_PROVIDER=twitterapi_io
X_DATA_PROVIDER=socialdata
```

There must be no automatic cheapest-provider selection and no hidden fallback to paid Official X. Any Official X benchmark, selective enrichment, or fallback request must remain explicit and cost-controlled.

The future boundary is:

```text
Provider
  -> Provider Adapter
  -> Normalized Post
  -> existing collector/storage
  -> relevance / Signals / Opportunities
```

Provider-specific response formats must terminate at the adapter. Downstream processing must use a stable internal Post contract and canonical X `post_id` deduplication. `x_home_timeline` and the future `x_followset` are separate logical sources. A provider cursor may be retained for that provider, but it must not become the only portable checkpoint.

For third-party discovery, the initial hypothesis is periodic public-Post collection from the account's current follow-set, estimated at approximately 370 accounts when this task was defined, with several manual or scheduled passes per day to be evaluated later. No provider purchase, adapter, scheduling, or collection is approved by this task.

The first future provider-quality test must be a shadow run over the same approximately 24-hour period for Official X, TwitterAPI.io, and SocialData, not a retrospective benchmark. Official X remains the production source during the test, and third-party results must not change operational checkpoints. The shadow run must compare:

- canonical Post ID coverage, missing Posts, and extra Posts;
- complete text and long Posts;
- original Posts, replies, and quote Posts;
- referenced Post context;
- author and timestamp integrity;
- media metadata;
- duplicates and pagination gaps;
- latency;
- actual provider cost.

The initial quality hypothesis for a cheaper provider is approximately 90-95% overall Post recall, provided missing Posts are not systematic; 100% full text for every received Post; no systematic loss of long Posts, quotes, or replies; stable canonical `post_id`; and materially lower cost than Official X. Relevant-Post recall must be evaluated separately after Task 006 produces real AI relevance decisions and is more important than aggregate raw recall.

A possible later operating model is broad collection through a cheaper provider with Official X retained for explicit benchmarks, selective enrichment, or controlled fallback.

The current Task 004D implementation is intentionally shadow-only:

- a local `official_x | twitterapi_io | socialdata` adapter boundary terminates in one Normalized Post comparison contract;
- one CLI command reads an Official X home benchmark and searches only authors active in that same window;
- raw responses remain under ignored `data/runtime/x-provider-shadow/`;
- each third-party provider has a hard $0.10 spend ceiling;
- HTTP 402 becomes `incomplete_due_to_credit`, not an automatic quality rejection;
- no PostgreSQL table, `sync_state`, production collector path, fallback, or provider switch is touched.

If the SocialData result justifies another experiment, grouped Search Query Monitors feeding webhooks into the Normalized Post boundary are the next separate optimization candidate. That future experiment must group followed authors and capture their Posts without a keyword pre-filter so Task 006 relevance logic remains authoritative. It must not create approximately 370 User Monitors. Monitoring, webhooks, scheduling, and polling replacement are not implemented by Task 004D.

#### Task 004D Completion Record

- Completion date: 2026-08-14
- Final implementation commit: `222bc5e9de2ea46b5fe26639a7ebbe612edb3cae`
- Live window: 2026-08-06T12:01:06Z through 2026-08-07T12:01:06Z
- Official X benchmark: fresh retrieval returned HTTP 402; 192 already-collected `x_home_timeline` Posts from 71 active authors were reused read-only with zero incremental X spend
- TwitterAPI.io result: incomplete due to trial credit; 25/192 matched IDs, 13.02% recall, 96.0% exact text on matches, $0.09975 actual spend
- SocialData result: incomplete due to budget; 11/192 matched IDs, 5.73% recall, 100% exact text on matches, $0.0966 conservative estimated spend
- Recommendation: accept neither provider; retain Official X as production source and do not promote SocialData Monitoring from this evidence
- Validation summary: 156 default tests passed with 4 external tests skipped; canonical DB counts and the `sync_state` fingerprint were identical before and after; raw provider data remains ignored and no production collector, database row, or checkpoint changed

## Stage 4 - Minimum Knowledge Base

Status: In Progress

Create the minimum reviewed knowledge required for credible Opportunity decisions:

- shared analytics terminology;
- project terminology;
- asset catalog;
- explorer and API capabilities;
- analytics capabilities;
- supported networks;
- capability limitations;
- public and internal provenance;
- stable asset IDs;
- human review process.
- explicit separation of static reviewed knowledge, first-party editorial corpus, and dynamic analytical evidence.

### Tasks

- Task 005 - Minimum Knowledge Base - In Progress
- Task 005A - Knowledge Architecture + Import Contract - Completed
- Task 005C - First-Party X Corpus Import + Continuous Sync - Completed by explicit owner decision before final unified vocabulary work
- Task 005C.1 - First-Party X Corpus Corrections - Completed
- Task 005B - Ethplorer Knowledge Import - Planned and next

### Task 005A Validation Record

- Completion date: 2026-08-07
- Inventory: two existing terminology documents preserved in separate namespaces; 17 complete canonical Ethplorer articles inventoried under `knowledge/sources/posts/`; zero asset or capability rows; one pending upstream terminology source retained with provenance
- Architecture: reviewed Git content under `knowledge/` is the MVP source of truth for static reviewed knowledge; PostgreSQL remains operational storage and no database, embedding, vector, search, crawler, or LLM runtime was added
- Source classes: static reviewed knowledge is canonical in Git; the future first-party Ethplorer/Binplorer X corpus is editorial context only; dynamic analytics such as `ethereum-top-addresses-pipeline` stay upstream and require dated, scoped, provenance-preserving on-demand reads
- Authority boundary: editorial history and dynamic metrics cannot silently establish a product capability; reviewed capability rows still require reviewed supporting static source IDs
- Source contract: reliable machine-readable Markdown with stable `source_id`, TOML metadata, public or approved provenance, product and network scope, review status, supported claims, limitations, and optional known dates; meaning-preserving structural normalization is allowed, but claim or fact changes are not
- Capability contract: the compact CSV catalog uses stable `asset_id` values and mandatory `source_ids`; a reviewed capability requires at least one reviewed source
- Safety: the 12 explicitly approved Ethplorer articles were inventoried in place; no private or licensed source text, invented product capability, or capability row was added
- Initial validation: offline knowledge validation reported 0 errors with 0 imported sources and 0 assets; the then-current default suite passed with 99 tests and 4 external tests skipped, without network requests, database access, or model calls
- Final implementation commit: `ec6c3d91428abd3cc770c8c3c34e8ed2c7db021d`
- Architecture amendment date: 2026-08-10
- Architecture amendment commit: `3e37ee6e52524f458e6023100c5af0398b40a04c`
- Article inventory amendment date: 2026-08-13
- Article inventory: all 12 files read in full; each has one unique H1, a substantial coherent body, distinct body content, stable source metadata, and `source_type = ethplorer_article`; Task 005A did not bulk-reformat the articles
- Article validator: canonical location, source type, title-to-H1 match, body completeness guard, fenced-block closure, and duplicate content checks are offline; validation targets structural usability rather than byte identity
- Normalization correction: Task 005B may make meaning-preserving Markdown repairs or normalization only where machine readability improves or an actual artifact is repaired; source identity, provenance, claims, historical facts, and meaning remain unchanged
- Normalization correction commit: `32f742baf7cec7e95468c535e6baf3b6875877ed`
- Article inventory validation: 12 sources and 0 assets validated with 0 errors, 0 network requests, and 0 LLM calls; the full default suite passed with 105 tests and 4 external tests skipped
- DOCX conversion amendment date: 2026-08-13
- DOCX conversion: five user-provided DOCX articles rendered across 33 pages, structurally inspected, converted to normalized Markdown with original filename and SHA-256 provenance, and checked at 99.7-100% source-token coverage
- DOCX media: 16 meaningful image instances consolidated into 11 unique local image assets stored directly under `knowledge/sources/posts/assets/`; the Q&A divider line was removed as an export artifact; two real Word tables were preserved as Markdown tables
- DOCX cleanup: the temporary `knowledge/sources/posts/Delete/` staging directory and all five source DOCX files were removed only after successful conversion checks
- Current inventory validation: 17 sources and 0 capability assets validated with 0 errors, 0 network requests, and 0 LLM calls; the full default suite passed with 108 tests and 4 external tests skipped
- DOCX conversion implementation commit: `1475479b9a2336c25d5f5b42ea22b6aa02b19444`
- Deferred to Task 005B: capability, limitation, topic, product, network, and `assets_catalog.csv` extraction
- Article inventory amendment commit: `29db23781fb5dca3373198477b19ea43303124b3`
- Stage boundary: Stage 4 remains In Progress; Task 005B is next and Task 006 has not started

### Task 005C Validation Record

- Completion date: 2026-08-14
- Final implementation commit: `44aec27c13d951f6d934ef60f3038152920e91f4`
- Owner sequencing decision: first-party corpus collection was performed before final unified vocabulary work; Task 005B remains the next separate static capability-review task
- Schema: migration 003 creates RLS-enabled `first_party_x_posts` and `first_party_x_post_references`, separate from incoming `posts`; no old migration was changed
- Corpus lifecycle: historical and future Ethplorer/Binplorer Posts share one permanent table; source checkpoints are `first_party_x_ethplorer` and `first_party_x_binplorer`; repeat sync uses `since_id`
- Content: original, reply, quote, and repost Posts are retained; long text prefers `note_tweet.text`; all direct relationships are ordered and lossless; context is explicitly available, unavailable, or not applicable; returned media metadata is stored without downloading media
- Inventory snapshot: Ethplorer 352 account-level Posts and Binplorer 39, treated only as reference counts
- Successful historical retrieval: Ethplorer 339 Posts and Binplorer 39; the Ethplorer difference of 13 is recorded as a retrieval difference, not asserted data loss
- Types: Ethplorer 156 originals, 121 replies, 24 quotes, and 38 reposts; Binplorer 14 originals, 11 replies, 2 quotes, and 12 reposts
- Context and media: 187 available and 17 unavailable direct relationship contexts across the stored corpus; successful run returned 198 unique media resources across its two source scopes
- Range: Ethplorer 2017-05-21 through 2026-07-23; Binplorer 2022-10-13 through 2026-07-16
- Historical run: 8 requests and `$2.650` estimated cost, including one batched two-User inventory lookup; resource-level partial errors were preserved as warnings
- Earlier bounded validation attempt: 5 requests and `$0.905` estimated cost exposed overly strict partial-resource classification, saved 132 rows, and advanced no checkpoint; the corrected run safely upserted those rows
- Repeat incremental validation: 2 timeline requests, 0 primary Posts, 0 new rows, `$0.000` estimated Post-resource cost, and unchanged checkpoints
- Final database: 378 corpus rows, 378 distinct Post IDs, zero duplicate groups; incoming `posts` remained 214 rows and 214 distinct IDs
- Checkpoints: Ethplorer `2080369149331558445`; Binplorer `2077741562402939325`
- Database health: PostgreSQL 17.6 healthy; migrations 1 through 3 current; no pending migrations; RLS intact on all operational tables
- Tests: 133 passed with 4 external tests skipped before final documentation validation; no default test made an X or PostgreSQL request
- Scope boundary: no keyword extraction, LLM analysis, style guide, relevance filter, Signals, Opportunities, analytics adapter, media download, X write access, scheduling, or publication was added

### Task 005C.1 Validation Record

- Completion date: 2026-08-14
- Accounting: first-party source usage now separates distinct primary, expanded, reference-completion, and total Post resources, expansion or lookup User resources, inventory User resources, Media resources, request count, and estimated Post, User, Media, and total cost; the guard uses the conservative total
- Pricing basis: configurable standard estimates are `$0.005` per Post Read, `$0.010` per User Read, and `$0.005` per Media Read, re-checked against current official X pricing documentation
- Context diagnostics: unavailable referenced Posts remain unavailable and can retain a compact safe resource-specific reason without raw error bodies; the existing 17 contexts were not re-fetched and may remain `unknown`
- Downstream reads: stored main and `note_tweet` URL entities resolve deterministically as `unwound_url`, then `expanded_url`, then `url`, with no redirect crawl or X request; authoritative Post text is unchanged
- Canonical analysis text: `first_party_x_posts.text` remains the full `note_tweet.text` when available and normal text only as fallback; `raw_json.text` is audit data and may be truncated
- Billing reconciliation: the USD 5.12 Developer Console balance observed on 2026-08-14 is recorded only as a forward baseline; historical Task 005C estimates from the prior accounting implementation were not retroactively reconstructed
- URL validation: 232 Posts contain 348 deduplicated URL entities; 343 have `expanded_url`, 62 have `unwound_url`, 4 remain `t.co`-only, and 103 resolve to Ethplorer or Binplorer sites
- Validation: 147 default tests passed with 4 external tests skipped; 2 PostgreSQL integration tests passed; knowledge validation passed for 17 sources and 0 assets; PostgreSQL validation preserved 378 first-party rows, 214 incoming rows, both first-party checkpoints, migrations 1 through 3, and RLS without an X request
- Scope boundary: no migration, historical backfill, keyword or knowledge extraction, LLM processing, Task 006, analytics adapter, provider adapter, media download, or X write operation was added
- Final implementation commit: `f222ac55c97002fb134ed3a4b1b6196ad8925866`

### Completion Record

- Completion date:
- Final commit:
- Validation summary: Tasks 005A and 005C complete; Task 005B and Stage 4 completion remain pending.
- Remaining limitations: The 17 Ethplorer articles remain pending substantive review; no evidence-backed capability rows have been extracted yet.

## Stage 5 - Relevance Filtering and Signal Clustering

Status: Planned

Reduce collected X content to a small auditable set of potential Signals:

- preliminary relevance decisions;
- rejection reasons;
- evidence and uncertainty;
- event clustering;
- source-post relationships;
- conflicting claims;
- structured Signal records;
- evaluation examples;
- false-positive and missed-candidate review.

Relevance alone must not create an Opportunity.

### Tasks

- Task 006 - Relevance Filtering and Signal Clustering - Planned
- Task 006B - Author Quality Monitoring and Follow-list Hygiene - Planned

### Task 006B - Planned Scope

Task 006B starts only after Task 006 produces real AI relevance decisions. The existing `author_source_stats` and `author_unfollow_candidates` views are preliminary keyword-based MVP tools for manual inspection. They are not a complete source-quality assessment and do not authorize any account action.

An author becomes eligible for manual review after at least 20 observed Posts or at least seven days of observation. Future metrics must include:

- observed Posts and estimated X Post Read cost;
- original, quote, reply, and low-information reply counts;
- main-text, referenced-text, and combined keyword matches;
- AI relevance counts for kept, rejected, and uncertain Posts;
- relevance ratio;
- Signals created and Opportunities accepted;
- last useful Post, last Signal, and observation span.

For every Post, future author analysis must use:

```text
effective_analysis_text = main Post text + referenced_post_text when available
```

Quote and reply context must participate in keyword matching, AI relevance filtering, author relevance statistics, and the manual candidate decision. The metrics `main_text_keyword_matches`, `referenced_text_keyword_matches`, and `combined_keyword_matches` must remain separate. `blockchain_keyword_matches` must represent the combined result and count a match found in either source. A short neutral main comment must not make its author look irrelevant when the quoted or parent Post contains a relevant blockchain discussion.

Missing referenced expansion must be represented as context unavailable. It must not cause a failure or a false conclusion that the unavailable context is irrelevant.

Manual author-review states are planned as:

- `unreviewed`;
- `keep`;
- `watch`;
- `unfollow_candidate`;
- `unfollowed`;
- `dismissed`.

Each review must retain the reviewer, review timestamp, reason, status, optional `review_again_after`, and a snapshot of the metrics used. An author may enter the manual queue only after reaching the observation threshold and having no AI-kept Posts or Signals, a very high rejected ratio, or meaningful cost without useful results. A zero keyword count can support review but is never a final decision, and quoted or referenced context must be considered.

Authors marked `keep` or `dismissed` must not repeatedly reappear. Re-evaluation may occur only after `review_again_after`, substantial new Post volume, a sharp relevance-ratio decline, meaningful cost growth, or a long period without a useful Post or Signal.

A future manual view such as `author_review_queue` should show username, profile URL, observed Posts, estimated cost, relevance statistics, Signals, Opportunities, last useful Post, suggested reason, and current review status.

Future Task 006B validation must include:

1. A quote with neutral main text and `Ethereum` in referenced text counts as a combined match and does not enter a zero-match candidate queue.
2. A short reply with relevant referenced blockchain context remains eligible for a low-information reply flag while preserving that context for AI and author statistics.
3. A Post without referenced context uses only its main text.
4. A missing expansion is safe, records unavailable context, and does not assert that the context is irrelevant.

Task 006B must not implement automatic unfollow, X write access, write OAuth scopes, or automatic follow-list changes. Every unfollow decision and action remains manual in X.

### Completion Record

- Completion date:
- Final commit:
- Validation summary:
- Remaining limitations:

## Stage 6 - Opportunity Gate and Context Enrichment

Status: Planned

Accept only Signals containing a real information gap that a documented Ethplorer asset can naturally close:

- accepted, rejected, and unresolved decisions;
- information-gap identification;
- exact asset matching;
- audience benefit;
- natural relevance;
- forced-promotion rejection;
- evidence sufficiency;
- selective thread and external context enrichment;
- Opportunity creation only after acceptance.

Rejected and unresolved Signals must not receive drafts.

### Tasks

- Task 007 - Opportunity Gate and Context Enrichment - Planned

### Completion Record

- Completion date:
- Final commit:
- Validation summary:
- Remaining limitations:

## Stage 7 - Drafts, Human Review and Pilot

Status: Planned

Turn accepted Opportunities into reviewable actions and validate the MVP through a two-week pilot:

- reply;
- quote post;
- own post;
- article idea;
- BizDev action;
- Visual Brief;
- human review;
- edited version;
- preservation of generated and edited versions;
- feedback taxonomy;
- pilot reporting;
- execution one or two times per day for two weeks;
- measurement of posts, Signals, Opportunities, time, and cost;
- false-positive and missed-candidate analysis;
- mandatory human publication.

At the end of the pilot, record whether to:

- stop;
- revise the pipeline;
- extend the pilot;
- proceed to post-MVP automation.

### Tasks

- Task 008 - Drafts, Human Review and Two-Week Pilot - Planned

### Completion Record

- Completion date:
- Final commit:
- Pilot dates:
- Pilot results:
- Final decision:
- Remaining limitations:

## Stage 8 - Scheduling and Delivery Automation

Status: Deferred

Possible post-MVP work:

- scheduled execution;
- GitHub Actions or another scheduler;
- Telegram delivery;
- review notifications;
- operational monitoring;
- automated reports;
- lightweight review interface;
- possible dashboard.

Automatic publication is not approved and requires a separate decision.

### Tasks

- Future tasks to be assigned after Stage 7

### Completion Record

- Completion date:
- Final commit:
- Validation summary:
- Remaining limitations:

## Roadmap Maintenance Rules

- Stage order must not change silently.
- Stage reorder or bypass requires an accepted decision.
- A stage begins when marked In Progress.
- A stage is marked Completed only after its task-specific validation passes.
- Written code alone does not complete a stage.
- Completion records must contain the final commit and validation result.
- README must be updated when the current stage changes.
- Product-behavior changes must update `docs/project-spec.md`.
- Architectural changes must update `docs/decisions.md`.
- Implementation stages must not be confused with runtime pipeline stages.
