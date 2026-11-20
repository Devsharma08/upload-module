import os
from datetime import datetime, timedelta, timezone

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, status

from app.auth import TrustedGatewayIdentity, require_trusted_gateway
from app.repositories.upload_sessions import (
    IdempotencyConflictError,
    SlotReservationConflictError,
    create_upload_session,
)
from app.schemas.uploads import CreateUploadSessionRequest, UploadSessionCreated


router = APIRouter(tags=["uploads"])


async def get_database_pool(request: Request) -> asyncpg.Pool:
    pool: asyncpg.Pool | None = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )
    return pool


def _session_ttl_seconds() -> int:
    raw_ttl = os.environ.get("UPLOAD_SESSION_TTL_SECONDS", "900")
    try:
        ttl_seconds = int(raw_ttl)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upload session TTL configuration is invalid",
        ) from exc
    if ttl_seconds <= 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upload session TTL configuration is invalid",
        )
    return ttl_seconds


@router.post(
    "/slots/{slot_id}/upload-sessions",
    response_model=UploadSessionCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    request: CreateUploadSessionRequest,
    slot_id: str = Path(min_length=1, max_length=255),
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=255,
    ),
    identity: TrustedGatewayIdentity = Depends(require_trusted_gateway),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> UploadSessionCreated:
    if identity.authorized_slot_id != slot_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Gateway authorization does not cover this slot",
        )

    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=_session_ttl_seconds()
    )
    try:
        session = await create_upload_session(
            pool,
            principal_id=identity.principal_id,
            slot_id=slot_id,
            slot_reservation_id=identity.slot_reservation_id,
            idempotency_key=idempotency_key,
            request=request,
            expires_at=expires_at,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except SlotReservationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return UploadSessionCreated(
        upload_id=session.id,
        state=session.state,
        expires_at=session.expires_at,
        content_path=None,
    )
