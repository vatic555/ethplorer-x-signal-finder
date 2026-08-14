CREATE TABLE first_party_x_posts (
    post_id text PRIMARY KEY,
    source_account text NOT NULL,
    source_user_id text NOT NULL,
    author_id text,
    author_username text,
    post_url text NOT NULL,
    created_at timestamptz NOT NULL,
    conversation_id text,
    in_reply_to_user_id text,
    post_type text NOT NULL,
    text text NOT NULL,
    lang text,
    entities jsonb NOT NULL DEFAULT '{}'::jsonb,
    public_metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    media_metadata jsonb NOT NULL DEFAULT '[]'::jsonb,
    referenced_relationships jsonb NOT NULL DEFAULT '[]'::jsonb,
    referenced_context_state text NOT NULL,
    raw_json jsonb NOT NULL,
    publication_origin text NOT NULL DEFAULT 'unknown',
    opportunity_id uuid REFERENCES opportunities(opportunity_id) ON DELETE SET NULL,
    first_seen_run_id uuid NOT NULL REFERENCES runs(run_id),
    last_seen_run_id uuid NOT NULL REFERENCES runs(run_id),
    first_collected_at timestamptz NOT NULL,
    last_collected_at timestamptz NOT NULL,
    CONSTRAINT first_party_x_posts_source_account_check CHECK (
        source_account IN ('ethplorer', 'binplorer')
    ),
    CONSTRAINT first_party_x_posts_type_check CHECK (
        post_type IN ('original', 'reply', 'quote', 'repost')
    ),
    CONSTRAINT first_party_x_posts_context_state_check CHECK (
        referenced_context_state IN ('available', 'unavailable', 'not_applicable')
    ),
    CONSTRAINT first_party_x_posts_publication_origin_check CHECK (
        publication_origin IN ('unknown', 'manual', 'pipeline_assisted')
    ),
    CONSTRAINT first_party_x_posts_media_array_check CHECK (
        jsonb_typeof(media_metadata) = 'array'
    ),
    CONSTRAINT first_party_x_posts_relationships_array_check CHECK (
        jsonb_typeof(referenced_relationships) = 'array'
    )
);

CREATE TABLE first_party_x_post_references (
    source_post_id text NOT NULL
        REFERENCES first_party_x_posts(post_id) ON DELETE CASCADE,
    relationship_index integer NOT NULL,
    relationship_type text NOT NULL,
    referenced_post_id text NOT NULL,
    context_state text NOT NULL,
    referenced_text text,
    referenced_author_id text,
    referenced_author_username text,
    referenced_created_at timestamptz,
    referenced_entities jsonb NOT NULL DEFAULT '{}'::jsonb,
    referenced_media_metadata jsonb NOT NULL DEFAULT '[]'::jsonb,
    raw_relationship jsonb NOT NULL,
    expanded_raw_json jsonb,
    PRIMARY KEY (source_post_id, relationship_index),
    CONSTRAINT first_party_x_post_references_index_check CHECK (
        relationship_index >= 0
    ),
    CONSTRAINT first_party_x_post_references_type_check CHECK (
        relationship_type IN ('replied_to', 'quoted', 'retweeted')
    ),
    CONSTRAINT first_party_x_post_references_context_state_check CHECK (
        context_state IN ('available', 'unavailable')
    ),
    CONSTRAINT first_party_x_post_references_media_array_check CHECK (
        jsonb_typeof(referenced_media_metadata) = 'array'
    )
);

CREATE INDEX first_party_x_posts_source_created_at_idx
    ON first_party_x_posts (source_account, created_at);
CREATE INDEX first_party_x_posts_post_type_idx
    ON first_party_x_posts (post_type);
CREATE INDEX first_party_x_posts_conversation_id_idx
    ON first_party_x_posts (conversation_id);
CREATE INDEX first_party_x_posts_opportunity_id_idx
    ON first_party_x_posts (opportunity_id);
CREATE INDEX first_party_x_post_references_referenced_post_id_idx
    ON first_party_x_post_references (referenced_post_id);
CREATE INDEX first_party_x_post_references_type_idx
    ON first_party_x_post_references (relationship_type);

ALTER TABLE first_party_x_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE first_party_x_post_references ENABLE ROW LEVEL SECURITY;
