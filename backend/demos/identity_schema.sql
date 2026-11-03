CREATE TABLE IF NOT EXISTS identity_link (
    id_hash text PRIMARY KEY,
    person_id uuid NOT NULL UNIQUE,
    method text NOT NULL,
    verified_at timestamptz NOT NULL DEFAULT now(),
    banned_until timestamptz
);
