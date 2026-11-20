import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.domain.upload_states import UploadState
from app.repositories.upload_sessions import (
    IdempotencyConflictError,
    SlotReservationConflictError,
    create_upload_session,
)
from app.schemas.uploads import CreateUploadSessionRequest


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: object) -> None:
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.sessions: list[dict[str, Any]] = []
        self.state_events: list[tuple[Any, ...]] = []

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        if query.lstrip().startswith("INSERT INTO upload_sessions"):
            if any(
                session["principal_id"] == args[1]
                and session["idempotency_key"] == args[3]
                or session["slot_reservation_id"] == args[4]
                for session in self.sessions
            ):
                return None

            now = datetime.now(timezone.utc)
            session = {
                "id": args[0],
                "principal_id": args[1],
                "slot_id": args[2],
                "idempotency_key": args[3],
                "slot_reservation_id": args[4],
                "filename": args[5],
                "declared_size": args[6],
                "declared_media_type": args[7],
                "client_sha256": args[8],
                "replace_existing": args[9],
                "state": args[10],
                "created_at": now,
                "updated_at": now,
                "expires_at": args[11],
            }
            self.sessions.append(session)
            return session

        if "WHERE principal_id = $1 AND idempotency_key = $2" in query:
            return next(
                (
                    session
                    for session in self.sessions
                    if session["principal_id"] == args[0]
                    and session["idempotency_key"] == args[1]
                ),
                None,
            )
        if "WHERE slot_reservation_id = $1" in query:
            return next(
                (
                    {"id": session["id"]}
                    for session in self.sessions
                    if session["slot_reservation_id"] == args[0]
                ),
                None,
            )
        raise AssertionError(f"Unexpected fetchrow query: {query}")

    async def execute(self, query: str, *args: Any) -> None:
        assert "INSERT INTO upload_state_events" in query
        self.state_events.append(args)


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, *_: object) -> None:
        return None

    def acquire(self) -> "FakePool":
        return self


def valid_request(**overrides: Any) -> CreateUploadSessionRequest:
    fields = {
        "filename": "resume.pdf",
        "declared_size": 1024,
        "declared_media_type": "application/pdf",
        "client_sha256": "A" * 64,
    }
    fields.update(overrides)
    return CreateUploadSessionRequest(**fields)


def test_create_session_persists_receiving_state_and_initial_audit_event() -> None:
    async def run() -> None:
        pool = FakePool()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        session = await create_upload_session(
            pool,
            principal_id="user-1",
            slot_id="application-1",
            slot_reservation_id="reservation-1",
            idempotency_key="attempt-1",
            request=valid_request(),
            expires_at=expires_at,
        )

        assert session.state is UploadState.RECEIVING
        assert isinstance(session.id, UUID)
        assert session.expires_at == expires_at
        assert len(pool.connection.state_events) == 1
        assert pool.connection.state_events[0] == (
            session.id,
            UploadState.RECEIVING.value,
        )
        assert pool.connection.sessions[0]["client_sha256"] == "a" * 64

    asyncio.run(run())


def test_matching_idempotent_request_returns_original_session() -> None:
    async def run() -> None:
        pool = FakePool()
        first = await create_upload_session(
            pool,
            principal_id="user-1",
            slot_id="application-1",
            slot_reservation_id="reservation-1",
            idempotency_key="attempt-1",
            request=valid_request(),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        replay = await create_upload_session(
            pool,
            principal_id="user-1",
            slot_id="application-1",
            slot_reservation_id="reservation-1",
            idempotency_key="attempt-1",
            request=valid_request(client_sha256="a" * 64),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )

        assert replay.id == first.id
        assert replay.created_at == first.created_at
        assert len(pool.connection.state_events) == 1

    asyncio.run(run())


def test_idempotency_key_cannot_be_reused_for_different_request() -> None:
    async def run() -> None:
        pool = FakePool()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        await create_upload_session(
            pool,
            principal_id="user-1",
            slot_id="application-1",
            slot_reservation_id="reservation-1",
            idempotency_key="attempt-1",
            request=valid_request(),
            expires_at=expires_at,
        )

        with pytest.raises(IdempotencyConflictError):
            await create_upload_session(
                pool,
                principal_id="user-1",
                slot_id="application-1",
                slot_reservation_id="reservation-1",
                idempotency_key="attempt-1",
                request=valid_request(filename="different.pdf"),
                expires_at=expires_at,
            )

        assert len(pool.connection.state_events) == 1

    asyncio.run(run())


def test_session_creation_requires_timezone_aware_expiry() -> None:
    async def run() -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            await create_upload_session(
                FakePool(),
                principal_id="user-1",
                slot_id="application-1",
                slot_reservation_id="reservation-1",
                idempotency_key="attempt-1",
                request=valid_request(),
                expires_at=datetime(2030, 1, 1),
            )

    asyncio.run(run())


def test_session_creation_rejects_oversized_idempotency_key() -> None:
    async def run() -> None:
        with pytest.raises(ValueError, match="at most 255"):
            await create_upload_session(
                FakePool(),
                principal_id="user-1",
                slot_id="application-1",
                slot_reservation_id="reservation-1",
                idempotency_key="k" * 256,
                request=valid_request(),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            )

    asyncio.run(run())


def test_slot_reservation_cannot_be_reused_for_another_request() -> None:
    async def run() -> None:
        pool = FakePool()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        await create_upload_session(
            pool,
            principal_id="user-1",
            slot_id="application-1",
            slot_reservation_id="reservation-1",
            idempotency_key="attempt-1",
            request=valid_request(),
            expires_at=expires_at,
        )

        with pytest.raises(SlotReservationConflictError):
            await create_upload_session(
                pool,
                principal_id="user-1",
                slot_id="application-1",
                slot_reservation_id="reservation-1",
                idempotency_key="attempt-2",
                request=valid_request(),
                expires_at=expires_at,
            )

    asyncio.run(run())
