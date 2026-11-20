CREATE TABLE upload_sessions (
    id UUID PRIMARY KEY,
    principal_id TEXT NOT NULL,
    slot_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL
        CHECK (char_length(idempotency_key) BETWEEN 1 AND 255),
    slot_reservation_id TEXT NOT NULL
        CONSTRAINT upload_sessions_slot_reservation_id_key UNIQUE
        CONSTRAINT upload_sessions_slot_reservation_id_length_check
        CHECK (char_length(slot_reservation_id) BETWEEN 1 AND 255),

    filename TEXT NOT NULL,
    declared_size BIGINT NOT NULL CHECK (declared_size > 0),
    declared_media_type TEXT,
    client_sha256 CHAR(64),
    replace_existing BOOLEAN NOT NULL DEFAULT FALSE,

    byte_size BIGINT CHECK (byte_size IS NULL OR byte_size >= 0),
    sha256 CHAR(64),
    detected_media_type TEXT,
    encrypted_object_ref TEXT,

    state TEXT NOT NULL CHECK (state IN (
        'RECEIVING', 'VALIDATING', 'SCANNING', 'ENCRYPTING',
        'READY', 'REJECTED', 'BLOCKED', 'FAILED', 'EXPIRED', 'DUPLICATE'
    )),
    reason_code TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,

    UNIQUE (principal_id, idempotency_key)
);

CREATE INDEX upload_sessions_slot_state_idx
    ON upload_sessions (slot_id, state);

CREATE INDEX upload_sessions_expiry_idx
    ON upload_sessions (expires_at)
    WHERE state IN ('RECEIVING', 'VALIDATING', 'SCANNING', 'ENCRYPTING');

CREATE UNIQUE INDEX upload_sessions_ready_slot_hash_idx
    ON upload_sessions (slot_id, sha256)
    WHERE state = 'READY' AND sha256 IS NOT NULL;


CREATE TABLE upload_state_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    upload_id UUID NOT NULL REFERENCES upload_sessions(id),
    from_state TEXT,
    to_state TEXT NOT NULL,
    reason_code TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX upload_state_events_upload_idx
    ON upload_state_events (upload_id, occurred_at);


CREATE TABLE outbox_events (
    id UUID PRIMARY KEY,
    aggregate_id UUID NOT NULL REFERENCES upload_sessions(id),
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,
    publish_attempts INTEGER NOT NULL DEFAULT 0 CHECK (publish_attempts >= 0),

    UNIQUE (aggregate_id, event_type)
);