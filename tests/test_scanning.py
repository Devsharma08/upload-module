from pathlib import Path
from subprocess import CompletedProcess

import pytest

import upload_module.scanning as scanning
from upload_module.scanning import (
    MalwareScanResult,
    ScannerUnavailableError,
    scan_file,
)


def test_scan_file_retries_scanner_error_then_returns_clean_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results = iter(
        [
            CompletedProcess(args=[], returncode=2),
            CompletedProcess(args=[], returncode=0),
        ]
    )
    calls = 0

    def fake_run(*args, **kwargs) -> CompletedProcess[bytes]:
        nonlocal calls
        calls += 1
        return next(results)

    monkeypatch.setattr(scanning.subprocess, "run", fake_run)
    monkeypatch.setattr(scanning, "sleep", lambda _seconds: None)

    result = scan_file(tmp_path / "upload.part", max_attempts=2)

    assert result == MalwareScanResult(clean=True)
    assert calls == 2


def test_scan_file_stops_after_configured_attempts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def failing_run(*args, **kwargs) -> CompletedProcess[bytes]:
        nonlocal calls
        calls += 1
        return CompletedProcess(args=[], returncode=2)

    monkeypatch.setattr(scanning.subprocess, "run", failing_run)
    monkeypatch.setattr(scanning, "sleep", lambda _seconds: None)

    with pytest.raises(ScannerUnavailableError):
        scan_file(tmp_path / "upload.part", max_attempts=3)

    assert calls == 3


def test_scan_file_does_not_retry_malware_detection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def malware_found(*args, **kwargs) -> CompletedProcess[bytes]:
        nonlocal calls
        calls += 1
        return CompletedProcess(args=[], returncode=1)

    monkeypatch.setattr(scanning.subprocess, "run", malware_found)

    result = scan_file(tmp_path / "upload.part", max_attempts=3)

    assert result == MalwareScanResult(clean=False)
    assert calls == 1
