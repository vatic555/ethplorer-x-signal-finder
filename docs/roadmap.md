# Ethplorer X Signal Finder - Implementation Roadmap

Status: Canonical implementation sequence and progress record

## Current Position

- Stage 0 - Repository Bootstrap - Completed
- Stage 1 - Durable Storage Foundation - Completed
- Stage 2 - X API Access Spike - Completed
- Stage 3 - X Collection Pipeline - In Progress
- Current task - Task 004A - Minimal X Collector to PostgreSQL - Completed
- Next task - Await the next explicit Stage 3 task specification
- Local PostgreSQL implementation is ready
- Real Supabase migration and database validation are complete
- Task 003 documentation review, diagnostic probe, live OAuth, endpoint, pagination, refresh, and checkpoint validation are complete
- Stage 2 decision - `constrained-go`; Stage 3 has started with the bounded Task 004A collector
- Task 004A implementation, synthetic validation, and bounded live X-to-Supabase validation are complete

Stage 1 must not be marked Completed until the real Supabase database has been created, migrations have been applied, and database validation has passed.

## MVP Boundary

Stages 0 through 7 constitute the MVP. Stage 7 completes the MVP through a two-week manually operated pilot. The MVP is not complete merely because the code exists.

Pipeline execution remains manually started one or two times per day during the MVP. Publication remains a mandatory human action. Stage 8 is post-MVP. Deferred does not mean rejected.

The MVP covers:

- automatic X collection;
- durable cloud storage;
- relevance filtering;
- Signal clustering;
- Opportunity Gate;
- selective context enrichment;
- knowledge-base matching;
- drafts and action suggestions;
- human review and editing;
- usage and cost accounting;
- a two-week pilot.

Post-MVP work may cover:

- scheduled execution;
- GitHub Actions or another scheduler;
- Telegram delivery;
- dashboards;
- real-time monitoring;
- automatic publication;
- automatic image generation;
- automatic model training;
- Opportunity Score.

## Stage Summary

| Stage | Name | Status | Task | MVP |
|---|---|---|---|---|
| 0 | Repository Bootstrap | Completed | Task 001 | Yes |
| 1 | Durable Storage Foundation | Completed | Task 002 | Yes |
| 2 | X API Access Spike | Completed | Task 003 | Yes |
| 3 | X Collection Pipeline | In Progress | Task 004A | Yes |
| 4 | Minimum Knowledge Base | Planned | Task 005 | Yes |
| 5 | Relevance Filtering and Signal Clustering | Planned | Task 006 | Yes |
| 6 | Opportunity Gate and Context Enrichment | Planned | Task 007 | Yes |
| 7 | Drafts, Human Review and Pilot | Planned | Task 008 | Yes |
| 8 | Scheduling and Delivery Automation | Deferred | Future task | No |

## Stage 0 - Repository Bootstrap

Status: Completed

Established the repository foundation:

- canonical specification;
- decision log;
- AGENTS instructions;
- terminology structure;
- knowledge-base placeholders;
- prompt contracts;
- minimal Python package and CLI;
- Git and environment safety rules.

### Tasks

- Task 001 - Repository Bootstrap - Completed
- Task 001A - Canonical Implementation Roadmap - Completed

### Completion Record

- Final commit: `f9b5abf9abe28f3891c0c1cf1376f9a1b87e8353`
- Commit message: `chore: bootstrap Ethplorer X Signal Finder`
- Roadmap task commit: `671a7cbd1f4990e78e41d4717dada5bde28abf59`
- Roadmap validation summary: canonical roadmap created; linked documents aligned; documentation consistency checks passed.

## Stage 1 - Durable Storage Foundation

Status: Completed

Create the cloud PostgreSQL foundation:

- Supabase as the initial provider;
- standard PostgreSQL access;
- migrations;
- runs, posts, Signals, Opportunities, reviews, usage, and sync state;
- repository API;
- DB CLI;
- tests and transaction-based validation;
- secret redaction.

Current state:

- local schema and implementation are ready;
- default tests pass;
- real Supabase connection is available;
- migration 1 is applied with no pending migrations;
- database structure, RLS, rollback behavior, and connectivity are validated.

### Tasks

- Task 002 - Durable Storage Foundation - Completed

### Completion Record

