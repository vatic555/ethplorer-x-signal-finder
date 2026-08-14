# First-Party X Editorial Corpus

Status: Task 005C complete; Stage 4 remains In Progress

Live validation date: 2026-08-14

## Purpose and authority

The first-party editorial corpus is the continuously updated record of actual Posts published by Ethplorer and Binplorer on X. Historical and future Posts share the same PostgreSQL tables and synchronization lifecycle. Text retrieved from X is authoritative even when a future pipeline draft or Opportunity exists.

The corpus may later support vocabulary discovery, style guidance, reply and quote patterns, historical topic interest, and prior public positioning. It cannot by itself establish a current product capability, supported network, price, API limit, product limitation, analytical metric, or numerical fact. Those claims require reviewed static evidence or fresh provenance-preserving dynamic analytical evidence as appropriate.

Raw corpus content is operational data. It belongs in PostgreSQL and must not be committed to Git, exported into repository fixtures, or printed in normal diagnostics.

## Sources and lifecycle

The fixed first-party sources are:

- `ethplorer`, user ID `866192511038922753`;
- `binplorer`, user ID `1565037191214030853`.

The command uses the read-only X User Posts endpoint and does not exclude replies or reposts. With no checkpoint, it follows `next_token` backwards until X exhausts the retrievable window or a guard stops the source. With a checkpoint, it sends `since_id` and normally retrieves only newer Posts. The source keys are:

- `first_party_x_ethplorer`;
- `first_party_x_binplorer`.

One source can complete and advance independently when the other source fails. A page, cost, response-shape, persistence, or request guard that leaves primary pagination incomplete preserves fetched rows and usage but does not advance that source checkpoint. Resource-level partial errors remain explicit warnings: unavailable direct referenced resources are not treated as irrelevant and do not invalidate an otherwise exhausted primary timeline window.

Run a bounded sync explicitly:

```sh
python -m x_signal_finder first-party-x sync --source ethplorer
python -m x_signal_finder first-party-x sync --source binplorer
python -m x_signal_finder first-party-x sync --source both
```

The defaults are five pages per source, a `$1.00` estimated-cost guard, three attempts, and at most 60 seconds for one retry wait. User timeline pages always request up to 100 primary Posts. The approved historical validation used:

```sh
python -m x_signal_finder first-party-x sync \
  --source both \
  --max-pages 10 \
  --max-estimated-cost-usd 5.00
```

Normal execution never applies migrations automatically. Apply migration 003 explicitly before the first sync.

## Storage contract

Migration `003_first_party_x_corpus.sql` creates:

- `first_party_x_posts` - one authoritative row per first-party X Post;
- `first_party_x_post_references` - an ordered, lossless set of direct reply, quote, and repost relationships.

Both tables have Row Level Security enabled with the same protected-connection model as the existing operational tables. `first_party_x_posts` is separate from incoming `posts` and uses `post_id` as its primary key. Upsert refreshes authoritative X content and last-seen values while preserving `first_seen_run_id`, `first_collected_at`, `publication_origin`, and `opportunity_id`.

`publication_origin` defaults to `unknown`. The optional values `manual` and `pipeline_assisted` are set only from known provenance. Task 005C performs no text-similarity or fuzzy Opportunity matching. `opportunity_id` remains nullable.

Long-form text prefers `note_tweet.text` and otherwise uses `text`. Original X fields remain in `raw_json`. The mapper stores returned main media metadata and every direct relationship, including its type, referenced ID, returned full text, author identity, creation time, entities, and media metadata. Each relationship has `available` or `unavailable` context state. A Post without a relationship uses `not_applicable` at Post level. Missing context is never guessed.

No image, video, GIF, audio, preview, subtitle, or other media blob is downloaded.

## Direct reference completion

After primary pagination, the synchronizer deduplicates direct referenced Post IDs that were not returned through expansions. It may query those IDs in bounded batches through the read-only Post Lookup endpoint while sharing the same cost guard. It does not recursively request references of referenced Posts and does not crawl unrelated thread history. A failed or partial completion lookup leaves the direct context explicitly `unavailable`.

## Usage and safe diagnostics

The synchronizer reuses `runs`, `usage_events`, and `sync_state`. Operations are recorded separately as:

- `first_party_x_inventory_lookup`;
- `first_party_x_sync_ethplorer`;
- `first_party_x_sync_binplorer`.

The configured estimates default to `$0.005` per distinct returned Post resource and `$0.010` per returned User resource. These are planning estimates, not Developer Console billing statements. Primary, expanded, reference-completion, media, User, and request counts remain distinct in metadata. Post IDs are deduplicated across Post-resource response sections for the source run. `reported_cost` remains NULL until reconciled externally.

CLI output contains counts, timestamps, IDs, checkpoints, estimated cost, warning codes, and safe error categories only. It never contains Post text, raw response bodies, authorization headers, or tokens.

## Live validation record

The successful historical validation refreshed account-level inventory values of 352 for Ethplorer and 39 for Binplorer. The retrievable corpus contains:

- Ethplorer - 339 Posts: 156 originals, 121 replies, 24 quotes, and 38 reposts; 166 available and 16 unavailable direct relationship contexts; 171 returned media resources; range 2017-05-21 through 2026-07-23;
- Binplorer - 39 Posts: 14 originals, 11 replies, 2 quotes, and 12 reposts; 21 available and 1 unavailable direct relationship contexts; 27 returned media resources; range 2022-10-13 through 2026-07-16.

The 13-Post difference between the Ethplorer inventory count and retrievable corpus is recorded as a retrieval difference, not asserted data loss or an implementation error. Binplorer's inventory and retrievable count were equal.

The successful historical run made eight requests and recorded a `$2.650` estimate, including one batched User Lookup. A preceding validation attempt made five requests and recorded `$0.905`; it exposed an overly strict treatment of resource-level partial errors, saved its 132 returned Posts, and advanced no checkpoint. The corrected successful run upserted those rows without duplicates. The repeat incremental validation then made two timeline requests, received zero Posts, recorded `$0.000` estimated Post-resource cost, and left both checkpoints unchanged.

PostgreSQL ended with 378 corpus rows, 378 distinct Post IDs, and zero duplicate groups. The separate incoming `posts` table remained at 214 rows and 214 distinct IDs. Migration 003 is current, no migrations are pending, and all operational tables retain RLS.

## Boundaries

Task 005C does not implement keyword extraction, trigger phrases, a prefilter vocabulary, style-guide generation, embeddings, clustering, LLM analysis, relevance filtering, Signals, Opportunities, media download, X write access, scheduling, publication, the Task 005B capability review, or the dynamic analytics adapter.
