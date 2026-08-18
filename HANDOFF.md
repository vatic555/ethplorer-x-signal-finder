# Ethplorer X Signal Finder - Handoff

Last updated: 2026-08-18

Repository HEAD before the Task 005D.1 implementation commit: `2653679b704166e111b6ccc3d71be1856ec0cca6`

Validated commit: pending Task 005D.1 implementation commit

Validated implementation commit: pending Task 005D.1 implementation commit

This file is a short current-state snapshot. It is not a canonical product, technical, architecture, or roadmap source.

## Source Hierarchy

1. [`docs/project-spec.md`](docs/project-spec.md) - canonical product and technical specification.
2. [`docs/roadmap.md`](docs/roadmap.md) - canonical stage order and status record.
3. [`docs/decisions.md`](docs/decisions.md) - accepted architecture decisions.
4. [`AGENTS.md`](AGENTS.md) - mandatory rules for contributors and AI agents.
5. [`HANDOFF.md`](HANDOFF.md) - concise current snapshot, not a source of truth.

If this file conflicts with a canonical document, update this file to match the canonical source.

## 1. Project Goal

The project is building an AI-assisted X intelligence pipeline for Ethplorer. It collects an authorized account's home timeline and `@Ethplorer` mentions, then will identify relevant blockchain discussions, group evidence into Signals, and apply an Opportunity Gate before producing reviewable Opportunities or drafts. A human reviews every result and publishes manually. Automatic publication is not allowed.

## 2. Current Status

- Current stage: Stage 4 - Minimum Knowledge Base - In Progress.
- Current task: Task 005D.1 - Vocabulary Precision Review - Completed.
- Last completed corrective task: Task 005D.1 - Vocabulary Precision Review.
- Last completed MVP product task: Task 005D - Reviewed Knowledge + Unified Prefilter Vocabulary.
- Completed bounded exception: Task 004D accepted no third-party provider and made no production change.
- Next implementation action: Task 005E - Dynamic Analytics Adapter, only after its explicit task specification is available.
- Roadmap status: Stages 0 through 3 are Completed; Stage 4 is In Progress; Stages 5 through 7 are Planned; Stage 8 automation is Deferred.
- Task 004D is a completed non-production shadow spike. It did not reopen Stage 3, change the production collector, or accept a third-party production provider.
- Task 006B - Author Quality Monitoring and Follow-list Hygiene is Planned after Task 006 produces real AI relevance decisions. It is not current work.

## 3. What Works Now

The following capabilities have been implemented and validated:

