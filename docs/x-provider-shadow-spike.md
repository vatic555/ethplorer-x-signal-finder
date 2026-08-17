# Task 004D - X Provider Shadow Quality Spike

Status: Task 004D completed with incomplete provider runs; Task 004D.2 zero-cost runner correction completed

## Purpose

Task 004D compares TwitterAPI.io and SocialData with one approximately 24-hour Official X home-timeline benchmark. It is a read-only quality and cost spike, not production provider integration.

Official X remains the production source. The normal shadow run does not import third-party content into PostgreSQL, write `posts`, update `sync_state`, change the existing collector, create provider fallback, or schedule collection. A separate confirmation-gated offline recovery command exists only for the 11 already-paid Official X pages retained by the failed 2026-08-14 run. It reuses the production Post mapping and never contacts X or advances `sync_state`.

## Provider and Pricing References

- Official X reverse chronological home timeline: <https://docs.x.com/x-api/users/get-timeline>
- Official X pay-per-use pricing: <https://docs.x.com/x-api/getting-started/pricing>
- TwitterAPI.io Advanced Search: <https://docs.twitterapi.io/api-reference/endpoint/tweet_advanced_search>
- TwitterAPI.io account credit balance: <https://docs.twitterapi.io/api-reference/endpoint/get_my_info>
- SocialData Search API: <https://docs.socialdata.tools/reference/get-search-results/>
- SocialData pricing: <https://docs.socialdata.tools/getting-started/pricing/>

The spike uses the documented estimates current on 2026-08-14:

- Official X - $0.005 per distinct Post or Media resource and $0.010 per User resource returned for the benchmark estimate; Developer Console and daily resource deduplication remain authoritative.
- TwitterAPI.io Advanced Search - $0.00015 per returned Post, with a documented $0.00015 minimum charge per request.
- SocialData Search - $0.0002 per returned Post; empty requests above the documented fair-use allowance may also cost $0.0002.

The hard Task 004D ceiling is $0.10 for each third-party provider. The CLI rejects a higher configured limit. Task 004D.2 no longer performs automatic balance calls or rate-limit retries: neither may add an unplanned external request. Cost is planned by reserving the provider's maximum 20-result page before every search request. HTTP 402 becomes `incomplete_due_to_credit` and does not automatically fail provider quality.

## Mandatory Cost Preflight for Any Future Run

The completed live result does not authorize another provider request. Before any future usage-based call, prepare a zero-cost preflight that shows the provider and endpoint, purpose, expected requests and billable resources, unit price, expected cost, conservative maximum cost, and the technical hard guard that prevents spending above that maximum. Stop and wait for explicit approval of that exact ceiling. Unknown pricing requires separate approval of an experiment with a technically enforced hard dollar cap.

Do not purchase a fresh Official X benchmark when suitable data already exists locally. Inspect the current 1,040 incoming Official X Posts in PostgreSQL and ignored approved runtime artifacts first. Third-party validation must begin with approximately 20 to 50 Posts or the smallest useful window needed to test schema, full text, quotes and replies, and pagination. A larger comparison requires a new preflight and approval. Pages, time window, Posts, retries, and provider calls may not expand beyond the approved ceiling.

After an approved paid run, report the planned maximum, actual requests and resources, estimated or known spend, variance from plan, and whether the run produced enough evidence.

## Local Configuration

Only local `.env` or process environment values may contain credentials:

```dotenv
TWITTERAPI_IO_API_KEY=
SOCIALDATA_API_KEY=
```

`.env.example` contains empty placeholders only. The command checks the selected provider keys before making a provider request.

## Commands

These two commands are zero-cost. They read only the existing PostgreSQL benchmark and do not load provider credentials or call Official X, TwitterAPI.io, or SocialData:

```sh
python -m x_signal_finder x-provider-shadow plan-discovery \
  --hours 24 --max-provider-spend-usd 0.10

python -m x_signal_finder x-provider-shadow plan-direct-id \
  --hours 168 --limit 50 --max-provider-spend-usd 0.02
```

