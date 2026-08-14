# Ethplorer X Signal Finder - Product and Technical Specification

Status: Canonical specification for the current MVP direction

## Specification and Roadmap

This document defines required product and technical behavior. `docs/roadmap.md` defines implementation sequence and progress. Stages 0 through 7 constitute the MVP, and Stage 8 is post-MVP. Roadmap status cannot redefine product requirements.

## 1. Product Goal

Ethplorer X Signal Finder is an AI-assisted intelligence pipeline that analyzes selected X sources and identifies rare, high-value discussions where Ethplorer can contribute natural, specific, and credible value through documented products, data, analytics, infrastructure, expertise, or business development opportunities.

The system is not a generic crypto-news aggregator. Its output is a small set of reviewable Opportunities, not a feed of everything that happened in crypto. A normal target is approximately one to three genuinely useful Opportunities per week.

## 2. Core Product Principle

The core question is: "Does this discussion contain an information gap that Ethplorer can naturally and credibly close with its documented products, data, analytics, infrastructure, or expertise?"

The system must begin with an existing information gap. It must not search for a way to mention Ethplorer. A Signal must pass the Opportunity Gate before an Opportunity or draft can be produced. The pipeline must prefer no output over weak output and reject forced promotional participation.

## 3. Current MVP Boundary

The intended MVP automates collection and filtering, including collection, durable storage, pagination, safe checkpoints, deduplication, preliminary relevance filtering, Signal clustering, Opportunity Gate evaluation, optional context enrichment, knowledge-base matching, Opportunity generation, draft generation, optional Visual Brief generation, and usage and cost accounting.

Execution is initially started manually once or twice per day. Humans review Opportunities, edit drafts, record feedback, and publish on X. Human publication is mandatory.

The current implementation includes the repository foundation, documentation, prompts, a local CLI, durable PostgreSQL storage, the isolated read-only X API access-spike probe, the completed Stage 3 collector, the Task 005A Git-backed knowledge architecture and 17-article inventory, and the Task 005C first-party X editorial corpus. Task 004B prefers `note_tweet.text` for long Posts, retains returned referenced Post and media metadata in the original Post's `raw_json`, and exposes manual PostgreSQL review views. Task 004C paginates forward from each independent source checkpoint until the API window ends or a configured page, primary-Post, cost, partial-response, or error guard stops the source. Task 004C.1 adds an explicit, confirmation-gated PostgreSQL-only action that may accept the newest collected point from a current incomplete run as a new operational baseline while recording that older Posts may have been skipped. The collector is manually started, uses a refresh token stored only in the ignored local `.env`, fetches home or `@Ethplorer` mentions through X API v2, excludes simple home reposts, and upserts returned Posts, run records, estimated usage, and independent source checkpoints into PostgreSQL. Its defaults are five pages of up to 100 primary Posts, a $1 estimated-cost guard, three attempts, and at most 60 seconds per retry wait. An optional primary-Post limit is global across home then mentions. Expanded Post resources count toward estimated cost but not the primary limit. An explicit bounded `--refresh-existing` mode omits `since_id`, anchors the request at the stored checkpoint with `until_id`, refreshes stored rows by Post ID, and leaves the operational checkpoint unchanged. It does not perform a historical backfill. A source checkpoint advances to the newest ID from its first page only after complete collection and persistence; incomplete work preserves fetched Posts and estimated usage but leaves the checkpoint unchanged and returns a non-zero CLI result. Usage is committed independently before Post upsert so a later database write failure does not erase the paid-fetch estimate. Live validation confirmed guard behavior, durable usage, deduplication, checkpoint non-advancement, manual baseline acceptance without X requests, and a bounded incremental run from the accepted baseline. Task 005A defines source metadata, source-to-capability evidence links, public-repository rules, offline validation, and the approved article inventory without adding runtime knowledge processing. Task 005C uses the same read-only OAuth and PostgreSQL foundations to retain historical and future Ethplorer/Binplorer Posts in one separate operational corpus with source-specific incremental checkpoints, complete direct relationship sets, optional bounded reference completion, and returned media metadata only. Automatic missed-window recovery and compliance automation remain unimplemented. Model calls, Signals, Opportunities, Telegram, scheduling, X write operations, automatic unfollow, media downloads, and publication are not implemented.

## 4. Inputs

The MVP's primary inputs are:

- the reverse chronological home timeline of Aleksandr's personal X account;
- mentions of `@Ethplorer`;
- collection metadata and checkpoints;
- documented Ethplorer knowledge-base assets and capabilities;
- optional thread, reply, quote-post, or external context for promising Signals;
- human editorial feedback and decisions.
- the continuously synchronized first-party Ethplorer and Binplorer editorial corpus as contextual evidence, not capability proof.

