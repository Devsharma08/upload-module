import subprocess
from dataclasses import dataclass
from pathlib import Path


class ScannerUnavailableError(RuntimeError):
    """Raised when malware scanning cannot produce a trustworthy result."""


@dataclass(frozen=True)
class MalwareScanResult:
    clean: bool


def scan_file(
    path: Path,
    *,
    executable: str = "clamscan",
    timeout_seconds: int = 30,
) -> MalwareScanResult:
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    try:
        result = subprocess.run(
            [executable, "--no-summary", str(path)],
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as error:
        raise ScannerUnavailableError(
            "The configured malware scanner executable was not found"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise ScannerUnavailableError(
            "Malware scan exceeded its time limit"
        ) from error

    if result.returncode == 0:
        return MalwareScanResult(clean=True)
    if result.returncode == 1:
        return MalwareScanResult(clean=False)

    raise ScannerUnavailableError(
        "Malware scanner returned an error"
    )
