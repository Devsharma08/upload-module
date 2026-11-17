import asyncio
import hashlib
from pathlib import Path
from typing import AsyncIterator

import pytest

from app.services.quarantine import (
    UploadSizeMismatchError,
    UploadTooLargeError,
    quarantine_upload,
)


async def chunks(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        yield part


def test_quarantine_streams_bytes_and_reports_authoritative_digest(
    tmp_path: Path,
) -> None:
    async def run() -> None:
        content = b"trusted input is still untrusted"

        async with quarantine_upload(
            chunks(b"trusted input ", b"is still untrusted"),
            quarantine_dir=tmp_path,
            max_bytes=1024,
            declared_size=len(content),
        ) as upload:
            assert upload.path.read_bytes() == content
            assert upload.byte_size == len(content)
            assert upload.sha256 == hashlib.sha256(content).hexdigest()

    asyncio.run(run())
    assert list(tmp_path.iterdir()) == []


def test_quarantine_rejects_stream_that_exceeds_limit(tmp_path: Path) -> None:
    async def run() -> None:
        with pytest.raises(UploadTooLargeError):
            async with quarantine_upload(
                chunks(b"123", b"456"),
                quarantine_dir=tmp_path,
                max_bytes=5,
            ):
                pytest.fail("Oversized upload must not be yielded")

    asyncio.run(run())
    assert list(tmp_path.iterdir()) == []


def test_quarantine_rejects_declared_size_mismatch(tmp_path: Path) -> None:
    async def run() -> None:
        with pytest.raises(UploadSizeMismatchError, match="expected 4"):
            async with quarantine_upload(
                chunks(b"123"),
                quarantine_dir=tmp_path,
                max_bytes=10,
                declared_size=4,
            ):
                pytest.fail("Mismatched upload must not be yielded")

    asyncio.run(run())
    assert list(tmp_path.iterdir()) == []


def test_quarantine_removes_file_when_consumer_fails(tmp_path: Path) -> None:
    async def run() -> None:
        with pytest.raises(RuntimeError, match="processing failed"):
            async with quarantine_upload(
                chunks(b"content"),
                quarantine_dir=tmp_path,
                max_bytes=10,
            ):
                raise RuntimeError("processing failed")

    asyncio.run(run())
    assert list(tmp_path.iterdir()) == []


def test_quarantine_rejects_oversized_declared_size_without_reading(
    tmp_path: Path,
) -> None:
    async def run() -> None:
        with pytest.raises(UploadTooLargeError):
            async with quarantine_upload(
                chunks(b""),
                quarantine_dir=tmp_path,
                max_bytes=5,
                declared_size=6,
            ):
                pytest.fail("Oversized declaration must not be yielded")

    asyncio.run(run())
    assert list(tmp_path.iterdir()) == []
