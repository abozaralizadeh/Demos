CREATE TABLE IF NOT EXISTS person (
    id uuid PRIMARY KEY,
    language text NOT NULL DEFAULT 'it',
    area text NOT NULL DEFAULT 'milan',
    joined_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'active',
    unlocked boolean NOT NULL DEFAULT false,
    notifications boolean NOT NULL DEFAULT false,
    is_sample boolean NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS consent (
    id bigserial PRIMARY KEY,
    person_id uuid NOT NULL REFERENCES person ON DELETE CASCADE,
    purpose text NOT NULL,
    text_version text NOT NULL,
    given_at timestamptz NOT NULL DEFAULT now(),
    withdrawn_at timestamptz
);

CREATE TABLE IF NOT EXISTS topic (
    id text PRIMARY KEY,
    title_en text NOT NULL,
    title_it text NOT NULL,
    area text NOT NULL DEFAULT 'milan',
    state text NOT NULL DEFAULT 'live',
    main_statement_id text,
    layout_x real NOT NULL DEFAULT 195,
    layout_y real NOT NULL DEFAULT 270,
    tilt real NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS statement (
    id text PRIMARY KEY,
    topic_id text NOT NULL REFERENCES topic,
    text_en text NOT NULL,
    text_it text NOT NULL,
    question_en text,
    question_it text,
    keywords text[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS topic_link (
    topic_a text NOT NULL REFERENCES topic,
    topic_b text NOT NULL REFERENCES topic,
    strength real NOT NULL DEFAULT 0,
    PRIMARY KEY (topic_a, topic_b)
);

CREATE TABLE IF NOT EXISTS grp (
    id text PRIMARY KEY,
    topic_id text NOT NULL REFERENCES topic,
    kind text NOT NULL DEFAULT 'life',
    label_en text NOT NULL,
    label_it text NOT NULL,
    keywords text[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS group_member (
    group_id text NOT NULL REFERENCES grp,
    person_id uuid NOT NULL REFERENCES person ON DELETE CASCADE,
    source text NOT NULL DEFAULT 'mirror',
    since timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (group_id, person_id)
);

CREATE TABLE IF NOT EXISTS conversation (
    id uuid PRIMARY KEY,
    person_id uuid NOT NULL REFERENCES person ON DELETE CASCADE,
    opened_by text NOT NULL DEFAULT 'person',
    topic_id text REFERENCES topic,
    state jsonb NOT NULL DEFAULT '{}',
    started_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz
);

CREATE TABLE IF NOT EXISTS turn (
    id bigserial PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES conversation ON DELETE CASCADE,
    speaker text NOT NULL,
    text text NOT NULL,
    move text,
    evidence_ids text[] NOT NULL DEFAULT '{}',
    excluded boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    delete_after timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS turn_conversation ON turn (conversation_id, id);

CREATE TABLE IF NOT EXISTS stance (
    id bigserial PRIMARY KEY,
    person_id uuid NOT NULL REFERENCES person ON DELETE CASCADE,
    statement_id text NOT NULL REFERENCES statement,
    value text NOT NULL CHECK (value IN ('agree', 'partly', 'unsure', 'disagree')),
    state text NOT NULL CHECK (state IN ('inferred', 'confirmed', 'corrected', 'dropped')),
    evidence_turn_id bigint REFERENCES turn ON DELETE SET NULL,
    after_argument_id bigint,
    valid_from timestamptz NOT NULL DEFAULT now(),
    valid_to timestamptz
);
CREATE INDEX IF NOT EXISTS stance_live ON stance (statement_id) WHERE valid_to IS NULL;
CREATE INDEX IF NOT EXISTS stance_person ON stance (person_id) WHERE valid_to IS NULL;

CREATE TABLE IF NOT EXISTS argument (
    id bigserial PRIMARY KEY,
    topic_id text NOT NULL REFERENCES topic,
    statement_id text NOT NULL REFERENCES statement,
    side text NOT NULL CHECK (side IN ('for', 'against')),
    summary_en text NOT NULL,
    summary_it text NOT NULL,
    text_en text NOT NULL,
    text_it text NOT NULL,
    state text NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'approved', 'retired')),
    retired_reason text,
    reviewed_by text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claim (
    id bigserial PRIMARY KEY,
    person_id uuid NOT NULL REFERENCES person ON DELETE CASCADE,
    turn_id bigint REFERENCES turn ON DELETE SET NULL,
    topic_id text REFERENCES topic,
    statement_id text REFERENCES statement,
    side text,
    text text NOT NULL,
    language text NOT NULL,
    argument_id bigint REFERENCES argument,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS argument_source (
    argument_id bigint NOT NULL REFERENCES argument ON DELETE CASCADE,
    person_id uuid NOT NULL REFERENCES person ON DELETE CASCADE,
    PRIMARY KEY (argument_id, person_id)
);

CREATE TABLE IF NOT EXISTS exposure (
    id bigserial PRIMARY KEY,
    person_id uuid NOT NULL REFERENCES person ON DELETE CASCADE,
    argument_id bigint NOT NULL REFERENCES argument ON DELETE CASCADE,
    heard_at timestamptz NOT NULL DEFAULT now(),
    view_changed boolean NOT NULL DEFAULT false,
    UNIQUE (person_id, argument_id)
);

CREATE TABLE IF NOT EXISTS bridge (
    id bigserial PRIMARY KEY,
    topic_id text NOT NULL REFERENCES topic,
    statement_id text NOT NULL REFERENCES statement,
    state text NOT NULL DEFAULT 'approved'
);

CREATE TABLE IF NOT EXISTS bridge_source (
    bridge_id bigint NOT NULL REFERENCES bridge ON DELETE CASCADE,
    person_id uuid NOT NULL REFERENCES person ON DELETE CASCADE,
    PRIMARY KEY (bridge_id, person_id)
);

CREATE TABLE IF NOT EXISTS agreement (
    id bigserial PRIMARY KEY,
    statement_id text NOT NULL UNIQUE REFERENCES statement,
    topic_id text NOT NULL REFERENCES topic,
    state text NOT NULL CHECK (state IN ('candidate', 'live', 'lapsed', 'dropped')),
    since timestamptz NOT NULL DEFAULT now(),
    live_since timestamptz,
    below_since timestamptz
);

CREATE TABLE IF NOT EXISTS agreement_snapshot (
    id bigserial PRIMARY KEY,
    agreement_id bigint NOT NULL REFERENCES agreement ON DELETE CASCADE,
    label text NOT NULL,
    support_pct real NOT NULL,
    base integer NOT NULL,
    at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS send_request (
    agreement_id bigint NOT NULL REFERENCES agreement ON DELETE CASCADE,
    person_id uuid NOT NULL REFERENCES person ON DELETE CASCADE,
    at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (agreement_id, person_id)
);

CREATE TABLE IF NOT EXISTS agreement_action (
    id bigserial PRIMARY KEY,
    agreement_id bigint NOT NULL REFERENCES agreement ON DELETE CASCADE,
    kind text NOT NULL,
    target text,
    reviewed_by text,
    sent_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fact (
    id bigserial PRIMARY KEY,
    topic_id text NOT NULL REFERENCES topic,
    title_en text NOT NULL,
    title_it text NOT NULL,
    label_en text NOT NULL,
    label_it text NOT NULL,
    value text NOT NULL,
    source_name text NOT NULL,
    source_url text,
    year text NOT NULL,
    is_placeholder boolean NOT NULL DEFAULT false,
    reviewed_by text,
    review_due date
);

CREATE TABLE IF NOT EXISTS report (
    id bigserial PRIMARY KEY,
    reporter_id uuid REFERENCES person ON DELETE SET NULL,
    turn_id bigint REFERENCES turn ON DELETE SET NULL,
    evidence_ids text[] NOT NULL DEFAULT '{}',
    reason text NOT NULL,
    state text NOT NULL DEFAULT 'open',
    decision text,
    decided_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS proposed_topic (
    id bigserial PRIMARY KEY,
    sample_text text NOT NULL,
    people integer NOT NULL,
    state text NOT NULL DEFAULT 'open',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS election (
    id bigserial PRIMARY KEY,
    area text NOT NULL,
    vote_date date NOT NULL,
    polls_close timestamptz NOT NULL,
    topic_ids text[] NOT NULL
);

CREATE TABLE IF NOT EXISTS opening_seen (
    person_id uuid NOT NULL REFERENCES person ON DELETE CASCADE,
    opening_key text NOT NULL,
    seen_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (person_id, opening_key)
);

CREATE TABLE IF NOT EXISTS safety_event (
    id bigserial PRIMARY KEY,
    kind text NOT NULL,
    at timestamptz NOT NULL DEFAULT now()
);

-- Preview: a person can drop anonymity and pick the name shown on petitions they sign.
ALTER TABLE person ADD COLUMN IF NOT EXISTS anonymous boolean NOT NULL DEFAULT true;
ALTER TABLE person ADD COLUMN IF NOT EXISTS display_name text;

CREATE TABLE IF NOT EXISTS petition_signature (
    agreement_id bigint NOT NULL REFERENCES agreement ON DELETE CASCADE,
    person_id uuid NOT NULL REFERENCES person ON DELETE CASCADE,
    at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (agreement_id, person_id)
);

CREATE TABLE IF NOT EXISTS reply_failure (
    id bigserial PRIMARY KEY,
    move text NOT NULL,
    reasons text[] NOT NULL,
    at timestamptz NOT NULL DEFAULT now()
);

-- One row a day: AI calls and tokens, checked against DAILY_REQUEST_CAP and DAILY_TOKEN_BUDGET.
CREATE TABLE IF NOT EXISTS ai_usage (
    day date PRIMARY KEY,
    requests integer NOT NULL DEFAULT 0,
    tokens bigint NOT NULL DEFAULT 0
);