Collected source posts must retain stable post IDs and enough source and collection metadata to support analysis, deduplication, missed-collection detection, and auditability, subject to X platform requirements.

When X returns `note_tweet.text`, it is the stored full text; otherwise the normal `text` field is used. The untouched normal `text`, the complete `note_tweet` object, returned expanded referenced Post context, referenced author identity, and matching returned media metadata remain auditable inside the main Post's `raw_json`. Missing expansions are nonfatal and never trigger an extra request. Media files are not downloaded.

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

For the MVP, reviewed Git content under `knowledge/` is the source of truth for static reviewed knowledge. PostgreSQL, embeddings, vector databases, semantic search, and runtime knowledge integration are not part of Task 005A. A future database or search index may be a reproducible derivative of Git but must not replace it as the canonical static knowledge source without an explicit specification and architecture decision change.

The architecture defines three knowledge source classes:

1. Static reviewed knowledge includes product articles, product documentation, terminology, capabilities, and limitations. Its reviewed Git content is canonical. A capability may be established only through reviewed supporting static evidence.
2. First-party editorial corpus consists of historical and future Ethplorer and Binplorer X Posts, including replies, quotes, and reposts. Task 005C stores it continuously in PostgreSQL through one historical and incremental lifecycle. Actual text retrieved from X is authoritative. The corpus may later support vocabulary, style, reaction patterns, topic interest, and prior public positioning, but it must not silently establish a product capability, limitation, current fact, supported network, price, API limit, analytical metric, or numerical claim.
3. Dynamic analytical evidence includes dated metrics and comparisons produced outside this repository, especially by `ethereum-top-addresses-pipeline`. That repository and its analytical state remain separate and are not copied into the static knowledge base. A future adapter must query the latest appropriate snapshot or comparison on demand and retain the as-of date, comparison dates, metric name, scope, and source provenance for every retrieved value.

The editorial corpus and dynamic analytical evidence are contextual evidence classes, not substitutes for reviewed static capability evidence. Missing authority, dates, scope, or provenance must produce an unresolved result rather than an inferred claim. Task 005C implements collection and storage for the editorial class only. It does not extract vocabulary or style rules, perform LLM analysis, or implement the dynamic analytics adapter, snapshot query, or runtime knowledge integration.

The knowledge base currently consists of:

- `knowledge/terminology/shared-analytics.md` for imported shared analytics concepts with upstream provenance and review status;
- `knowledge/terminology/x-signal.md` for project-specific operational terms;
- `knowledge/sources/` for public or explicitly approved static evidence documents with stable identity and provenance;
- `knowledge/assets_catalog.csv` for structured capability records linked to evidence by stable source ID;
- `knowledge/source_documents.md` for inventory and provenance tracking;
- `knowledge/README.md` for the source and catalog contracts.

`knowledge/sources/posts/` is the canonical location for the 17 current Ethplorer Markdown articles and their managed local article media. They must not be moved or renamed merely to match a proposed product-oriented layout. Each uses `source_type = ethplorer_article`, which is distinct from the PostgreSQL first-party X editorial corpus.

Every imported source document must use a stable `source_id`, reliable machine-readable Markdown, required metadata, approved provenance, and a review status of `pending`, `reviewed`, or `deprecated`. Pending sources may leave product, network, supported-claim, and limitation lists empty until substantive review. A reviewed source must state at least one explicit supported claim. Full source text may be stored only when the material is public or explicitly approved for this public repository. Private, internal, confidential, and licensed document text must not be committed.

Source identity, provenance, claims, historical facts, and substantive meaning must be preserved, but byte-for-byte body identity is not required. Meaning-preserving normalization may remove whitespace or export artifacts, repair Markdown, headings, lists, tables, images, captions, and unambiguous links, or add useful section structure. It must not rewrite claims for style, silently update facts, prices, limits, dates, or capabilities, add absent information, change meaning, or promote inference into a source claim. Task 005A does not bulk-reformat the current articles. Necessary normalization and capability, limitation, topic, and asset-catalog extraction are reserved for Task 005B.

Every asset or capability record must use a stable `asset_id` and reference one or more existing `source_id` values. A reviewed capability must have at least one reviewed supporting source. A URL, product positioning, TODO, filename, or general knowledge is not capability evidence. If the exact supporting asset is absent or insufficient, the candidate is unresolved.

