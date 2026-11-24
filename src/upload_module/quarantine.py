from dataclasses import dataclass
from functools import partial
from hashlib import sha256
import errno
import os
from pathlib import Path
from tempfile import mkstemp
from time import sleep
from typing import AsyncIterable, Callable, Iterable

import anyio


class UploadTooLargeError(ValueError):
    """Raised when an upload exceeds the configured byte limit."""


class UploadSizeMismatchError(ValueError):
    """Raised when actual upload size differs from the declared size."""


@dataclass(frozen=True)
class QuarantinedUpload:
    path: Path
    size_bytes: int
    sha256: str


class _QuarantineWriter:
    def __init__(
        self,
        quarantine_dir: Path,
        *,
        max_bytes: int,
        declared_size_bytes: int | None,
        file_prefix: str,
        max_storage_attempts: int,
    ) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be greater than zero")
        if max_storage_attempts <= 0:
            raise ValueError("max_storage_attempts must be greater than zero")
        if not file_prefix or Path(file_prefix).name != file_prefix:
            raise ValueError("file_prefix must not contain a directory path")

        if not quarantine_dir.is_dir():
            raise FileNotFoundError("Quarantine directory does not exist")

        self.max_storage_attempts = max_storage_attempts
        self._fd, self.path = self._create_temp_file(
            quarantine_dir,
            file_prefix,
        )
        self.max_bytes = max_bytes
        self.declared_size_bytes = declared_size_bytes
        self.digest = sha256()
        self.size_bytes = 0
        self.completed = False

    def _create_temp_file(
        self,
        quarantine_dir: Path,
        file_prefix: str,
    ) -> tuple[int, Path]:
        for attempt in range(self.max_storage_attempts):
            try:
                file_descriptor, filename = mkstemp(
                    dir=quarantine_dir,
                    prefix=file_prefix,
                    suffix=".part",
                )
                return file_descriptor, Path(filename)
            except OSError:
                if attempt + 1 == self.max_storage_attempts:
                    raise
                sleep(min(0.05 * (attempt + 1), 0.2))

        raise AssertionError("Temporary file retry loop exited unexpectedly")

    def _retry_storage_call(self, operation: Callable[[], None]) -> None:
        for attempt in range(self.max_storage_attempts):
            try:
                operation()
                return
            except OSError:
                if attempt + 1 == self.max_storage_attempts:
                    raise
                sleep(min(0.05 * (attempt + 1), 0.2))

    def write_chunk(self, chunk: bytes) -> None:
        if not isinstance(chunk, bytes):
            raise TypeError("Upload chunks must be bytes")

        next_size = self.size_bytes + len(chunk)
        if next_size > self.max_bytes:
            raise UploadTooLargeError("Upload exceeds the byte limit")

        for attempt in range(self.max_storage_attempts):
            offset = 0
            try:
                while offset < len(chunk):
                    written = os.write(self._fd, chunk[offset:])
                    if written == 0:
                        raise OSError(errno.EIO, "Quarantine write made no progress")
                    offset += written
                break
            except OSError as error:
                try:
                    os.ftruncate(self._fd, self.size_bytes)
                    os.lseek(self._fd, self.size_bytes, os.SEEK_SET)
                except OSError as rollback_error:
                    raise rollback_error from error
                if attempt + 1 == self.max_storage_attempts:
                    raise
                sleep(min(0.05 * (attempt + 1), 0.2))

        self.digest.update(chunk)
        self.size_bytes = next_size

    def finish(self) -> QuarantinedUpload:
        self._retry_storage_call(lambda: os.fsync(self._fd))
        file_descriptor = self._fd
        self._fd = -1
        os.close(file_descriptor)
        if (
            self.declared_size_bytes is not None
            and self.size_bytes != self.declared_size_bytes
        ):
            raise UploadSizeMismatchError(
                "Actual upload size does not match declared size"
            )

        self._retry_storage_call(lambda: os.chmod(self.path, 0o400))
        self.completed = True
        return QuarantinedUpload(
            path=self.path,
            size_bytes=self.size_bytes,
            sha256=self.digest.hexdigest(),
        )

    def abort(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1
        self.path.unlink(missing_ok=True)


def write_quarantine(
    chunks: Iterable[bytes],
    quarantine_dir: Path,
    *,
    max_bytes: int,
    declared_size_bytes: int | None = None,
    file_prefix: str = "upload-",
    max_storage_attempts: int = 2,
) -> QuarantinedUpload:
    writer = _QuarantineWriter(
        quarantine_dir,
        max_bytes=max_bytes,
        declared_size_bytes=declared_size_bytes,
        file_prefix=file_prefix,
        max_storage_attempts=max_storage_attempts,
    )
    try:
        for chunk in chunks:
            writer.write_chunk(chunk)
        return writer.finish()
    finally:
        if not writer.completed:
            writer.abort()


async def write_quarantine_async(
    chunks: AsyncIterable[bytes],
    quarantine_dir: Path,
    *,
    max_bytes: int,
    declared_size_bytes: int | None = None,
    file_prefix: str = "upload-",
    max_storage_attempts: int = 2,
) -> QuarantinedUpload:
    writer = await anyio.to_thread.run_sync(
        partial(
            _QuarantineWriter,
            quarantine_dir,
            max_bytes=max_bytes,
            declared_size_bytes=declared_size_bytes,
            file_prefix=file_prefix,
            max_storage_attempts=max_storage_attempts,
        )
    )
    try:
        async for chunk in chunks:
            await anyio.to_thread.run_sync(writer.write_chunk, chunk)
        return await anyio.to_thread.run_sync(writer.finish)
    finally:
        if not writer.completed:
            with anyio.CancelScope(shield=True):
                await anyio.to_thread.run_sync(writer.abort)
