# Ethplorer X Signal Finder - Product and Technical Specification

Status: Canonical specification for the current MVP direction

## 1. Product Goal

Ethplorer X Signal Finder is an AI-assisted intelligence pipeline that analyzes selected X sources and identifies rare, high-value discussions where Ethplorer can contribute natural, specific, and credible value through documented products, data, analytics, infrastructure, expertise, or business development opportunities.

The system is not a generic crypto-news aggregator. Its output is a small set of reviewable Opportunities, not a feed of everything that happened in crypto. A normal target is approximately one to three genuinely useful Opportunities per week.

## 2. Core Product Principle

The core question is: "Does this discussion contain an information gap that Ethplorer can naturally and credibly close with its documented products, data, analytics, infrastructure, or expertise?"

The system must begin with an existing information gap. It must not search for a way to mention Ethplorer. A Signal must pass the Opportunity Gate before an Opportunity or draft can be produced. The pipeline must prefer no output over weak output and reject forced promotional participation.

## 3. Current MVP Boundary

The intended MVP automates collection and filtering, including collection, durable storage, pagination, safe checkpoints, deduplication, preliminary relevance filtering, Signal clustering, Opportunity Gate evaluation, optional context enrichment, knowledge-base matching, Opportunity generation, draft generation, optional Visual Brief generation, and usage and cost accounting.

Execution is initially started manually once or twice per day. Humans review Opportunities, edit drafts, record feedback, and publish on X. Human publication is mandatory.

This bootstrap stage creates the repository foundation, documentation, prompts, and a minimal local CLI only. It does not implement collection, database access, model calls, Telegram, publication, or other external integrations.

## 4. Inputs

The MVP's primary inputs are:

- the reverse chronological home timeline of Aleksandr's personal X account;
- mentions of `@Ethplorer`;
- collection metadata and checkpoints;
- documented Ethplorer knowledge-base assets and capabilities;
- optional thread, reply, quote-post, or external context for promising Signals;
- human editorial feedback and decisions.

Collected source posts must retain stable post IDs and enough source and collection metadata to support analysis, deduplication, missed-collection detection, and auditability, subject to X platform requirements.

## 5. Supported Products and Networks

The currently supported explorer products and networks are:

- Ethereum - https://ethplorer.io
- BNB Chain - https://binplorer.com
- Blast - https://blastplorer.info
- Linea - https://lineaplorer.build
- World Chain - https://worldplorer.com

Potentially relevant documented capability areas include blockchain explorer functionality, address and wallet analytics, token-holder distribution, capital concentration analysis, Rich List analysis, PPI and SIT analytics, Ethplorer APIs, supported network explorers, data-provider or analytics partnerships, and business development opportunities.

This list identifies areas that may be relevant, but it is not evidence that a specific capability exists. A capability may be used by the pipeline only after it is documented in the knowledge base.

Events from other networks are relevant only when they directly affect Ethereum or a supported network, affect a relevant token or address, create a plausible new explorer integration, or create an infrastructure, data, analytics, or partnership opportunity for Ethplorer.

## 6. Functional Requirements

The eventual MVP must:

1. Collect both configured X sources and preserve fetched source posts for analysis and audit, subject to X platform requirements.
2. Support full pagination across every available page in a collection run.
3. Store posts durably and deduplicate them by X post ID.
4. Keep collection checkpoints per source and advance them only after the complete collection for that source succeeds.
5. Detect missed collections and warn when the available timeline window may have been truncated before the previous checkpoint was reached.
6. Apply a preliminary relevance filter without treating relevance as proof of an Opportunity.
7. Group related posts into Signals or event clusters while preserving links to all source evidence.
8. Apply the Opportunity Gate before generating any Opportunity or draft.
9. Enrich context only when it can resolve a material question for a promising Signal.
10. Match every proposed contribution to an exact, documented knowledge-base asset or capability.
11. Generate auditable, structured Opportunity records and optional drafts only for accepted Signals.
12. Track external-service usage and cost attributable to a run and processing stage.
13. Record human editorial decisions and feedback without automatically publishing.

