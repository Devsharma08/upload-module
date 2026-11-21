# Product Scope and System-Wide Requirements

## 1. Purpose

Phase 1 is the trusted preparation layer between uploaded source material and
downstream evaluation. For each accepted resume or job description, it must
produce a versioned record whose claims, transformations, and final normalized
values can be independently traced to the original file.

Phase 1 does not score or rank candidates, judge candidate quality, decide
whether a claim is true, infer personality, compare candidates, or fetch
external resources. Those activities are outside this product boundary.

## 2. Actors and records

- **Uploader / candidate:** submits a resume and receives an understandable
  outcome or resubmission request.
- **Recruiter:** supplies or finalizes job-description requirements and may
  review or edit the JD-derived requirement set.
- **Reviewer / security reviewer:** handles explicit human-review or security
  stop states.
- **Operations / security staff:** respond to infrastructure faults and
  integrity failures.
- **Taxonomy maintainer:** reviews skill terms that cannot be mapped.
- **Pipeline services:** perform deterministic processing and record service
  actors in audit events.
- **Independent verifier:** checks persisted evidence and signatures without
  trusting the pipeline database.

Each upload has an owner, a job/application context, a track (`resume` or
`job_description`), a version identifier, a monotonically increasing version
sequence, an upload timestamp, and a processing outcome. The exact identity
provider and owner/job authorization interfaces are open integration decisions.

## 3. Mandatory system rules

### 3.1 Faithful claims and safe uncertainty

- **PR-001:** Every Phase 1 claim MUST represent document content, not a
  statement that the content is true.
- **PR-002:** Evidence MUST NOT be promoted above `SELF_CLAIMED`.
- **PR-003:** Missing, ambiguous, imprecise, unreadable, or uncertain
  information MUST remain missing/unplaced or be marked `NOT_EVALUATED` with a
  reason. The system MUST NOT guess.
- **PR-004:** No instruction-following language model may read a resume or
  decide a Phase 1 field. Rules are authoritative. An optional fixed,
  non-generative tagger may only propose existing verified text and MUST pass
  all agreement-gate conditions in the Stage 4 requirements.
- **PR-005:** Document content MUST be treated as passive data, never as
  instructions to the service, workers, reviewers' automation, or models.
- **PR-006:** The system MUST NOT score, rank, assess personality, or compare
  candidates in Phase 1.
- **PR-007:** It MUST NOT follow links or look up information outside the
  submitted material.

### 3.2 Traceability and reproducibility

- **PR-008:** Every claim MUST trace through an exact character span in a
  verified block, the block's frame and page, the clean artifact, and the
  original file digest.
- **PR-009:** Every output MUST pin the parser, policy, rule-set, taxonomy,
  hashing, and (where used) OCR/tagger versions that produced it.
- **PR-010:** Stages 4 and 5 MUST be deterministic for the same input and pinned
  versions.
- **PR-011:** A stage result MUST be cached/reused by its input hash and stage
  version. Reprocessing an unchanged input with unchanged versions MUST NOT
  repeat expensive work unnecessarily.
- **PR-012:** Failures MUST be explicit, named, and routed. The service MUST
  NOT silently drop data or emit a success-shaped empty/partial result.

### 3.3 Human decisions and audit

- **PR-013:** Every human decision MUST record a decision ID, actor ID and role,
  target version or job, state before and after, reason code, and time.
- **PR-014:** A version MUST NOT leave a stop state without a corresponding
  signed human-decision entry.
- **PR-015:** Human decisions MUST NOT rewrite claims extracted from the source.
  A decision can change workflow state; changed record content requires a new
  record and seal. Superseded values remain in audit history.
- **PR-016:** A flag MUST lower trust in the affected text and route it for
  review; it MUST NOT be treated as a judgment about a person or automatically
  reject a candidate.

## 4. Hashing and sealed evidence

- **TR-001:** Canonical JSON MUST use sorted keys, UTF-8, Unicode NFC, and no
  extra whitespace.
- **TR-002:** Positions MUST use integers (for example thousandths of a point),
  never floating-point values.
- **TR-003:** A record hash MUST be
  `SHA-256(domain_tag + 0x00 + canonical_bytes)`, with a distinct tag for each
  record type. The source examples include `egca/block/v1`,
  `egca/clean/v1`, `egca/record/v1`, and `egca/norm/v1`.
- **TR-004:** Every hashed record MUST include the versions that produced it.
- **TR-005:** `original_sha256` MUST fingerprint the exact uploaded bytes.
  Subsequent hashes form a chain: original -> clean artifact/blocks -> record
  -> normalized record -> signature.
- **TR-006:** The final `stage5_root` MUST be signed with Ed25519 by a separate
  sealer component. The seal MUST include a key ID, version ID, run versions,
  and time. The signing key MUST NOT be available to ordinary pipeline workers.
- **TR-007:** Seals and decisions MUST be appended to a tamper-evident,
  append-only hash-chained log. A periodic signed checkpoint MUST be exported
  outside the pipeline's mutable database.
- **TR-008:** "Tamper-evident" MUST NOT be represented as "tamper-proof". Key
  compromise, parser/OCR limitations, and taxonomy quality are residual risks.

## 5. Privacy and deletion

- **TR-009:** Identity details MUST be stored separately and referenced through
  `pii_ref`; processing records should not expose identity unnecessarily.
- **TR-010:** A deletion operation MUST erase the original file, forensic
  artifacts, block text, record text, identity fields, and per-block hashes.
  Per-block hashes are removed because short personal values can be guessed
  from their hashes.
- **TR-011:** Deletion MUST append a signed tombstone containing the version,
  deletion time, approved reason and request reference, deleted scope, retained
  roots, seal ID, and deletion actor.
- **TR-012:** The four roots (`original_sha256`, `clean_artifact_sha256`,
  `record_root`, `stage5_root`), seal, version numbers, and log remain
  verifiable after deletion. Content-dependent verifier checks MUST return
  `NOT_POSSIBLE_DELETED`, never PASS or FAIL.
- **TR-013:** Backups MUST follow the same approved deletion policy.

## 6. Open service and policy decisions

The following are intentionally not selected by this requirements document:

- User identity provider, authentication protocol details, and authorization
  service for owner/job/slot access.
- Database, queue, cache, object storage, key management, and deployment
  providers.
- Production malware scanner, signature update policy, and outage disposition.
- Maximum bytes/pages, upload-window duration, retention periods, retry counts,
  reviewer deadlines, and numeric rate limits. Values shown as examples in
  other documents are not automatically calibrated or approved.
- Exact file-type/active-content decision matrix and whether particular
  findings are `REJECTED` or `BLOCKED`.
- Production signing-key custody, rotation, public-key distribution, and
  checkpoint export destination.
- The tagger, if any, and taxonomy ownership/release process.

These decisions MUST be resolved before claiming production readiness. Local
development choices MUST be labeled as such and MUST NOT be represented as
production controls.
