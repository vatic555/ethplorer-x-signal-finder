# Ethplorer X Signal Finder

Ethplorer X Signal Finder is the foundation for an AI-assisted X intelligence pipeline. It is intended to find rare discussions with a real information gap that Ethplorer can close naturally and credibly using documented products, data, analytics, infrastructure, expertise, or business development capabilities.

It is not a generic crypto-news aggregator, an automatic publishing bot, or a mechanism for forcing Ethplorer into unrelated conversations.

## Current Status

The repository is bootstrapped with the canonical specification, decision log, terminology structure, knowledge-base placeholders, initial prompt templates, and a minimal Python CLI. X collection, durable database storage, LLM integration, Telegram, and publication are not implemented. The CLI makes no external API calls and needs no credentials.

## Repository Structure

```text
.
├── AGENTS.md                  # Instructions for coding agents
├── docs/                      # Canonical specification and decisions
├── knowledge/                 # Terminology, sources, and asset catalog
├── prompts/                   # Initial processing-stage prompt templates
├── src/x_signal_finder/       # Cross-platform Python package and CLI
├── migrations/                # Future database migrations
├── scripts/                   # Future optional helper scripts
├── tests/                     # Future automated tests
└── data/
    ├── exports/               # Ignored analytical exports
    └── fixtures/              # Safe future test fixtures
```

## Setup on macOS or Linux

Python 3.11 or newer is required.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --editable .
```

## Setup on Windows

Using PowerShell with Python 3.11 or newer:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --editable .
```

If PowerShell execution policy prevents activation, the virtual-environment interpreter can be used directly:

```powershell
.venv\Scripts\python.exe -m pip install --editable .
```

## Run the CLI

After installation:

```sh
python -m x_signal_finder --help
python -m x_signal_finder status
```

The installed console entry point is equivalent:

```sh
x-signal-finder --help
x-signal-finder status
```

No `.env` file or credentials are required for these commands.

## Current Limitations

- No X API collection or pagination
- No operational database or Supabase integration
- No LLM calls
- No context enrichment from external sources
- No Telegram delivery
- No automatic image generation
- No GitHub Actions
- No automatic publication

All publication remains a mandatory human action.

## Next Implementation Milestone

Design and implement durable storage and X collection with safe pagination and checkpoints.

Before changing architecture or product behavior, read [`docs/project-spec.md`](docs/project-spec.md). Never commit secrets, runtime databases, raw operational X content, or private or licensed exports.
