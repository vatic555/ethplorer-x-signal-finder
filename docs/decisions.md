# Architecture Decision Log

This log records meaningful architectural and product decisions. New entries must include a date, status, context, and decision.

## 2026-07-22 - Private repository during MVP

Status: Accepted

The repository begins private because the MVP may include implementation details related to private data sources and licensed content. Repository privacy does not permit secrets or runtime data to be committed.

## 2026-07-22 - Markdown specification in Git is canonical

Status: Accepted

`docs/project-spec.md` is the canonical product and technical specification. Product behavior changes require a corresponding specification update.

## 2026-07-22 - Two-file terminology architecture

Status: Accepted

Shared Ethplorer analytics terminology and project-specific X Signal Finder terminology are maintained separately in `knowledge/shared-analytics-terminology.md` and `knowledge/x-signal-terminology.md`. Definitions must not be synchronized or changed silently.

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
