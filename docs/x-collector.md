# Stage 3 X Collector

Status: Tasks 004A and 004B complete; Stage 3 remains In Progress

Live validation date: 2026-08-06

Live validation fetched 21 home Posts across the required baseline and repeated runs, excluded 4 simple reposts, and saved 17 unique home rows. The stored rows included 13 original Posts, 2 replies, and 2 quote Posts. The repeated run reused and advanced the home checkpoint, and PostgreSQL contained 17 rows with 17 distinct Post IDs. The mentions request succeeded with an empty result and recorded an independent successful sync state. No Post text or raw response was printed or exported during validation.

Task 004B live validation applied migration 002 and confirmed PostgreSQL 17.6 healthy with migrations 1 and 2 current and operational-table RLS intact. The required long quote Post now stores 1,320 characters from `note_tweet.text` instead of the 319-character normal `text`, with returned referenced context and video metadata. The required short reply remains `unprocessed` and is marked only as a low-information review candidate. The checkpoint fingerprint did not change, first-seen values were preserved, and duplicate groups remained zero. Three bounded attempts used 78 X Post Reads at an estimated $0.390: two current-window attempts exposed time drift, and the final one-page checkpoint-anchored refresh validated both required Posts.

## Setup

The collector uses the existing standard PostgreSQL `DATABASE_URL`, X app client ID, localhost callback, and source user IDs from the ignored local `.env`. Run one interactive setup after creating the X app or whenever authorization is revoked:

```text
python -m x_signal_finder x-api oauth-setup
```

The command opens the official X authorization page, completes OAuth 2.0 Authorization Code with S256 PKCE, validates one refresh, and stores only `X_REFRESH_TOKEN` in local `.env`. It does not persist the access token. Later collection runs refresh automatically and replace a rotated refresh token before calling X.

## Bounded collection

Run the required Task 004A validation commands explicitly:

```text
python -m x_signal_finder collect --source home --max-pages 1 --max-results 20
python -m x_signal_finder collect --source home --max-pages 1 --max-results 20
python -m x_signal_finder collect --source mentions --max-pages 1 --max-results 20
```

The safe defaults are also one page and 20 Posts. `--source both` is available, but the required first validation uses separate commands so each result is easy to audit.

Home requests use `exclude=retweets`, and the mapper also rejects any returned Post whose `referenced_tweets` contains `type=retweeted`. Original Posts, replies, and quote Posts are retained. The command prints only a JSON summary containing the run ID, request and Post counts, excluded repost count, newest and oldest IDs, checkpoint before and after, estimated public Post-read cost, warnings, and safe error categories.

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

Later runs pass the saved checkpoint as `since_id`. A checkpoint advances only after the source response has been mapped and its Posts, usage event, and sync state are committed successfully. It does not advance when:

- an X request fails;
- a database write fails;
- an HTTP 200 response contains partial errors;
- pagination metadata is missing;
- duplicate Post IDs make completeness uncertain;
- the configured incremental page limit is reached while another page remains.

Task 004A does not implement full historical-window recovery. Operators must increase the explicit page limit and investigate warnings before relying on a stalled incremental checkpoint.

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

## Deferred after Task 004B

Task 004B does not implement LLM filtering, Signals, clustering, Opportunities, drafts, Telegram, scheduling, GitHub Actions, automatic publication, automatic unfollow, X write access, complete historical backfill, media download or analysis, complex usage dashboards, compliance streams, periodic X Content revalidation, automated content deletion, protection or block-event handling, or production retention workflows.

The current `posts.source_key` column stores one source value per Post row. If the same Post later appears in both sources, the most recent upsert supplies the stored source value. Multi-source membership needs an evidence-backed schema decision in later Stage 3 work and is not introduced by Task 004A.
