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
uvicorn upload_module.app:app --reload
```

`POST /uploads` streams the raw request body into the configured quarantine
directory, applies `UPLOAD_MAX_BYTES` (10 MiB by default), and returns an
opaque upload ID, actual byte count, and server-computed SHA-256. It reports
`QUARANTINED`, not `READY`: malware scanning, persistence, authentication,
authorization, duplicate detection, and downstream handoff are not implemented
yet. The endpoint refuses requests unless `UPLOAD_ENV=development`; do not
bind this development endpoint to a shared or public network.

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

Dependencies for storage, persistence, scanning, authentication, and
rate-limiting will be added only when those modules are started.

See [the upload requirements](docs/requirements/README.md) for scope,
trust-boundary requirements, and implementation order.
