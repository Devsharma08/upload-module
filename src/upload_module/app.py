from functools import partial
import os
from pathlib import Path

import anyio
from fastapi import FastAPI
from fastapi import HTTPException, Request

from upload_module.quarantine import (
    UploadSizeMismatchError,
    UploadTooLargeError,
    write_quarantine_async,
)
from upload_module.inspection import (
    UploadBlockedError,
    UploadRejectedError,
    InspectionUnavailableError,
    inspect_upload,
)
from upload_module.scanning import ScannerUnavailableError, scan_file

app = FastAPI(title="Upload Module")

DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024 # 10 MB
DEFAULT_MAX_PDF_PAGES = 300
DEFAULT_MAX_DOCX_ENTRIES = 1000
DEFAULT_MAX_DOCX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
DEFAULT_MAX_DOCX_COMPRESSION_RATIO = 100


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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/uploads", status_code=201)
async def upload(request: Request) -> dict[str, int | str | None]:
    if os.environ.get("UPLOAD_ENV") != "development":
        raise HTTPException(
            status_code=503,
            detail="Upload endpoint is available only in local development",
        )

    max_bytes = _positive_int_setting("UPLOAD_MAX_BYTES", DEFAULT_MAX_UPLOAD_BYTES)
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

    quarantine_dir = Path(
        os.environ.get("UPLOAD_QUARANTINE_DIR", ".quarantine")
    )
    try:
        quarantine_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail="Quarantine storage is unavailable",
        ) from error

    declared_size_bytes: int | None = None
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_size_bytes = int(content_length)
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail="Content-Length must be an integer",
            ) from error

        if declared_size_bytes < 0:
            raise HTTPException(
                status_code=400,
                detail="Content-Length cannot be negative",
            )
        if declared_size_bytes > max_bytes:
            raise HTTPException(
                status_code=413,
                detail="Upload exceeds the byte limit",
            )

    try:
        quarantined = await write_quarantine_async(
            request.stream(),
            quarantine_dir,
            max_bytes=max_bytes,
            declared_size_bytes=declared_size_bytes,
        )
    except UploadTooLargeError as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except UploadSizeMismatchError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail="Unable to store upload in quarantine",
        ) from error

    try:
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
        raise HTTPException(
            status_code=422,
            detail={
                "status": "REJECTED",
                "reason_code": error.reason_code,
                "message": str(error),
            },
        ) from error
    except UploadBlockedError as error:
        raise HTTPException(
            status_code=423,
            detail={
                "status": "BLOCKED",
                "upload_id": quarantined.path.stem.removeprefix("upload-"),
                "reason_code": error.reason_code,
                "message": str(error),
            },
        ) from error
    except InspectionUnavailableError as error:
        quarantined.path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=503,
            detail="Document inspection service is unavailable",
        ) from error
    except OSError as error:
        quarantined.path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=503,
            detail="Unable to inspect quarantined upload",
        ) from error

    scanner_executable = os.environ.get(
        "UPLOAD_SCANNER_EXECUTABLE",
        "clamscan",
    )
    try:
        scan_result = await anyio.to_thread.run_sync(
            partial(
                scan_file,
                quarantined.path,
                executable=scanner_executable,
            )
        )
    except ScannerUnavailableError as error:
        quarantined.path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=503,
            detail="Malware scanner is unavailable",
        ) from error
    except OSError as error:
        quarantined.path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=503,
            detail="Unable to scan quarantined upload",
        ) from error

    if not scan_result.clean:
        raise HTTPException(
            status_code=423,
            detail={
                "status": "BLOCKED",
                "upload_id": quarantined.path.stem.removeprefix("upload-"),
                "reason_code": "MALWARE_DETECTED",
            },
        )

    return {
        "upload_id": quarantined.path.stem.removeprefix("upload-"),
        "status": "QUARANTINED",
        "size_bytes": quarantined.size_bytes,
        "sha256": quarantined.sha256,
        "actual_type": inspection.actual_type,
        "page_count": inspection.page_count,
    }
