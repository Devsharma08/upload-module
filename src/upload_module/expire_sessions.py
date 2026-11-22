import os
from pathlib import Path

from upload_module.repository import UploadRepository


def main() -> None:
    database_path = Path(
        os.environ.get("UPLOAD_DATABASE_PATH", ".upload-metadata.sqlite3")
    )
    repository = UploadRepository(database_path)
    expired_count = repository.expire_sessions()
    print(f"Expired {expired_count} upload session(s)")


if __name__ == "__main__":
    main()