- Completion date: 2026-07-23
- Final commit: `dda7e417550a8f5a05c88f2277443e07c577fcc0`
- Validation summary: Supabase PostgreSQL 17.6; migration 1 applied; `db doctor` healthy; `db smoke-test` passed with all synthetic changes rolled back; 12 default tests passed with 1 optional integration test skipped; explicit Supabase integration test passed; repeat migration reported no pending work.
- Remaining limitations: No known Task 002 limitations. X collection and later pipeline stages remain unimplemented.

## Stage 2 - X API Access Spike

Status: Completed

Verify the real technical and commercial limits of X before building the collector:

- personal-account authentication;
- home timeline access;
- `@Ethplorer` mentions;
- pagination;
- token refresh;
- response fields;
- rate limits;
- available history;
- storage and retention restrictions;
- expected cost;
- go, constrained-go, or no-go decision.

Current state:

- official X documentation review is complete as of 2026-08-05;
- isolated read-only probe, OAuth 2.0 PKCE helper, synthetic fixtures, and mocked tests are implemented;
- live OAuth 2.0 PKCE authorization and refresh succeeded;
- live home-timeline requests returned HTTP 200, exercised multiple pages, showed no duplicate IDs, repeated page one consistently, and reached an in-memory checkpoint;
- the direct `@Ethplorer` mentions request returned HTTP 200 under Aleksandr user context, demonstrating that separate Ethplorer authorization is not required to call the endpoint in this configuration;
- the mentions response contained no Posts, so mentions pagination could not be observed live;
- decision is `constrained-go` because of bounded history windows, possible partial errors, unobserved mentions pagination, Developer Console billing dependence, and unresolved operational compliance details;
- Stage 3 subsequently started with Task 004A and remains In Progress.

### Tasks

- Task 003 - X API Access Spike - Completed

### Completion Record

- Completion date: 2026-08-05
- Final implementation commit: `d21fb2cd99cab8fa6b37fa465501e90db03ca751`
- Decision: `constrained-go`
- Validation summary: OAuth 2.0 PKCE authorization and refresh succeeded; home and mentions endpoints returned HTTP 200; home pagination, page-repeat consistency, duplicate detection, returned fields, actual rate-limit headers, and in-memory checkpoint reachability were validated; the default test suite passed without external calls; tokens, responses, and Post text were not persisted.
- Remaining limitations: Home is bounded to the documented 3,200-Post or seven-day window, and mentions to 800 Posts. The live mentions result was empty, so its pagination was not exercised. Home responses can contain partial object errors even with HTTP 200. Exact charged usage remains a Developer Console observation. Stage 3 must implement independent safe checkpoints, complete pagination, partial-error failure handling, possible-window-truncation warnings, usage accounting, and an approved retention and deletion process.

## Stage 3 - X Collection Pipeline

Status: In Progress

Build reliable automatic collection while keeping execution manually initiated:

- home timeline;
- `@Ethplorer` mentions;
- pagination;
- durable storage;
- post-ID deduplication;
- independent checkpoints;
- safe checkpoint advancement;
- retry and partial-failure protection;
- missed-window warnings;
- collection usage and cost accounting;
- macOS and Windows support.

Current state:

- Task 004A implements a manually invoked `collect` command with one-page and 20-Post safe defaults;
- OAuth access tokens are refreshed in memory, and only the rotated refresh token is stored in ignored local `.env`;
- home and mentions use independent `sync_state` keys;
- Post mapping, simple-repost exclusion, upsert deduplication, safe checkpoint updates, minimal usage estimates, and secret-safe summaries are implemented without a schema migration;
- an intentionally bounded first run establishes a current baseline and records that older history was not backfilled;
- incomplete incremental pagination, partial response errors, or duplicate IDs prevent checkpoint advancement;
- required bounded live home, repeated-home, and mentions runs against X and Supabase passed;
- full Stage 3 pagination, retry hardening, missed-window recovery, and compliance automation are not part of Task 004A.

### Tasks

- Task 004A - Minimal X Collector to PostgreSQL - Completed
- Further Stage 3 hardening - Planned; task not yet assigned

### Task 004A Validation Record

