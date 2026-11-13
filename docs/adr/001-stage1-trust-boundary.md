# ADR-001: Stage 1 Trust Boundary

- **Status:** Accepted baseline
- **Date:** 2026-11-12

## Context

Stage 1 accepts attacker-controlled uploads. Browser checks can be bypassed,
and file parsers, antivirus engines, and archive/PDF probes process hostile
input. Parsing that input in the stateless API would broaden the control plane's
attack surface and couple request handling to resource-intensive operations.

## Decision

Separate Stage 1 into three execution zones:

1. The client is untrusted and performs UX checks only.
2. The control plane independently enforces identity, authorization, slot
   ownership, idempotency, rate limits, byte caps, and deterministic state
   transitions. It does not parse file internals.
3. An isolated, resource-capped ephemeral worker inspects quarantined bytes,
   performs security/structure checks, and encrypts accepted content for the
   permanent vault.

Use the server-computed SHA-256 as the authoritative fingerprint. Client
hashes may be used only as an optimization hint. Commit `READY` metadata and
the outbox event atomically after encrypted storage succeeds.

## Consequences

- Upload requests must be authorized and limited regardless of client-side
  validation.
- Base and direct-to-quarantine upload flows must converge on the same worker
  checks and state semantics.
- Workers need bounded resources, no outbound network access, and reliable
  temporary-data cleanup.
- Operational configuration and tests must verify that the control plane
  remains content-blind.

## Trade-offs

- Isolation and asynchronous processing add infrastructure and operational
  complexity.
- Strict resource caps can reject unusually complex but benign documents;
  limits need corpus-based calibration.
- Client-side duplicate hints improve responsiveness but cannot replace the
  authoritative server-side lookup.
- This ADR decides the trust boundary only. It does not decide the complete
  accepted-format matrix, numeric quotas, forensic-retention policy, or which
  structural findings block versus produce advisories; track those in
  [ARCHITECTURE.md](../ARCHITECTURE.md).
