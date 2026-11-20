import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from app.api.uploads import get_database_pool
from app.auth import require_trusted_gateway
from app.domain.upload_states import UploadState
from app.main import app, lifespan
from app.repositories.upload_sessions import (
    IdempotencyConflictError,
    SlotReservationConflictError,
    UploadSessionRecord,
)

GATEWAY_SECRET = "test-gateway-secret-that-is-long-enough"


def call_api(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json: dict[str, object] | None = None,
) -> httpx.Response:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.request(method, url, headers=headers, json=json)

    return asyncio.run(run())


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def gateway_headers(**overrides: str) -> dict[str, str]:
    headers = {
        "X-Gateway-Token": GATEWAY_SECRET,
        "X-Authenticated-Principal": "principal-1",
        "X-Authorized-Slot": "slot-1",
        "X-Slot-Reservation": "reservation-1",
        "Idempotency-Key": "request-1",
    }
    headers.update(overrides)
    return headers


def valid_request() -> dict[str, object]:
    return {
        "filename": "resume.pdf",
        "declared_size": 1024,
        "declared_media_type": "application/pdf",
        "client_sha256": "a" * 64,
    }


def test_create_session_requires_configured_gateway_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRUSTED_GATEWAY_TOKEN", raising=False)

    response = call_api(
        "POST",
        "/slots/slot-1/upload-sessions",
        headers=gateway_headers(),
        json=valid_request(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Trusted gateway authentication is not securely configured"
    )


def test_create_session_rejects_short_gateway_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRUSTED_GATEWAY_TOKEN", "too-short")

    response = call_api(
        "POST",
        "/slots/slot-1/upload-sessions",
        headers=gateway_headers(),
        json=valid_request(),
    )

    assert response.status_code == 503


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-Gateway-Token": "wrong"},
        {
            "X-Gateway-Token": GATEWAY_SECRET,
            "X-Authenticated-Principal": "principal-1",
        },
        {
            "X-Gateway-Token": GATEWAY_SECRET,
            "X-Authenticated-Principal": "principal-1",
            "X-Authorized-Slot": "slot-1",
        },
    ],
)
def test_create_session_rejects_untrusted_or_incomplete_gateway_headers(
    monkeypatch: pytest.MonkeyPatch,
    headers: dict[str, str],
) -> None:
    monkeypatch.setenv("TRUSTED_GATEWAY_TOKEN", GATEWAY_SECRET)

    response = call_api(
        "POST",
        "/slots/slot-1/upload-sessions",
        headers=headers,
        json=valid_request(),
    )

    assert response.status_code == 401


def test_non_ascii_gateway_token_is_rejected_without_internal_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRUSTED_GATEWAY_TOKEN", GATEWAY_SECRET)

    async def run() -> None:
        with pytest.raises(HTTPException) as exc_info:
            await require_trusted_gateway(
                gateway_token="é" * 32,
                principal_id="principal-1",
                authorized_slot_id="slot-1",
                slot_reservation_id="reservation-1",
            )
        assert exc_info.value.status_code == 401

    asyncio.run(run())


def test_create_session_rejects_slot_not_authorized_by_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRUSTED_GATEWAY_TOKEN", GATEWAY_SECRET)
    app.dependency_overrides[get_database_pool] = lambda: object()

    response = call_api(
        "POST",
        "/slots/slot-2/upload-sessions",
        headers=gateway_headers(),
        json=valid_request(),
    )

    assert response.status_code == 403