- Completion date: 2026-08-06
- Live runs: home baseline, repeated incremental home, and mentions
- Live result: 21 Posts fetched across two home requests, 4 simple reposts excluded, and 17 unique home rows saved; stored types were 13 original Posts, 2 replies, and 2 quote Posts; the mentions request succeeded with zero Posts.
- Deduplication: 17 total Post rows and 17 distinct `post_id` values after the repeated home run; duplicate groups were zero.
- Checkpoints: `x_home_timeline` stored and reused a non-empty checkpoint; `x_ethplorer_mentions` recorded a successful empty collection with no checkpoint value.
- Usage estimate: 2 home requests and 1 mentions request; 21 public Post reads; $0.105 estimated X Post-read cost before Developer Console reconciliation.
- Database validation: PostgreSQL 17.6; migration 1 current; no pending migrations; required tables present; RLS enabled; no new migration created.
- Tests: 42 passed and 3 optional integration tests skipped before live validation.
- Remaining limitations: bounded initial baseline, no historical backfill, no full Stage 3 recovery workflow, no automated X Content revalidation or deletion, and one stored `source_key` value per Post row.

### Completion Record

- Completion date:
- Final commit:
- Validation summary:
- Remaining limitations:

## Stage 4 - Minimum Knowledge Base

Status: Planned

Create the minimum reviewed knowledge required for credible Opportunity decisions:

- shared analytics terminology;
- project terminology;
- asset catalog;
- explorer and API capabilities;
- analytics capabilities;
- supported networks;
- capability limitations;
- public and internal provenance;
- stable asset IDs;
- human review process.

### Tasks

- Task 005 - Minimum Knowledge Base - Planned

### Completion Record

- Completion date:
- Final commit:
- Validation summary:
- Remaining limitations:

## Stage 5 - Relevance Filtering and Signal Clustering

Status: Planned

Reduce collected X content to a small auditable set of potential Signals:

- preliminary relevance decisions;
- rejection reasons;
- evidence and uncertainty;
- event clustering;
- source-post relationships;
- conflicting claims;
- structured Signal records;
- evaluation examples;
- false-positive and missed-candidate review.

Relevance alone must not create an Opportunity.

### Tasks

- Task 006 - Relevance Filtering and Signal Clustering - Planned

### Completion Record

- Completion date:
- Final commit:
- Validation summary:
- Remaining limitations:

## Stage 6 - Opportunity Gate and Context Enrichment

Status: Planned

Accept only Signals containing a real information gap that a documented Ethplorer asset can naturally close:

- accepted, rejected, and unresolved decisions;
- information-gap identification;
- exact asset matching;
- audience benefit;
- natural relevance;
- forced-promotion rejection;
- evidence sufficiency;
- selective thread and external context enrichment;
- Opportunity creation only after acceptance.

Rejected and unresolved Signals must not receive drafts.

### Tasks

- Task 007 - Opportunity Gate and Context Enrichment - Planned

### Completion Record

- Completion date:
- Final commit:
- Validation summary:
- Remaining limitations:

## Stage 7 - Drafts, Human Review and Pilot

Status: Planned

Turn accepted Opportunities into reviewable actions and validate the MVP through a two-week pilot:

- reply;
- quote post;
- own post;
- article idea;
- BizDev action;
- Visual Brief;
- human review;
- edited version;
- preservation of generated and edited versions;
- feedback taxonomy;
- pilot reporting;
- execution one or two times per day for two weeks;
- measurement of posts, Signals, Opportunities, time, and cost;
- false-positive and missed-candidate analysis;
- mandatory human publication.

At the end of the pilot, record whether to:

- stop;
- revise the pipeline;
- extend the pilot;
- proceed to post-MVP automation.

### Tasks

- Task 008 - Drafts, Human Review and Two-Week Pilot - Planned

### Completion Record

- Completion date:
- Final commit:
- Pilot dates:
- Pilot results:
- Final decision:
- Remaining limitations:

## Stage 8 - Scheduling and Delivery Automation

Status: Deferred

Possible post-MVP work:

- scheduled execution;
- GitHub Actions or another scheduler;
- Telegram delivery;
- review notifications;
- operational monitoring;
- automated reports;
- lightweight review interface;
- possible dashboard.

Automatic publication is not approved and requires a separate decision.

### Tasks

- Future tasks to be assigned after Stage 7

### Completion Record

- Completion date:
- Final commit:
- Validation summary:
- Remaining limitations:

## Roadmap Maintenance Rules

- Stage order must not change silently.
- Stage reorder or bypass requires an accepted decision.
- A stage begins when marked In Progress.
- A stage is marked Completed only after its task-specific validation passes.
- Written code alone does not complete a stage.
- Completion records must contain the final commit and validation result.
- README must be updated when the current stage changes.
- Product-behavior changes must update `docs/project-spec.md`.
- Architectural changes must update `docs/decisions.md`.
- Implementation stages must not be confused with runtime pipeline stages.