The live discovery command is blocked unless its exact combined plan SHA-256 has been separately approved. This is an operating reference only and must not be executed from Task 004D.2:

```sh
python -m x_signal_finder x-provider-shadow run \
  --hours 24 \
  --max-provider-spend-usd 0.10 \
  --approved-provider-plan-sha256 APPROVED_PLAN_SHA256
```

Raw responses and the local safe summary are written under `data/runtime/x-provider-shadow/<run-id>/`. That tree is ignored by Git. CLI output and committed documentation contain aggregate metrics and never contain Post text, raw provider payloads, or credentials.

Task 004D.2 discovery accepts only the stored Official X benchmark. Fresh Official X retrieval is disabled in this runner. The earlier standalone Official X safeguard still makes successful pages and `partial-summary.json` durable, but buying a new benchmark is outside this correction and requires a separate task and preflight.

## Normalized Comparison Contract

Every adapter terminates in the same local shadow-only contract:

- canonical X `post_id`;
- author and optional author ID;
- UTC `created_at`;
- full text;
- `original`, `reply`, `quote`, or `repost`;
- `conversation_id`;
- direct `referenced_post_id`;
- direct referenced Post author, timestamp, text, and media when returned;
- main Post media metadata;
- provider identifier: `official_x`, `twitterapi_io`, or `socialdata`.

This contract is not wired into production collection. The future `x_followset` is a separate logical source from `x_home_timeline`. Canonical deduplication uses X `post_id`; provider cursors remain local diagnostics and cannot become the only portable checkpoint.

## Search Strategy

The Official X benchmark defines the exact UTC window and the authors who actually appeared in that home timeline. Third-party Advanced Search requests are restricted to those active authors and the same timestamps.

Each initial search task contains one active benchmark author. Lower-volume benchmark authors run first. The two providers then use separate traversal methods:

- TwitterAPI.io does not treat one Advanced Search page as complete. `has_next_page`, an explicit incompleteness signal, or a full 20-result page causes the exact UTC interval to be divided into two non-overlapping halves. Both halves must complete. Splitting stops at the configured minimum time slice; overflow there yields `incomplete_due_to_minimum_time_slice`. Repeated windows are blocked, and all parent and child results are deduplicated by canonical `post_id`. Advanced Search cursor state is not the canonical mechanism.
- SocialData does not inherit the TwitterAPI.io algorithm. It follows `next_cursor` while it advances. If a page can still be incomplete but supplies no valid cursor, it continues with a decreasing `max_id` while retaining the same time query and optional `since_id`. Repeated cursor, repeated `max_id`, repeated page state, missing continuation, or exhaustion of the approved request cap yields an explicit incomplete status.

Before every request, both strategies reserve a full 20-result page. There are no automatic retries and the configured hard cap never increases. Raw pages remain local and ignored; provider traversal state never becomes production `sync_state`.

## Task 004D.2 Zero-Cost Preflight Examples

The current stored 24-hour benchmark contains 826 Posts from 132 authors. With the unchanged $0.10 cap per provider, discovery is blocked before credentials or an external request:

| Provider | Strategy | Initial requests | Expected max resources | Expected cost | Hard-cap requests/resources | Conservative maximum | Fits cap |
|---|---|---:|---:|---:|---:|---:|---:|
| TwitterAPI.io | recursive author-window time slicing | 132 | 2,640 | $0.39600 | 33 / 660 | $0.09900 | No |
| SocialData | cursor, then `max_id` fallback | 132 | 2,640 | $0.5280 | 25 / 500 | $0.1000 | No |

The zero-cost combined discovery plan SHA-256 was `f0f85fecbfe9500f86fd563ef1c526a86e9514c0def1567d6b042bc51f51693a`. It is evidence only, not an approval request, and `all_plans_fit_hard_caps=false` makes it non-executable even if copied to the live command.

