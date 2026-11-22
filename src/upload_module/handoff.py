import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from upload_module.repository import OutboxEvent, UploadRepository


class HandoffConflictError(RuntimeError):
    """Raised when a handoff target exists with different event content."""


def _event_bytes(event: OutboxEvent) -> bytes:
    envelope = {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "upload_id": event.upload_id,
        "created_at": event.created_at,
        "payload": json.loads(event.payload),
    }
    return (
        json.dumps(
            envelope,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _write_once(target: Path, content: bytes) -> None:
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=".handoff-",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())

        try:
            os.link(temporary_path, target)
        except FileExistsError:
            if target.read_bytes() != content:
                raise HandoffConflictError(
                    "Handoff target already contains different event content"
                )
        else:
            directory_fd = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def dispatch_outbox(
    repository: UploadRepository,
    handoff_dir: Path,
    *,
    limit: int = 100,
) -> int:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    handoff_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    published_count = 0
    for event in repository.pending_outbox(limit=limit):
        target = handoff_dir / f"{event.event_id}.json"
        _write_once(target, _event_bytes(event))
        if repository.mark_outbox_published(event.event_id):
            published_count += 1
    return published_count
