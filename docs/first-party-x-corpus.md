# First-Party X Editorial Corpus

Status: Tasks 005C, 005C.1, and 005C.2 complete; Stage 4 remains In Progress

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

Normal execution never applies migrations automatically. Apply migrations 003 and 004 explicitly before a future sync.

## Storage contract

Migration `003_first_party_x_corpus.sql` creates:

- `first_party_x_posts` - one authoritative row per first-party X Post;
- `first_party_x_post_references` - an ordered, lossless set of direct reply, quote, and repost relationships.

Both tables have Row Level Security enabled with the same protected-connection model as the existing operational tables. `first_party_x_posts` is separate from incoming `posts` and uses `post_id` as its primary key. Upsert refreshes authoritative X content and last-seen values while preserving `first_seen_run_id`, `first_collected_at`, `publication_origin`, and `opportunity_id`.

Migration `004_first_party_x_review_fields.sql` adds relational `unavailable_reason` to each direct reference. Available context requires a NULL reason. Unavailable context requires `not_found`, `protected_or_inaccessible`, `api_unavailable`, or `unknown`. The 17 historical unavailable rows were backfilled as `unknown` without another X request. Future sync persistence writes the safe parser reason while retaining the existing JSON audit representation.

Migration 004 also adds two protected security-invoker review views:

- `first_party_x_post_urls` - one row per deduplicated stored URL entity from both main and `note_tweet` entities, including original, expanded, unwound, resolved, hostname, first-party-site, and article-path fields;
- `first_party_x_posts_review` - one row per first-party Post with canonical text, provenance, reference state, resolved URL arrays, article URL arrays, and counts for convenient Supabase inspection.

`publication_origin` defaults to `unknown`. The optional values `manual` and `pipeline_assisted` are set only from known provenance. Task 005C performs no text-similarity or fuzzy Opportunity matching. `opportunity_id` remains nullable.

`first_party_x_posts.text` is the canonical field for downstream first-party corpus analysis. It contains `note_tweet.text` when X returned it and normal `text` only as fallback. `raw_json.text` may be truncated and must not be the default analysis field. Original X fields remain in `raw_json`, and Task 005C.1 does not rewrite any stored authoritative text.

The mapper stores returned main media metadata and every direct relationship, including its type, referenced ID, returned full text, author identity, creation time, entities, and media metadata. Each relationship has `available` or `unavailable` context state. When X returns a resource-specific error for an unavailable referenced ID, the relationship may retain only a compact category: `not_found`, `protected_or_inaccessible`, `api_unavailable`, or `unknown`. Raw error response bodies are neither stored nor printed. Existing unavailable relationships are not re-fetched merely to classify them and may therefore remain `unknown`. A Post without a relationship uses `not_applicable` at Post level. Missing context is never guessed and never treated as irrelevant.

No image, video, GIF, audio, preview, subtitle, or other media blob is downloaded.

## Direct reference completion

After primary pagination, the synchronizer deduplicates direct referenced Post IDs that were not returned through expansions. It may query those IDs in bounded batches through the read-only Post Lookup endpoint while sharing the same cost guard. It does not recursively request references of referenced Posts and does not crawl unrelated thread history. A failed or partial completion lookup leaves the direct context explicitly `unavailable`.

## Deterministic URL reads

Authoritative text remains unchanged and may contain `t.co` links. Downstream readers use the stored X entity fields without an HTTP redirect crawl or another X request. For every stored URL entity the reusable read contract selects:

```text
unwound_url
else expanded_url
else url
```

The helper reads both the stored main `entities` object and `raw_json.note_tweet.entities` when present, removes duplicate representations within one Post, and returns the original and resolved values plus the selected source. It performs no network I/O.

The PostgreSQL URL view uses the same precedence. It flags Ethplorer and Binplorer hostnames directly from the resolved destination and marks `is_article_url` only for deterministic Ethplorer `/posts/...` paths currently present in the corpus. It does not infer links from Post text, crawl redirects, or map an article URL to a static knowledge `source_id`. Exact URL-to-source mapping is reserved for Task 005D.

## Usage and safe diagnostics

The synchronizer reuses `runs`, `usage_events`, and `sync_state`. Operations are recorded separately as:

- `first_party_x_inventory_lookup`;
- `first_party_x_sync_ethplorer`;
- `first_party_x_sync_binplorer`.

