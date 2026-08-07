# Stage 3 X Collector

Status: Tasks 004A through 004C.1 complete; Stage 3 Completed

Live validation date: 2026-08-07

Live validation fetched 21 home Posts across the required baseline and repeated runs, excluded 4 simple reposts, and saved 17 unique home rows. The stored rows included 13 original Posts, 2 replies, and 2 quote Posts. The repeated run reused and advanced the home checkpoint, and PostgreSQL contained 17 rows with 17 distinct Post IDs. The mentions request succeeded with an empty result and recorded an independent successful sync state. No Post text or raw response was printed or exported during validation.

Task 004B live validation applied migration 002 and confirmed PostgreSQL 17.6 healthy with migrations 1 and 2 current and operational-table RLS intact. The required long quote Post now stores 1,320 characters from `note_tweet.text` instead of the 319-character normal `text`, with returned referenced context and video metadata. The required short reply remains `unprocessed` and is marked only as a low-information review candidate. The checkpoint fingerprint did not change, first-seen values were preserved, and duplicate groups remained zero. Three bounded attempts used 78 X Post Reads at an estimated $0.390: two current-window attempts exposed time drift, and the final one-page checkpoint-anchored refresh validated both required Posts.

Task 004C implements complete forward pagination with explicit page, global primary-Post, estimated-cost, retry-wait, and attempt guards. Its bounded live run received 20 primary and 17 expanded Posts, counted 30 distinct Post resources, saved 18 Posts after repost exclusion, recorded $0.150 estimated usage, and left the incomplete home checkpoint unchanged. The following guarded `both` run received 194 primary and 113 expanded Posts across two home requests, counted 272 distinct resources, saved 152 Posts including 134 new rows, and stopped at a $1.360 estimate. The permitted one-page cost overshoot occurred, home remained incomplete, and mentions was not requested. PostgreSQL then contained 201 rows with 201 distinct Post IDs and no duplicates.

Task 004C.1 manually accepted `2085449523904778414`, the validated newest first-page ID from that incomplete home run, as the new baseline. Acceptance used PostgreSQL only, made no X request, created no Posts, and preserved all 201 rows. One subsequent cheap incremental request from that checkpoint received 19 primary and 10 expanded Posts, counted 29 distinct resources, saved 13 new Posts after 6 repost exclusions, and estimated $0.145. The explicit one-page limit left the source incomplete, so its checkpoint correctly remained at the accepted baseline. PostgreSQL ended with 214 rows, 214 distinct Post IDs, and zero duplicates. This completed Stage 3 without historical backfill or another read of the skipped older window.

## Setup

The collector uses the existing standard PostgreSQL `DATABASE_URL`, X app client ID, localhost callback, and source user IDs from the ignored local `.env`. Run one interactive setup after creating the X app or whenever authorization is revoked:

```text
python -m x_signal_finder x-api oauth-setup
```

The command opens the official X authorization page, completes OAuth 2.0 Authorization Code with S256 PKCE, validates one refresh, and stores only `X_REFRESH_TOKEN` in local `.env`. It does not persist the access token. Later collection runs refresh automatically and replace a rotated refresh token before calling X.

## Incremental collection and guards

Normal manually initiated collection uses these defaults:

```text
python -m x_signal_finder collect --source both
```

The defaults are:

- `--max-pages 5` per source;
- `--max-results 100` primary Posts per API page;
- `--max-estimated-cost-usd 1.00` across the run;
- `--max-primary-posts-total` unset;
- `--max-attempts 3` per page;
- `--max-retry-wait-seconds 60` per retry wait.

With `--source both`, home runs before mentions. A configured primary-Post total is shared across the whole run. If home consumes it, mentions is not requested and reports `not_requested_due_to_primary_post_limit`. Expanded Posts do not count toward the primary limit but do count toward estimated cost.

The cheap validation mode is:

