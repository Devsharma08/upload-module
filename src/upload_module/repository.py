import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from upload_module.contracts import CreateUploadRequest, UploadOutcome


class IdempotencyConflictError(ValueError):
    """Raised when an idempotency key is reused for different request data."""


class UploadSessionNotFoundError(LookupError):
    """Raised when the requested development upload session does not exist."""


class UploadSessionStateError(ValueError):
    """Raised when an upload session is not in the expected state."""


@dataclass(frozen=True)
class UploadSession:
    upload_id: str
    owner_id: str
    job_id: str
    track: str
    filename: str
    declared_content_type: str | None
    declared_size_bytes: int | None
    status: str
    expires_at: str
    reason_code: str | None
    size_bytes: int | None
    sha256: str | None
    actual_type: str | None
    page_count: int | None
    version_seq: int | None
    uploaded_at: str | None
    duplicate_of: str | None
    quarantine_ref: str | None


@dataclass(frozen=True)
class OutboxEvent:
    event_id: str
    upload_id: str
    event_type: str
    payload: str
    created_at: str


def _session_from_row(row: sqlite3.Row) -> UploadSession:
    return UploadSession(
        upload_id=row["upload_id"],
        owner_id=row["owner_id"],
        job_id=row["job_id"],
        track=row["track"],
        filename=row["filename"],
        declared_content_type=row["declared_content_type"],
        declared_size_bytes=row["declared_size_bytes"],
        status=row["status"],
        expires_at=row["expires_at"],
        reason_code=row["reason_code"],
        size_bytes=row["size_bytes"],
        sha256=row["sha256"],
        actual_type=row["actual_type"],
        page_count=row["page_count"],
        version_seq=row["version_seq"],
        uploaded_at=row["uploaded_at"],
        duplicate_of=row["duplicate_of"],
        quarantine_ref=row["quarantine_ref"],
    )


class UploadRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        database_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    upload_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_fingerprint TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    track TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    declared_content_type TEXT,
                    declared_size_bytes INTEGER,
                    status TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    reason_code TEXT,
                    size_bytes INTEGER,
                    sha256 TEXT,
                    actual_type TEXT,
                    page_count INTEGER,
                    version_seq INTEGER,
                    uploaded_at TEXT,
                    duplicate_of TEXT,
                    quarantine_ref TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE (principal_id, idempotency_key)
                );

                CREATE UNIQUE INDEX IF NOT EXISTS uploads_version_sequence
                ON uploads (owner_id, job_id, track, version_seq)
                WHERE version_seq IS NOT NULL;

                CREATE INDEX IF NOT EXISTS uploads_digest_lookup
                ON uploads (owner_id, job_id, sha256, status);

                CREATE TABLE IF NOT EXISTS outbox (
                    event_id TEXT PRIMARY KEY,
                    upload_id TEXT NOT NULL REFERENCES uploads(upload_id),
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    published_at TEXT
                );
                """
            )
        self.database_path.chmod(0o600)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create_session(
        self,
        *,
        upload_id: str,
        principal_id: str,
        idempotency_key: str,
        request: CreateUploadRequest,
        session_ttl_seconds: int,
    ) -> tuple[UploadSession, bool]:
        if session_ttl_seconds <= 0:
            raise ValueError("session_ttl_seconds must be greater than zero")
        request_data = request.model_dump(mode="json")
        fingerprint = json.dumps(
            request_data,
            sort_keys=True,
            separators=(",", ":"),
        )
        created_at = datetime.now(timezone.utc)
        now = created_at.isoformat()
        expires_at = (
            created_at + timedelta(seconds=session_ttl_seconds)
        ).isoformat()

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE uploads
                SET status = ?
                WHERE principal_id = ? AND idempotency_key = ?
                    AND status = 'CREATED' AND expires_at <= ?
                """,
                (
                    UploadOutcome.EXPIRED.value,
                    principal_id,
                    idempotency_key,
                    now,
                ),
            )
            existing = connection.execute(
                """
                SELECT * FROM uploads
                WHERE principal_id = ? AND idempotency_key = ?
                """,
                (principal_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["request_fingerprint"] != fingerprint:
                    raise IdempotencyConflictError(
                        "Idempotency key was already used with different request data"
                    )
                return _session_from_row(existing), False

            connection.execute(
                """
                INSERT INTO uploads (
                    upload_id, principal_id, idempotency_key,
                    request_fingerprint, owner_id, job_id, track, filename,
                    declared_content_type, declared_size_bytes, status,
                    expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    upload_id,
                    principal_id,
                    idempotency_key,
                    fingerprint,
                    request.owner_id,
                    request.job_id,
                    request.track.value,
                    request.filename,
                    request.declared_content_type,
                    request.declared_size_bytes,
                    "CREATED",
                    expires_at,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM uploads WHERE upload_id = ?",
                (upload_id,),
            ).fetchone()
            return _session_from_row(row), True

    def get_session(self, upload_id: str, *, principal_id: str) -> UploadSession:
        with self._connect() as connection:
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                """
                UPDATE uploads
                SET status = ?
                WHERE upload_id = ? AND principal_id = ?
                    AND status = 'CREATED' AND expires_at <= ?
                """,
                (
                    UploadOutcome.EXPIRED.value,
                    upload_id,
                    principal_id,
                    now,
                ),
            )
            row = connection.execute(
                """
                SELECT * FROM uploads
                WHERE upload_id = ? AND principal_id = ?
                """,
                (upload_id, principal_id),
            ).fetchone()
        if row is None:
            raise UploadSessionNotFoundError("Upload session was not found")
        return _session_from_row(row)

    def expire_sessions(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE uploads
                SET status = ?
                WHERE status = 'CREATED' AND expires_at <= ?
                """,
                (UploadOutcome.EXPIRED.value, now),
            )
        return cursor.rowcount

    def complete_upload(
        self,
        upload_id: str,
        *,
        principal_id: str,
        size_bytes: int,
        digest: str,
        actual_type: str,
        page_count: int | None,
        quarantine_ref: str,
    ) -> UploadSession:
        uploaded_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM uploads
                WHERE upload_id = ? AND principal_id = ?
                """,
                (upload_id, principal_id),
            ).fetchone()
            if row is None:
                raise UploadSessionNotFoundError("Upload session was not found")
            if row["status"] != "CREATED":
                raise UploadSessionStateError(
                    "Upload session is not waiting for file content"
                )

            duplicate = connection.execute(
                """
                SELECT upload_id, quarantine_ref FROM uploads
                WHERE owner_id = ? AND job_id = ? AND sha256 = ?
                    AND status = ?
                ORDER BY version_seq
                LIMIT 1
                """,
                (
                    row["owner_id"],
                    row["job_id"],
                    digest,
                    UploadOutcome.READY.value,
                ),
            ).fetchone()
            if duplicate is not None:
                connection.execute(
                    """
                    UPDATE uploads SET
                        status = ?, size_bytes = ?, sha256 = ?,
                        actual_type = ?, page_count = ?, duplicate_of = ?,
                        uploaded_at = ?, quarantine_ref = ?
                    WHERE upload_id = ?
                    """,
                    (
                        UploadOutcome.DUPLICATE.value,
                        size_bytes,
                        digest,
                        actual_type,
                        page_count,
                        duplicate["upload_id"],
                        uploaded_at,
                        duplicate["quarantine_ref"],
                        upload_id,
                    ),
                )
            else:
                sequence = connection.execute(
                    """
                    SELECT COALESCE(MAX(version_seq), 0) + 1
                    FROM uploads
                    WHERE owner_id = ? AND job_id = ? AND track = ?
                    """,
                    (row["owner_id"], row["job_id"], row["track"]),
                ).fetchone()[0]
                connection.execute(
                    """
                    UPDATE uploads SET
                        status = ?, size_bytes = ?, sha256 = ?,
                        actual_type = ?, page_count = ?, version_seq = ?,
                        uploaded_at = ?, quarantine_ref = ?
                    WHERE upload_id = ?
                    """,
                    (
                        UploadOutcome.READY.value,
                        size_bytes,
                        digest,
                        actual_type,
                        page_count,
                        sequence,
                        uploaded_at,
                        quarantine_ref,
                        upload_id,
                    ),
                )
                payload = json.dumps(
                    {
                        "upload_id": upload_id,
                        "version_seq": sequence,
                        "owner_id": row["owner_id"],
                        "job_id": row["job_id"],
                        "track": row["track"],
                        "sha256": digest,
                        "quarantine_ref": quarantine_ref,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                connection.execute(
                    """
                    INSERT INTO outbox (
                        event_id, upload_id, event_type, payload, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        upload_id,
                        upload_id,
                        "UPLOAD_READY",
                        payload,
                        uploaded_at,
                    ),
                )

            updated = connection.execute(
                "SELECT * FROM uploads WHERE upload_id = ?",
                (upload_id,),
            ).fetchone()
            return _session_from_row(updated)

    def set_outcome(
        self,
        upload_id: str,
        *,
        principal_id: str,
        outcome: UploadOutcome,
        reason_code: str,
        size_bytes: int | None = None,
        digest: str | None = None,
        actual_type: str | None = None,
        page_count: int | None = None,
        quarantine_ref: str | None = None,
    ) -> UploadSession:
        if outcome not in {
            UploadOutcome.REJECTED,
            UploadOutcome.BLOCKED,
            UploadOutcome.FAILED,
        }:
            raise ValueError("Outcome is not a terminal failure outcome")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE uploads
                SET status = ?, reason_code = ?, size_bytes = ?, sha256 = ?,
                    actual_type = ?, page_count = ?, quarantine_ref = ?,
                    uploaded_at = ?
                WHERE upload_id = ? AND principal_id = ? AND status = 'CREATED'
                """,
                (
                    outcome.value,
                    reason_code,
                    size_bytes,
                    digest,
                    actual_type,
                    page_count,
                    quarantine_ref,
                    datetime.now(timezone.utc).isoformat(),
                    upload_id,
                    principal_id,
                ),
            )
            if cursor.rowcount == 0:
                raise UploadSessionNotFoundError("Upload session was not found")
            row = connection.execute(
                "SELECT * FROM uploads WHERE upload_id = ?",
                (upload_id,),
            ).fetchone()
            return _session_from_row(row)

    def pending_outbox(self, *, limit: int = 100) -> list[OutboxEvent]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_id, upload_id, event_type, payload, created_at
                FROM outbox
                WHERE published_at IS NULL
                ORDER BY created_at, event_id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            OutboxEvent(
                event_id=row["event_id"],
                upload_id=row["upload_id"],
                event_type=row["event_type"],
                payload=row["payload"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def mark_outbox_published(self, event_id: str) -> bool:
        published_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE outbox
                SET published_at = ?
                WHERE event_id = ? AND published_at IS NULL
                """,
                (published_at, event_id),
            )
        return cursor.rowcount == 1
