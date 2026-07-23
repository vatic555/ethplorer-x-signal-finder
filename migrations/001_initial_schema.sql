CREATE TABLE IF NOT EXISTS schema_migrations (
    version bigint PRIMARY KEY,
    name text NOT NULL,
    checksum text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE runs (
    run_id uuid PRIMARY KEY,
    started_at timestamptz NOT NULL,
    finished_at timestamptz,
    status text NOT NULL,
    trigger_type text NOT NULL,
    application_version text,
    git_commit text,
    fetched_posts_count integer NOT NULL DEFAULT 0,
    new_posts_count integer NOT NULL DEFAULT 0,
    rejected_posts_count integer NOT NULL DEFAULT 0,
    signals_count integer NOT NULL DEFAULT 0,
    opportunities_count integer NOT NULL DEFAULT 0,
    warning_count integer NOT NULL DEFAULT 0,
    error_summary text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT runs_status_check CHECK (
        status IN ('running', 'completed', 'completed_with_warnings', 'failed')
    )
);

CREATE TABLE posts (
    post_id text PRIMARY KEY,
    author_id text,
    author_username text,
    created_at timestamptz NOT NULL,
    conversation_id text,
    referenced_post_id text,
    post_type text NOT NULL,
    source_key text NOT NULL,
    text text NOT NULL,
    raw_json jsonb NOT NULL,
    first_seen_run_id uuid NOT NULL REFERENCES runs(run_id),
    last_seen_run_id uuid NOT NULL REFERENCES runs(run_id),
    first_collected_at timestamptz NOT NULL,
    last_collected_at timestamptz NOT NULL,
    processing_status text NOT NULL,
    rejection_stage text,
    rejection_reason text,
    availability_status text NOT NULL,
    last_verified_at timestamptz,
    content_deleted_at timestamptz
);

CREATE TABLE signals (
    signal_id uuid PRIMARY KEY,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    first_run_id uuid NOT NULL REFERENCES runs(run_id),
    title text NOT NULL,
    summary text NOT NULL,
    topic text,
    status text NOT NULL,
    gate_decision text NOT NULL,
    gate_reason text,
    evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
    inferences jsonb NOT NULL DEFAULT '[]'::jsonb,
    uncertainties jsonb NOT NULL DEFAULT '[]'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT signals_gate_decision_check CHECK (
        gate_decision IN ('accepted', 'rejected', 'unresolved', 'not_evaluated')
    )
);

CREATE TABLE signal_posts (
    signal_id uuid NOT NULL REFERENCES signals(signal_id),
    post_id text NOT NULL REFERENCES posts(post_id),
    relationship_type text NOT NULL,
    added_at timestamptz NOT NULL,
    PRIMARY KEY (signal_id, post_id)
);

CREATE TABLE opportunities (
    opportunity_id uuid PRIMARY KEY,
    signal_id uuid NOT NULL REFERENCES signals(signal_id),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    opportunity_type text NOT NULL,
    information_gap text NOT NULL,
    audience_benefit text NOT NULL,
    asset_id text,
    natural_relevance_reason text NOT NULL,
    recommended_action text NOT NULL,
    gate_snapshot jsonb NOT NULL,
    evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
    verified_facts jsonb NOT NULL DEFAULT '[]'::jsonb,
    inferences jsonb NOT NULL DEFAULT '[]'::jsonb,
    uncertainties jsonb NOT NULL DEFAULT '[]'::jsonb,
    draft_text text,
    visual_required boolean NOT NULL DEFAULT false,
    visual_brief jsonb,
    review_status text NOT NULL,
    current_review_comment text,
    edited_text text,
    published_url text,
    reviewed_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT opportunities_type_check CHECK (
        opportunity_type IN ('reply', 'quote_post', 'own_post', 'article', 'bizdev')
    ),
    CONSTRAINT opportunities_review_status_check CHECK (
        review_status IN (
            'pending', 'accepted', 'rejected', 'needs_edit',
            'needs_evidence', 'deferred', 'published'
        )
    )
);

CREATE TABLE human_reviews (
    review_id uuid PRIMARY KEY,
    opportunity_id uuid NOT NULL REFERENCES opportunities(opportunity_id),
    reviewer text NOT NULL,
    decision text NOT NULL,
    reason text,
    edited_text text,
    published_url text,
    created_at timestamptz NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT human_reviews_decision_check CHECK (
        decision IN (
            'pending', 'accepted', 'rejected', 'needs_edit',
            'needs_evidence', 'deferred', 'published'
        )
    )
);

CREATE TABLE usage_events (
    usage_event_id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES runs(run_id),
    provider text NOT NULL,
    operation text NOT NULL,
    model text,
    request_count integer NOT NULL,
    input_units bigint,
    output_units bigint,
    reported_cost numeric,
    estimated_cost numeric,
    currency text,
    created_at timestamptz NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE sync_state (
    source_key text PRIMARY KEY,
    checkpoint_value text,
    checkpoint_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_attempt_at timestamptz,
    last_successful_at timestamptz,
    last_successful_run_id uuid REFERENCES runs(run_id),
    last_warning_code text,
    updated_at timestamptz NOT NULL
);

CREATE INDEX posts_created_at_idx ON posts (created_at);
CREATE INDEX posts_source_key_created_at_idx ON posts (source_key, created_at);
CREATE INDEX posts_processing_status_idx ON posts (processing_status);
CREATE INDEX posts_conversation_id_idx ON posts (conversation_id);
CREATE INDEX signals_created_at_idx ON signals (created_at);
CREATE INDEX signals_gate_decision_idx ON signals (gate_decision);
CREATE INDEX signal_posts_post_id_idx ON signal_posts (post_id);
CREATE INDEX opportunities_review_status_created_at_idx
    ON opportunities (review_status, created_at);
CREATE INDEX opportunities_signal_id_idx ON opportunities (signal_id);
CREATE INDEX human_reviews_opportunity_id_created_at_idx
    ON human_reviews (opportunity_id, created_at);
CREATE INDEX usage_events_run_id_created_at_idx
    ON usage_events (run_id, created_at);
CREATE INDEX runs_started_at_idx ON runs (started_at);
CREATE INDEX sync_state_last_successful_at_idx ON sync_state (last_successful_at);

ALTER TABLE schema_migrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE signal_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE human_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_state ENABLE ROW LEVEL SECURITY;
