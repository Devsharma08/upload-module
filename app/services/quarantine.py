import hashlib
import os
import tempfile
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterable, AsyncIterator


class UploadTooLargeError(ValueError):
    pass


class UploadSizeMismatchError(ValueError):
    pass


@dataclass(frozen=True)
class QuarantinedUpload:
    path: Path
    byte_size: int
    sha256: str


@asynccontextmanager
async def quarantine_upload(
    chunks: AsyncIterable[bytes],
    *,
    quarantine_dir: Path,
    max_bytes: int,
    declared_size: int | None = None,
) -> AsyncIterator[QuarantinedUpload]:
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if declared_size is not None and declared_size < 0:
        raise ValueError("declared_size cannot be negative")
    if declared_size is not None and declared_size > max_bytes:
        raise UploadTooLargeError(f"Upload exceeds the {max_bytes}-byte limit")
    if not quarantine_dir.is_dir():
        raise NotADirectoryError(
            f"Quarantine directory does not exist: {quarantine_dir}"
        )

    file_descriptor, filename = tempfile.mkstemp(
        prefix="egca-upload-",
        dir=quarantine_dir,
    )
    path = Path(filename)
    digest = hashlib.sha256()
    byte_size = 0

    try:
        with os.fdopen(file_descriptor, "wb") as quarantined_file:
            async for chunk in chunks:
                if not isinstance(chunk, bytes):
                    raise TypeError("Upload chunks must be bytes")
                if not chunk:
                    continue
                if byte_size + len(chunk) > max_bytes:
                    raise UploadTooLargeError(
                        f"Upload exceeds the {max_bytes}-byte limit"
                    )

                quarantined_file.write(chunk)
                digest.update(chunk)
                byte_size += len(chunk)

            quarantined_file.flush()

        if declared_size is not None and byte_size != declared_size:
            raise UploadSizeMismatchError(
                f"Received {byte_size} bytes but expected {declared_size}"
            )

        yield QuarantinedUpload(
            path=path,
            byte_size=byte_size,
            sha256=digest.hexdigest(),
        )
    finally:
        path.unlink(missing_ok=True)
