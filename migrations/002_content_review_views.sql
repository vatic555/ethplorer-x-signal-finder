CREATE VIEW public.posts_review
WITH (security_invoker = true)
AS
SELECT
    p.post_id,
    CASE
        WHEN NULLIF(p.author_username, '') IS NOT NULL
            THEN 'https://x.com/' || p.author_username || '/status/' || p.post_id
        ELSE 'https://x.com/i/web/status/' || p.post_id
    END AS post_url,
    p.author_username,
    p.created_at,
    p.post_type,
    p.source_key,
    p.text,
    char_length(p.text) AS text_length,
    COALESCE(
        p.raw_json #>> '{_collector,full_text_source}',
        'text'
    ) AS full_text_source,
    GREATEST(
        COALESCE(media.expanded_media_count, 0),
        CASE
            WHEN jsonb_typeof(p.raw_json #> '{attachments,media_keys}') = 'array'
                THEN jsonb_array_length(p.raw_json #> '{attachments,media_keys}')
            ELSE 0
        END
    ) > 0 AS has_media,
    COALESCE(media.has_video, false) AS has_video,
    COALESCE(media.media_types, ARRAY[]::text[]) AS media_types,
    GREATEST(
        COALESCE(media.expanded_media_count, 0),
        CASE
            WHEN jsonb_typeof(p.raw_json #> '{attachments,media_keys}') = 'array'
                THEN jsonb_array_length(p.raw_json #> '{attachments,media_keys}')
            ELSE 0
        END
    ) AS media_count,
    p.referenced_post_id,
    CASE
        WHEN p.referenced_post_id IS NULL THEN NULL
        WHEN NULLIF(
            p.raw_json #>> '{_expanded,referenced_post_author,username}',
            ''
        ) IS NOT NULL THEN
            'https://x.com/'
            || (p.raw_json #>> '{_expanded,referenced_post_author,username}')
            || '/status/' || p.referenced_post_id
        ELSE 'https://x.com/i/web/status/' || p.referenced_post_id
    END AS referenced_post_url,
    p.raw_json #>> '{_expanded,referenced_post_author,username}'
        AS referenced_post_author_username,
    COALESCE(
        p.raw_json #>> '{_expanded,referenced_post,note_tweet,text}',
        p.raw_json #>> '{_expanded,referenced_post,text}'
    ) AS referenced_post_text,
    char_length(
        COALESCE(
            p.raw_json #>> '{_expanded,referenced_post,note_tweet,text}',
            p.raw_json #>> '{_expanded,referenced_post,text}'
        )
    ) AS referenced_post_text_length,
    (
        p.post_type = 'reply'
        AND char_length(trim(p.text)) <= 80
        AND normalized.normalized_text IN (
            '', 'thanks', 'thankyou', 'agreed', 'yes', 'this'
        )
    ) AS low_information_reply_candidate,
    p.processing_status,
    p.first_collected_at,
    p.last_collected_at
FROM public.posts AS p
LEFT JOIN LATERAL (
    SELECT
        count(*)::integer AS expanded_media_count,
        array_agg(DISTINCT item ->> 'type' ORDER BY item ->> 'type')
            FILTER (WHERE NULLIF(item ->> 'type', '') IS NOT NULL)
            AS media_types,
        bool_or((item ->> 'type') IN ('video', 'animated_gif')) AS has_video
    FROM jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(p.raw_json #> '{_expanded,media}') = 'array'
                THEN p.raw_json #> '{_expanded,media}'
            ELSE '[]'::jsonb
        END
    ) AS expanded_media(item)
) AS media ON true
CROSS JOIN LATERAL (
    SELECT lower(
        regexp_replace(
            regexp_replace(
                regexp_replace(
                    p.text,
                    'https?://[^[:space:]]+',
                    '',
                    'gi'
                ),
                '@[_[:alnum:]]+',
                '',
                'g'
            ),
            '(^|[[:space:]])(ft|cc|h/t)([[:space:]]|$)',
            '',
            'gi'
        )
    ) AS without_attribution
) AS stripped
CROSS JOIN LATERAL (
    SELECT regexp_replace(
        stripped.without_attribution,
        '[^[:alnum:]]+',
        '',
        'g'
    ) AS normalized_text
) AS normalized;

COMMENT ON VIEW public.posts_review IS
    'Manual review view only. Flags do not change Post status or checkpoints.';

CREATE VIEW public.author_source_stats
WITH (security_invoker = true)
AS
SELECT
    source_post.author_id,
    p.author_username,
    count(*)::bigint AS observed_posts,
    count(*) FILTER (WHERE p.post_type = 'original')::bigint AS original_posts,
    count(*) FILTER (WHERE p.post_type = 'quote')::bigint AS quote_posts,
    count(*) FILTER (WHERE p.post_type = 'reply')::bigint AS reply_posts,
    count(*) FILTER (
        WHERE p.low_information_reply_candidate
    )::bigint AS low_information_reply_candidates,
    count(*) FILTER (
        WHERE p.text ~* (
            '(^|[^[:alnum:]_])'
            || '(ethereum|evm|blockchain|crypto|bitcoin|token|stablecoin|wallet|'
            || 'onchain|smart[[:space:]]+contract|explorer|api|bnb|base|arbitrum|'
            || 'optimism|polygon|avalanche|solana|layer[[:space:]]*2|l2|web3|'
            || 'defi|nft)'
            || '([^[:alnum:]_]|$)'
        )
    )::bigint AS blockchain_keyword_matches,
    round(
        count(*) FILTER (
            WHERE p.text ~* (
                '(^|[^[:alnum:]_])'
                || '(ethereum|evm|blockchain|crypto|bitcoin|token|stablecoin|'
                || 'wallet|onchain|smart[[:space:]]+contract|explorer|api|bnb|'
                || 'base|arbitrum|optimism|polygon|avalanche|solana|'
                || 'layer[[:space:]]*2|l2|web3|defi|nft)'
                || '([^[:alnum:]_]|$)'
            )
        )::numeric / NULLIF(count(*), 0),
        4
    ) AS keyword_match_ratio,
    min(p.created_at) AS first_observed_at,
    max(p.created_at) AS last_observed_at,
    round(
        (extract(epoch FROM (max(p.created_at) - min(p.created_at))) / 86400)::numeric,
        2
    ) AS observation_span_days,
    round((count(*) * 0.005)::numeric, 3)
        AS estimated_stored_post_cost_usd
FROM public.posts_review AS p
JOIN public.posts AS source_post ON source_post.post_id = p.post_id
WHERE p.source_key = 'x_home_timeline'
GROUP BY source_post.author_id, p.author_username;

COMMENT ON VIEW public.author_source_stats IS
    'Stored home Post statistics. Keyword matches are a coarse manual-review heuristic, not AI relevance.';

CREATE VIEW public.author_unfollow_candidates
WITH (security_invoker = true)
AS
SELECT
    author_username AS username,
    observed_posts,
    observation_span_days,
    blockchain_keyword_matches,
    estimated_stored_post_cost_usd,
    first_observed_at,
    last_observed_at
FROM public.author_source_stats
WHERE blockchain_keyword_matches = 0
  AND (observed_posts >= 20 OR observation_span_days >= 7)
ORDER BY observed_posts DESC, estimated_stored_post_cost_usd DESC;

COMMENT ON VIEW public.author_unfollow_candidates IS
    'Candidates for manual owner review only. This view performs no X write or unfollow action.';

REVOKE ALL ON public.posts_review FROM PUBLIC;
REVOKE ALL ON public.author_source_stats FROM PUBLIC;
REVOKE ALL ON public.author_unfollow_candidates FROM PUBLIC;
