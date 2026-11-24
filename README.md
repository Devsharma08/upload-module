# Upload Module

A Python implementation of the EGCA Stage 1 upload and quarantine boundary.
Stages 2–5 are out of scope.

## Development setup

The project supports Python 3.12–3.14. Create a local virtual environment
with a supported interpreter, then activate it:

```bash
python3 -m venv .venv
source .venv/bin/activate
python --version
```

Install and lock the initial API and test dependencies:

```bash
python -m pip install "pip-tools>=7.4,<8.0"
pip-compile --extra dev --strip-extras --generate-hashes \
  --output-file requirements.lock pyproject.toml
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
pytest
```

Run the API locally with its development-only upload endpoint enabled:

```bash
UPLOAD_ENV=development \
UPLOAD_QUARANTINE_DIR=.quarantine \
UPLOAD_DATABASE_PATH=.upload-metadata.sqlite3 \
uvicorn upload_module.app:app --reload
```

Open `http://127.0.0.1:8000/` for the local upload desk. It supports resume
and job-description PDF/DOCX uploads, displays the outcome and basic file
details, and lets you refresh the status by upload ID. The page is served only
when `UPLOAD_ENV=development`, reflects the configured `UPLOAD_MAX_BYTES`
limit, and has no external assets or frontend build step.

The local API uses three steps:

1. `POST /uploads` with JSON request metadata and an `Idempotency-Key` header
   creates or replays an upload session.
2. `PUT /uploads/{upload_id}/content` streams the raw body into the configured
   quarantine directory, applies `UPLOAD_MAX_BYTES` (10 MiB by default),
   performs file inspection and malware scanning, then records an explicit
   outcome.
3. `GET /uploads/{upload_id}` reads the stored session status.

SQLite stores local session metadata, idempotency keys, version sequences, and
an outbox row in the same transaction as the `READY` status. Run
`upload-dispatch-outbox` to write pending events as one JSON file per event to
`UPLOAD_HANDOFF_DIR` (defaults to `.upload-handoff`). Event filenames are
stable; a retry after writing the file but before acknowledging SQLite verifies
the existing file and safely marks the event published. A different payload at
the same event path is an explicit conflict. This local handoff is a filesystem
queue for development, not a production queue integration. The dispatcher
prints its count and exits nonzero with the underlying error if delivery or
database acknowledgement fails; run it again after addressing the cause.
Failed upload sessions are terminal. After a transient intake failure, create a
new session with a new `Idempotency-Key` and resend the original bytes; reusing
the old key replays the failed session. Scanner outages/timeouts are attempted
at most `UPLOAD_SCANNER_MAX_ATTEMPTS` times (2 by default); exhausted attempts
mark the session `FAILED`.

Duplicate bytes in the same owner/job scope link to the existing ready upload
and do not create another outbox row. A job description uses the same PDF/DOCX
document flow as a resume, selected with `"track": "job_description"` when
creating the session. Plain-text JD intake is not part of this local MVP.

Unfinished sessions expire after `UPLOAD_SESSION_TTL_SECONDS` (one hour by
default); expiration is applied when a session is read or its content is
submitted. Expired session metadata is also copied to the local
`expired_upload_archive` table; registered version data is not deleted, so no
signed tombstone is created. Stale unreferenced partial files are removed by
the cleanup command after the configured age. Run `upload-expire-sessions` to
archive all other elapsed `CREATED` sessions as `EXPIRED` without waiting for
a request. Run `upload-cleanup-quarantine` to expire sessions and remove
stale, unreferenced temporary files older than
`UPLOAD_QUARANTINE_ORPHAN_TTL_SECONDS` (24 hours by default). It leaves files
referenced by any upload, including `READY` and `BLOCKED` uploads, and skips
files belonging to active sessions. A retention period for completed, blocked,
or failed uploads is not defined for this local MVP.
The API and ready-event contract expose `version_id` (the ready upload's
`upload_id`) and `original_sha256` (the stored SHA-256 value); the older
`sha256` response/event key is retained as a compatibility alias. Completed
quarantine files are changed to owner-read-only mode (`0400`) on the local
filesystem. Quarantine setup, file creation, chunk writes, and flush operations
are retried up to
`UPLOAD_STORAGE_MAX_ATTEMPTS` times (2 by default) before failing.
Quarantine filenames remain internal metadata and are not returned by the API.

All endpoints refuse requests unless `UPLOAD_ENV=development`; the identity is
a fixed local `dev-user`, not real authentication or authorization. Do not bind
this development API to a shared or public network. Local PDF/DOCX inspection
and ClamAV scanning are not sandboxed and are not production security
boundaries.

The local inspection step requires Poppler's `pdfinfo` executable for PDF page
count and encryption checks. PDF page and DOCX archive limits have conservative
local defaults and can be overridden with `UPLOAD_MAX_PDF_PAGES`,
`UPLOAD_MAX_DOCX_ENTRIES`, `UPLOAD_MAX_DOCX_UNCOMPRESSED_BYTES`, and
`UPLOAD_MAX_DOCX_COMPRESSION_RATIO`. These are development defaults, not
approved production policy thresholds.

Uploads also require ClamAV's `clamscan` executable. The API accepts a file
only when the scanner reports clean; a missing scanner, timeout, or scanner
error fails closed. Set `UPLOAD_SCANNER_EXECUTABLE` only to a trusted local
scanner executable. Install and keep ClamAV signatures updated before running
the upload endpoint.

SQLite uses Python's standard library. Authentication and distributed
rate-limiting remain deferred and are release blockers before any shared or
public deployment.

See [the upload requirements](docs/requirements/README.md) for scope,
trust-boundary requirements, and implementation order.
