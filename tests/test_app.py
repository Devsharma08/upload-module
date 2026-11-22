from hashlib import sha256

import httpx
import pytest

from upload_module.app import app


async def make_request(
    *,
    content: bytes = b"",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.post("/uploads", content=content, headers=headers)


@pytest.mark.anyio
async def test_health_endpoint() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_upload_endpoint_streams_bytes_to_quarantine(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UPLOAD_ENV", "development")
    monkeypatch.setenv("UPLOAD_QUARANTINE_DIR", str(tmp_path))

    content = b"small upload body"
    response = await make_request(content=content)

    assert response.status_code == 201
    result = response.json()
    assert result["status"] == "QUARANTINED"
    assert result["size_bytes"] == len(content)
    assert result["sha256"] == sha256(content).hexdigest()
    assert (tmp_path / f"upload-{result['upload_id']}.part").read_bytes() == content


@pytest.mark.anyio
async def test_upload_endpoint_rejects_body_over_configured_limit(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UPLOAD_ENV", "development")
    monkeypatch.setenv("UPLOAD_QUARANTINE_DIR", str(tmp_path))
    monkeypatch.setenv("UPLOAD_MAX_BYTES", "4")

    response = await make_request(content=b"12345")

    assert response.status_code == 413
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_upload_endpoint_rejects_declared_size_mismatch(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UPLOAD_ENV", "development")
    monkeypatch.setenv("UPLOAD_QUARANTINE_DIR", str(tmp_path))

    response = await make_request(
        content=b"actual",
        headers={"content-length": "10"},
    )

    assert response.status_code == 400
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_upload_endpoint_is_disabled_outside_explicit_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UPLOAD_ENV", raising=False)

    response = await make_request(content=b"not stored")

    assert response.status_code == 503
