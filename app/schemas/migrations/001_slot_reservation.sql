BEGIN;

ALTER TABLE upload_sessions
    ADD COLUMN IF NOT EXISTS slot_reservation_id TEXT;

UPDATE upload_sessions
SET slot_reservation_id = 'legacy-' || id::text
WHERE slot_reservation_id IS NULL;

ALTER TABLE upload_sessions
    ALTER COLUMN slot_reservation_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'upload_sessions_slot_reservation_id_key'
          AND conrelid = 'upload_sessions'::regclass
    ) THEN
        ALTER TABLE upload_sessions
            ADD CONSTRAINT upload_sessions_slot_reservation_id_key
            UNIQUE (slot_reservation_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'upload_sessions_slot_reservation_id_length_check'
          AND conrelid = 'upload_sessions'::regclass
    ) THEN
        ALTER TABLE upload_sessions
            ADD CONSTRAINT upload_sessions_slot_reservation_id_length_check
            CHECK (char_length(slot_reservation_id) BETWEEN 1 AND 255);
    END IF;
END;
$$;

COMMIT;