The planning-only 50-ID benchmark uses existing PostgreSQL data and deliberately includes long Posts, replies, quotes, returned reference context, and media. It selected 50 IDs from 35 authors: 39 long Posts, 23 replies, 25 quotes, 48 with referenced context, and 38 with media.

| Provider | Planned ID batches | Expected resources | Expected cost | Conservative maximum | Hard cap |
|---|---:|---:|---:|---:|---:|
| TwitterAPI.io | 3 | 50 | $0.00750 | $0.00900 | $0.02 |
| SocialData | 3 | 50 | $0.0100 | $0.0120 | $0.02 |

The direct-ID combined plan SHA-256 was `cae638973f8a3102440b57a94cd37956038917d90400c9b2b135e3071c0a8b14`. Direct-ID provider endpoints and pricing still require verification, so API execution is intentionally not implemented. Offline fixture comparison already reports availability, exact and full text, long-Post fidelity, reply and quote types, referenced context, and media by canonical `post_id`.

## Comparison

For each third-party provider, the safe report records:

- raw and unique Posts returned;
- matched, missing, and extra canonical IDs;
- overall recall;
- exact full-text match rate;
- long-Post recall and truncation or mismatch count;
- type accuracy and recall by original, reply, quote, and repost;
- referenced-ID correctness and referenced-context text coverage;
- media coverage for matched benchmark Posts;
- author, timestamp, conversation, and reference field loss;
- duplicate rows and pagination-gap signals;
- request count;
- estimated and provider-reported spend when available;
- explicit systematic-loss flags.

Extra Posts are reported but do not count against recall because author search may return public Posts that did not appear in the personalized Official X home timeline.

The initial acceptance hypothesis is 90-95% overall recall, 100% exact full text among matched Posts, stable canonical IDs, no systematic long-Post, reply, or quote loss, and materially lower spend than Official X. Relevant-Post recall remains a separate and more important later test after Task 006 produces real relevance decisions.

## Live Result

Completed on 2026-08-14 against the same stored Official X `x_home_timeline` window from `2026-08-06T12:01:06Z` through `2026-08-07T12:01:06Z`. The first fresh Official X attempt did not fail before retrieving data: 11 paid pages returned successfully, containing 1,082 primary Posts. The subsequent twelfth request returned HTTP 402. Because the original runner propagated that terminal error before constructing a benchmark result, the third-party comparison was then run against the already-collected 192-Post PostgreSQL window from 71 active authors. That comparison benchmark contained 112 original Posts, 40 replies, 40 quotes, 33 long Posts, 80 Posts with a direct reference, and 85 with media.

The 11 ignored local pages contain 1,082 unique primary Posts, 596 unique expanded Posts, 408 unique Users, and 761 unique Media resources. The owner-reported X Developer Console result for this failed fresh attempt is 1,133 Post Reads and $5.665. The local resource inventory is provenance evidence, not a reconstruction of X daily billing deduplication. The earlier statement that the fresh attempt incurred zero incremental X spend was incorrect; only the later PostgreSQL benchmark reuse incurred zero additional Official X spend.

| Metric | TwitterAPI.io | SocialData |
|---|---:|---:|
| Status | `incomplete_due_to_credit` | `incomplete_due_to_budget` |
| Requests | 180 across bounded attempts | 247 |
| Raw / unique Posts | 537 / 249 | 404 / 68 |
| Matched benchmark IDs | 25 | 11 |
| Missing / extra IDs | 167 / 224 | 181 / 57 |
| Recall | 13.02% | 5.73% |
| Exact full text on matches | 24/25 - 96.0% | 11/11 - 100% |
| Long-Post recall | 3/33 - 9.09% | 0/33 - 0% |
| Exact text on matched long Posts | 3/3 - 100% | not measurable |
| Original / reply / quote recall | 19.64% / 2.5% / 5.0% | 9.82% / 0% / 0% |
| Type accuracy on matches | 100% | 100% |
| Referenced-context text coverage | 2/3 - 66.67% | no referenced match |
| Media coverage on matched media Posts | 16/16 - 100% | 11/11 - 100% |
| Duplicate rows across requests | 288 | 336 |
| Pagination-gap signals | 129 | 168 |
| Spend | $0.09975 actual | $0.0966 conservative estimate; actual unavailable |
| Observed response span | 1423.33 s across all attempts; final broad pass 112.08 s | 238.55 s |

