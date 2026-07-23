# Ethplorer X Signal Finder

Ethplorer X Signal Finder is an AI-assisted X intelligence pipeline foundation. It is intended to find rare discussions with a real information gap that Ethplorer can close naturally and credibly using documented products, data, analytics, infrastructure, expertise, or business development capabilities.

It is not a generic crypto-news aggregator, an automatic publishing bot, or a mechanism for forcing Ethplorer into unrelated conversations.

## Current Status

The durable PostgreSQL storage foundation is implemented. PostgreSQL is the operational source of truth, with Supabase selected as the initial managed provider. Application code uses the standard PostgreSQL protocol through `psycopg` and does not use the Supabase Python SDK.

X collection, LLM integration, Telegram, and publication are not implemented. All publication remains a mandatory human action.

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

Database commands:

```sh
python -m x_signal_finder db doctor
python -m x_signal_finder db migrate
python -m x_signal_finder db status
python -m x_signal_finder db smoke-test
```

`db doctor` and `db status` are read-only. `db migrate` is the only command that applies schema migrations. Migrations never run automatically during normal pipeline execution. `db smoke-test` creates clearly synthetic records inside one transaction, rolls it back, and verifies that no synthetic rows remain.

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

- No X API collection or pagination
- No LLM calls or prompt execution
- No context enrichment from external sources
- No Telegram delivery
- No automatic image generation
- No GitHub Actions
- No automatic publication

Before changing architecture or product behavior, read `docs/project-spec.md`.
