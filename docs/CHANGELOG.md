# Changelog

All notable changes to the EGCA Pipeline Stage 1 design, policy, and contracts
are recorded here. This project follows the Keep a Changelog format.

## [Unreleased]

### Added

- Added transactional upload-session creation with idempotent replay checks and
  an initial state audit event.
- Added an initial context-managed quarantine streaming primitive that enforces
  a byte cap, checks declared size, computes SHA-256, and removes temporary
  bytes when processing exits.
- Initial Stage 1 architecture, trust boundaries, lifecycle/state model, and
  proposed `Stage1ReadyHandoff` v1 in [ARCHITECTURE.md](ARCHITECTURE.md).
- Baseline format, worker, session, and rate-limit policy inventory in
  [POLICY_AND_LIMITS.md](POLICY_AND_LIMITS.md).
- Dependency-ordered delivery plan and current implementation snapshot in
  [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md).
- Initial FastAPI package, health endpoint, Python dependency manifest, and
  state/schema/API tests.
- Accepted trust-boundary decision in
  [ADR-001](adr/001-stage1-trust-boundary.md).
- Global Tailwind stylesheet for the upload UI in `upload_ui/app/globals.css`.

### Changed

- Imported the global stylesheet from the Next.js root layout.

### Fixed

- Prevented the upload UI from logging raw file bytes or labeling local
  preflight validation as server-confirmed `READY`.
- Constrained the Stage 2 handoff model to the documented contract version 1.
- Removed an unused Next.js starter import.

### Security

- Documented that client-side validation is UX-only and that file-internal
  inspection belongs in an isolated, ephemeral worker.

### Policy Updates

- Recorded the initial 10 MB generic upload ceiling, 15-minute session and
  pre-signed URL TTLs, `< 20:1` DOCX expansion ratio, 512 MB illustrative
  worker-memory target, 10-second illustrative timeout, and sub-50 ms
  duplicate-response target as **Placeholders**, not measured thresholds.
- Marked per-format page/character caps, CPU quota, and numeric rate limits as
  TBD. No calibration dataset or benchmark evidence was supplied.
