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

Install application and development dependencies only as their modules are
started. The initial project setup intentionally has no application
dependencies. Dependency additions and their lock workflow will be documented
with the first runtime/test setup checkpoint.

See [the upload requirements](docs/requirements/README.md) for scope,
trust-boundary requirements, and implementation order.
