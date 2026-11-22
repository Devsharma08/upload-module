import os
from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException, Request

from upload_module.quarantine import (
    UploadSizeMismatchError,
    UploadTooLargeError,
    write_quarantine_async,
)

app = FastAPI(title="Upload Module")

DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/uploads", status_code=201)
async def upload(request: Request) -> dict[str, int | str]:
    if os.environ.get("UPLOAD_ENV") != "development":
        raise HTTPException(
            status_code=503,
            detail="Upload endpoint is available only in local development",
        )

    try:
        max_bytes = int(
            os.environ.get("UPLOAD_MAX_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
        )
    except ValueError as error:
        raise HTTPException(
            status_code=500,
            detail="Upload byte limit configuration is invalid",
        ) from error

    if max_bytes <= 0:
        raise HTTPException(
            status_code=500,
            detail="Upload byte limit must be greater than zero",
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

    return {
        "upload_id": quarantined.path.stem.removeprefix("upload-"),
        "status": "QUARANTINED",
        "size_bytes": quarantined.size_bytes,
        "sha256": quarantined.sha256,
    }
