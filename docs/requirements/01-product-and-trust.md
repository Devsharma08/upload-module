# Upload Module Scope and Trust Requirements

## Purpose

The upload module is the application's trusted intake boundary. It accepts a
resume or job description, holds the original bytes in quarantine, verifies
basic file safety and integrity, registers an upload version, and hands an
approved file to downstream processing.

Its responsibility ends at a durable, explicit intake outcome and a reliable
handoff. It does not parse document meaning, evaluate candidates, or implement
Stages 2–5.

## Actors and trust boundaries

- **Uploader:** an authenticated user or authorized upstream application.
- **Identity/authorization provider:** verifies identity and permission to
  upload for an owner, job, and track. The provider is not selected yet.
- **Upload API:** validates request metadata, enforces quotas and limits,
  streams bytes, coordinates persistence, and exposes upload status.
- **Quarantine storage:** holds untrusted originals in an immutable or
  write-once boundary.
- **Intake worker/scanner:** inspects file signatures, structural safety
  indicators, archives, and malware in an isolated processing boundary.
- **Database/queue:** stores session and version state and reliably signals
  downstream processing.
- **Downstream pipeline:** receives only a validated file reference and
  authoritative metadata; it is not implemented by this module.

All client-supplied values—including filename, extension, MIME type, size,
digest, owner/job identifiers, track, and claimed validation results—are
untrusted until checked by the server or an explicitly trusted service.

## Upload-module requirements

- **UM-001 — No production bypass:** Before the API is exposed outside a
  developer's local machine, every upload/session/status operation MUST require
  authentication and server-side authorization for the relevant owner, job,
  and track. Unauthenticated or unauthorized callers receive no session or
  object information. Local-only development may use a fixed development
  identity adapter to unblock vertical-slice work; it must refuse to start when
  the runtime environment is not explicitly `development`.
- **UM-002 — Client metadata is advisory:** The server MUST determine actual
  byte count, file type, and SHA-256. Client hashes may accelerate a hint only;
  they cannot authorize or prove a file safe.
- **UM-003 — Bounded intake:** The service MUST apply a hard, configured byte
  ceiling while streaming. It MUST NOT trust only `Content-Length` or buffer an
  unbounded request body in memory.
- **UM-004 — Quarantine first:** Original bytes MUST remain in restricted
  quarantine and MUST NOT be parsed by downstream document-processing code
  until the intake checks pass.
- **UM-005 — Original is immutable:** No stage may modify the original
  quarantined object. Transformations, if any, create separate objects.
- **UM-006 — Safe storage references:** API responses and queue messages MUST
  use opaque, access-controlled object references, never public URLs,
  credentials, or unrestricted storage paths.
- **UM-007 — Exact fingerprint:** The authoritative `original_sha256` MUST
  cover the exact received bytes. Any later read before handoff SHOULD verify
  that it still matches.
- **UM-008 — Explicit outcomes:** Every request reaches an explicit state and
  stable reason code. Scanner or storage errors MUST NOT appear as successful
  validation.
- **UM-009 — No duplicate work:** A duplicate is linked to its existing
  version and MUST NOT trigger another downstream job.
- **UM-010 — Reliable handoff:** Persisting a ready upload and scheduling its
  next stage MUST be recoverable as one logical operation, typically with a
  transactional outbox.
- **UM-011 — Privacy:** Keep identity data separate from processing metadata
  where feasible. Do not log file bytes, document contents, secrets, or
  unrestricted object locations.
- **UM-012 — Cleanup and retention:** Remove temporary plaintext on all
  success, failure, cancellation, and retry-exhaustion paths unless a
  documented retention/security policy requires restricted retention.
- **UM-013 — No candidate judgment:** File rejection or security blocking is
  about the submitted file, not candidate merit. The upload module MUST NOT
  score or rank a person.
- **UM-014 — Preserve trace inputs:** Preserve the original digest, upload
  timestamp, version ID/sequence, track, actual type/size, outcome, and opaque
  quarantine reference for downstream traceability.

## Implementation sequencing

Authentication integration and API request-rate limiting are intentionally
late development tasks, after the upload/session/storage path can be exercised
locally. Deferring them is not permission to expose the service:

1. First establish the Python project and virtual environment without
   application dependencies. Add runtime, test, and service dependencies only
   as their corresponding module is started.
2. Local development may use a fixed `dev-user` identity adapter, guarded by an
   explicit development environment setting. Production/staging startup must
   fail if real identity and authorization configuration is missing.
3. Distributed API rate limits may be added after the initial local upload
   vertical slice. Before any shared or public deployment, configure and test
   a distributed limiter with the chosen shared store; an in-process counter
   is not sufficient across workers or replicas.
4. This deferral does **not** apply to hard request-body byte limits,
   streaming without unbounded memory buffering, scanner/parser resource caps,
   storage quotas, or safe quarantine cleanup. Those controls are required
   while implementing the initial intake path.
5. The development identity must never be selectable through a request header,
   query parameter, or client-supplied field, and must never be enabled by a
   production default.

## Upload lifecycle boundary

The upload module owns this lifecycle only:

```text
request authorized
  -> session created
  -> bytes streamed to quarantine
  -> file safety/intake checks
  -> fingerprint and version registration
  -> READY / DUPLICATE / REJECTED / BLOCKED / FAILED / EXPIRED
  -> reliable downstream handoff if READY
```

Downstream parsing and later pipeline stages own all work after the upload
handoff. This boundary must be represented by a versioned, fixed-shape
contract.

## Unresolved service decisions

The specification is vendor-neutral. Before production implementation, decide
and document:

- Identity and authorization provider, including how owner/job permissions
  are checked.
- Metadata database, migration strategy, and transaction guarantees.
- Queue or outbox publisher and delivery/retry semantics.
- Quarantine object store and the mechanism enforcing write-once access.
- Malware scanner, signature freshness, isolation, timeout, and fail-closed
  behavior.
- Production key management/encryption policy, if required for quarantine.
- Production deployment, network boundaries, secret management, and observability.
- Numeric file-size/page/archive limits, upload-session TTL, retention period,
  rate limits, retry budget, and expiration behavior.
- Exact policy for embedded scripts, active content, encrypted files, and
  malware/active-content disposition.

## Current local MVP selections

These are development-only implementation choices, not production approvals:

- SQLite stores local upload sessions, version sequences, and transactional
  outbox records. The outbox currently has no publisher.
- A local filesystem directory stores quarantined files under generated,
  opaque references.
- Poppler `pdfinfo` performs basic PDF page/encryption checks. Python's
  standard-library ZIP reader performs bounded DOCX package inspection.
- ClamAV `clamscan` is the intended malware-scanner executable. A missing,
  timed-out, or erroring scanner fails closed. Developers must install ClamAV
  and keep signatures updated; tests use controlled fake executables and do
  not certify the local scanner installation.
- The API uses a fixed `dev-user` identity only when `UPLOAD_ENV=development`.
  This is not authentication or owner/job authorization.

None of these choices resolves the production provider, isolation, retention,
threshold, authorization, or deployment decisions above.
