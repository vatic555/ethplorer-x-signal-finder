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
