ALTER TABLE public.first_party_x_post_references
    ADD COLUMN unavailable_reason text;

UPDATE public.first_party_x_post_references
SET unavailable_reason = 'unknown'
WHERE context_state = 'unavailable';

ALTER TABLE public.first_party_x_post_references
    ADD CONSTRAINT first_party_x_post_references_unavailable_reason_check
    CHECK (
        (context_state = 'available' AND unavailable_reason IS NULL)
        OR (
            context_state = 'unavailable'
            AND unavailable_reason IN (
                'not_found',
                'protected_or_inaccessible',
                'api_unavailable',
                'unknown'
            )
        )
    );

CREATE VIEW public.first_party_x_post_urls
WITH (security_invoker = true)
AS
WITH url_entities AS (
    SELECT
        p.post_id,
        p.source_account,
        p.created_at,
        p.post_type,
        p.post_url,
        main_url.entity,
        0 AS source_order,
        main_url.ordinality AS entity_order
    FROM public.first_party_x_posts AS p
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(p.entities -> 'urls') = 'array'
                THEN p.entities -> 'urls'
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS main_url(entity, ordinality)

    UNION ALL

    SELECT
        p.post_id,
        p.source_account,
        p.created_at,
        p.post_type,
        p.post_url,
        note_url.entity,
        1 AS source_order,
        note_url.ordinality AS entity_order
    FROM public.first_party_x_posts AS p
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(
                p.raw_json #> '{note_tweet,entities,urls}'
            ) = 'array'
                THEN p.raw_json #> '{note_tweet,entities,urls}'
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS note_url(entity, ordinality)
), normalized AS (
    SELECT
        post_id,
        source_account,
        created_at,
        post_type,
        post_url,
        NULLIF(entity ->> 'url', '') AS original_url,
        NULLIF(entity ->> 'expanded_url', '') AS expanded_url,
        NULLIF(entity ->> 'unwound_url', '') AS unwound_url,
        source_order,
        entity_order
    FROM url_entities
), resolved AS (
    SELECT
        post_id,
        source_account,
        created_at,
        post_type,
        post_url,
        original_url,
        expanded_url,
        unwound_url,
        COALESCE(unwound_url, expanded_url, original_url) AS resolved_url,
        CASE
            WHEN unwound_url IS NOT NULL THEN 'unwound_url'
            WHEN expanded_url IS NOT NULL THEN 'expanded_url'
            ELSE 'url'
        END AS resolution_source,
        source_order,
        entity_order
    FROM normalized
    WHERE original_url IS NOT NULL
), deduplicated AS (
    SELECT DISTINCT ON (
        post_id,
        original_url,
        resolved_url,
        resolution_source
    )
        post_id,
        source_account,
        created_at,
        post_type,
        post_url,
        original_url,
        expanded_url,
        unwound_url,
        resolved_url,
        resolution_source
    FROM resolved
    ORDER BY
        post_id,
        original_url,
        resolved_url,
        resolution_source,
        source_order,
        entity_order
), parsed AS (
    SELECT
        deduplicated.*,
        rtrim(
            lower(
                substring(
                    resolved_url
                    FROM '^[[:alpha:]][[:alnum:]+.-]*://([^/:?#]+)'
                )
            ),
            '.'
        ) AS hostname
    FROM deduplicated
)
SELECT
    post_id,
    source_account,
    created_at,
    post_type,
    post_url,
    original_url,
    expanded_url,
    unwound_url,
    resolved_url,
    resolution_source,
    hostname,
    (
        hostname = 'ethplorer.io'
        OR hostname LIKE '%.ethplorer.io'
    ) AS is_ethplorer_url,
    (
        hostname = 'binplorer.com'
        OR hostname LIKE '%.binplorer.com'
    ) AS is_binplorer_url,
    (
        hostname = 'ethplorer.io'
        OR hostname LIKE '%.ethplorer.io'
        OR hostname = 'binplorer.com'
        OR hostname LIKE '%.binplorer.com'
    ) AS is_first_party_site_url,
    (
        lower(resolved_url)
        ~ '^https?://(www[.])?ethplorer[.]io/posts/[^/?#]+'
    ) AS is_article_url
FROM parsed;

COMMENT ON VIEW public.first_party_x_post_urls IS
    'Stored first-party X URL entities resolved without network access.';

CREATE VIEW public.first_party_x_posts_review
WITH (security_invoker = true)
AS
SELECT
    p.post_id,
    p.source_account,
    p.author_username,
    p.created_at,
    p.post_type,
    p.post_url,
    p.text,
    p.referenced_context_state,
    p.publication_origin,
    p.opportunity_id,
    COALESCE(
        url_summary.resolved_urls,
        ARRAY[]::text[]
    ) AS resolved_urls,
    COALESCE(
        url_summary.article_urls,
        ARRAY[]::text[]
    ) AS article_urls,
    COALESCE(url_summary.url_count, 0)::bigint AS url_count,
    COALESCE(url_summary.article_url_count, 0)::bigint AS article_url_count,
    p.first_collected_at,
    p.last_collected_at
FROM public.first_party_x_posts AS p
LEFT JOIN LATERAL (
    SELECT
        array_agg(DISTINCT u.resolved_url ORDER BY u.resolved_url)
            AS resolved_urls,
        array_agg(DISTINCT u.resolved_url ORDER BY u.resolved_url)
            FILTER (WHERE u.is_article_url) AS article_urls,
        count(*) AS url_count,
        count(*) FILTER (WHERE u.is_article_url) AS article_url_count
    FROM public.first_party_x_post_urls AS u
    WHERE u.post_id = p.post_id
) AS url_summary ON true;

COMMENT ON VIEW public.first_party_x_posts_review IS
    'Manual first-party corpus review with canonical text and stored resolved URLs.';

REVOKE ALL ON public.first_party_x_post_urls FROM PUBLIC;
REVOKE ALL ON public.first_party_x_posts_review FROM PUBLIC;