No Opportunity should be generated merely because Ethplorer can be mentioned.

## 7. Processing Pipeline

The intended processing sequence is:

1. Start a run manually.
2. Read the last committed checkpoint for each source.
3. Fetch every available page in reverse chronological order until the checkpoint or a documented stopping condition is reached.
4. Persist fetched posts and collection metadata using post ID for deduplication.
5. Validate collection completeness, record possible window truncation or missed-collection warnings, and only then advance the checkpoint.
6. Apply preliminary relevance filtering.
7. Cluster related posts into Signals or event clusters.
8. Apply the Opportunity Gate.
9. Optionally enrich context for unresolved but promising Signals.
10. Match accepted candidates to documented knowledge-base assets.
11. Create Opportunity records, and only then create an appropriate draft or action suggestion.
12. Optionally create a short Visual Brief when a visual adds real explanatory value.
13. Record usage, cost, evidence, uncertainty, and provenance.
14. Present outputs for human review, editing, feedback, and manual publication.

Every stage must preserve traceability to the originating posts and run.

## 8. Opportunity Gate

For every candidate Signal, the system must determine:

1. Is there a real information gap?
2. Can Ethplorer close it better than a generic crypto commentator?
3. Which exact documented Ethplorer product, dataset, API, metric, explorer, or capability applies?
4. Would the contribution help the audience of the original discussion?
5. Would the participation look like forced promotion?
6. Are there enough verified facts to support a credible response?
7. Is more context required from the thread, replies, quote posts, or external sources?

The Gate outcome must be `accepted`, `rejected`, or `unresolved`, with concise reasons and supporting evidence. `Unresolved` is required when a material fact is missing or the knowledge base does not document the proposed contribution. Rejected and unresolved Signals must not receive drafts. Generic commentary, forced marketing relevance, and a mere opportunity to mention Ethplorer must be rejected.

## 9. Context Enrichment

Context enrichment is selective, not a default expansion of every Signal. It may inspect a thread, replies, quote posts, linked sources, or other relevant external sources only to answer explicit unresolved questions.

Enrichment must record what was requested, which sources were consulted, which claims became verified, which claims remain inferred, and which uncertainties remain unresolved. If enrichment does not provide sufficient evidence, the candidate remains unresolved or is rejected.

## 10. Knowledge Base

The knowledge base contains only reviewed, attributable information about applicable assets and capabilities. It currently consists of:

- `knowledge/shared-analytics-terminology.md` for imported shared analytics concepts;
- `knowledge/x-signal-terminology.md` for project-specific operational terms;
- `knowledge/assets_catalog.csv` for structured capability records;
- `knowledge/source_documents.md` for provenance and source tracking.

The two terminology files have separate ownership and must not be silently merged. Shared definitions are imported only from an identified source and reviewed. Project-specific definitions are maintained locally. A future process may compare imported shared terms with an upstream shared terminology repository, but automatic synchronization is outside this task.

The system must not infer that a capability exists from product positioning alone. If the exact supporting asset is absent or insufficient, the candidate is unresolved.

## 11. Opportunity Output

An Opportunity is created only after a Signal passes the Opportunity Gate. Its structured record should include:

- stable identifiers and links to its Signal, event cluster, run, and source posts;
- a concise description of the information gap;
- the audience benefit;
- the exact documented Ethplorer asset or capability that closes the gap;
- an evidence list with source provenance;
- verified facts, model inferences, and unresolved uncertainties as separate fields;
- Gate answers, outcome, and rationale;
- recommended action type: reply, quote post, own post, article idea, BizDev action, or no action;
- an optional draft appropriate to the action type;
- an optional Visual Brief;
- human review status, edits, decision, and feedback.

A draft is an artifact of an accepted Opportunity, not a synonym for a Signal or Opportunity.

## 12. Visual Brief

A Visual Brief is an optional, short specification for a visual that would materially improve clarity or evidence. It should state the communication goal, audience, data or facts to show, proposed format, required sources, uncertainty, and constraints.

