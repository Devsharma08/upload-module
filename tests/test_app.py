from hashlib import sha256
import io
import zipfile

import httpx
import pytest

from upload_module.app import app


def make_pdf(page_count: int = 1) -> bytes:
    objects = [
        f"<< /Type /Catalog /Pages 2 0 R >>".encode(),
        (
            f"<< /Type /Pages /Kids [{' '.join(f'{index} 0 R' for index in range(3, 3 + page_count))}] "
            f"/Count {page_count} >>"
        ).encode(),
    ]
    for index in range(page_count):
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 612 792] >>"
            ).encode()
        )
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode())
        content.extend(obj)
        content.extend(b"\nendobj\n")

    xref_offset = len(content)
    content.extend(f"xref\n0 {len(offsets)}\n".encode())
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010} 00000 n \n".encode())
    content.extend(
        (
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    return bytes(content)


def make_docx() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    return buffer.getvalue()


def make_scanner(tmp_path, *, exit_code: int) -> str:
    scanner = tmp_path / f"scanner-{exit_code}"
    scanner.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    scanner.chmod(0o700)
    return str(scanner)


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
    monkeypatch.setenv(
        "UPLOAD_SCANNER_EXECUTABLE",
        make_scanner(tmp_path, exit_code=0),
    )

    content = make_pdf()
    response = await make_request(content=content)

    assert response.status_code == 201
    result = response.json()
    assert result["status"] == "QUARANTINED"
    assert result["size_bytes"] == len(content)
    assert result["sha256"] == sha256(content).hexdigest()
    assert result["actual_type"] == "application/pdf"
    assert result["page_count"] == 1
    assert (tmp_path / f"upload-{result['upload_id']}.part").read_bytes() == content


@pytest.mark.anyio
async def test_upload_endpoint_rejects_unsupported_content(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UPLOAD_ENV", "development")
    monkeypatch.setenv("UPLOAD_QUARANTINE_DIR", str(tmp_path))

    response = await make_request(content=b"not a supported document")

    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == "UNSUPPORTED_FILE_TYPE"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_upload_endpoint_rejects_pdf_over_page_limit(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UPLOAD_ENV", "development")
    monkeypatch.setenv("UPLOAD_QUARANTINE_DIR", str(tmp_path))
    monkeypatch.setenv("UPLOAD_MAX_PDF_PAGES", "1")

    response = await make_request(content=make_pdf(page_count=2))

    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == "PDF_PAGE_LIMIT_EXCEEDED"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_upload_endpoint_accepts_docx_package(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UPLOAD_ENV", "development")
    monkeypatch.setenv("UPLOAD_QUARANTINE_DIR", str(tmp_path))
    monkeypatch.setenv(
        "UPLOAD_SCANNER_EXECUTABLE",
        make_scanner(tmp_path, exit_code=0),
    )

    response = await make_request(content=make_docx())

    assert response.status_code == 201
    assert response.json()["actual_type"].endswith("wordprocessingml.document")
    assert response.json()["page_count"] is None


@pytest.mark.anyio
async def test_upload_endpoint_blocks_malware(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UPLOAD_ENV", "development")
    monkeypatch.setenv("UPLOAD_QUARANTINE_DIR", str(tmp_path))
    monkeypatch.setenv(
        "UPLOAD_SCANNER_EXECUTABLE",
        make_scanner(tmp_path, exit_code=1),
    )

    response = await make_request(content=make_pdf())

    assert response.status_code == 423
    assert response.json()["detail"]["status"] == "BLOCKED"
    assert response.json()["detail"]["reason_code"] == "MALWARE_DETECTED"
    assert len(list(tmp_path.glob("upload-*.part"))) == 1


@pytest.mark.anyio
async def test_upload_endpoint_fails_closed_when_scanner_is_unavailable(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UPLOAD_ENV", "development")
    monkeypatch.setenv("UPLOAD_QUARANTINE_DIR", str(tmp_path))
    monkeypatch.setenv(
        "UPLOAD_SCANNER_EXECUTABLE",
        str(tmp_path / "does-not-exist"),
    )

    response = await make_request(content=make_pdf())

    assert response.status_code == 503
    assert list(tmp_path.iterdir()) == []


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

    response = await make_request(content=make_pdf())

    assert response.status_code == 503
