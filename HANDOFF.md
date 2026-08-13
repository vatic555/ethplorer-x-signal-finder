# Ethplorer X Signal Finder - Handoff

Last updated: 2026-08-13

Repository HEAD: `29db23781fb5dca3373198477b19ea43303124b3` at article-inventory validation; a HANDOFF-only metadata commit follows it

Validated commit: `29db23781fb5dca3373198477b19ea43303124b3`

Validated implementation commit: `29db23781fb5dca3373198477b19ea43303124b3` for the Task 005A canonical article inventory

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
- Current task: Task 005A - Knowledge Architecture + Import Contract - Completed after validation.
- Last completed task: Task 005A - Knowledge Architecture + Import Contract.
- Next task: Task 005B - Ethplorer Knowledge Import. It is Planned and must wait for its explicit task specification.
- Roadmap status: Stages 0 through 3 are Completed; Stage 4 is In Progress; Stages 5 through 7 are Planned; Stage 8 automation is Deferred.
- Task 006B - Author Quality Monitoring and Follow-list Hygiene is Planned after Task 006 produces real AI relevance decisions. It is not current work.

## 3. What Works Now

The following capabilities have been implemented and validated:

- protected PostgreSQL storage hosted in Supabase;
- checksum-tracked migrations 001 and 002;
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
- distinct primary and expanded Post-resource cost accounting;
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
- 12 canonical Ethplorer Markdown articles inventoried in place with stable IDs and `ethplorer_article` source type, without capability extraction.

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

The X API, collector, and PostgreSQL portion exists. Runtime relevance filtering, Signals, Opportunity Gate evaluation, Opportunity creation, draft generation, and the human review workflow are not implemented. Publication remains outside the application and must be performed manually.

The Git-backed static knowledge architecture and 12-article Ethplorer source inventory exist, but Task 005B has not extracted reviewed capabilities or asset rows. A future first-party X corpus may inform style, reaction patterns, and prior public positioning only. Future dynamic analytics must be queried from their upstream source with temporal scope and provenance. Neither adapter exists yet.

## 5. Architecture Snapshot

- Python 3.11 or newer is the cross-platform runtime.
- PostgreSQL is the operational source of truth.
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
- [`knowledge/README.md`](knowledge/README.md) - Task 005A source-document, capability, import, and validation contracts.
- [`knowledge/source_documents.md`](knowledge/source_documents.md) - current source inventory and provenance index.
- [`knowledge/terminology/`](knowledge/terminology/) - separate shared analytics and project terminology.
- [`knowledge/sources/`](knowledge/sources/) - preserved public or approved evidence documents and import template.
- [`knowledge/sources/posts/`](knowledge/sources/posts/) - canonical location for the 12 preserved Ethplorer Markdown articles.
- [`knowledge/assets_catalog.csv`](knowledge/assets_catalog.csv) - compact evidence-linked asset and capability catalog.
- [`src/x_signal_finder/knowledge.py`](src/x_signal_finder/knowledge.py) - offline knowledge validator.
- [`src/x_signal_finder/collector.py`](src/x_signal_finder/collector.py) - X Post mapping, bounded fetching, refresh behavior, and persistence orchestration.
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
- `usage_events` - request and estimated-cost records;
- `signals` - future structured Signal records;
- `signal_posts` - future Signal-to-Post evidence links;
- `opportunities` - future Opportunity and reviewable artifact records;
- `human_reviews` - future human decisions and edits.

Review views:

