from hashlib import sha256
import os
import sqlite3
import time
from pathlib import Path

from upload_module.cleanup import cleanup_quarantine_orphans
from upload_module.contracts import CreateUploadRequest
from upload_module.repository import UploadRepository


def make_request(filename: str) -> CreateUploadRequest:
    return CreateUploadRequest(
        owner_id="owner-1",
        job_id="job-1",
        track="resume",
        filename=filename,
    )


def quarantine_path(quarantine_dir: Path, upload_id: str) -> Path:
    upload_hash = sha256(upload_id.encode("utf-8")).hexdigest()
    return quarantine_dir / f"upload-{upload_hash}-temporary.part"


def test_cleanup_removes_old_orphans_but_preserves_active_and_referenced_files(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "metadata.sqlite3"
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir()
    repository = UploadRepository(database_path)

    expired, _ = repository.create_session(
        upload_id="expired-upload",
        principal_id="dev-user",
        idempotency_key="expired-key",
        request=make_request("expired.pdf"),
        session_ttl_seconds=3600,
    )
    active, _ = repository.create_session(
        upload_id="active-upload",
        principal_id="dev-user",
        idempotency_key="active-key",
        request=make_request("active.pdf"),
        session_ttl_seconds=3600,
    )
    ready, _ = repository.create_session(
        upload_id="ready-upload",
        principal_id="dev-user",
        idempotency_key="ready-key",
        request=make_request("ready.pdf"),
        session_ttl_seconds=3600,
    )
    ready_file = quarantine_path(quarantine_dir, ready.upload_id)
    ready_file.write_bytes(b"ready")
    repository.complete_upload(
        ready.upload_id,
        principal_id="dev-user",
        size_bytes=5,
        digest="a" * 64,
        actual_type="application/pdf",
        page_count=1,
        quarantine_ref=ready_file.name,
    )

    expired_file = quarantine_path(quarantine_dir, expired.upload_id)
    active_file = quarantine_path(quarantine_dir, active.upload_id)
    orphan_file = quarantine_path(quarantine_dir, "missing-upload")
    for path in (expired_file, active_file, orphan_file):
        path.write_bytes(b"temporary")
        os.utime(path, (time.time() - 100, time.time() - 100))
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE uploads SET expires_at = ? WHERE upload_id = ?",
            ("2000-01-01T00:00:00+00:00", expired.upload_id),
        )
    repository.expire_sessions()

    removed_count = cleanup_quarantine_orphans(
        quarantine_dir,
        repository,
        min_age_seconds=10,
    )

    assert removed_count == 2
    assert not expired_file.exists()
    assert not orphan_file.exists()
    assert active_file.exists()
    assert ready_file.exists()