The two terminology files have separate ownership and must not be silently merged. Shared definitions are imported only from an identified upstream source and reviewed. Project-specific definitions are maintained locally. A future process may compare imported shared terms with an upstream shared terminology repository, but automatic synchronization is outside this task.

Offline validation must check required knowledge structure and source metadata, unique source and asset IDs, allowed review statuses, catalog-to-source references, reviewed-evidence rules, and local references without network access or model calls.

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

PostgreSQL is the operational source of truth. Supabase is the initial managed PostgreSQL provider, but application code uses standard PostgreSQL interfaces through `psycopg` and does not depend on the Supabase Python SDK. The connection string is read from `DATABASE_URL`; local `.env` configuration is optional, and real environment variables take precedence.

The implemented schema includes `schema_migrations`, `runs`, `posts`, `first_party_x_posts`, `first_party_x_post_references`, `signals`, `signal_posts`, `opportunities`, `human_reviews`, `usage_events`, and `sync_state`. The first-party tables are permanent and separate from incoming `posts`; historical and future first-party Posts share the same table. Application-generated UUIDs avoid provider-specific UUID extensions. Repository operations use parameterized SQL and caller-owned explicit transactions.

Schema migrations are deterministic, reviewable, safe to run repeatedly, and tracked by version and SHA-256 checksum. A changed or missing applied migration causes a clear failure. Migrations run only through an explicit database CLI command and never during normal pipeline execution.

All operational tables have Row Level Security enabled with no anonymous or authenticated public policies. The MVP application uses a protected PostgreSQL connection and does not use anon keys, authenticated roles, service-role keys, or public Supabase API access. Security-invoker review views provide Post links, referenced context and media indicators, stored-author statistics, and conservative manual unfollow candidates. These views never change processing status, checkpoints, or X account state.

Git must not be used as the operational store for raw X content. Runtime databases, raw runtime data, and private or licensed exports must not be committed. CSV and XLSX files are analytical exports, not the operational source of truth.

This operational-data rule does not conflict with the Git-backed static knowledge source of truth. Knowledge files contain reviewed public or explicitly approved static evidence and structured capability claims, not raw operational X content. First-party X content is a separate PostgreSQL editorial corpus and must not be committed as raw operational content. Dynamic analytics remain in their upstream repository and are read later through a provenance-preserving adapter. PostgreSQL remains the operational source of truth, while Git is the MVP source of truth for static reviewed knowledge.

Audit records must make it possible to reconstruct which inputs, evidence, knowledge-base version, processing outcome, usage, and human decision produced an Opportunity. Retention and deletion must comply with applicable X platform requirements.

## 14. Cross-Platform Execution

The project must run on macOS, Windows, Linux, and future GitHub Actions runners. Python 3.11 or newer is the primary runtime. The platform-independent module entry point is:

```text
python -m x_signal_finder run
```

Platform-specific scripts may be optional conveniences but must never be the only way to operate the pipeline. Paths, subprocess behavior, configuration, and tests must avoid platform-specific assumptions.

## 15. Usage and Cost Tracking

Future external-service activity must produce structured usage events linked to a run and processing stage. Records should capture the provider, operation or model, request count, measured input and output units where available, reported or estimated cost, currency, timestamp, and relevant entity IDs.

Reported usage, estimated usage, and unknown cost must remain distinguishable. The collector estimates X cost from unique Post IDs returned in primary `data` and expanded `includes.tweets`, deduplicated within each source across pages and response sections. The current configurable estimate is $0.005 per distinct Post resource. A cost guard prevents further pagination after the accumulated estimate reaches its limit, but it is not an exact billing cap and may overshoot by one completed page and its expansions. Actual billing remains a Developer Console fact. Default commands and tests perform no external service calls. Explicit X API access-spike commands can incur pay-per-use X charges during authorized live validation, but they do not persist operational usage records because they are diagnostics rather than pipeline runs.

First-party X sync records separate inventory, Ethplorer, and Binplorer usage operations. It distinguishes primary, expanded, reference-completion, media, and User resources. Distinct Post IDs are deduplicated for estimated Post-resource cost within each source sync. The current configurable User Read estimate is $0.010. `reported_cost` remains NULL until Developer Console reconciliation.

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
- What retention, deletion, and content-display policies are required by the applicable X terms?
- How should event-cluster identity and later cluster merging be represented?
- Which structured schemas and confidence rules should each prompt stage use?
- Which approved knowledge sources and review process establish that an Ethplorer asset is usable?
- How should model and enrichment budgets be allocated and enforced per run?
- Which human feedback taxonomy will be useful without creating unnecessary editorial overhead?
