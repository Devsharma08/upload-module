from hashlib import sha256
import io
import sqlite3
import zipfile

import httpx
import pytest

from upload_module.app import app


def make_pdf(page_count: int = 1) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            f"<< /Type /Pages /Kids "
            f"[{' '.join(f'{index} 0 R' for index in range(3, 3 + page_count))}] "
            f"/Count {page_count} >>"
        ).encode(),
    ]
    for _ in range(page_count):
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>"
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


def make_docx(
    *,
    with_macro: bool = False,
    with_external_relationship: bool = False,
    padding: bytes = b"",
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", b"<document/>" + padding)
        if with_macro:
            archive.writestr("word/vbaProject.bin", b"macro")
        if with_external_relationship:
            archive.writestr(
                "word/_rels/document.xml.rels",
                '<Relationships><Relationship TargetMode = "External" '
                'Target="https://example.invalid"/></Relationships>',
            )
    return buffer.getvalue()


def make_scanner(tmp_path, *, exit_code: int) -> str:
    scanner = tmp_path / f"scanner-{exit_code}"
    scanner.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    scanner.chmod(0o700)
    return str(scanner)


def enable_development(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UPLOAD_ENV", "development")
    monkeypatch.setenv("UPLOAD_QUARANTINE_DIR", str(tmp_path / "quarantine"))
    monkeypatch.setenv(
        "UPLOAD_DATABASE_PATH",
        str(tmp_path / "metadata.sqlite3"),
    )
    monkeypatch.setenv(
        "UPLOAD_SCANNER_EXECUTABLE",
        make_scanner(tmp_path, exit_code=0),
    )


async def send_request(
    method: str,
    path: str,
    *,
    content: bytes | None = None,
    json_body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.request(
            method,
            path,
            content=content,
            json=json_body,
            headers=headers,
        )


async def create_session(
    *,
    filename: str = "resume.pdf",
    track: str = "resume",
    declared_content_type: str | None = None,
    declared_size_bytes: int | None = None,
    idempotency_key: str = "test-upload",
) -> httpx.Response:
    body: dict[str, object] = {
        "owner_id": "owner-1",
        "job_id": "job-1",
        "track": track,
        "filename": filename,
    }
    if declared_content_type is not None:
        body["declared_content_type"] = declared_content_type
    if declared_size_bytes is not None:
        body["declared_size_bytes"] = declared_size_bytes

    return await send_request(
        "POST",
        "/uploads",
        json_body=body,
        headers={"Idempotency-Key": idempotency_key},
    )


async def put_content(
    upload_id: str,
    content: bytes,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return await send_request(
        "PUT",
        f"/uploads/{upload_id}/content",
        content=content,
        headers=headers,
    )


@pytest.mark.anyio
async def test_health_endpoint() -> None:
    response = await send_request("GET", "/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_upload_home_page_is_development_only_and_shows_configured_limit(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UPLOAD_ENV", raising=False)
    disabled_response = await send_request("GET", "/")

    enable_development(tmp_path, monkeypatch)
    monkeypatch.setenv("UPLOAD_MAX_BYTES", "5242880")
    enabled_response = await send_request("GET", "/")

    assert disabled_response.status_code == 503
    assert enabled_response.status_code == 200
    assert "Upload desk" in enabled_response.text
    assert "job_description" in enabled_response.text
    assert "Upload steps" in enabled_response.text
    assert "upload-progress" in enabled_response.text
    assert "5242880" in enabled_response.text
    assert "__MAX_UPLOAD_BYTES__" not in enabled_response.text


@pytest.mark.anyio
async def test_upload_session_and_content_reach_ready(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    content = make_pdf()

    created = await create_session(declared_size_bytes=len(content))
    assert created.status_code == 201
    upload_id = created.json()["upload_id"]
    assert created.json()["status"] == "CREATED"

    response = await put_content(upload_id, content)

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "READY"
    assert result["size_bytes"] == len(content)
    assert result["sha256"] == sha256(content).hexdigest()
    assert result["actual_type"] == "application/pdf"
    assert result["page_count"] == 1
    assert result["version_seq"] == 1
    assert "quarantine_ref" not in result

    quarantine_files = list((tmp_path / "quarantine").glob("upload-*.part"))
    assert len(quarantine_files) == 1
    quarantine_path = quarantine_files[0]
    assert quarantine_path.read_bytes() == content

    status_response = await send_request("GET", f"/uploads/{upload_id}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "READY"
    assert "quarantine_ref" not in status_response.json()

    with sqlite3.connect(tmp_path / "metadata.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 1
        stored_ref = connection.execute(
            "SELECT quarantine_ref FROM uploads WHERE upload_id = ?",
            (upload_id,),
        ).fetchone()[0]
    assert stored_ref == quarantine_path.name


@pytest.mark.anyio
async def test_upload_accepts_docx_package(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    content = make_docx()
    session = await create_session(filename="candidate.docx")

    response = await put_content(session.json()["upload_id"], content)

    assert response.status_code == 200
    assert response.json()["status"] == "READY"
    assert response.json()["actual_type"].endswith("wordprocessingml.document")
    assert response.json()["page_count"] is None
    assert response.json()["sha256"] == sha256(content).hexdigest()


@pytest.mark.anyio
async def test_job_description_accepts_document_upload(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    content = make_docx()
    session = await create_session(
        filename="job-description.docx",
        track="job_description",
    )

    response = await put_content(session.json()["upload_id"], content)

    assert response.status_code == 200
    assert response.json()["status"] == "READY"
    assert response.json()["actual_type"].endswith("wordprocessingml.document")


@pytest.mark.anyio
async def test_upload_rejects_mismatched_filename_extension(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    session = await create_session(filename="resume.docx")

    response = await put_content(session.json()["upload_id"], make_pdf())

    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == "FILE_EXTENSION_MISMATCH"
    assert list((tmp_path / "quarantine").iterdir()) == []


@pytest.mark.anyio
async def test_upload_rejects_mismatched_declared_content_type(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    session = await create_session(
        declared_content_type="application/vnd.example",
    )

    response = await put_content(session.json()["upload_id"], make_pdf())

    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == "CONTENT_TYPE_MISMATCH"
    assert list((tmp_path / "quarantine").iterdir()) == []


@pytest.mark.anyio
async def test_upload_blocks_docx_with_embedded_macro(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    session = await create_session(filename="candidate.docx")

    response = await put_content(
        session.json()["upload_id"],
        make_docx(with_macro=True),
    )
    status_response = await send_request(
        "GET",
        f"/uploads/{session.json()['upload_id']}",
    )

    assert response.status_code == 423
    assert response.json()["detail"]["reason_code"] == "DOCX_ACTIVE_CONTENT"
    assert status_response.json()["status"] == "BLOCKED"
    assert "quarantine_ref" not in status_response.json()
    assert len(list((tmp_path / "quarantine").glob("upload-*.part"))) == 1


@pytest.mark.anyio
async def test_upload_blocks_docx_with_external_relationship(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    session = await create_session(filename="candidate.docx")

    response = await put_content(
        session.json()["upload_id"],
        make_docx(with_external_relationship=True),
    )

    assert response.status_code == 423
    assert (
        response.json()["detail"]["reason_code"]
        == "DOCX_EXTERNAL_RELATIONSHIP"
    )


@pytest.mark.anyio
async def test_upload_blocks_pdf_with_active_content_marker(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    session = await create_session()
    content = make_pdf().replace(
        b"/Type /Catalog",
        b"/Type /Catalog /OpenAction (unsafe)",
    )

    response = await put_content(session.json()["upload_id"], content)

    assert response.status_code == 423
    assert response.json()["detail"]["reason_code"] == "PDF_ACTIVE_CONTENT"


@pytest.mark.anyio
async def test_upload_rejects_docx_expansion_over_configured_limit(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    monkeypatch.setenv("UPLOAD_MAX_DOCX_UNCOMPRESSED_BYTES", "10")
    session = await create_session(filename="candidate.docx")

    response = await put_content(
        session.json()["upload_id"],
        make_docx(padding=b"x" * 100),
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]["reason_code"]
        == "DOCX_EXPANSION_LIMIT_EXCEEDED"
    )
    assert list((tmp_path / "quarantine").iterdir()) == []


@pytest.mark.anyio
async def test_upload_versions_increase_for_same_owner_job_track(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)

    first_session = await create_session(idempotency_key="version-one")
    first_result = await put_content(
        first_session.json()["upload_id"],
        make_pdf(),
    )
    second_session = await create_session(idempotency_key="version-two")
    second_result = await put_content(
        second_session.json()["upload_id"],
        make_pdf(page_count=2),
    )

    assert first_result.json()["version_seq"] == 1
    assert second_result.json()["version_seq"] == 2
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 2


@pytest.mark.anyio
async def test_upload_session_idempotency_replays_or_conflicts(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)

    first = await create_session(idempotency_key="same-key")
    replay = await create_session(idempotency_key="same-key")
    conflict = await create_session(
        filename="different.pdf",
        idempotency_key="same-key",
    )
    assert first.status_code == 201
    assert first.status_code == 201
    assert replay.json()["upload_id"] == first.json()["upload_id"]
    assert replay.json()["upload_id"] == first.json()["upload_id"]
    assert conflict.status_code == 409


@pytest.mark.anyio
async def test_created_session_expires_before_content_transfer(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    session = await create_session()
    upload_id = session.json()["upload_id"]

    with sqlite3.connect(tmp_path / "metadata.sqlite3") as connection:
        connection.execute(
            "UPDATE uploads SET expires_at = ? WHERE upload_id = ?",
            ("2000-01-01T00:00:00+00:00", upload_id),
        )

    status_response = await send_request("GET", f"/uploads/{upload_id}")
    transfer_response = await put_content(upload_id, make_pdf())

    assert status_response.json()["status"] == "EXPIRED"
    assert transfer_response.status_code == 409
    assert not (tmp_path / "quarantine").exists()


@pytest.mark.anyio
async def test_duplicate_upload_links_existing_version_without_new_outbox_event(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    content = make_pdf()

    first_session = await create_session(idempotency_key="first-upload")
    first_result = await put_content(first_session.json()["upload_id"], content)
    second_session = await create_session(idempotency_key="second-upload")
    second_result = await put_content(second_session.json()["upload_id"], content)

    assert first_result.json()["status"] == "READY"
    assert second_result.json()["status"] == "DUPLICATE"
    assert second_result.json()["duplicate_of"] == first_session.json()["upload_id"]
    assert second_result.json()["version_seq"] is None
    assert len(list((tmp_path / "quarantine").glob("upload-*.part"))) == 1
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 1


@pytest.mark.anyio
async def test_upload_rejects_unsupported_content_and_cleans_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    session = await create_session()

    response = await put_content(session.json()["upload_id"], b"not a document")
    status_response = await send_request(
        "GET",
        f"/uploads/{session.json()['upload_id']}",
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == "UNSUPPORTED_FILE_TYPE"
    assert status_response.json()["status"] == "REJECTED"
    assert list((tmp_path / "quarantine").iterdir()) == []


@pytest.mark.anyio
async def test_upload_rejects_pdf_over_page_limit(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    monkeypatch.setenv("UPLOAD_MAX_PDF_PAGES", "1")
    session = await create_session()

    response = await put_content(
        session.json()["upload_id"],
        make_pdf(page_count=2),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == "PDF_PAGE_LIMIT_EXCEEDED"
    assert list((tmp_path / "quarantine").iterdir()) == []


@pytest.mark.anyio
async def test_upload_blocks_malware_and_retains_quarantined_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    monkeypatch.setenv(
        "UPLOAD_SCANNER_EXECUTABLE",
        make_scanner(tmp_path, exit_code=1),
    )
    session = await create_session()

    response = await put_content(session.json()["upload_id"], make_pdf())
    status_response = await send_request(
        "GET",
        f"/uploads/{session.json()['upload_id']}",
    )

    assert response.status_code == 423
    assert response.json()["detail"]["reason_code"] == "MALWARE_DETECTED"
    assert status_response.json()["status"] == "BLOCKED"
    assert "quarantine_ref" not in status_response.json()
    assert len(list((tmp_path / "quarantine").glob("upload-*.part"))) == 1


@pytest.mark.anyio
async def test_upload_fails_closed_when_scanner_is_unavailable(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    monkeypatch.setenv(
        "UPLOAD_SCANNER_EXECUTABLE",
        str(tmp_path / "does-not-exist"),
    )
    session = await create_session()

    response = await put_content(session.json()["upload_id"], make_pdf())
    status_response = await send_request(
        "GET",
        f"/uploads/{session.json()['upload_id']}",
    )

    assert response.status_code == 503
    assert status_response.json()["status"] == "FAILED"
    assert list((tmp_path / "quarantine").iterdir()) == []


@pytest.mark.anyio
async def test_transient_scanner_failure_recovers_with_new_session(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    monkeypatch.setenv(
        "UPLOAD_SCANNER_EXECUTABLE",
        str(tmp_path / "does-not-exist"),
    )
    first_session = await create_session(idempotency_key="failed-attempt")

    failed_response = await put_content(
        first_session.json()["upload_id"],
        make_pdf(),
    )
    replayed_session = await create_session(idempotency_key="failed-attempt")

    assert failed_response.status_code == 503
    assert replayed_session.json()["status"] == "FAILED"
    assert replayed_session.json()["upload_id"] == first_session.json()["upload_id"]

    monkeypatch.setenv(
        "UPLOAD_SCANNER_EXECUTABLE",
        make_scanner(tmp_path, exit_code=0),
    )
    retry_session = await create_session(idempotency_key="retry-attempt")
    retry_response = await put_content(
        retry_session.json()["upload_id"],
        make_pdf(),
    )
    original_status = await send_request(
        "GET",
        f"/uploads/{first_session.json()['upload_id']}",
    )

    assert retry_response.status_code == 200
    assert retry_response.json()["status"] == "READY"
    assert original_status.json()["status"] == "FAILED"
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 1


@pytest.mark.anyio
async def test_upload_rejects_body_over_configured_limit(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    monkeypatch.setenv("UPLOAD_MAX_BYTES", "4")
    session = await create_session()

    response = await put_content(session.json()["upload_id"], b"12345")

    assert response.status_code == 413
    assert list((tmp_path / "quarantine").iterdir()) == []


@pytest.mark.anyio
async def test_upload_rejects_declared_size_mismatch(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_development(tmp_path, monkeypatch)
    session = await create_session(declared_size_bytes=10)

    response = await put_content(session.json()["upload_id"], b"actual")

    assert response.status_code == 400
    assert list((tmp_path / "quarantine").iterdir()) == []


@pytest.mark.anyio
async def test_upload_endpoint_is_disabled_outside_explicit_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UPLOAD_ENV", raising=False)

    response = await create_session()

    assert response.status_code == 503
