import os
import re
import stat
import time
from hashlib import sha256
from pathlib import Path

from upload_module.repository import UploadRepository

_UPLOAD_FILE_PATTERN = re.compile(r"^upload-([0-9a-f]{64})-.+\.part$")


def cleanup_quarantine_orphans(
    quarantine_dir: Path,
    repository: UploadRepository,
    *,
    min_age_seconds: int = 24 * 60 * 60,
) -> int:
    if min_age_seconds <= 0:
        raise ValueError("min_age_seconds must be greater than zero")
    if not quarantine_dir.exists():
        return 0
    if not quarantine_dir.is_dir():
        raise NotADirectoryError("Quarantine path is not a directory")

    active_upload_ids, quarantine_refs = repository.quarantine_cleanup_state()
    active_upload_hashes = {
        sha256(upload_id.encode("utf-8")).hexdigest()
        for upload_id in active_upload_ids
    }
    cutoff = time.time() - min_age_seconds
    removed_count = 0
    for path in quarantine_dir.iterdir():
        match = _UPLOAD_FILE_PATTERN.fullmatch(path.name)
        if match is None or path.name in quarantine_refs or path.is_symlink():
            continue
        if match.group(1) in active_upload_hashes:
            continue

        try:
            file_stat = path.stat(follow_symlinks=False)
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_mtime > cutoff:
            continue

        try:
            path.unlink()
        except FileNotFoundError:
            continue
        removed_count += 1
    return removed_count


def main() -> None:
    database_path = Path(
        os.environ.get("UPLOAD_DATABASE_PATH", ".upload-metadata.sqlite3")
    )
    quarantine_dir = Path(
        os.environ.get("UPLOAD_QUARANTINE_DIR", ".quarantine")
    )
    try:
        min_age_seconds = int(
            os.environ.get("UPLOAD_QUARANTINE_ORPHAN_TTL_SECONDS", "86400")
        )
        repository = UploadRepository(database_path)
        expired_count = repository.expire_sessions()
        removed_count = cleanup_quarantine_orphans(
            quarantine_dir,
            repository,
            min_age_seconds=min_age_seconds,
        )
    except (OSError, ValueError) as error:
        raise SystemExit(f"Quarantine cleanup failed: {error}") from error

    print(
        f"Expired {expired_count} session(s); removed "
        f"{removed_count} orphaned quarantine file(s)"
    )


if __name__ == "__main__":
    main()