def test_create_session_passes_authenticated_identity_and_returns_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.uploads as uploads_api

    monkeypatch.setenv("TRUSTED_GATEWAY_TOKEN", GATEWAY_SECRET)
    now = datetime.now(timezone.utc)
    expected = UploadSessionRecord(
        id=uuid4(),
        state=UploadState.RECEIVING,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=15),
    )
    calls: list[dict[str, object]] = []

    async def create_session_stub(pool, **kwargs):
        calls.append({"pool": pool, **kwargs})
        return expected

    monkeypatch.setattr(uploads_api, "create_upload_session", create_session_stub)
    app.dependency_overrides[get_database_pool] = lambda: object()

    response = call_api(
        "POST",
        "/slots/slot-1/upload-sessions",
        headers=gateway_headers(),
        json=valid_request(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["upload_id"] == str(expected.id)
    assert body["state"] == "RECEIVING"
    assert datetime.fromisoformat(body["expires_at"]) == expected.expires_at
    assert body["content_path"] is None
    assert len(calls) == 1
    assert calls[0]["principal_id"] == "principal-1"
    assert calls[0]["slot_id"] == "slot-1"
    assert calls[0]["slot_reservation_id"] == "reservation-1"
    assert calls[0]["idempotency_key"] == "request-1"
    assert calls[0]["request"].filename == "resume.pdf"


def test_create_session_returns_conflict_for_idempotency_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.uploads as uploads_api

    monkeypatch.setenv("TRUSTED_GATEWAY_TOKEN", GATEWAY_SECRET)

    async def conflict(*_args, **_kwargs):
        raise IdempotencyConflictError("Idempotency key was already used")

    monkeypatch.setattr(uploads_api, "create_upload_session", conflict)
    app.dependency_overrides[get_database_pool] = lambda: object()

    response = call_api(
        "POST",
        "/slots/slot-1/upload-sessions",
        headers=gateway_headers(),
        json=valid_request(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Idempotency key was already used"


def test_create_session_returns_conflict_for_reused_gateway_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.uploads as uploads_api

    monkeypatch.setenv("TRUSTED_GATEWAY_TOKEN", GATEWAY_SECRET)

    async def conflict(*_args, **_kwargs):
        raise SlotReservationConflictError("Slot reservation was already used")

    monkeypatch.setattr(uploads_api, "create_upload_session", conflict)
    app.dependency_overrides[get_database_pool] = lambda: object()

    response = call_api(
        "POST",
        "/slots/slot-1/upload-sessions",
        headers=gateway_headers(),
        json=valid_request(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Slot reservation was already used"


def test_session_ttl_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRUSTED_GATEWAY_TOKEN", GATEWAY_SECRET)
    monkeypatch.setenv("UPLOAD_SESSION_TTL_SECONDS", "0")
    app.dependency_overrides[get_database_pool] = lambda: object()

    response = call_api(
        "POST",
        "/slots/slot-1/upload-sessions",
        headers=gateway_headers(),
        json=valid_request(),
    )

    assert response.status_code == 503


def test_create_session_fails_closed_when_database_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRUSTED_GATEWAY_TOKEN", GATEWAY_SECRET)

    response = call_api(
        "POST",
        "/slots/slot-1/upload-sessions",
        headers=gateway_headers(),
        json=valid_request(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Database is not configured"


def test_readiness_executes_database_probe() -> None:
    class Connection:
        async def execute(self, query: str) -> None:
            assert query == "SELECT 1"

    class Pool:
        async def __aenter__(self) -> Connection:
            return Connection()

        async def __aexit__(self, *_: object) -> None:
            return None

        def acquire(self) -> "Pool":
            return self

    app.state.db_pool = Pool()
    try:
        response = call_api("GET", "/readyz")
    finally:
        del app.state.db_pool

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_reports_database_connection_failures() -> None:
    class Connection:
        async def execute(self, _query: str) -> None:
            raise OSError("database unavailable")

    class Pool:
        async def __aenter__(self) -> Connection:
            return Connection()

        async def __aexit__(self, *_: object) -> None:
            return None

        def acquire(self) -> "Pool":
            return self

    app.state.db_pool = Pool()
    try:
        response = call_api("GET", "/readyz")
    finally:
        del app.state.db_pool

    assert response.status_code == 503
    assert response.json()["detail"] == "Database is unavailable"


def test_lifespan_creates_and_closes_database_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Pool:
        closed = False

        async def close(self) -> None:
            self.closed = True

    pool = Pool()
    calls: list[tuple[str, int]] = []

    async def create_pool(database_url: str, *, min_size: int) -> Pool:
        calls.append((database_url, min_size))
        return pool

    async def run() -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql://test")
        monkeypatch.setattr("app.main.asyncpg.create_pool", create_pool)

        async with lifespan(app):
            assert app.state.db_pool is pool

        assert pool.closed
        assert calls == [("postgresql://test", 0)]

    try:
        asyncio.run(run())
    finally:
        if hasattr(app.state, "db_pool"):
            del app.state.db_pool


def test_readiness_is_unavailable_without_database_pool() -> None:
    response = call_api("GET", "/readyz")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database is not configured"
