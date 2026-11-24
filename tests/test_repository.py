from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from pathlib import Path

from upload_module.contracts import CreateUploadRequest
from upload_module.repository import UploadRepository


def make_request(filename: str) -> CreateUploadRequest:
    return CreateUploadRequest(
        owner_id="owner-1",
        job_id="job-1",
        track="resume",
        filename=filename,
    )


def test_concurrent_idempotent_session_creation_returns_one_session(
    tmp_path: Path,
) -> None:
    repository = UploadRepository(tmp_path / "metadata.sqlite3")
    request = make_request("resume.pdf")

    def create(upload_id: str):
        return repository.create_session(
            upload_id=upload_id,
            principal_id="dev-user",
            idempotency_key="same-key",
            request=request,
            session_ttl_seconds=3600,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create, ["candidate-a", "candidate-b"]))

    assert results[0][0].upload_id == results[1][0].upload_id
    assert sorted(result[1] for result in results) == [False, True]
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM uploads").fetchone()[0] == 1


def test_concurrent_uploads_allocate_distinct_version_sequences(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "metadata.sqlite3"
    repository = UploadRepository(database_path)
    sessions = []
    for index in range(2):
        session, _ = repository.create_session(
            upload_id=f"candidate-{index}",
            principal_id="dev-user",
            idempotency_key=f"key-{index}",
            request=make_request(f"resume-{index}.pdf"),
            session_ttl_seconds=3600,
        )
        sessions.append(session)

    def complete(index: int) -> int:
        completed = repository.complete_upload(
            sessions[index].upload_id,
            principal_id="dev-user",
            size_bytes=100 + index,
            digest=f"{index:064x}",
            actual_type="application/pdf",
            page_count=1,
            quarantine_ref=f"opaque-{index}",
        )
        return completed.version_seq

    with ThreadPoolExecutor(max_workers=2) as executor:
        sequences = list(executor.map(complete, [0, 1]))

    assert sorted(sequences) == [1, 2]
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(DISTINCT version_seq) FROM uploads"
        ).fetchone()[0] == 2


def test_expire_sessions_marks_only_elapsed_created_sessions(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "metadata.sqlite3"
    repository = UploadRepository(database_path)
    expired, _ = repository.create_session(
        upload_id="expired-session",
        principal_id="dev-user",
        idempotency_key="expired-key",
        request=make_request("expired.pdf"),
        session_ttl_seconds=3600,
    )
    active, _ = repository.create_session(
        upload_id="active-session",
        principal_id="dev-user",
        idempotency_key="active-key",
        request=make_request("active.pdf"),
        session_ttl_seconds=3600,
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE uploads SET expires_at = ? WHERE upload_id = ?",
            ("2000-01-01T00:00:00+00:00", expired.upload_id),
        )

    assert repository.expire_sessions() == 1
    assert repository.get_session(
        expired.upload_id,
        principal_id="dev-user",
    ).status == "EXPIRED"
    assert repository.get_session(
        active.upload_id,
        principal_id="dev-user",
    ).status == "CREATED"
    assert repository.expire_sessions() == 0
    with sqlite3.connect(database_path) as connection:
        archived = connection.execute(
            "SELECT record_json FROM expired_upload_archive WHERE upload_id = ?",
            (expired.upload_id,),
        ).fetchone()
    assert archived is not None
    archived_record = json.loads(archived[0])
    assert archived_record["upload_id"] == expired.upload_id
    assert archived_record["outcome"] == "EXPIRED"
    assert archived_record["version_id"] is None
