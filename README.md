# Ethplorer X Signal Finder

Ethplorer X Signal Finder is an AI-assisted X intelligence pipeline foundation. It is intended to find rare discussions with a real information gap that Ethplorer can close naturally and credibly using documented products, data, analytics, infrastructure, expertise, or business development capabilities.

It is not a generic crypto-news aggregator, an automatic publishing bot, or a mechanism for forcing Ethplorer into unrelated conversations.

## Current Status

The durable PostgreSQL storage foundation is implemented and validated against the real Supabase database. PostgreSQL is the operational source of truth, with Supabase selected as the initial managed provider. Application code uses the standard PostgreSQL protocol through `psycopg` and does not use the Supabase Python SDK.

Stage 2 is complete with a `constrained-go` decision. Stage 3 is In Progress, and Task 004A is complete. Its bounded manually started collector uses OAuth refresh, fetches home or `@Ethplorer` mentions, excludes simple reposts from home, and upserts Posts plus independent source checkpoints into PostgreSQL. Live validation saved real home Posts in Supabase, retained original Posts, replies, and quote Posts, created no duplicate `post_id` rows on a repeated run, and completed an empty mentions run successfully. Task 004A is deliberately not the full production collector: defaults are one page and 20 Posts, initial history is not backfilled automatically, and incomplete incremental pagination or partial errors do not advance a checkpoint.

LLM integration, Telegram, and publication are not implemented. All publication remains a mandatory human action.

The repository remains public during the MVP. Public visibility does not change the existing prohibition on committing credentials, local `.env` files, raw operational X content, runtime database data or dumps, private or licensed exports, or confidential internal documents.

## Implementation Status

- Stage 0 - Repository Bootstrap - Completed
- Stage 1 - Durable Storage Foundation - Completed
- Stage 2 - X API Access Spike - Completed
- Stage 3 - X Collection Pipeline - In Progress
- Current task - Task 004A - Minimal X Collector to PostgreSQL - Completed
- Next task - Await the next explicit Stage 3 task specification

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

Task 004A collector setup and bounded runs:

```sh
python -m x_signal_finder x-api oauth-setup
python -m x_signal_finder collect --source home --max-pages 1 --max-results 20
python -m x_signal_finder collect --source mentions --max-pages 1 --max-results 20
```

`oauth-setup` stores only the refresh token in the ignored local `.env`. Every collector run refreshes the access token in memory and safely replaces a rotated refresh token in `.env`. Collector output contains counts, checkpoints, IDs, estimated X cost, and warnings only. It never prints Post text, raw JSON, or credentials. See [the Task 004A collector guide](docs/x-collector.md) for checkpoint behavior and Supabase inspection.

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

- Task 004A is a bounded viability collector, not the complete Stage 3 pipeline
- No automatic historical backfill or production missed-window recovery
- Mentions pagination was not observed live because the validated response was empty
- No LLM calls or prompt execution
- No context enrichment from external sources
- No Telegram delivery
- No automatic image generation
- No GitHub Actions
- No automatic publication

Before changing architecture or product behavior, read `docs/project-spec.md`.