```text
python -m x_signal_finder collect --source home --max-pages 1 --max-results 20 --max-primary-posts-total 20 --max-estimated-cost-usd 0.15
```

Home requests use `exclude=retweets`, and the mapper also rejects any returned Post whose `referenced_tweets` contains `type=retweeted`. Original Posts, replies, and quote Posts are retained. The command prints only a JSON summary containing the run ID, primary, expanded, and distinct resource counts, excluded repost count, newest and oldest IDs, checkpoint before and after, completion state, estimated public Post-read cost, warnings, and safe error categories.

## Cost and usage accounting

`X_POST_READ_UNIT_COST_USD` defaults to `0.005` and can be overridden locally. For each source, distinct Post resources are the unique IDs from primary `data` and expanded `includes.tweets` across all successful pages. An ID returned more than once, or in both response sections, counts once. Estimated cost is distinct resources multiplied by the configured unit estimate. `reported_cost` remains NULL until reconciled with X Developer Console.

The cost guard decides whether another page may be requested. It is not an exact billing cap: an already completed page and its expansions are counted, so the final estimate may overshoot the guard by one page. Successful-response usage is committed in its own transaction before Post upsert. A later Post database failure therefore retains one best-effort usage event and never retries that insert automatically.

## Retry policy

The collector retries only connection failures, timeouts, HTTP 500, 502, 503, 504, and HTTP 429 when the required wait fits the configured bound. It prefers `Retry-After`, then the X rate-limit reset timestamp, then bounded exponential backoff. HTTP 400, 401, 403, malformed responses, invalid Post shapes, and configuration failures are not retried. Default tests replace sleep and transport with synthetic functions.

## Full text and expanded context

The collector requests `note_tweet` and stores `note_tweet.text` as `posts.text` when present. Otherwise it uses the normal `text`. It does not truncate content. Both original fields remain unchanged at the top level of `raw_json`, while `raw_json._collector.full_text_source` records `note_tweet` or `text`.

The content parser indexes `includes.tweets` and `includes.media` without exposing their content in diagnostics. For a quote or reply, the matching returned referenced Post is stored under `raw_json._expanded.referenced_post`; its returned author ID and username are stored under `referenced_post_author`. Matching media objects for the main Post are stored under `raw_json._expanded.media`. If `attachments.media_keys` exists but an object is missing, collection continues and `_collector.media_expansion_incomplete` is true. No additional context request or media download occurs.

## Refresh existing Posts

Use this only when explicitly refreshing a bounded recent window:

```text
python -m x_signal_finder collect --source home --max-pages 1 --max-results 20 --refresh-existing
```

This mode does not send `since_id`. When a stored checkpoint exists, it uses that value as `until_id` so the bounded request refreshes the last committed window instead of drifting to newer Posts. It never exceeds the explicit page limit and upserts by `post_id`. Existing `first_seen_run_id`, `first_collected_at`, processing and rejection state, availability state, and deletion timestamp remain unchanged. Content, expanded metadata, last-seen values, and last verification time are refreshed. The mode does not write `sync_state`, so its operational checkpoint remains unchanged. It is not automatic and is not a historical backfill.

## Checkpoint behavior

The source keys are:

- `x_home_timeline`
- `x_ethplorer_mentions`

The first bounded run intentionally establishes a current baseline instead of loading the complete historical window. If another page exists, the summary records `initial_history_not_backfilled` and may still save the newest observed ID as the baseline checkpoint.

Later runs pass the saved checkpoint as `since_id` and continue until `next_token` disappears. The candidate checkpoint is the newest ID from the first page. A checkpoint advances only after a complete source response has been mapped and its Posts, usage event, and sync state are committed successfully. It does not advance when:

- an X request fails;
- a database write fails;
- an HTTP 200 response contains partial errors;
- pagination metadata is missing;
- duplicate Post IDs make completeness uncertain;
- the configured page limit is reached while another page remains;
- the primary-Post or estimated-cost guard stops further pagination;
- retry exhaustion or an invalid Post shape makes the source incomplete;
- usage recording or Post persistence fails.

