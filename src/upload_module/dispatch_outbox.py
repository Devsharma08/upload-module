import os
from pathlib import Path

from upload_module.handoff import dispatch_outbox
from upload_module.repository import UploadRepository


def main() -> None:
    database_path = Path(
        os.environ.get("UPLOAD_DATABASE_PATH", ".upload-metadata.sqlite3")
    )
    handoff_dir = Path(
        os.environ.get("UPLOAD_HANDOFF_DIR", ".upload-handoff")
    )
    repository = UploadRepository(database_path)
    published_count = dispatch_outbox(repository, handoff_dir)
    print(f"Published {published_count} outbox event(s) to {handoff_dir}")


if __name__ == "__main__":
    main()