- protected PostgreSQL storage hosted in Supabase;
- checksum-tracked migrations 001 through 004;
- migration 003 with a separate permanent first-party X corpus and ordered direct-reference table;
- Row Level Security on operational tables;
- OAuth 2.0 Authorization Code flow with S256 PKCE;
- local refresh-token persistence and refresh-token rotation;
- authorized reverse-chronological home timeline access;
- direct mentions endpoint access;
- manually invoked bounded collection for home and mentions;
- forward incremental pagination until `next_token` ends or an explicit guard stops the source;
- independent source checkpoints and safe non-advancement on known incomplete conditions;
- global primary-Post and estimated-cost guards across home then mentions;
- bounded transient-error retries with mockable sleep;
- separate primary, expanded, reference-completion, total Post, User, and Media resource accounting with a conservative total-cost guard;
- best-effort usage persistence before Post upsert;
- home missed-window and mentions truncation-risk warnings;
- `post_id` upsert deduplication;
- full long-Post text from `note_tweet.text` with `text` fallback;
- returned referenced Post and author context in `raw_json._expanded`;
- returned media metadata without media download;
- explicit bounded refresh of existing content without changing `sync_state`;
- explicit confirmation-gated baseline acceptance from a validated incomplete run without an X request;
- Post, media, referenced-context, author-statistics, and manual candidate review views.
- Git-backed MVP source of truth for static reviewed knowledge, with separate evidence and capability layers;
- separate shared analytics and X Signal Finder terminology namespaces;
- source-document template with stable IDs, provenance, review status, supported claims, and limitations;
- asset catalog schema with mandatory source-ID evidence links;
- offline knowledge validation for structure, metadata, IDs, statuses, evidence links, and local references.
- documented separation of static reviewed knowledge, first-party editorial corpus, and dynamic analytical evidence, with distinct future authority and read contracts.
- 17 canonical Ethplorer Markdown articles fully reviewed with stable IDs, explicit claims and limitations, and 11 inspected managed images;
- 11 compact reviewed capabilities linked only to reviewed static evidence;
- 12 canonical Ethplorer article routes carried by source metadata and normalized offline;
- 91 derivative vocabulary triggers with static, authored, referenced-context, and exact-link provenance;
- precision-first vocabulary semantics where context-only combinations cannot create a future PASS and negative context is never a hard reject;
- exact stored first-party article URL linkage to 5 static source IDs across 8 Posts without fuzzy matching or committed per-Post data;
- complete historical Ethplorer and Binplorer first-party X import within the retrievable API window;
- one shared historical/future first-party corpus lifecycle with independent incremental checkpoints;
- original, reply, quote, and repost retention, full long-form text, lossless direct relationship sets, explicit unavailable context, and media metadata without downloads;
- bounded deduplicated completion of direct referenced Post context and content-safe corpus diagnostics.
- compact safe reasons for unavailable referenced context when X supplies a resource-specific error;
- deterministic destination URLs from stored X entities without redirect crawling or another X request;
- `first_party_x_posts.text` as the canonical downstream analysis text, with full `note_tweet.text` preferred over normal `text`.
- relational unavailable-reference reasons constrained to safe categories, with historical unknown backfill and preserved JSON provenance;
- security-invoker first-party URL and Post review views with deterministic stored URL resolution and article URL arrays.
- completed Task 004D read-only provider comparison with canonical ID, content, context, media, pagination, and spend reporting; neither trial was accepted and Official X remains production.
- confirmation-gated offline recovery planning for 11 already-paid Official X shadow pages, using production mapping, artifact hashing, canonical Post-ID deduplication, and no `sync_state` mutation;
- future Official X shadow protection with atomic page persistence, per-page partial summaries, retained partial results after HTTP 402, mandatory approved spend inputs, and dynamic page sizing near the approved boundary;
- provider-specific shadow discovery: recursive TwitterAPI.io time slicing and separate SocialData cursor plus `max_id` traversal, with repeated-progress protection and canonical Post-ID dedupe;
- zero-cost discovery and direct-ID preflight reports bound to SHA-256 approval, with explicit request/resource/cost maxima and execution blocked before provider credentials when the plan is absent, mismatched, or over cap;
- deterministic local selection and offline fixture comparison for a future approximately 50-ID provider lookup; provider direct-ID execution remains absent;
- exact-plan provider approvals covering benchmark tasks or selected IDs, provider-specific response-size contracts, TwitterAPI.io pacing without retry, collision-resistant artifact identities, and explicit raw-recall/content-completeness acceptance thresholds;

## 4. Current Data Flow

```text
X API
  -> collector
  -> PostgreSQL posts
  -> future relevance filter
  -> future Signals
  -> future Opportunity Gate
  -> future human review workflow
  -> manual publication
```

In parallel, Task 005C provides:

```text
Ethplorer/Binplorer User Posts
  -> first-party X sync
  -> PostgreSQL first_party_x_posts + first_party_x_post_references
  -> future vocabulary/style/context use
```

The X API, collector, and PostgreSQL portion exists. Runtime relevance filtering, Signals, Opportunity Gate evaluation, Opportunity creation, draft generation, and the human review workflow are not implemented. Publication remains outside the application and must be performed manually.

