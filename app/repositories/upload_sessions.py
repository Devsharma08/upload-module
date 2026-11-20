import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg

from app.domain.upload_states import UploadState, validate_transition
from app.schemas.uploads import CreateUploadSessionRequest, Stage1ReadyHandoff


class IdempotencyConflictError(ValueError):
    pass


class SlotReservationConflictError(ValueError):
    pass


class UploadNotFoundError(LookupError):
    pass


class InvalidReadyHandoffError(ValueError):
    pass


@dataclass(frozen=True)
class UploadSessionRecord:
    id: UUID
    state: UploadState
    created_at: datetime
    updated_at: datetime
    expires_at: datetime


async def create_upload_session(
    pool: asyncpg.Pool,
    *,
    principal_id: str,
    slot_id: str,
    slot_reservation_id: str,
    idempotency_key: str,
    request: CreateUploadSessionRequest,
    expires_at: datetime,
) -> UploadSessionRecord:
    """Create or replay a session after caller authorization and slot reservation."""
    if not principal_id.strip() or principal_id != principal_id.strip():
        raise ValueError(
            "principal_id must be non-empty without surrounding whitespace"
        )
    if not slot_id.strip() or slot_id != slot_id.strip():
        raise ValueError("slot_id must be non-empty without surrounding whitespace")
    if (
        not slot_reservation_id.strip()
        or slot_reservation_id != slot_reservation_id.strip()
        or len(slot_reservation_id) > 255
    ):
        raise ValueError("slot_reservation_id must contain 1 to 255 characters")
    if (
        not idempotency_key.strip()
        or idempotency_key != idempotency_key.strip()
    ):
        raise ValueError("idempotency_key must not be empty")
    if len(idempotency_key) > 255:
        raise ValueError("idempotency_key must be at most 255 characters")
    if expires_at.tzinfo is None or expires_at.utcoffset() is None:
        raise ValueError("expires_at must be timezone-aware")

    upload_id = uuid4()
    async with pool.acquire() as connection:
        async with connection.transaction():
            session = await connection.fetchrow(
                """
                INSERT INTO upload_sessions (
                    id, principal_id, slot_id, idempotency_key,
                    slot_reservation_id,
                    filename, declared_size, declared_media_type, client_sha256,
                    replace_existing, state, expires_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT DO NOTHING
                RETURNING id, state, created_at, updated_at, expires_at
                """,
                upload_id,
                principal_id,
                slot_id,
                idempotency_key,
                slot_reservation_id,
                request.filename,
                request.declared_size,
                request.declared_media_type,
                request.client_sha256.lower() if request.client_sha256 else None,
                request.replace_existing,
                UploadState.RECEIVING.value,
                expires_at,
            )

            if session is not None:
                await connection.execute(
                    """
                    INSERT INTO upload_state_events (
                        upload_id, from_state, to_state, reason_code
                    )
                    VALUES ($1, NULL, $2, NULL)
                    """,
                    session["id"],
                    UploadState.RECEIVING.value,
                )
                return _session_record(session)

            existing = await connection.fetchrow(
                """
                SELECT id, state, created_at, updated_at, expires_at,
                       slot_id, filename, declared_size, declared_media_type,
                       client_sha256, replace_existing, slot_reservation_id
                FROM upload_sessions
                WHERE principal_id = $1 AND idempotency_key = $2
                FOR UPDATE
                """,
                principal_id,
                idempotency_key,
            )
            if existing is None:
                reservation = await connection.fetchrow(
                    """
                    SELECT id
                    FROM upload_sessions
                    WHERE slot_reservation_id = $1
                    """,
                    slot_reservation_id,
                )
                if reservation is not None:
                    raise SlotReservationConflictError(
                        "Slot reservation was already used"
                    )
                raise RuntimeError("Conflicting upload session was not found")

            expected_sha256 = (
                request.client_sha256.lower() if request.client_sha256 else None
            )
            if (
                existing["slot_id"] != slot_id
                or existing["filename"] != request.filename
                or existing["declared_size"] != request.declared_size
                or existing["declared_media_type"] != request.declared_media_type
                or existing["client_sha256"] != expected_sha256
                or existing["replace_existing"] != request.replace_existing
                or existing["slot_reservation_id"] != slot_reservation_id
            ):
                raise IdempotencyConflictError(
                    "Idempotency key was already used with a different upload request"
                )

            return _session_record(existing)


def _session_record(row: asyncpg.Record) -> UploadSessionRecord:
    return UploadSessionRecord(
        id=row["id"],
        state=UploadState(row["state"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        expires_at=row["expires_at"],
    )


async def transition_upload(
    pool: asyncpg.Pool,
    upload_id: UUID,
    target: UploadState,
    *,
    reason_code: str | None = None,
    ready_handoff: Stage1ReadyHandoff | None = None,
) -> UploadState:
    """Persist an allowed transition, its audit event, and READY outbox event."""
    if target is UploadState.READY and ready_handoff is None:
        raise InvalidReadyHandoffError(
            "A Stage1ReadyHandoff is required for the READY transition"
        )
    if target is not UploadState.READY and ready_handoff is not None:
        raise InvalidReadyHandoffError(
            "A handoff may only be supplied for the READY transition"
        )

    async with pool.acquire() as connection:
        async with connection.transaction():
            session = await connection.fetchrow(
                """
                SELECT state, slot_id
                FROM upload_sessions
                WHERE id = $1
                FOR UPDATE
                """,
                upload_id,
            )
            if session is None:
                raise UploadNotFoundError(f"Upload {upload_id} does not exist")

            current = UploadState(session["state"])
            validate_transition(current, target)

            if ready_handoff is not None:
                if ready_handoff.slot_id != session["slot_id"]:
                    raise InvalidReadyHandoffError(
                        "Handoff slot_id does not match the upload session"
                    )

                await connection.execute(
                    """
                    UPDATE upload_sessions
                    SET state = $2,
                        reason_code = NULL,
                        byte_size = $3,
                        sha256 = $4,
                        detected_media_type = $5,
                        encrypted_object_ref = $6,
                        updated_at = now()
                    WHERE id = $1
                    """,
                    upload_id,
                    target.value,
                    ready_handoff.byte_size,
                    ready_handoff.sha256.lower(),
                    ready_handoff.media_type,
                    ready_handoff.encrypted_object_ref,
                )

                await connection.execute(
                    """
                    INSERT INTO outbox_events (
                        id, aggregate_id, event_type, payload
                    )
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    uuid4(),
                    upload_id,
                    "Stage1ReadyHandoff.v1",
                    json.dumps(ready_handoff.model_dump(mode="json")),
                )
            else:
                await connection.execute(
                    """
                    UPDATE upload_sessions
                    SET state = $2,
                        reason_code = $3,
                        updated_at = now()
                    WHERE id = $1
                    """,
                    upload_id,
                    target.value,
                    reason_code,
                )

            await connection.execute(
                """
                INSERT INTO upload_state_events (
                    upload_id, from_state, to_state, reason_code
                )
                VALUES ($1, $2, $3, $4)
                """,
                upload_id,
                current.value,
                target.value,
                reason_code,
            )

    return target