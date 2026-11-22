from functools import partial
from hashlib import sha256
import os
from pathlib import Path
import secrets
import sqlite3

import anyio
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import Response
from starlette.requests import ClientDisconnect

from upload_module.contracts import CreateUploadRequest, UploadOutcome
from upload_module.inspection import (
    InspectionUnavailableError,
    UploadBlockedError,
    UploadRejectedError,
    inspect_upload,
)
from upload_module.quarantine import (
    UploadSizeMismatchError,
    UploadTooLargeError,
    write_quarantine_async,
)
from upload_module.repository import (
    IdempotencyConflictError,
    UploadRepository,
    UploadSession,
    UploadSessionNotFoundError,
    UploadSessionStateError,
)
from upload_module.scanning import ScannerUnavailableError, scan_file

app = FastAPI(title="Upload Module")

DEVELOPMENT_PRINCIPAL = "dev-user"
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB
DEFAULT_MAX_PDF_PAGES = 300
DEFAULT_MAX_DOCX_ENTRIES = 1000
DEFAULT_MAX_DOCX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
DEFAULT_MAX_DOCX_COMPRESSION_RATIO = 100
DEFAULT_SCANNER_MAX_ATTEMPTS = 2
DEFAULT_UPLOAD_SESSION_TTL_SECONDS = 3600


def _require_development() -> None:
    if os.environ.get("UPLOAD_ENV") != "development":
        raise HTTPException(
            status_code=503,
            detail="Upload endpoint is available only in local development",
        )


