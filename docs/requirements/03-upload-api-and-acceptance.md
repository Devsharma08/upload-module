# Upload API, Service Boundaries, and Acceptance

This document covers the upload module only. It defines the API responsibilities
and operational requirements needed to implement Stage 1 without specifying or
implementing later pipeline stages.

## API capabilities

The final public API shape is subject to product approval, but it must support
the following capabilities:

1. **Create upload/session:** accept track and upload metadata, enforce
   authentication/authorization, idempotency, and policy limits, then return an
   opaque upload/session ID and expiry.
2. **Transfer file bytes:** stream bytes into quarantine under server-enforced
   limits. This may be one request or a session-based protocol, but a client
   must not be able to change owner/job/track authorization mid-session.
3. **Read upload status:** return only the authenticated caller's permitted
   session status and safe reason/advisory fields. Do not expose raw object
   paths or credentials.
4. **Retry/replay:** a retry with the same idempotency key and same request
   returns the same logical session. Reusing the key with materially different
   request data returns a conflict.
5. **Downstream handoff:** publish an approved `READY` upload exactly once
   logically, even if delivery is retried.

Exact routes, HTTP method names, and whether bytes use multipart, raw streaming,
or a presigned upload are product/infrastructure decisions. No API may claim
`READY` before all required checks and persistence succeed.

The current local development prototype uses `POST /uploads` to create a
metadata session with an `Idempotency-Key`, `PUT /uploads/{upload_id}/content`
to stream bytes, and `GET /uploads/{upload_id}` to read status. This route
shape is a development interface, not final product approval. Its `READY`
outbox event is persisted locally and can be dispatched to a development-only
filesystem handoff using `upload-dispatch-outbox`; no production queue is
selected.
The local `upload-expire-sessions` command marks elapsed `CREATED` sessions
`EXPIRED`; it does not remove quarantined objects. Local retention for
completed, blocked, and failed uploads remains an explicit open decision.
The local `upload-cleanup-quarantine` command removes only old, unreferenced
temporary files; it leaves files referenced by upload records untouched.
Scanner outages/timeouts are attempted at most twice by default before the
session is marked `FAILED`.

## Session and version requirements

- **API-001:** Session identifiers are unpredictable and do not disclose
  sequential database IDs.
- **API-002:** Idempotency is scoped to the authenticated principal and upload
  context. The same key and same request replay the original result; a
  different request conflicts.
- **API-003:** Session expiry is enforced server-side. Expiry revokes further
  byte transfer and routes the session to `EXPIRED`; abandoned bytes are
  cleaned up according to retention policy.
- **API-004:** Version registration is keyed by owner, job, and track. The
  `version_seq` is monotonic within that scope.
- **API-005:** Concurrent registrations use compare-and-swap or equivalent
  database constraints/locking so only one sequence is current.
- **API-006:** Duplicate detection uses the server-computed digest and the
  specification-defined owner/job scope. Client-provided hashes are not
  authoritative.
- **API-007:** Replacement behavior must be explicitly authorized. A
  replacement flag alone is not authorization.
- **API-008:** State transitions are validated and audited. Invalid transitions
  fail visibly and do not mutate the record.

Authentication integration and API request-rate limiting may be scheduled
after the first local upload vertical slice. The local identity adapter must be
explicitly development-only. Real authentication, owner/job authorization,
and shared-store rate limiting are release gates before staging or public
exposure. Hard streaming byte ceilings and processing-resource bounds are
required from the first upload implementation and are not deferred.

## Service boundaries

The Python implementation should define small interfaces around the selected
production services:

| Boundary | Upload-module responsibility |
|---|---|
| Identity/authorization | Return authenticated principal and verified permission for owner/job/track. |
| Metadata repository | Transactional session, version, outcome, idempotency, duplicate, and audit persistence. |
| Quarantine storage | Restricted immutable object write/read/delete and opaque reference generation. |
| Malware scanner | Scan a quarantined object with explicit clean, detection, timeout, and unavailable outcomes. |
| File inspector | Determine allowed actual file type and run bounded PDF/DOCX intake checks without passing unchecked content downstream. |
| Outbox/queue | Deliver `READY` work to the downstream handoff with retries and idempotent event identity. |
| Configuration/secrets | Validate required service URLs, credentials, limits, and key references at startup; never silently default production secrets. |

Service-provider selection is explicitly open. An adapter or local development
service must not be described as a production integration until its security,
availability, and lifecycle requirements are verified.

## Failure semantics and HTTP behavior

- Malformed request metadata: return a client error with a stable safe code.
- Authentication failure: reject without disclosing whether a job/session
  exists.
- Authorization failure: reject without creating a session or leaking owner/job
  information.
- Same idempotency key with changed request: return a conflict.
- Unsupported/signature-mismatched file, over-limit file, or unopenable
  encrypted file: `REJECTED` with a safe reason code.
- Malware or policy-defined active-content risk: `BLOCKED`; never enqueue
  downstream processing.
- Scanner or storage outage: `FAILED` after a bounded retry policy; never treat
  an unavailable scanner as a clean scan.
- Same authoritative bytes already registered in scope: `DUPLICATE`, linked
  to the existing version; do not enqueue repeated work.
- Expired session: `EXPIRED`; reject late transfer/completion and clean up
  abandoned quarantine data.
- Internal failures: return a generic safe response with a correlation ID;
  retain detailed diagnostics in access-controlled logs without file content
  or secrets.

The exact HTTP status mapping, reason-code catalog, user-facing wording,
retry count, and retry delays remain open decisions.

## Operational and security acceptance

- Resource limits cover API body streaming, scanner memory/CPU/time, archive
  inspection, temporary disk, concurrency, and database/queue pools.
- Network policy prevents untrusted clients from reaching internal worker,
  scanner, database, queue, object-store, and signing interfaces directly.
- Quarantine access is least-privilege; temporary data is deleted on every
  terminal path as required by policy.
- Logs and metrics expose state counts, latency, failures, retry exhaustion,
  scanner health, cleanup errors, and outbox lag without logging document
  content, bytes, secrets, or raw personal data.
- Readiness checks verify required dependencies; liveness does not claim
  downstream processing is healthy when it is not.
- Secret/key rotation and expiry are operationally documented and tested.
- Rate limiting and abuse controls are configured before public exposure; the
  source spec does not define numeric quotas.

## Definition of done for the upload module

1. Authenticated and unauthorized upload cases are covered by API tests.
2. PDF and DOCX happy paths produce correct server-side size, type, and
   SHA-256 values and an opaque quarantine reference.
3. Streamed over-limit input is stopped before exceeding the configured
   storage/memory budget.
4. Signature mismatch, unsupported type, encryption, active content, archive
   abuse, and malware fixtures reach the approved explicit outcomes.
5. Scanner/storage failures never become `READY`; retry exhaustion is visible.
6. Matching retries are idempotent; mismatching retries conflict.
7. Same-scope duplicates do not create a second version or downstream event.
8. Concurrent uploads cannot create two current versions.
9. Database/outbox crash tests prove durable, recoverable handoff.
10. Expiry, cancellation, and all failure paths verify temporary/quarantine
    cleanup or approved retention.
11. Status authorization, safe error responses, logs, metrics, and readiness
    behavior are tested.
12. All unspecified thresholds/providers are tracked as explicit decisions and
    never represented as calibrated or production-ready by default.
