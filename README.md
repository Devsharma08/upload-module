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

Run the local API shell with:

```bash
uvicorn upload_module.app:app --reload
```

Dependencies for storage, persistence, scanning, authentication, and
rate-limiting will be added only when those modules are started.

See [the upload requirements](docs/requirements/README.md) for scope,
trust-boundary requirements, and implementation order.