The configured standard estimates default to `$0.005` per returned Post resource, `$0.010` per returned User resource, and `$0.005` per returned Media resource. These are planning estimates, not Developer Console billing statements. Each source usage event retains distinct primary, expanded, reference-completion, total Post, expansion or lookup User, Media, and request counts, with separate Post, User, Media, and total estimated costs. Inventory User resources remain in their own usage event. Post IDs are deduplicated across Post-resource response sections for the source run. The cost guard uses the conservative full estimated total across all applicable resource classes. `reported_cost` remains NULL until reconciled externally.

CLI output contains counts, timestamps, IDs, checkpoints, estimated cost, warning codes, and safe error categories only. It never contains Post text, raw response bodies, authorization headers, or tokens.

## Live validation record

The successful historical validation refreshed account-level inventory values of 352 for Ethplorer and 39 for Binplorer. The retrievable corpus contains:

- Ethplorer - 339 Posts: 156 originals, 121 replies, 24 quotes, and 38 reposts; 166 available and 16 unavailable direct relationship contexts; 171 returned media resources; range 2017-05-21 through 2026-07-23;
- Binplorer - 39 Posts: 14 originals, 11 replies, 2 quotes, and 12 reposts; 21 available and 1 unavailable direct relationship contexts; 27 returned media resources; range 2022-10-13 through 2026-07-16.

The 13-Post difference between the Ethplorer inventory count and retrievable corpus is recorded as a retrieval difference, not asserted data loss or an implementation error. Binplorer's inventory and retrievable count were equal.

The successful historical run made eight requests and recorded a `$2.650` estimate, including one batched User Lookup. A preceding validation attempt made five requests and recorded `$0.905`; it exposed an overly strict treatment of resource-level partial errors, saved its 132 returned Posts, and advanced no checkpoint. The corrected successful run upserted those rows without duplicates. The repeat incremental validation then made two timeline requests, received zero Posts, recorded `$0.000` estimated Post-resource cost, and left both checkpoints unchanged. These historical values were produced by the previous accounting implementation and are not retroactively presented as corrected Post, User, and Media totals.

On 2026-08-14 the observed X Developer Console remaining balance was USD 5.12. It is a forward reconciliation baseline only: no reliable immediately-before balance exists, so it must not be used to infer Task 005C actual cost. For a future explicitly approved live X validation, where practical record `balance_before`, run identity, `balance_after`, and `observed_delta`. Actual observed billing remains separate from internal estimated usage.

PostgreSQL ended with 378 corpus rows, 378 distinct Post IDs, and zero duplicate groups. The separate incoming `posts` table remained at 214 rows and 214 distinct IDs.

Task 005C.1 validated deterministic URL reads against the unchanged 378-row corpus without an X request. The corpus contains 232 Posts with URL entities and 348 deduplicated URL entities: 343 include `expanded_url`, 62 include `unwound_url`, and 4 remain `t.co`-only after deterministic resolution. Resolved destinations include 81 Ethplorer and 22 Binplorer site URLs. PostgreSQL integration tests passed, both first-party checkpoints remained unchanged, and the separate incoming table remained at 214 rows.

Task 005C.2 applied migration 004 without an X request. PostgreSQL 17.6 is healthy with migrations 1 through 4 current, no pending migration, and RLS intact. All 17 existing unavailable references have relational reason `unknown`; no available reference has a reason. The URL view contains 348 rows across 232 Posts, including 81 Ethplorer URLs, 22 Binplorer URLs, and 8 deterministic Ethplorer article URLs. Both new views use `security_invoker=true`. The known Rich List destination `https://ethplorer.io/posts/ethereum-rich-list-by-aggregated-usd-holdings-part-1` is visible in both the URL view and the Post review view. The 378 first-party rows, 214 incoming rows, and both first-party checkpoints remain unchanged.

## Boundaries

Tasks 005C through 005C.2 do not implement keyword extraction, trigger phrases, a prefilter vocabulary, style-guide generation, embeddings, clustering, LLM analysis, relevance filtering, Signals, Opportunities, media download, X write access, scheduling, publication, reviewed capability extraction, URL-to-`source_id` mapping, or the dynamic analytics adapter. Reviewed Knowledge + Unified Prefilter Vocabulary remains the separate Task 005D direction.