- `posts_review` - direct links, full text source, referenced context, and media indicators;
- `author_source_stats` - preliminary stored home-author statistics;
- `author_unfollow_candidates` - preliminary keyword-based candidates for manual review only.

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
- Latest database check found 214 Post rows, 214 distinct `post_id` values, and zero duplicate groups. The home checkpoint is the accepted baseline `2085449523904778414`.
- PostgreSQL 17.6 was healthy with migrations 1 and 2 current, no pending migrations, and operational-table RLS intact.
- Latest default suite: 105 passed with 4 external tests skipped. Explicit PostgreSQL integration suite: 2 passed during the unchanged Stage 3 database validation.
- Task 005A inventory found two terminology documents, 12 canonical Ethplorer articles, and zero asset or capability rows. All articles were read in full and have unique H1 titles, substantial coherent bodies, distinct content, stable pending metadata, and exactly preserved bodies. The source contract, catalog evidence rules, template, local-link checks, and offline CLI validation use no network requests, database access, or model calls.
- The 2026-08-10 Task 005A amendment documents three knowledge source classes and future import/read contracts only. It adds no X corpus data, importer, analytics adapter, metric retrieval, capability, database change, or runtime integration.
- The 2026-08-11 first-party X inventory made exactly two `GET /2/users/by/username/{username}` requests for Ethplorer and Binplorer with only `created_at` and `public_metrics` requested. It retrieved no Posts, timelines, search results, expansions, or raw response storage. The estimated standard User Read cost was $0.020 total; Owned Read pricing does not apply to User Lookup. Developer Console billing remains unreconciled.

These are validation estimates and observations, not a Developer Console billing statement. No raw Post text or raw X response belongs in this file.

## 10. Known Limitations

- The collector is manually invoked and bounded by explicit page and cost guards.
- Full historical backfill and automatic missed-window recovery are not implemented.
- X Developer Console billing remains unreconciled; stored cost values are estimates.
- No LLM calls or runtime relevance filter exist.
- The knowledge base is not integrated into runtime processing.
- The 12 canonical Ethplorer articles are inventoried but remain pending substantive review; no evidence-backed capability row exists yet.
- PostgreSQL, embeddings, vector search, crawling, and semantic retrieval are not part of the knowledge architecture.
- The first-party Ethplorer/Binplorer X editorial corpus importer and compliant corpus storage are not implemented.
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

The next intended work is Task 005B - Ethplorer Knowledge Import. Its completion criterion is substantive review of the 12 inventoried articles and extraction of only the capabilities, limitations, topics, products, networks, and asset links directly supported by those source IDs.

Private or licensed source text, unsupported capabilities, crawling, database or vector storage, runtime knowledge integration, LLM calls, Task 006 relevance filtering, Signals, Opportunities, delivery automation, and publication are outside Task 005B unless its explicit specification says otherwise within canonical project boundaries.

## 12. Deferred and Planned Work

- Historical backfill and automatic missed-window recovery.
- A first-party Ethplorer/Binplorer X editorial corpus importer and compliant read contract implementation.
- An on-demand adapter for dated, scoped, provenance-rich dynamic evidence from `ethereum-top-addresses-pipeline` and other approved analytical sources.
- Task 006B - Author Quality Monitoring and Follow-list Hygiene, after Task 006 produces real AI relevance decisions. It must combine main and referenced context, keep separate main, referenced, and combined metrics, and produce a manual review queue only.
- X Content compliance revalidation, removal, and deletion automation.
- A future database-hosting decision if the current Supabase arrangement is reconsidered.
- GitHub Actions and another scheduler.
- Automatic publication remains prohibited and would require an explicit specification and architecture decision change.

## 13. Safety

- The repository is public. Treat every committed file as publicly visible.
- Never commit secrets, credentials, `.env`, database URLs, raw operational X content, runtime databases, dumps, or private and licensed exports.
- Never print access tokens, refresh tokens, authorization headers, or raw API response bodies.
- Do not invent Ethplorer capabilities. Use only reviewed knowledge-base evidence.
- Do not treat first-party editorial history or dynamic metrics as capability proof without reviewed supporting static evidence.
- Keep verified facts, inference, and unresolved uncertainty distinct.
- Do not start the next stage or implement a planned task without an explicit task specification.
- Do not add X write access, automatic unfollow, scheduling, or automatic publication without explicit approved changes.
