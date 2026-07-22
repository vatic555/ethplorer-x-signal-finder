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

## 2026-07-22 - Git excludes raw operational X content

Status: Accepted

Git is not an operational data store. Raw X content, runtime databases, and private or licensed runtime exports must not be committed.

## 2026-07-22 - Python is the cross-platform runtime

Status: Accepted

Python 3.11 or newer is the main runtime. Platform-specific scripts may be optional helpers but cannot be the sole execution path.

## 2026-07-22 - Publication remains manual

Status: Accepted

Every draft requires human review, and a human must publish it. Automatic publication requires an explicit future specification and architecture decision change.
