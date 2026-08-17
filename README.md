# Ethplorer X Signal Finder

Ethplorer X Signal Finder is an AI-assisted X intelligence pipeline foundation. It is intended to find rare discussions with a real information gap that Ethplorer can close naturally and credibly using documented products, data, analytics, infrastructure, expertise, or business development capabilities.

It is not a generic crypto-news aggregator, an automatic publishing bot, or a mechanism for forcing Ethplorer into unrelated conversations.

> Start here for current project state: [`HANDOFF.md`](HANDOFF.md)

## Current Status

The durable PostgreSQL storage foundation is implemented and validated against the real Supabase database. PostgreSQL is the operational source of truth, with Supabase selected as the initial managed provider. Application code uses the standard PostgreSQL protocol through `psycopg` and does not use the Supabase Python SDK.

Stage 2 is complete with a `constrained-go` decision, and Stage 3 collection is complete. Stage 4 is In Progress. Task 005A defines a Git-backed static knowledge source of truth, provenance-preserving and normalization-aware source-document contract, evidence-linked asset catalog, and offline validator. It also separates static reviewed knowledge from the first-party Ethplorer/Binplorer X editorial corpus and dynamic analytical evidence such as `ethereum-top-addresses-pipeline`. Task 005C implements the first-party corpus in PostgreSQL as a permanent, continuously updated record of actual public Posts. Editorial history may guide style and prior positioning but cannot prove capabilities. Dynamic metrics remain upstream and must later be queried with dates, scope, metric identity, and provenance. The dynamic analytics adapter is not implemented.

The existing knowledge inventory contains two separate terminology documents and 17 complete Ethplorer Markdown articles in their canonical `knowledge/sources/posts/` location. Five user-provided DOCX sources were converted to normalized Markdown with 11 deduplicated local image assets, then removed after structural, visual, and text-completeness checks. All articles have stable source metadata and remain pending substantive review. No capability rows exist. Task 005D will handle Reviewed Knowledge + Unified Prefilter Vocabulary under a separate explicit specification and may extract only evidence-supported capabilities, limitations, topics, and asset links.

The manually started collector uses OAuth refresh, fetches home or `@Ethplorer` mentions, excludes simple reposts from home, and upserts Posts plus independent source checkpoints into PostgreSQL. It preserves long-form `note_tweet.text`, returned referenced Post context, and returned media metadata without downloading media. It follows incremental pagination until completion or an explicit page, primary-Post, cost, partial-response, or error guard. Incomplete work saves available Posts and estimated usage but does not advance its source checkpoint. An explicit confirmation-gated baseline action can accept the newest first-page ID from a validated incomplete run without making another X request.

Task 004D provides a separate shadow CLI for one bounded Official X, TwitterAPI.io, and SocialData quality and cost comparison. It uses an internal Normalized Post comparison contract, writes raw responses only under ignored local runtime storage, and never changes the production collector. Its normal shadow run does not write PostgreSQL. A separate confirmation-gated offline command can recover the 11 already-paid Official X pages retained before HTTP 402 through the production Post mapping without external calls or `sync_state` changes. LLM integration, Telegram, and publication are not implemented. All publication remains a mandatory human action.

Every future usage-based external call requires a zero-cost preflight and explicit approval of a technically enforced maximum spend. The preflight must identify the provider, endpoint, purpose, expected requests and billable resources, unit price, expected cost, conservative maximum, and hard guard. Existing PostgreSQL data or approved local artifacts must be reused before equivalent data is purchased. Provider quality tests begin with approximately 20 to 50 Posts or the smallest sufficient window; a larger comparison requires a new preflight and approval.

The repository remains public during the MVP. Public visibility does not change the existing prohibition on committing credentials, local `.env` files, raw operational X content, runtime database data or dumps, private or licensed exports, or confidential internal documents.

## Implementation Status

- Stage 0 - Repository Bootstrap - Completed
- Stage 1 - Durable Storage Foundation - Completed
- Stage 2 - X API Access Spike - Completed
- Stage 3 - X Collection Pipeline - Completed
- Stage 4 - Minimum Knowledge Base - In Progress
- Completed bounded exception - Task 004D - X Provider Shadow Quality Spike
- Last completed corrective task - Task 004D Recovery Amendment
- Last completed MVP product task - Task 005C.2 - First-Party X Reference Reasons + URL Review Views
- Next MVP task - Task 005D - Reviewed Knowledge + Unified Prefilter Vocabulary - Planned, awaiting its explicit task specification

See the canonical [implementation roadmap](docs/roadmap.md), [product and technical specification](docs/project-spec.md), and [architecture decision log](docs/decisions.md).

## Repository Structure