The one TwitterAPI.io text mismatch was a quote: the provider returned 14 characters while the stored Official X text contained 38 characters including an appended URL. It was not a long-Post truncation, but it fails the strict 100% full-text requirement. Author, timestamp, conversation ID, and referenced Post ID had no mismatch on matched Posts for either provider.

Neither provider is accepted. TwitterAPI.io produced the larger sample and higher observed recall, but its trial ended incomplete, full-text exactness was below 100%, and reply/quote recall was materially weak. SocialData also ended incomplete and returned no matched long Posts, replies, or quotes. Because both runs were limited by trial budget or credit and had large pagination gaps, their low recall is not treated as a definitive provider quality failure. Official X remains the production source. No SocialData Monitoring experiment is promoted from this result.

Before and after the spike, PostgreSQL remained at 214 `posts`, 378 `first_party_x_posts`, and four `sync_state` rows. The serialized `sync_state` SHA-256 stayed `92646163dc70d3888c0fa1f981a1af725c5cd3f5f836211c3d4cc7b32990df53`.

## Offline Recovery Aftermath

The retained Official X pages are recoverable without another external request. The recovery path validates every saved page with the existing X content parser, aggregates returned Users, referenced Posts, and Media across pages, applies the production `map_x_post` contract, excludes simple reposts, deduplicates by canonical `post_id`, and compares candidate IDs with PostgreSQL before any write.

The 2026-08-17 read-only dry-run produced:

- raw primary Posts: 1,082;
- valid primary Posts: 1,082;
- invalid primary Posts: 0;
- simple reposts excluded: 256;
- valid mapped Posts: 826;
- duplicates already in `posts`: 0;
- unique new Posts ready to insert: 826;
- artifact manifest SHA-256: `85a70f069262451a275f626209ed3836e4eb2fcdfa6b93cb20a94d221566b00d`.

The dry-run wrote neither PostgreSQL nor `sync_state` and made zero external API requests. The owner approved this exact manifest, and the atomic apply completed on 2026-08-17 as recovery run `029a02d5-28e3-44b2-aa19-db027c529c9c`. It created an `incomplete_recovered` audit outcome represented by database status `completed_with_warnings`, inserted 826 Posts through the existing production mapping, and stored the recovery provenance on all 826 rows. The `posts` table increased from 214 to 1,040 rows with 1,040 distinct IDs. Historical usage records 11 successful paid requests, 1,133 owner-reported Post Reads, and $5.665 reported cost; external requests during recovery are zero.

The four `sync_state` rows were unchanged. Their verification SHA-256 was `575476c6591871422c1249dc68f56f28507ff1d13792778f36b13a07ef6b5454` both immediately before and after apply. No X or third-party request occurred during dry-run, apply, or verification.

## Future SocialData Monitoring Experiment

If a future separately authorized test supplies stronger SocialData evidence, the next possible optimization experiment remains:

```text
grouped Search Query Monitors
  -> webhook
  -> Normalized Post
```

That experiment is not implemented by Task 004D. It must group followed authors, attempt broad Post capture without keyword pre-filtering, and leave relevance decisions to the project's own LLM pipeline. It must not create approximately 370 permanent User Monitors. Monitoring, webhooks, scheduling, provider switching, fallback, and polling replacement require a separate explicit task and cost controls.
