from hashlib import sha256

import pytest

from upload_module.quarantine import (
    UploadSizeMismatchError,
    UploadTooLargeError,
    write_quarantine,
)


def test_write_quarantine_saves_bytes_and_returns_digest(tmp_path) -> None:
    content = b"hello upload"
    result = write_quarantine(
        [b"hello ", b"upload"],
        tmp_path,
        max_bytes=20,
    )

    assert result.path.read_bytes() == content
    assert result.size_bytes == len(content)
    assert result.sha256 == sha256(content).hexdigest()


def test_write_quarantine_removes_partial_file_when_limit_is_exceeded(
    tmp_path,
) -> None:
    with pytest.raises(UploadTooLargeError):
        write_quarantine(
            [b"1234", b"5678"],
            tmp_path,
            max_bytes=6,
        )

    assert list(tmp_path.iterdir()) == []


def test_write_quarantine_removes_file_when_declared_size_mismatches(
    tmp_path,
) -> None:
    with pytest.raises(UploadSizeMismatchError):
        write_quarantine(
            [b"actual"],
            tmp_path,
            max_bytes=20,
            declared_size_bytes=10,
        )

    assert list(tmp_path.iterdir()) == []


def test_write_quarantine_accepts_chunks_matching_declared_size(tmp_path) -> None:
    result = write_quarantine(
        [b"act", b"ual"],
        tmp_path,
        max_bytes=20,
        declared_size_bytes=6,
    )

    assert result.path.read_bytes() == b"actual"
    assert result.size_bytes == 6


def test_write_quarantine_removes_file_when_chunk_source_fails(
    tmp_path,
) -> None:
    def failing_chunks():
        yield b"partial data"
        raise OSError("incoming stream failed")

    with pytest.raises(OSError, match="incoming stream failed"):
        write_quarantine(
            failing_chunks(),
            tmp_path,
            max_bytes=100,
        )

    assert list(tmp_path.iterdir()) == []


def test_write_quarantine_accepts_upload_at_exact_limit(tmp_path) -> None:
    content = b"exactly the limit"
    result = write_quarantine(
        [content],
        tmp_path,
        max_bytes=len(content),
    )

    assert result.size_bytes == len(content)
    assert result.path.read_bytes() == content


def test_write_quarantine_rejects_nonpositive_limit(tmp_path) -> None:
    with pytest.raises(ValueError, match="max_bytes must be greater than zero"):
        write_quarantine(
            [b"data"],
            tmp_path,
            max_bytes=0,
        )


def test_write_quarantine_rejects_missing_directory(tmp_path) -> None:
    missing_dir = tmp_path / "missing"

    with pytest.raises(
        FileNotFoundError,
        match="Quarantine directory does not exist",
    ):
        write_quarantine(
            [b"data"],
            missing_dir,
            max_bytes=10,
        )