```text
.
|-- AGENTS.md
|-- docs/                      # Canonical specification and decisions
|-- knowledge/                 # Git-backed terminology, evidence sources, and asset catalog
|-- migrations/                # Reviewable PostgreSQL migrations
|-- prompts/                   # Processing-stage prompt templates
|-- src/x_signal_finder/       # Cross-platform package, CLI, and storage code
|-- tests/                     # Unit and optional PostgreSQL integration tests
`-- data/
    `-- exports/               # Ignored analytical exports
```

Git does not store runtime databases, database dumps, raw X content, or operational exports.

## Setup

Python 3.11 or newer is required.

macOS or Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --editable ".[dev]"
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --editable ".[dev]"
```

## Database Configuration

Copy `.env.example` to `.env` for local development and set:

```dotenv
DATABASE_URL=postgresql://...
```

`.env` is local and ignored by Git. Never commit the database password or paste it into documentation, issues, or chat. Real environment variables override `.env`.

For Supabase:

1. Create a Supabase project and choose its database password.
2. Open the project's connection dialog and copy a PostgreSQL connection string appropriate for the execution environment.
3. Replace the password placeholder locally and save the full value only as `DATABASE_URL` in `.env`.
4. Run the explicit migration and validation commands below.

The MVP uses a protected PostgreSQL connection. It does not use anon keys, authenticated roles, service-role keys, or public API policies. RLS is enabled on operational tables with no anonymous or authenticated public policies.

## CLI

General commands:

```sh
python -m x_signal_finder --help
python -m x_signal_finder status
```

Offline knowledge validation:

```sh
python -m x_signal_finder knowledge validate
```

The knowledge validator reads local Markdown and CSV only. It checks structure, metadata, unique IDs, review statuses, evidence links, and local references without network access, database access, or LLM calls. See the [knowledge architecture and import contract](knowledge/README.md).

X API access-spike diagnostics:

```sh
python -m x_signal_finder x-api --help
python -m x_signal_finder x-api probe home --user-id USER_ID --max-pages 2
python -m x_signal_finder x-api probe mentions --user-id USER_ID --max-pages 2
python -m x_signal_finder x-api oauth-probe --source both --max-pages 2
```

These commands must be invoked explicitly. They do not write to PostgreSQL or disk and never print Post text, raw API responses, or credentials. The OAuth command uses one temporary localhost callback, validates PKCE and refresh in memory, and stops the callback server before exiting.

Stage 3 collector setup and incremental runs:

```sh
python -m x_signal_finder x-api oauth-setup
python -m x_signal_finder collect --source home
python -m x_signal_finder collect --source mentions
python -m x_signal_finder collect --source both
python -m x_signal_finder collect --source home --max-pages 1 --max-results 20 --max-primary-posts-total 20 --max-estimated-cost-usd 0.15
python -m x_signal_finder collect --source home --max-pages 1 --max-results 20 --refresh-existing
python -m x_signal_finder collect accept-baseline --source home --run-id RUN_ID
python -m x_signal_finder collect accept-baseline --source home --run-id RUN_ID --confirm-skip-older-posts
```

`oauth-setup` stores only the refresh token in the ignored local `.env`. Every collector run refreshes the access token in memory and safely replaces a rotated refresh token in `.env`. Collector defaults are `--max-pages 5`, `--max-results 100`, `--max-estimated-cost-usd 1.00`, no total primary-Post limit, `--max-attempts 3`, and `--max-retry-wait-seconds 60`. A total primary limit applies to home then mentions across the whole run. Expanded Posts count toward the estimate, and the cost guard can overshoot by one completed page and its expansions. Collector output contains counts, checkpoints, IDs, estimated X cost, and warnings only. It never prints Post text, raw JSON, or credentials. `--refresh-existing` is explicit and bounded: it omits `since_id`, anchors the window at the stored checkpoint with `until_id`, refreshes returned rows, and does not alter the operational checkpoint. `accept-baseline` is also explicit: without the confirmation flag it prints a safe summary and refuses to mutate state; with confirmation it updates only the selected source checkpoint and audit metadata, making no X request and creating no Posts. See [the Stage 3 collector guide](docs/x-collector.md) for checkpoint behavior and Supabase review views.

First-party editorial corpus synchronization:

```sh
python -m x_signal_finder first-party-x sync --source ethplorer
python -m x_signal_finder first-party-x sync --source binplorer
python -m x_signal_finder first-party-x sync --source both
```

The same tables contain historical and future Ethplorer/Binplorer Posts. Initial sync paginates the retrievable User Posts window; later runs use independent `since_id` checkpoints. Replies, quotes, and reposts are retained. Direct referenced context is completed in bounded deduplicated batches when needed, and missing context remains explicitly unavailable with a safe relational reason and its JSON audit representation. `first_party_x_posts.text` is the canonical analysis field: it uses `note_tweet.text` when available and normal text only as fallback. The security-invoker views `first_party_x_post_urls` and `first_party_x_posts_review` expose deterministic stored destinations and article URLs without redirect crawling. They do not map an article URL to a static knowledge source ID. Returned Post, User, and Media resource classes are counted and costed separately, and the guard uses their conservative estimated total. No media is downloaded, no X write scope is requested, and diagnostics contain no Post text. See [the first-party corpus operating guide](docs/first-party-x-corpus.md).

Task 004D provider shadow spike:

```sh
python -m x_signal_finder x-provider-shadow run \
  --hours 24 \
  --max-provider-spend-usd 0.10 \
  --approved-max-official-spend-usd APPROVED_MAX \
  --official-worst-case-cost-per-primary-usd PREFLIGHT_BOUND
