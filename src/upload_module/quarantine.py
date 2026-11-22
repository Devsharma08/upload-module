from dataclasses import dataclass
from functools import partial
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import AsyncIterable, Iterable

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
    ) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be greater than zero")

        if not quarantine_dir.is_dir():
            raise FileNotFoundError("Quarantine directory does not exist")

        self._file = NamedTemporaryFile(
            mode="wb",
            dir=quarantine_dir,
            prefix="upload-",
            suffix=".part",
            delete=False,
        )
        self.path = Path(self._file.name)
        self.max_bytes = max_bytes
        self.declared_size_bytes = declared_size_bytes
        self.digest = sha256()
        self.size_bytes = 0
        self.completed = False

    def write_chunk(self, chunk: bytes) -> None:
        if not isinstance(chunk, bytes):
            raise TypeError("Upload chunks must be bytes")

        next_size = self.size_bytes + len(chunk)
        if next_size > self.max_bytes:
            raise UploadTooLargeError("Upload exceeds the byte limit")

        self._file.write(chunk)
        self.digest.update(chunk)
        self.size_bytes = next_size

    def finish(self) -> QuarantinedUpload:
        self._file.close()
        if (
            self.declared_size_bytes is not None
            and self.size_bytes != self.declared_size_bytes
        ):
            raise UploadSizeMismatchError(
                "Actual upload size does not match declared size"
            )

        self.completed = True
        return QuarantinedUpload(
            path=self.path,
            size_bytes=self.size_bytes,
            sha256=self.digest.hexdigest(),
        )

    def abort(self) -> None:
        if not self._file.closed:
            self._file.close()
        self.path.unlink(missing_ok=True)


def write_quarantine(
    chunks: Iterable[bytes],
    quarantine_dir: Path,
    *,
    max_bytes: int,
    declared_size_bytes: int | None = None,
) -> QuarantinedUpload:
    writer = _QuarantineWriter(
        quarantine_dir,
        max_bytes=max_bytes,
        declared_size_bytes=declared_size_bytes,
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
) -> QuarantinedUpload:
    writer = await anyio.to_thread.run_sync(
        partial(
            _QuarantineWriter,
            quarantine_dir,
            max_bytes=max_bytes,
            declared_size_bytes=declared_size_bytes,
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
