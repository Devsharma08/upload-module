# upload-module — EGCA Pipeline Stage 1

In a zero-trust architecture such as the EGCA Pipeline, client-side checks are
for user experience only: they provide fast feedback, but are not a security
boundary. Browser code can be bypassed with tools such as `curl` or a modified
script, so the backend must independently verify every security-relevant
condition.

## Backend Development Scaffold

The backend currently contains a minimal FastAPI application and health check;
the upload endpoints, persistence, and worker are not implemented yet.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Run the backend tests with:

```bash
pytest
```

The current scaffold exposes `GET /healthz`.

This document describes the production Stage 1 upload architecture, its trust
boundaries, task allocation, and two deployment flows.

## 1. Execution Boundaries

Production Stage 1 separates work across three execution zones:

1. **Client side — untrusted zone:** Browser/frontend code performs pre-flight
   UX checks, may compute a client-side hash for a fast duplicate hint, and
   uploads directly to quarantine storage in the optimized plan. Its results
   are never authoritative.
2. **Server side — control plane (API gateway and orchestrator):** Stateless
   FastAPI servers, PostgreSQL, and Redis handle authentication, slot
   ownership, rate limits, idempotency, and atomic database state transitions.
   The control plane does not parse untrusted file internals.
3. **Server side — ephemeral data plane (isolated quarantine and worker):**
   Short-lived, resource-capped containers or subprocesses handle untrusted
   file bytes. Workers use limits such as `ulimit`/cgroups, have no outbound
   network access, and use ephemeral temporary storage. Dangerous binary
   operations happen here; the environment is destroyed after processing.

## 2. Task Allocation Matrix

| Operation / task | Client side (browser) | Control plane (FastAPI / DB) | Ephemeral worker (quarantine) | Production rationale |
|---|---|---|---|---|
| **Authentication and slot ownership** | Hide the upload button when the user is unauthorized or the slot appears full. This is UX only. | Enforce JWT/session authentication and verify in the database that the slot is empty, unless an explicit `Replace` flag is set. | — | Prevents unauthorized overwrites and race conditions on a job/application slot. |
| **Idempotency and session TTL** | Generate a UUID `Idempotency-Key` per upload attempt and reuse it for retries after network drops. | Enforce key uniqueness in Redis/DB and expire abandoned sessions after 15 minutes (`EXPIRED`). | — | Prevents retries, including near-complete uploads, from creating duplicate records. |
| **Two-tier rate limiting** | Debounce the submit button to avoid accidental double-clicks. | Enforce Tier 1 per-uploader/minute and Tier 2 per-SHA-256/hour limits. | — | Stops bulk spam and duplicate-session abuse before workers are started. |
| **File size and extension pre-check** | Check `file.size <= 10 MB` and `.pdf`, `.docx`, or `.txt` extension for an immediate error message. | Enforce a hard byte ceiling while streaming; abort the stream if exceeded. | — | Client checks save bandwidth; the server-side streaming limit prevents disk exhaustion. |
| **SHA-256 fingerprinting and deduplication** | *(Optimized)* Compute a Web Crypto SHA-256 hash before upload and ask the server whether the hash already exists in the slot. | Compute the authoritative streaming SHA-256 and check the slot database for a `< 50 ms` `DUPLICATE` exit. | Re-verify SHA-256 before encryption/Stage 2. | The client hash supports a fast UX shortcut; the server hash is the tamper-resistant source of record. |
| **Magic-byte and UTF-8 verification** | — | — | Run `libmagic` on leading bytes, check extension/MIME agreement, and validate strict UTF-8 where applicable. | Untrusted file headers must be inspected inside the isolated quarantine boundary. |
| **Antivirus scan (ClamAV)** | — | — | Run `clamd` against quarantined bytes; move detections to a forensic vault and mark them `BLOCKED`. | Malware scanning is CPU-intensive and processes hostile payloads, so it belongs in isolation. |
| **Archive-bomb and macro guards** | — | — | Inspect the ZIP central directory, enforce an expansion ratio below `20:1`, and reject `vbaProject.bin`. | Protects against crafted ZIP bombs exhausting memory or disk; cgroup limits provide an additional boundary. |
| **PDF structural probe and advisories** | — | — | Run `pikepdf` in a capped subprocess to inspect page count, user/owner passwords, `/JS`, and `/Font`. | Parsing malformed PDF cross-reference tables may expose native libraries to exploits; probing must be ephemeral. |
| **Envelope encryption and vault write** | — | Request a per-document DEK from KMS and atomically commit metadata with a `READY` outbox event. | Encrypt raw quarantined bytes with the DEK and write ciphertext to write-once storage. | Raw unencrypted files never enter permanent storage; ephemeral quarantine is wiped immediately after processing. |

## 3. End-to-End Production Lifecycle

### Base plan: synchronous, single-hop

1. **Client:** Validate extension and size locally, then send
   `POST /slots/{slot_id}/upload` with an `Idempotency-Key`.
2. **Control plane:** Verify authentication, slot availability, and rate
   limits. Stream bytes into an ephemeral quarantine volume while computing
   SHA-256.
3. **Deduplication:** Check the authoritative SHA-256 against the slot. If it
   matches, delete the quarantine file and return `DUPLICATE` immediately.
4. **Ephemeral worker:** Start with strict memory, CPU, and timeout limits
   (illustratively `512 MB` and `10s`), then run `libmagic`, `clamd`, and
   `pikepdf`/`zipfile` probes.
5. **Vault and atomic commit:** Encrypt the raw file with a unique DEK and write
   it to write-once storage. The control plane commits database metadata and a
   `READY` event in one transaction. Wipe the ephemeral quarantine.

### Optimized plan: direct-to-storage, asynchronous queue

In the optimized production setup, large file bytes bypass the API servers so
web workers do not block on slow client connections:

1. **Client → control plane:** Send file metadata and a client-computed
   SHA-256 to `POST /upload-sessions`.
2. **Control plane:** Check authentication, rate limits, and the slot hash. If
   it is a duplicate, return the `< 50 ms` `DUPLICATE` shortcut. Otherwise,
   issue a short-lived pre-signed quarantine upload URL (15-minute TTL) capped
   at the format's maximum byte size.
3. **Client → quarantine bucket:** Upload the bytes directly to the isolated
   quarantine object bucket.
4. **Queue → warm ephemeral worker:** Object-upload completion triggers an
   asynchronous job. The worker pulls the file to local tmpfs (RAM disk), runs
   antivirus and structural probes, computes the authoritative SHA-256,
   encrypts the file into the permanent vault, deletes the quarantine object,
   and commits the `READY` event.

## 4. Security Invariants

- Treat all client-provided metadata, hashes, filenames, MIME types, and
  validation results as untrusted input.
- Re-check authentication, authorization, slot state, quotas, and byte limits
  on the server for every upload.
- Use the server-computed hash as the authoritative fingerprint; a client hash
  is only an optimization hint.
- Do not parse hostile file internals in the API control plane. Perform
  inspection in an isolated, resource-limited worker.
- Keep unencrypted bytes in ephemeral quarantine only. Persist encrypted
  content and commit metadata/state atomically.
- Expire abandoned upload sessions and remove quarantine data after completion
  or rejection.

> **Configuration note:** Values such as the 10 MB upload limit, 15-minute
> session TTL, `< 50 ms` duplicate response target, `512 MB` worker memory
> limit, `10s` timeout, and `< 20:1` archive expansion ratio are the
> production targets described here. Confirm and enforce them consistently
> across the client, API, storage policy, and worker configuration.