```

The command requires local provider keys, benchmarks one fixed home-timeline window, searches only authors active in that benchmark, compares canonical X Post IDs and normalized content quality, and stores raw responses only under ignored `data/runtime/`. It never writes PostgreSQL or production checkpoints. A fresh Official X benchmark additionally requires `--approved-max-official-spend-usd` and `--official-worst-case-cost-per-primary-usd`; the page size is reduced near the approved boundary and successful pages remain durable if a later request fails. The completed trial accepted neither provider: TwitterAPI.io reached 13.02% recall with 96.0% exact matched text at $0.09975 actual spend, while SocialData reached 5.73% recall with 100% exact matched text at $0.0966 estimated spend. Both runs were incomplete, so the low recall is not a definitive quality failure. Official X remains production.

Offline recovery dry-run for the retained paid pages:

```sh
python -m x_signal_finder x-provider-shadow recover-official \
  --artifact-dir data/runtime/x-provider-shadow/20260814T205734Z/official_x
```

The dry-run validates and maps local files, reads only existing PostgreSQL IDs, forces transaction rollback, makes no X request, and prints the artifact manifest required for a later `--apply`. The approved 2026-08-17 recovery inserted 826 Posts atomically, taking `posts` to 1,040 distinct rows, and preserved the exact four-row `sync_state` fingerprint. It made no X or third-party request. Any future recovery apply remains permitted only after explicit approval of its exact dry-run manifest. See [the Task 004D operating and report document](docs/x-provider-shadow-spike.md).

Database commands:

```sh
python -m x_signal_finder db doctor
python -m x_signal_finder db migrate
python -m x_signal_finder db status
python -m x_signal_finder db smoke-test
```

`db doctor` and `db status` are read-only. `db migrate` is the only command that applies schema migrations. Migrations never run automatically during normal pipeline execution. `db smoke-test` creates clearly synthetic records inside one transaction, rolls it back, and verifies that no synthetic rows remain.

X API spike commands and one-time OAuth setup are documented in [the X API access spike report](docs/x-api-access-spike.md). Probe commands are diagnostic only, never write to PostgreSQL, and never persist API responses.

All database commands return a non-zero exit code on failure and redact PostgreSQL connection strings from output.

## Tests

Default tests require no credentials and make no external API calls:

```sh
python -m pytest
```

Optional PostgreSQL integration tests use only `TEST_DATABASE_URL` and never fall back to `DATABASE_URL`:

```sh
python -m pytest -m integration
```

## Current Limitations

- No automatic historical backfill or production missed-window recovery
- Most X billing remains unreconciled; the owner separately reported 1,133 Post Reads and $5.665 for the failed fresh Task 004D attempt
- Task 004D accepted no third-party provider; Official X remains production and the incomplete trials do not establish definitive third-party quality
- Mentions pagination was not observed live because the validated response was empty
- No LLM calls or prompt execution
- The 17 Ethplorer articles are inventoried but not yet reviewed for capabilities, limitations, topics, products, networks, or asset links
- No knowledge database, embeddings, vector search, crawler, or runtime knowledge integration
- The first-party X editorial corpus is collected, but no vocabulary, style, or LLM analysis is derived from it yet
- No dynamic analytics adapter; `ethereum-top-addresses-pipeline` remains in its own repository
- No context enrichment from external sources
- No Telegram delivery
- No automatic image generation
- No GitHub Actions
- No automatic publication
- No automatic unfollow or X write access
- Author unfollow candidates currently use a coarse keyword heuristic
- Full author-quality evaluation is planned in Task 006B after real AI relevance decisions exist
- Automatic unfollow remains prohibited; every follow-list change is a manual human action in X
- No media download, audio extraction, speech-to-text, or image analysis

Before changing architecture or product behavior, read `docs/project-spec.md`.