Home records `home_history_window_at_risk` after six days since the last successful collection and adds `home_history_window_may_be_lost` after seven days. These are risk warnings, not proof of data loss. Incomplete mentions pagination adds `mentions_history_may_be_truncated`. Automatic missed-window recovery is not implemented. Operators must adjust explicit guards and investigate warnings before relying on a stalled checkpoint.

## Explicit baseline acceptance

Use baseline acceptance only when an incomplete run has already saved a useful recent window and the operator explicitly chooses not to read its older remaining pages:

```text
python -m x_signal_finder collect accept-baseline --source home --run-id RUN_ID
python -m x_signal_finder collect accept-baseline --source home --run-id RUN_ID --confirm-skip-older-posts
```

The first form is a read-only preview. It prints a safe summary and exits without changing the checkpoint. The confirmed form validates the run, source, incomplete reason, and newest first-page ID, then updates only `sync_state` and audit metadata inside PostgreSQL. It does not initialize X configuration, refresh OAuth, call X, change existing Posts, create Posts, or delete data. The audit records the source run, previous and accepted checkpoints, incomplete reason, primary and saved counts, acceptance timestamp, `older_window_may_have_been_skipped=true`, and `manual_baseline_acceptance=true`. A failed run or a run without a valid newest ID cannot be accepted.

## Review Posts and authors in Supabase

1. Open the Supabase project.
2. Open Table Editor and select the `public.posts_review` view.
3. Show the Post link, full-text source, referenced context, media indicators, and collection timestamps.
4. Sort `created_at` descending.
5. Filter `source_key` with equals `x_home_timeline` for home or equals `x_ethplorer_mentions` for mentions.

The views added by migration 002 are:

- `public.posts_review` for direct Post links, full and referenced text, and media indicators;
- `public.author_source_stats` for stored home-timeline activity and a coarse blockchain keyword ratio;
- `public.author_unfollow_candidates` for accounts with zero keyword matches after at least 20 stored Posts or seven observed days.

The low-information reply and keyword fields are review heuristics only. They do not reject Posts, alter checkpoints, change processing status, or make a relevance decision. The unfollow list is only for a manual owner decision. The application has no X write scope and performs no unfollow action.

Use the Supabase SQL Editor for a compact review:

```sql
SELECT
    post_id,
    author_username,
    created_at,
    post_type,
    source_key,
    text
FROM posts_review
ORDER BY created_at DESC
LIMIT 100;
```

Count rows by source and verify global `post_id` deduplication:

```sql
SELECT source_key, count(*) AS row_count
FROM posts
GROUP BY source_key
ORDER BY source_key;

SELECT post_id, count(*) AS row_count
FROM posts
GROUP BY post_id
HAVING count(*) > 1;
```

The duplicate query must return zero rows. Inspect checkpoints with:

```sql
SELECT
    source_key,
    checkpoint_value,
    last_attempt_at,
    last_successful_at,
    last_warning_code
FROM sync_state
WHERE source_key IN ('x_home_timeline', 'x_ethplorer_mentions')
ORDER BY source_key;
```

## Deferred after Task 004C

Task 004C does not implement LLM filtering, knowledge-base runtime, Signals, clustering, Opportunities, drafts, Telegram, scheduling, GitHub Actions, automatic publication, automatic unfollow, X write access, historical backfill, automatic missed-window recovery, media download or analysis, complex usage dashboards, compliance streams, periodic X Content revalidation, automated content deletion, protection or block-event handling, or production retention workflows.

The current `posts.source_key` column stores one source value per Post row. If the same Post later appears in both sources, the most recent upsert supplies the stored source value. Multi-source membership needs an evidence-backed schema decision in later Stage 3 work and is not introduced by Task 004A.