The reviewed Git knowledge layer now includes 17 reviewed sources, 11 capabilities, canonical article identity, and a 91-trigger derivative vocabulary. First-party X informed wording and audience context but did not establish capabilities. Task 005D.1 removed or demoted obvious broad routing noise and added compact non-authoritative negative context without changing the capability catalog. Future dynamic analytics must be queried from their upstream source with temporal scope and provenance. No runtime prefilter or dynamic analytics adapter exists yet.

## 5. Architecture Snapshot

- Python 3.11 or newer is the cross-platform runtime.
- PostgreSQL is the operational source of truth.
- PostgreSQL stores the first-party editorial corpus; Git never stores its raw X content.
- Reviewed Git content under `knowledge/` is the MVP source of truth for static reviewed knowledge.
- Supabase is the current managed PostgreSQL provider.
- Application database access uses standard `psycopg` and parameterized SQL.
- Local configuration and credentials exist only in ignored `.env` or real environment variables.
- The GitHub repository is public.
- The application does not use the Supabase Python SDK.
- MongoDB is not part of the architecture.
- GitHub Actions and scheduled execution are not implemented at the current stage.
- No knowledge content is stored canonically in PostgreSQL, embeddings, or a vector database.
- `ethereum-top-addresses-pipeline` and other dynamic analytical evidence remain upstream and are not copied into static knowledge.

## 6. Important Files

- [`AGENTS.md`](AGENTS.md) - mandatory repository and safety rules.
- [`README.md`](README.md) - project overview, setup, commands, and visible status.
- [`docs/project-spec.md`](docs/project-spec.md) - canonical product and technical behavior.
- [`docs/roadmap.md`](docs/roadmap.md) - canonical implementation order, task status, and validation records.
- [`docs/decisions.md`](docs/decisions.md) - accepted architecture and product decisions.
- [`docs/x-api-access-spike.md`](docs/x-api-access-spike.md) - Task 003 evidence, constraints, pricing, and compliance analysis.
- [`docs/x-collector.md`](docs/x-collector.md) - Stage 3 collector behavior and operating guide.
- [`docs/first-party-x-corpus.md`](docs/first-party-x-corpus.md) - Task 005C corpus authority, schema, sync, guards, and validation record.
- [`docs/x-provider-shadow-spike.md`](docs/x-provider-shadow-spike.md) - Task 004D provider contracts, cost guards, comparison semantics, and live report.
- [`knowledge/README.md`](knowledge/README.md) - Task 005A source-document, capability, import, and validation contracts.
- [`knowledge/source_documents.md`](knowledge/source_documents.md) - current source inventory and provenance index.
- [`knowledge/terminology/`](knowledge/terminology/) - separate shared analytics and project terminology.
- [`knowledge/sources/`](knowledge/sources/) - public or approved evidence documents with stable identity and provenance, plus the import template.
- [`knowledge/sources/posts/`](knowledge/sources/posts/) - canonical location for the 17 Ethplorer Markdown articles; shared local images use the flat `assets/` child directory.
- [`knowledge/assets_catalog.csv`](knowledge/assets_catalog.csv) - compact evidence-linked asset and capability catalog.
- [`knowledge/prefilter/`](knowledge/prefilter/) - derivative vocabulary contract and reviewed trigger catalog; no runtime matcher.
- [`knowledge/review_summary.md`](knowledge/review_summary.md) - public-safe Task 005D review and Task 005D.1 precision-correction record.
- [`src/x_signal_finder/knowledge.py`](src/x_signal_finder/knowledge.py) - offline knowledge validator.
- [`src/x_signal_finder/collector.py`](src/x_signal_finder/collector.py) - X Post mapping, bounded fetching, refresh behavior, and persistence orchestration.
- [`src/x_signal_finder/first_party_x.py`](src/x_signal_finder/first_party_x.py) - first-party corpus mapping, pagination, reference completion, usage, and checkpoint behavior.
- [`src/x_signal_finder/x_content.py`](src/x_signal_finder/x_content.py) - safe downstream helpers for deterministic URL resolution and unavailable-reference reasons.
- [`src/x_signal_finder/x_provider_shadow.py`](src/x_signal_finder/x_provider_shadow.py) - isolated provider adapters, provider-specific discovery, zero-cost preflight, direct-ID planning, Normalized Post contract, cost guards, and shadow comparison.
- [`src/x_signal_finder/x_shadow_recovery.py`](src/x_signal_finder/x_shadow_recovery.py) - local-only Task 004D page validation, production mapping reuse, dry-run inventory, manifest confirmation, and recovery provenance.
- [`src/x_signal_finder/x_api/`](src/x_signal_finder/x_api/) - read-only X API client, OAuth, configuration, and probe code.
- [`src/x_signal_finder/db/`](src/x_signal_finder/db/) - PostgreSQL connection, migration, checks, and repository code.
- [`migrations/`](migrations/) - ordered, checksum-tracked PostgreSQL schema migrations.
- [`knowledge/`](knowledge/) - terminology, capability catalog, and source tracking.
- [`prompts/`](prompts/) - future processing-stage prompt contracts; not executed yet.
- [`tests/`](tests/) - default synthetic tests and optional explicit integration tests.

