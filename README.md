# Ethplorer X Signal Finder

Ethplorer X Signal Finder is an AI-assisted X intelligence pipeline foundation. It is intended to find rare discussions with a real information gap that Ethplorer can close naturally and credibly using documented products, data, analytics, infrastructure, expertise, or business development capabilities.

It is not a generic crypto-news aggregator, an automatic publishing bot, or a mechanism for forcing Ethplorer into unrelated conversations.

> Start here for current project state: [`HANDOFF.md`](HANDOFF.md)

## Current Status

The durable PostgreSQL storage foundation is implemented and validated against the real Supabase database. PostgreSQL is the operational source of truth, with Supabase selected as the initial managed provider. Application code uses the standard PostgreSQL protocol through `psycopg` and does not use the Supabase Python SDK.

Stage 2 is complete with a `constrained-go` decision. Stage 3 is complete. Tasks 004A through 004C.1 are implemented and live-validated. The manually started collector uses OAuth refresh, fetches home or `@Ethplorer` mentions, excludes simple reposts from home, and upserts Posts plus independent source checkpoints into PostgreSQL. It preserves long-form `note_tweet.text`, returned referenced Post context, and returned media metadata without downloading media. It follows incremental pagination until completion or an explicit page, primary-Post, cost, partial-response, or error guard. Incomplete work saves available Posts and estimated usage but does not advance its source checkpoint. An explicit confirmation-gated baseline action can accept the newest first-page ID from a validated incomplete run without making another X request.

LLM integration, Telegram, and publication are not implemented. All publication remains a mandatory human action.

The repository remains public during the MVP. Public visibility does not change the existing prohibition on committing credentials, local `.env` files, raw operational X content, runtime database data or dumps, private or licensed exports, or confidential internal documents.

## Implementation Status

- Stage 0 - Repository Bootstrap - Completed
- Stage 1 - Durable Storage Foundation - Completed
- Stage 2 - X API Access Spike - Completed
- Stage 3 - X Collection Pipeline - Completed
- Current task - Task 004C.1 - Explicit Baseline Acceptance - Completed
- Next task - Task 005A - Knowledge Base Inventory and Schema - Planned, awaiting its explicit task specification

See the canonical [implementation roadmap](docs/roadmap.md), [product and technical specification](docs/project-spec.md), and [architecture decision log](docs/decisions.md).

## Repository Structure

```text
.
|-- AGENTS.md
|-- docs/                      # Canonical specification and decisions
|-- knowledge/                 # Terminology, sources, and asset catalog
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
- X Developer Console billing remains unreconciled; stored cost values are estimates
- Mentions pagination was not observed live because the validated response was empty
- No LLM calls or prompt execution
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
