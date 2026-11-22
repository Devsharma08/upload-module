import json
import sqlite3
from pathlib import Path

import pytest

from upload_module.contracts import CreateUploadRequest
from upload_module.handoff import HandoffConflictError, dispatch_outbox
from upload_module.repository import UploadRepository


def create_ready_event(database_path: Path) -> UploadRepository:
    repository = UploadRepository(database_path)
    request = CreateUploadRequest(
        owner_id="owner-1",
        job_id="job-1",
        track="resume",
        filename="resume.pdf",
    )
    repository.create_session(
        upload_id="opaque-upload-1",
        principal_id="dev-user",
        idempotency_key="key-1",
        request=request,
        session_ttl_seconds=3600,
    )
    repository.complete_upload(
        "opaque-upload-1",
        principal_id="dev-user",
        size_bytes=123,
        digest="a" * 64,
        actual_type="application/pdf",
        page_count=1,
        quarantine_ref="upload-file.part",
    )
    return repository


def test_dispatch_writes_ready_event_and_marks_it_published(tmp_path: Path) -> None:
    repository = create_ready_event(tmp_path / "metadata.sqlite3")
    handoff_dir = tmp_path / "handoff"

    published_count = dispatch_outbox(repository, handoff_dir)

    event_path = handoff_dir / "opaque-upload-1.json"
    event = json.loads(event_path.read_text())
    assert published_count == 1
    assert event["event_id"] == "opaque-upload-1"
    assert event["event_type"] == "UPLOAD_READY"
    assert event["payload"]["sha256"] == "a" * 64
    assert event["payload"]["quarantine_ref"] == "upload-file.part"
    assert repository.pending_outbox() == []
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as connection:
        assert connection.execute(
            "SELECT published_at FROM outbox WHERE event_id = ?",
            ("opaque-upload-1",),
        ).fetchone()[0] is not None


def test_dispatch_is_idempotent_when_repeated(tmp_path: Path) -> None:
    repository = create_ready_event(tmp_path / "metadata.sqlite3")
    handoff_dir = tmp_path / "handoff"

    assert dispatch_outbox(repository, handoff_dir) == 1
    event_path = handoff_dir / "opaque-upload-1.json"
    original_content = event_path.read_bytes()

    assert dispatch_outbox(repository, handoff_dir) == 0
    assert event_path.read_bytes() == original_content
    assert list(handoff_dir.iterdir()) == [event_path]


def test_dispatch_recovers_if_acknowledgement_fails_after_file_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_ready_event(tmp_path / "metadata.sqlite3")
    handoff_dir = tmp_path / "handoff"

    def fail_acknowledgement(_event_id: str) -> bool:
        raise OSError("database acknowledgement failed")

    monkeypatch.setattr(repository, "mark_outbox_published", fail_acknowledgement)
    with pytest.raises(OSError, match="database acknowledgement failed"):
        dispatch_outbox(repository, handoff_dir)

    monkeypatch.undo()
    assert len(list(handoff_dir.glob("*.json"))) == 1
    assert dispatch_outbox(repository, handoff_dir) == 1
    assert repository.pending_outbox() == []
    assert len(list(handoff_dir.glob("*.json"))) == 1


def test_dispatch_refuses_to_overwrite_different_event_content(
    tmp_path: Path,
) -> None:
    repository = create_ready_event(tmp_path / "metadata.sqlite3")
    handoff_dir = tmp_path / "handoff"
    handoff_dir.mkdir()
    target = handoff_dir / "opaque-upload-1.json"
    target.write_text('{"event_id":"not-the-same-event"}\n')

    with pytest.raises(HandoffConflictError):
        dispatch_outbox(repository, handoff_dir)

    assert repository.pending_outbox()
