# Ethplorer X Signal Finder - Implementation Roadmap

Status: Canonical implementation sequence and progress record

## Current Position

- Stage 0 - Repository Bootstrap - Completed
- Stage 1 - Durable Storage Foundation - In Progress
- Current task - Task 002 - Durable Storage Foundation
- Local PostgreSQL implementation is ready
- Real Supabase connection is available
- Supabase migration and full database validation are still pending

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
| 1 | Durable Storage Foundation | In Progress | Task 002 | Yes |
| 2 | X API Access Spike | Planned | Task 003 | Yes |
| 3 | X Collection Pipeline | Planned | Task 004 | Yes |
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
- Task 001A - Canonical Implementation Roadmap - In Progress

### Completion Record

- Final commit: `f9b5abf9abe28f3891c0c1cf1376f9a1b87e8353`
- Commit message: `chore: bootstrap Ethplorer X Signal Finder`

## Stage 1 - Durable Storage Foundation

Status: In Progress

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
- Supabase migration and full database validation remain pending.

### Tasks

- Task 002 - Durable Storage Foundation - In Progress

### Completion Record

- Completion date:
- Final commit:
- Validation summary:
- Remaining limitations:

## Stage 2 - X API Access Spike

Status: Planned

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

### Tasks

- Task 003 - X API Access Spike - Planned

### Completion Record

- Completion date:
- Final commit:
- Validation summary:
- Remaining limitations:

## Stage 3 - X Collection Pipeline

Status: Planned

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

### Tasks

- Task 004 - X Collection Pipeline - Planned

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