## 7. Database Snapshot

Operational tables:

- `runs` - execution status and counters;
- `posts` - deduplicated X Posts and audit metadata;
- `sync_state` - independent source checkpoints and collection state;
- `first_party_x_posts` - permanent deduplicated Ethplorer/Binplorer editorial corpus;
- `first_party_x_post_references` - ordered direct reply, quote, and repost context with availability state and safe unavailable reason;
- `usage_events` - request and estimated-cost records;
- `signals` - future structured Signal records;
- `signal_posts` - future Signal-to-Post evidence links;
- `opportunities` - future Opportunity and reviewable artifact records;
- `human_reviews` - future human decisions and edits.

Review views:

- `posts_review` - direct links, full text source, referenced context, and media indicators;
- `author_source_stats` - preliminary stored home-author statistics;
- `author_unfollow_candidates` - preliminary keyword-based candidates for manual review only.
- `first_party_x_post_urls` - one row per deduplicated stored URL entity with deterministic destination and first-party/article flags;
- `first_party_x_posts_review` - canonical first-party text, provenance, context state, and resolved/article URL arrays for manual inspection.

The author views are not AI source-quality evaluation and never change X account state.

## 8. Commands

Activate the existing virtual environment on macOS or Linux:

```sh
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install the package in editable mode and run default tests:

```sh
python -m pip install --editable ".[dev]"
python -m pytest
```

Validate the Git-backed knowledge base offline:

```sh
python -m x_signal_finder knowledge validate
```

Inspect or explicitly migrate PostgreSQL:

```sh
python -m x_signal_finder db doctor
python -m x_signal_finder db migrate
```

Run bounded collection explicitly:

```sh
python -m x_signal_finder collect --source home --max-pages 1 --max-results 20
python -m x_signal_finder collect --source mentions --max-pages 1 --max-results 20
python -m x_signal_finder collect --source both --max-pages 5 --max-results 100 --max-estimated-cost-usd 1.00
python -m x_signal_finder collect --source home --max-pages 1 --max-results 20 --max-primary-posts-total 20 --max-estimated-cost-usd 0.15
python -m x_signal_finder collect --source home --max-pages 1 --max-results 20 --refresh-existing
python -m x_signal_finder collect accept-baseline --source home --run-id RUN_ID
python -m x_signal_finder collect accept-baseline --source home --run-id RUN_ID --confirm-skip-older-posts
python -m x_signal_finder first-party-x sync --source ethplorer
python -m x_signal_finder first-party-x sync --source binplorer
python -m x_signal_finder first-party-x sync --source both
```

These commands read required values from local environment configuration. Never put secret values in command examples or documentation.

## 9. Live Validation Record

- OAuth 2.0 PKCE authorization and token refresh succeeded live.
- Home timeline and direct mentions requests returned HTTP 200.
- Task 004A fetched 21 home Posts across two requests, excluded 4 simple reposts, stored 17 unique home rows, and completed an empty mentions request. Its recorded estimate was 21 X Post Reads and $0.105.
- Task 004B applied migration 002, validated complete long-Post text, referenced context, video metadata, review flags, preserved first-seen values, and unchanged checkpoint state during refresh.
- Task 004B live validation used 78 X Post Reads with an estimated cost of $0.390 across three bounded attempts.
- Task 004C bounded validation received 20 primary and 17 expanded Posts, counted 30 distinct Post resources, recorded a $0.150 estimate, saved 18 Posts after repost exclusion, returned incomplete, and preserved the home checkpoint.
- Task 004C full guarded validation received 194 primary and 113 expanded Posts over two home requests, counted 272 distinct Post resources, recorded a $1.360 estimate, saved 152 Posts including 134 new rows after repost exclusion, and correctly stopped incomplete at the cost guard. Mentions was not requested because the run guard was exhausted.
- Task 004C.1 accepted `2085449523904778414` as the explicit home baseline from the incomplete guarded run. Acceptance used PostgreSQL only, produced no X request, did not create or change Posts, and retained audit metadata.
- The single cheap incremental validation from that baseline received 19 primary and 10 expanded Posts, counted 29 distinct resources, saved 13 new Posts after 6 repost exclusions, estimated $0.145, and correctly left the checkpoint unchanged because the explicit one-page limit made the source incomplete.
- Across the two Task 004C guarded runs and the final cheap validation, estimated usage was 331 distinct Post resources and $1.655. Developer Console billing remains unreconciled.
- The pre-recovery Stage 3 database check found 214 Post rows, 214 distinct `post_id` values, and zero duplicate groups. The home checkpoint is the accepted baseline `2085449523904778414`.
- PostgreSQL 17.6 was healthy with migrations 1 and 2 current, no pending migrations, and operational-table RLS intact.
- The Task 005D knowledge inventory contains 17 reviewed sources, 11 reviewed capabilities, 12 canonical article routes, and 76 vocabulary triggers. All 11 managed informative images were inspected. The validator checks evidence authority, routes, vocabulary references, duplicates, and managed images without PostgreSQL, network requests, or model calls.
- The 2026-08-10 Task 005A amendment documents three knowledge source classes and future import/read contracts only. It adds no X corpus data, importer, analytics adapter, metric retrieval, capability, database change, or runtime integration.
- The 2026-08-11 first-party X inventory made exactly two `GET /2/users/by/username/{username}` requests for Ethplorer and Binplorer with only `created_at` and `public_metrics` requested. It retrieved no Posts, timelines, search results, expansions, or raw response storage. The estimated standard User Read cost was $0.020 total; Owned Read pricing does not apply to User Lookup. Developer Console billing remains unreconciled.
- Task 004D was recorded on 2026-08-14 as documentation-only Deferred optimization. Knowledge validation passed for 17 sources and 0 assets with no network or model calls; the default suite passed with 108 tests and 4 external tests skipped. No adapter, provider purchase, X request, shadow run, collector change, database change, or checkpoint change occurred.
- Task 005C applied migration 003 and completed a bounded historical sync for both first-party accounts. Current inventory snapshots are Ethplorer 352 and Binplorer 39; retrievable corpus counts are 339 and 39 respectively.
- Task 005C stored 378 rows with 378 distinct Post IDs and zero duplicate groups. Ethplorer types are 156 original, 121 reply, 24 quote, and 38 repost; Binplorer types are 14 original, 11 reply, 2 quote, and 12 repost.
- The corpus has 187 available and 17 unavailable direct relationship contexts. The successful historical run returned 198 unique media resources across the two source scopes and downloaded no media.
- The successful historical run made 8 requests and recorded a `$2.650` estimate. An earlier safe validation attempt made 5 requests and recorded `$0.905` while exposing overly strict partial-resource classification; it advanced no checkpoint and its saved rows were deduplicated by the corrected run. Total Task 005C live validation therefore recorded 15 requests and `$3.555` estimated cost including the final repeat.
- The repeat incremental run made 2 timeline requests, returned zero Posts, recorded `$0.000` estimated Post-resource cost, and preserved checkpoints `2080369149331558445` for Ethplorer and `2077741562402939325` for Binplorer.
- PostgreSQL 17.6 is healthy with migrations 1 through 3 current, no pending migrations, and RLS intact. The separate incoming table remains 214 rows with 214 distinct IDs.
- Task 005C.1 corrected estimated usage accounting across Post, User, and Media resources and changed the first-party cost guard to use their conservative total. Historical estimates were not retroactively reconstructed.
- Task 005C.1 validated deterministic URLs against stored entities only: 232 Posts contain 348 deduplicated URL entities, 343 have `expanded_url`, 62 have `unwound_url`, 4 remain `t.co`-only, and 103 resolve to Ethplorer or Binplorer sites.
- Task 005C.1 preserved 378 distinct first-party rows, 214 distinct incoming rows, both first-party checkpoints, migrations 1 through 3, and RLS. It made no X request.
- The X Developer Console balance observed on 2026-08-14 was USD 5.12. This is a forward reconciliation baseline only, not evidence of Task 005C actual cost; future approved live validation should record balance before and after the run where practical.
- Task 004D first received 11 successful paid Official X pages containing 1,082 primary Posts; the twelfth request returned HTTP 402. The owner reported 1,133 Post Reads and $5.665. The original runner lost the in-memory result but retained all 11 raw pages locally, so the later comparison reused a stored 192-Post benchmark. TwitterAPI.io matched 25 IDs at 13.02% recall and 96.0% exact matched text for $0.09975 actual spend; SocialData matched 11 IDs at 5.73% recall and 100% exact matched text for a conservative $0.0966 estimate. Both third-party runs were incomplete and neither provider was accepted.
- Task 004D DB verification preserved 214 `posts`, 378 `first_party_x_posts`, four `sync_state` rows, and the exact pre-run `sync_state` fingerprint.
- The 2026-08-17 recovery dry-run made zero external calls and zero database writes. It validated all 1,082 primary Posts, excluded 256 simple reposts, found zero existing duplicates, and prepared 826 unique new Posts under manifest `85a70f069262451a275f626209ed3836e4eb2fcdfa6b93cb20a94d221566b00d`.
- After explicit owner approval, recovery run `029a02d5-28e3-44b2-aa19-db027c529c9c` atomically inserted all 826 Posts through production mapping. `posts` now has 1,040 rows and 1,040 distinct IDs; all 826 recovered rows retain manifest provenance. The run is `completed_with_warnings` with source state `incomplete_due_to_credit` and recovery state `recovered`.
- Recovery usage records the historical 11 successful paid requests, 1,133 owner-reported Post Reads, and $5.665 reported cost. External requests during recovery were zero. All four `sync_state` rows and fingerprint `575476c6591871422c1249dc68f56f28507ff1d13792778f36b13a07ef6b5454` were identical immediately before and after apply.
- Task 004D.2 made zero Official X, TwitterAPI.io, or SocialData calls. Its stored 24-hour discovery plan found 826 Posts from 132 authors; the initial 132 requests exceed the unchanged $0.10 cap for both providers, so execution is deterministically blocked. Estimated initial costs are $0.39600 for TwitterAPI.io and $0.5280 for SocialData.
- The zero-cost 50-ID plan selected 39 long Posts, 23 replies, 25 quotes, 48 Posts with referenced context, and 38 with media. Under a $0.02 planning cap, TwitterAPI.io estimates $0.00750 with a $0.00900 conservative maximum and SocialData estimates $0.0100 with a $0.0120 conservative maximum. Provider direct-ID endpoints were not called and are not implemented.
- Task 004D.2.1 recalculated the exact offline plans from the retained Official X artifacts. Discovery digest `c4e39d9ef46889b66c2e3d6de8bf383d035831fc9fa874bb395c72b5f81e9ede` is blocked because 132 initial author requests exceed both approved request caps. The exact 50-ID digest is `a31b0214801f8d17be2cefb7e79aaefcfd1d3f09ff873110c9abc0f5b3d38a32`; it remains planning-only and unapproved.
- Task 004D.2.1 validation passed 31 targeted offline tests and the full suite with 197 passed and 5 external tests skipped; compileall and diff checks passed. No provider request, database write, migration, or `sync_state` code path was executed.
- A mandatory cost-preflight rule now blocks every future usage-based external call until its provider, endpoint, purpose, expected requests and resources, price, expected cost, conservative maximum, and enforcing hard guard are shown and explicitly approved. Local data must be reused before purchasing equivalent data, and provider tests start with approximately 20 to 50 Posts or the smallest sufficient window.
- Task 005C.2 applied migration 004 without an X request. All 17 historical unavailable references now have relational reason `unknown`; available references have NULL. The two security-invoker review views expose 348 URL rows across 232 Posts, including 81 Ethplorer, 22 Binplorer, and 8 deterministic article URLs.
- The known Rich List destination `https://ethplorer.io/posts/ethereum-rich-list-by-aggregated-usd-holdings-part-1` is visible in both first-party review views from stored entities only and resolves exactly to its reviewed static source ID.
- Task 005D analysed all 378 first-party Posts as 170 originals, 132 replies, 26 quotes, and 50 reposts, with 187 available and 17 unavailable references. Exact article linkage covered 8 Posts and 5 reviewed source IDs.
- Task 005D preserved 378 distinct first-party Posts, 1,040 distinct incoming Posts, 4 migrations, 4 `sync_state` rows, and checkpoint fingerprint `410535ed27aa2a464bc63953df0aa318`. PostgreSQL 17.6 is healthy, migrations are current, RLS is intact, 184 default tests passed with 5 external tests skipped, 3 PostgreSQL integration tests passed, and offline knowledge validation passed for 17 sources, 11 assets, 12 routes, and 76 triggers.
- Task 005D.1 changed the derivative vocabulary from 76 to 91 rows while preserving all 11 capabilities. It removed 2 broad rows, demoted 6 positive rows, added 17 precise or compact negative-context rows, and left 53 positive, 17 context-only, and 21 negative-context rows. Offline validation passed for 17 sources, 11 assets, 12 routes, and 91 triggers; 50 focused tests and 198 default tests passed with 5 external tests skipped. The local PostgreSQL review was read-only and made no external call.