def _positive_int_setting(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise HTTPException(
            status_code=500,
            detail=f"{name} must be an integer",
        ) from error

    if value <= 0:
        raise HTTPException(
            status_code=500,
            detail=f"{name} must be greater than zero",
        )
    return value


def _repository() -> UploadRepository:
    database_path = Path(
        os.environ.get("UPLOAD_DATABASE_PATH", ".upload-metadata.sqlite3")
    )
    try:
        return UploadRepository(database_path)
    except (OSError, sqlite3.Error) as error:
        raise HTTPException(
            status_code=503,
            detail="Upload metadata storage is unavailable",
        ) from error


def _session_response(session: UploadSession) -> dict[str, int | str | None]:
    return {
        "upload_id": session.upload_id,
        "status": session.status,
        "reason_code": session.reason_code,
        "filename": session.filename,
        "size_bytes": session.size_bytes,
        "sha256": session.sha256,
        "actual_type": session.actual_type,
        "page_count": session.page_count,
        "version_seq": session.version_seq,
        "uploaded_at": session.uploaded_at,
        "expires_at": session.expires_at,
        "duplicate_of": session.duplicate_of,
        "upload_url": f"/uploads/{session.upload_id}/content"
        if session.status == "CREATED"
        else None,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/uploads", status_code=status.HTTP_201_CREATED)
async def create_upload(
    request: CreateUploadRequest,
    http_response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
) -> dict[str, int | str | None]:
    _require_development()
    repository = _repository()
    session_ttl_seconds = _positive_int_setting(
        "UPLOAD_SESSION_TTL_SECONDS",
        DEFAULT_UPLOAD_SESSION_TTL_SECONDS,
    )

    try:
        session, created = repository.create_session(
            upload_id=secrets.token_urlsafe(24),
            principal_id=DEVELOPMENT_PRINCIPAL,
            idempotency_key=idempotency_key,
            request=request,
            session_ttl_seconds=session_ttl_seconds,
        )
    except IdempotencyConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    http_response.status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    return _session_response(session)


@app.put("/uploads/{upload_id}/content")
async def upload_content(upload_id: str, request: Request) -> dict[str, int | str | None]:
    _require_development()
    repository = _repository()
    try:
        session = repository.get_session(
            upload_id,
            principal_id=DEVELOPMENT_PRINCIPAL,
        )
    except UploadSessionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if session.status != "CREATED":
        raise HTTPException(
            status_code=409,
            detail="Upload session is not waiting for file content",
        )

    max_bytes = _positive_int_setting("UPLOAD_MAX_BYTES", DEFAULT_MAX_UPLOAD_BYTES)
    scanner_max_attempts = _positive_int_setting(
        "UPLOAD_SCANNER_MAX_ATTEMPTS",
        DEFAULT_SCANNER_MAX_ATTEMPTS,
    )
    quarantine_dir = Path(os.environ.get("UPLOAD_QUARANTINE_DIR", ".quarantine"))
    try:
        quarantine_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail="Quarantine storage is unavailable",
        ) from error

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            request_size = int(content_length)
        except ValueError as error:
            repository.set_outcome(
                upload_id,
                principal_id=DEVELOPMENT_PRINCIPAL,
                outcome=UploadOutcome.REJECTED,
                reason_code="INVALID_CONTENT_LENGTH",
            )
            raise HTTPException(
                status_code=400,
                detail="Content-Length must be an integer",
            ) from error
        if request_size < 0:
            repository.set_outcome(
                upload_id,
                principal_id=DEVELOPMENT_PRINCIPAL,
                outcome=UploadOutcome.REJECTED,
                reason_code="INVALID_CONTENT_LENGTH",
            )
            raise HTTPException(
                status_code=400,
                detail="Content-Length cannot be negative",
            )
        if request_size > max_bytes:
            repository.set_outcome(
                upload_id,
                principal_id=DEVELOPMENT_PRINCIPAL,
                outcome=UploadOutcome.REJECTED,
                reason_code="UPLOAD_TOO_LARGE",
            )
            raise HTTPException(
                status_code=413,
                detail="Upload exceeds the byte limit",
            )
        if (
            session.declared_size_bytes is not None
            and request_size != session.declared_size_bytes
        ):
            repository.set_outcome(
                upload_id,
                principal_id=DEVELOPMENT_PRINCIPAL,
                outcome=UploadOutcome.REJECTED,
                reason_code="SIZE_MISMATCH",
            )
            raise HTTPException(
                status_code=400,
                detail="Content-Length differs from the declared session size",
            )

    declared_size = session.declared_size_bytes
    if declared_size is None and content_length is not None:
        declared_size = int(content_length)
    try:
        quarantined = await write_quarantine_async(
            request.stream(),
            quarantine_dir,
            max_bytes=max_bytes,
            declared_size_bytes=declared_size,
            file_prefix=(
                "upload-"
                f"{sha256(upload_id.encode('utf-8')).hexdigest()}-"
            ),
        )
    except UploadTooLargeError as error:
        repository.set_outcome(
            upload_id,
            principal_id=DEVELOPMENT_PRINCIPAL,
            outcome=UploadOutcome.REJECTED,
            reason_code="UPLOAD_TOO_LARGE",
        )
        raise HTTPException(status_code=413, detail=str(error)) from error
    except UploadSizeMismatchError as error:
        repository.set_outcome(
            upload_id,
            principal_id=DEVELOPMENT_PRINCIPAL,
            outcome=UploadOutcome.REJECTED,
            reason_code="SIZE_MISMATCH",
        )
        raise HTTPException(status_code=400, detail=str(error)) from error
    except ClientDisconnect as error:
        repository.set_outcome(
            upload_id,
            principal_id=DEVELOPMENT_PRINCIPAL,
            outcome=UploadOutcome.FAILED,
            reason_code="CLIENT_DISCONNECTED",
        )
        raise HTTPException(
            status_code=400,
            detail="Upload connection ended before content was complete",
        ) from error
    except OSError as error:
        repository.set_outcome(
            upload_id,
            principal_id=DEVELOPMENT_PRINCIPAL,
            outcome=UploadOutcome.FAILED,
            reason_code="QUARANTINE_STORAGE_FAILURE",
        )
        raise HTTPException(
            status_code=503,
            detail="Unable to store upload in quarantine",
        ) from error

    scanner_executable = os.environ.get("UPLOAD_SCANNER_EXECUTABLE", "clamscan")
    try:
        scan_result = await anyio.to_thread.run_sync(
            partial(
                scan_file,
                quarantined.path,
                executable=scanner_executable,
                max_attempts=scanner_max_attempts,
            )
        )
    except (ScannerUnavailableError, OSError) as error:
        quarantined.path.unlink(missing_ok=True)
        repository.set_outcome(
            upload_id,
            principal_id=DEVELOPMENT_PRINCIPAL,
            outcome=UploadOutcome.FAILED,
            reason_code="SCANNER_UNAVAILABLE",
        )
        raise HTTPException(
            status_code=503,
            detail="Malware scanner is unavailable",
        ) from error

    if not scan_result.clean:
        repository.set_outcome(
            upload_id,
            principal_id=DEVELOPMENT_PRINCIPAL,
            outcome=UploadOutcome.BLOCKED,
            reason_code="MALWARE_DETECTED",
            size_bytes=quarantined.size_bytes,
            digest=quarantined.sha256,
            quarantine_ref=quarantined.path.name,
        )
        raise HTTPException(
            status_code=423,
            detail={
                "status": "BLOCKED",
                "upload_id": upload_id,
                "reason_code": "MALWARE_DETECTED",
            },
        )

    try:
        max_pdf_pages = _positive_int_setting(
            "UPLOAD_MAX_PDF_PAGES",
            DEFAULT_MAX_PDF_PAGES,
        )
        max_docx_entries = _positive_int_setting(
            "UPLOAD_MAX_DOCX_ENTRIES",
            DEFAULT_MAX_DOCX_ENTRIES,
        )
        max_docx_uncompressed_bytes = _positive_int_setting(
            "UPLOAD_MAX_DOCX_UNCOMPRESSED_BYTES",
            DEFAULT_MAX_DOCX_UNCOMPRESSED_BYTES,
        )
        max_docx_compression_ratio = _positive_int_setting(
            "UPLOAD_MAX_DOCX_COMPRESSION_RATIO",
            DEFAULT_MAX_DOCX_COMPRESSION_RATIO,
        )
        inspection = await anyio.to_thread.run_sync(
            partial(
                inspect_upload,
                quarantined.path,
                max_pdf_pages=max_pdf_pages,
                max_docx_entries=max_docx_entries,
                max_docx_uncompressed_bytes=max_docx_uncompressed_bytes,
                max_docx_compression_ratio=max_docx_compression_ratio,
            )
        )
    except UploadRejectedError as error:
        quarantined.path.unlink(missing_ok=True)
        repository.set_outcome(
            upload_id,
            principal_id=DEVELOPMENT_PRINCIPAL,
            outcome=UploadOutcome.REJECTED,
            reason_code=error.reason_code,
        )
        raise HTTPException(
            status_code=422,
            detail={
                "status": "REJECTED",
                "reason_code": error.reason_code,
                "message": str(error),
            },
        ) from error
    except UploadBlockedError as error:
        repository.set_outcome(
            upload_id,
            principal_id=DEVELOPMENT_PRINCIPAL,
            outcome=UploadOutcome.BLOCKED,
            reason_code=error.reason_code,
            size_bytes=quarantined.size_bytes,
            digest=quarantined.sha256,
            quarantine_ref=quarantined.path.name,
        )
        raise HTTPException(
            status_code=423,
            detail={
                "status": "BLOCKED",
                "upload_id": upload_id,
                "reason_code": error.reason_code,
            },
        ) from error
    except InspectionUnavailableError as error:
        quarantined.path.unlink(missing_ok=True)
        repository.set_outcome(
            upload_id,
            principal_id=DEVELOPMENT_PRINCIPAL,
            outcome=UploadOutcome.FAILED,
            reason_code="INSPECTION_UNAVAILABLE",
        )
        raise HTTPException(
            status_code=503,
            detail="Document inspection service is unavailable",
        ) from error
    except OSError as error:
        quarantined.path.unlink(missing_ok=True)
        repository.set_outcome(
            upload_id,
            principal_id=DEVELOPMENT_PRINCIPAL,
            outcome=UploadOutcome.FAILED,
            reason_code="INSPECTION_FAILURE",
        )
        raise HTTPException(
            status_code=503,
            detail="Unable to inspect quarantined upload",
        ) from error

    expected_extension = {
        "application/pdf": ".pdf",
        (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ): ".docx",
    }[inspection.actual_type]
    if Path(session.filename).suffix.lower() != expected_extension:
        quarantined.path.unlink(missing_ok=True)
        repository.set_outcome(
            upload_id,
            principal_id=DEVELOPMENT_PRINCIPAL,
            outcome=UploadOutcome.REJECTED,
            reason_code="FILE_EXTENSION_MISMATCH",
        )
        raise HTTPException(
            status_code=422,
            detail={
                "status": "REJECTED",
                "reason_code": "FILE_EXTENSION_MISMATCH",
            },
        )
    if (
        session.declared_content_type is not None
        and session.declared_content_type != inspection.actual_type
    ):
        quarantined.path.unlink(missing_ok=True)
        repository.set_outcome(
            upload_id,
            principal_id=DEVELOPMENT_PRINCIPAL,
            outcome=UploadOutcome.REJECTED,
            reason_code="CONTENT_TYPE_MISMATCH",
        )
        raise HTTPException(
            status_code=422,
            detail={
                "status": "REJECTED",
                "reason_code": "CONTENT_TYPE_MISMATCH",
            },
        )

    try:
        completed = repository.complete_upload(
            upload_id,
            principal_id=DEVELOPMENT_PRINCIPAL,
            size_bytes=quarantined.size_bytes,
            digest=quarantined.sha256,
            actual_type=inspection.actual_type,
            page_count=inspection.page_count,
            quarantine_ref=quarantined.path.name,
        )
    except UploadSessionStateError as error:
        quarantined.path.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail=str(error)) from error

    if completed.status == UploadOutcome.DUPLICATE.value:
        quarantined.path.unlink(missing_ok=True)

    return _session_response(completed)


@app.get("/uploads/{upload_id}")
async def get_upload(upload_id: str) -> dict[str, int | str | None]:
    _require_development()
    try:
        session = _repository().get_session(
            upload_id,
            principal_id=DEVELOPMENT_PRINCIPAL,
        )
    except UploadSessionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return _session_response(session)
