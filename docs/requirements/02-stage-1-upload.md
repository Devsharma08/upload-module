# Stage 1 Requirements: Upload and Quarantine

Stage 1 receives a resume or job description, establishes its exact byte
identity, performs intake checks, registers a version, and produces one
explicit outcome. It MUST NOT hand bytes to document parsing until all required
intake checks pass.

## 1. Inputs and authorization

- **S1-001:** Accept a declared track: `resume` or `job_description`.
- **S1-002:** Authenticate the uploader and authorize access to the applicable
  owner, job, and track before accepting content. Client-provided owner/job
  identifiers are untrusted; authorization MUST be checked against the
  approved identity/authorization service.
- **S1-003:** Support the specification's PDF and DOCX upload track. The
  specification also permits a JD supplied as text, but does not fully define
  that intake contract; decide and document whether plain text is accepted in
  the initial upload endpoint.
- **S1-004:** Treat filename, extension, declared MIME type, client hash, and
  other client metadata as hints only. The server/isolated inspection path
  determines actual format and authoritative digest.
- **S1-005:** Support retry-safe upload/session requests. A repeated request
  must not create duplicate versions or trigger duplicate work.

## 2. Quarantine and byte handling

- **S1-006:** Receive raw bytes into a restricted quarantine location before
  processing.
- **S1-007:** Store quarantined raw bytes in write-once storage or enforce an
  equivalent immutability boundary: no later stage may modify the original.
- **S1-008:** The quarantine pointer MUST be opaque and access-controlled. Raw
  storage credentials MUST NOT appear in API responses or handoff contracts.
- **S1-009:** Enforce a configured hard byte limit while streaming, not solely
  from `Content-Length` or client-declared size. Avoid buffering an
  unbounded upload in application memory.
- **S1-010:** Record actual byte count and compare it with declared metadata
  when the protocol supplies a declaration. A mismatch MUST produce an
  explicit failure/rejection and quarantine cleanup or retention according to
  policy.
- **S1-011:** Temporary plaintext copies MUST be removed on success, failure,
  cancellation, and retry exhaustion in accordance with the retention policy.

## 3. Intake checks

- **S1-012:** Determine actual file type from bytes/signature, not filename
  extension alone; reject unsupported or mismatched types with a named reason.
- **S1-013:** Enforce configured size and page limits. The source specification
  requires limits but does not give approved numeric thresholds; leave them
  configurable and unresolved until product/policy owners approve them.
- **S1-014:** Detect encrypted/password-protected files and apply the approved
  policy. The specified outcome is `REJECTED` when the service cannot open the
  file; password handling is otherwise undefined.
- **S1-015:** Detect embedded executables or scripts and other approved active
  content. The policy must distinguish security blocking from ordinary format
  rejection. Do not silently continue after detection.
- **S1-016:** Inspect DOCX archive metadata without unbounded extraction.
  Enforce approved expansion-size, ratio, entry-count, and macro policies. The
  numeric values and exact DOCX package rules remain open decisions.
- **S1-017:** Run an approved malware scan in a restricted processing
  boundary. Malware findings produce `BLOCKED` and the file MUST NOT be parsed.
- **S1-018:** Treat storage/scanner failures as infrastructure failures, not
  clean results. Route to `FAILED`, apply bounded retries, and escalate after
  retry exhaustion.

## 4. Fingerprint, registration, and publication

- **S1-019:** Compute `original_sha256` over the exact uploaded bytes on the
  server. This is the authoritative root for all later traces.
- **S1-020:** Register each upload in a version registry keyed by owner, job,
  and track. Assign `version_id`, monotonically increasing `version_seq`, and
  a fixed `uploaded_at` timestamp.
- **S1-021:** Use compare-and-swap or equivalent concurrency control so
  simultaneous uploads cannot both become the latest version.
- **S1-022:** Detect duplicates by authoritative digest within the specified
  owner/job scope. A duplicate MUST link to the existing version and MUST NOT
  enqueue new parsing work.
- **S1-023:** Persist the intake outcome and outgoing work notification in one
  transaction using a transactional outbox. A message MUST NOT be published
  for an uncommitted record; a committed ready record MUST NOT be stranded
  without its notification.
- **S1-024:** Record enough immutable metadata to reproduce the decision,
  including actual type, actual byte count, uploaded time, track, outcome,
  reason code/advisories, original digest, version identifiers, and opaque
  quarantine reference.

## 5. Outcomes

Every intake attempt MUST end in exactly one explicit outcome:

| Outcome | Required meaning and behavior |
|---|---|
| `READY` | All intake checks passed; eligible for Stage 3 pre-gate. |
| `DUPLICATE` | Same authoritative `original_sha256` already exists for the owner/job scope; link to existing version, do no further work. |
| `REJECTED` | Unsupported/wrong type, over limit, or unopenable encrypted file; return a safe reason and stop. |
| `BLOCKED` | Malware or approved active-content security risk; hold for security review and never parse. |
| `FAILED` | Temporary infrastructure failure such as storage/scanner fault; bounded retry then operations escalation. |
| `EXPIRED` | Upload window or retention period elapsed; apply approved archive/deletion behavior and, when deleted, signed tombstone requirements. |

No automatic outcome may reject a candidate as a person. `REJECTED` concerns
the submitted file or policy, not candidate merit.

## 6. Stage 1 acceptance tests

- A valid PDF and DOCX each reach `READY`; their server-computed digest matches
  an independently computed digest of the exact source bytes.
- Unsupported/signature-mismatched formats, over-limit streams, mismatched
  sizes, and unopenable encrypted files reach explicit `REJECTED` outcomes.
- Malware and active-content test fixtures reach `BLOCKED`, and no parse job is
  published for them.
- Scanner and storage faults reach `FAILED`; retry counts are bounded and
  exhaustion is visible to operations.
- Re-uploading identical bytes in the same owner/job scope returns `DUPLICATE`
  linked to the existing version, without a second parse job.
- Concurrent uploads cannot create two latest versions for the same
  owner/job/track.
- Crash injection around database commit and message publication proves the
  transactional outbox can recover without a lost or duplicate logical job.
- Cancellation and every terminal path demonstrate required quarantine
  cleanup or policy-governed retention.