These are validation estimates and observations, not a Developer Console billing statement. No raw Post text or raw X response belongs in this file.

## 10. Known Limitations

- The collector is manually invoked and bounded by explicit page and cost guards.
- Full historical backfill and automatic missed-window recovery are not implemented.
- X Developer Console billing remains unreconciled; stored cost values are estimates, and the USD 5.12 balance observed on 2026-08-14 is only a forward baseline.
- No LLM calls or runtime relevance filter exist.
- The knowledge base is not integrated into runtime processing.
- Reviewed product evidence is historical in places and does not prove current availability, pricing, limits, or analytical values.
- Reviewed static Binplorer capability evidence is missing; Binplorer and BNB Chain routing terms remain candidate or contextual.
- PostgreSQL, embeddings, vector search, crawling, and semantic retrieval are not part of the knowledge architecture.
- Production provider-independent X ingestion is not implemented. Official X remains the production source. Task 004D implements only an isolated local shadow comparison and no provider switch, fallback, scheduler, monitor, webhook, or checkpoint integration.
- Task 004D did not produce a qualifying third-party provider. Its historical stored benchmark and incomplete trial runs limit provider-quality conclusions; Official X remains production.
- Task 004D.2 corrects discovery methodology but supplies no new live provider-quality evidence. No paid provider test is approved.
- Task 004D.2.1 does not treat SocialData's expected 20-result page as a documented maximum or hard dollar guarantee. No paid provider test is approved.
- The vocabulary is a derivative artifact only; no runtime matching, scoring, status mutation, style model, or LLM analysis exists.
- The dynamic analytics adapter is not implemented; `ethereum-top-addresses-pipeline` remains separate and no snapshot is copied into this repository.
- Signals and Opportunities have schema placeholders but no runtime creation pipeline.
- Telegram delivery is not implemented.
- No scheduler or GitHub Actions workflow exists.
- Automatic publication is not implemented and remains prohibited.
- Current author candidates use a coarse keyword heuristic rather than AI relevance decisions.
- Current author keyword statistics do not yet provide the future separate main, referenced, and combined relevance metrics.
- Automatic unfollow and X write access are prohibited.
- Compliance revalidation and deletion automation are deferred.