No Visual Brief should be produced when text is sufficient, when reliable data is unavailable, or merely to make a post look more promotional. Automatic image generation is deferred.

## 13. Storage and Auditability

The intended operational source of truth is a managed PostgreSQL database such as Supabase. Database integration is not implemented in this bootstrap task. Likely entities include `runs`, `posts`, `signals`, `opportunities`, `usage_events`, and `sync_state`; their final schema remains an open design decision.

Git must not be used as the operational store for raw X content. Runtime databases, raw runtime data, and private or licensed exports must not be committed. CSV and XLSX files are analytical exports, not the operational source of truth.

Audit records must make it possible to reconstruct which inputs, evidence, knowledge-base version, processing outcome, usage, and human decision produced an Opportunity. Retention and deletion must comply with applicable X platform requirements.

## 14. Cross-Platform Execution

The project must run on macOS, Windows, Linux, and future GitHub Actions runners. Python 3.11 or newer is the primary runtime. The platform-independent module entry point is:

```text
python -m x_signal_finder run
```

Platform-specific scripts may be optional conveniences but must never be the only way to operate the pipeline. Paths, subprocess behavior, configuration, and tests must avoid platform-specific assumptions.

## 15. Usage and Cost Tracking

Future external-service activity must produce structured usage events linked to a run and processing stage. Records should capture the provider, operation or model, request count, measured input and output units where available, reported or estimated cost, currency, timestamp, and relevant entity IDs.

Reported usage, estimated usage, and unknown cost must remain distinguishable. This bootstrap stage performs no external calls and incurs no API usage.

## 16. Human Review and Feedback

Every Opportunity and draft requires human review. Reviewers may accept, reject, edit, defer, or request more evidence and should be able to record a reason and structured feedback. The system must preserve the original generated artifact and the final edited version for audit and learning.

Publication to X is manual and mandatory in the MVP. The system must never publish, schedule publication, or imply publication occurred.

## 17. Non-Goals

The MVP is not intended to provide:

- generic crypto-news aggregation;
- exhaustive commentary on relevant events;
- DeFi liquidity analysis;
- AML analysis;
- risk scoring;
- automatic model training from feedback;
- an operational database stored in Git;
- automatic publication.

## 18. Success Criteria

The MVP is successful when it:

- reliably collects and durably stores all posts available within the configured source windows;
- supports full pagination, safe checkpoints, post-ID deduplication, missed-collection detection, and possible-truncation warnings;
- preserves sufficient evidence and provenance for audit;
- produces approximately one to three genuinely useful Opportunities per week under normal use;
- rejects weak, generic, forced, or unsupported candidates;
- never creates a draft for a Signal that has not passed the Opportunity Gate;
- links every accepted Opportunity to an exact documented asset or capability;
- supports manual review and mandatory human publication;
- runs through a cross-platform Python entry point;
- tracks external-service usage and cost once such integrations exist.

## 19. Deferred Features

The following features are explicitly deferred:

- GitHub Actions;
- Telegram delivery, buttons, and webhooks;
- automatic X publication;
- automatic image generation;
- a web dashboard;
- real-time monitoring;
- Opportunity Score;
- automatic model training from feedback.

## 20. Open Technical Questions

- Which X API access tier and endpoints can satisfy source access, pagination, retention, and compliance requirements?
- What exact boundary defines a complete collection when an API window ends before the stored checkpoint?
- What checkpoint and transaction design guarantees that partial collection never advances state?
- What managed PostgreSQL provider and schema best satisfy durability, audit, privacy, and cost needs?
- What retention, deletion, and content-display policies are required by the applicable X terms?
- How should event-cluster identity and later cluster merging be represented?
- Which structured schemas and confidence rules should each prompt stage use?
- Which approved knowledge sources and review process establish that an Ethplorer asset is usable?
- How should model and enrichment budgets be allocated and enforced per run?
- Which human feedback taxonomy will be useful without creating unnecessary editorial overhead?
