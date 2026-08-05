# Task 004A X Collector

Status: Task 004A complete; bounded Stage 3 viability collector

Live validation date: 2026-08-06

Live validation fetched 21 home Posts across the required baseline and repeated runs, excluded 4 simple reposts, and saved 17 unique home rows. The stored rows included 13 original Posts, 2 replies, and 2 quote Posts. The repeated run reused and advanced the home checkpoint, and PostgreSQL contained 17 rows with 17 distinct Post IDs. The mentions request succeeded with an empty result and recorded an independent successful sync state. No Post text or raw response was printed or exported during validation.

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

## View Posts in Supabase

1. Open the Supabase project.
2. Open Table Editor and select the `public.posts` table.
3. Show `post_id`, `author_username`, `created_at`, `post_type`, `source_key`, `text`, `first_seen_run_id`, `last_seen_run_id`, and `last_collected_at`.
4. Sort `created_at` descending.
5. Filter `source_key` with equals `x_home_timeline` for home or equals `x_ethplorer_mentions` for mentions.

Use the Supabase SQL Editor for a compact review:

```sql
SELECT
    post_id,
    author_username,
    created_at,
    post_type,
    source_key,
    text
FROM posts
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

## Deferred after Task 004A

Task 004A does not implement LLM filtering, Signals, clustering, Opportunities, drafts, Telegram, scheduling, GitHub Actions, browser review, automatic publication, complete historical backfill, complex usage dashboards, compliance streams, periodic X Content revalidation, automated content deletion, protection or block-event handling, or production retention workflows.

The current `posts.source_key` column stores one source value per Post row. If the same Post later appears in both sources, the most recent upsert supplies the stored source value. Multi-source membership needs an evidence-backed schema decision in later Stage 3 work and is not introduced by Task 004A.