## 11. Next Intended Work

The next intended work is Task 005E - Dynamic Analytics Adapter. It must dynamically discover the latest appropriate `ethereum-top-addresses-pipeline` comparison, verify exact values against structured files from the same comparison, and preserve upstream commit, dates, metric name, scope, entity, source path, and caveats.

Hard-coded dated analytics paths, copied dynamic datasets, private or licensed source text, unsupported capabilities, crawling, vector storage, LLM calls, Task 006 relevance filtering, Signals, Opportunities, delivery automation, and publication remain outside Task 005E. Do not begin it until its explicit specification is provided.

## 12. Deferred and Planned Work

- Historical backfill and automatic missed-window recovery.
- A separate future SocialData experiment may evaluate grouped Search Query Monitors feeding webhook events into the Normalized Post boundary, but Task 004D evidence does not promote it. It must not create approximately 370 User Monitors or use keyword pre-filtering in place of project relevance logic.
- Future integration of the implemented first-party incremental sync into the eventual normal pipeline orchestration.
- Task 005E on-demand adapter for dated, scoped, provenance-rich dynamic evidence from `ethereum-top-addresses-pipeline`; it is next, not yet implemented.
- Task 006B - Author Quality Monitoring and Follow-list Hygiene, after Task 006 produces real AI relevance decisions. It must combine main and referenced context, keep separate main, referenced, and combined metrics, and produce a manual review queue only.
- X Content compliance revalidation, removal, and deletion automation.
- A future database-hosting decision if the current Supabase arrangement is reconsidered.
- GitHub Actions and another scheduler.
- Automatic publication remains prohibited and would require an explicit specification and architecture decision change.

## 13. Safety

- The repository is public. Treat every committed file as publicly visible.
- Never commit secrets, credentials, `.env`, database URLs, raw operational X content, runtime databases, dumps, or private and licensed exports.
- Never print access tokens, refresh tokens, authorization headers, or raw API response bodies.
- Before any usage-based or potentially paid external call, perform a zero-cost preflight, show the exact input identity, request cap, expected and conservative spend, documented response maximum when available, and enforcing guard. Never label an unbounded response estimate as a technical hard dollar cap. Wait for explicit approval of the exact plan digest.
- Do not purchase data already available in PostgreSQL or approved local artifacts. Start external quality tests with approximately 20 to 50 Posts or the smallest sufficient window, and report actual usage and spend after every approved run.
- Do not invent Ethplorer capabilities. Use only reviewed knowledge-base evidence.
- Do not treat first-party editorial history or dynamic metrics as capability proof without reviewed supporting static evidence.
- Keep verified facts, inference, and unresolved uncertainty distinct.
- Do not start the next stage or implement a planned task without an explicit task specification.
- Do not add X write access, automatic unfollow, scheduling, or automatic publication without explicit approved changes.
