# Cross-Stage Contracts, Failure Handling, and Acceptance

## 1. Handoff contracts

Every inter-stage contract MUST have fixed field names and types, reject
unknown fields, and carry the version metadata needed to reproduce its result.
A receiver MUST validate required values and hashes before processing. A
failed validation is a named failure, never a partial success.

| Handoff | Required information | Receiver checks |
|---|---|---|
| Stage 1 -> Stage 3 pre-gate | `version_id`, `version_seq`, `original_sha256`, actual file type, `uploaded_at`, track, quarantine pointer | Outcome is `READY`; reading bytes from quarantine recomputes to `original_sha256`. |
| Stage 3 pre-gate -> Stage 2 | Above plus idempotency key and `run_profile_hash` | Key not processed before; version is current; job/application remains open. |
| Stage 2 -> Stage 3 post-gate | Blocks and `block_hash` values, `clean_artifact_sha256`, side channel, parse status, risk tier, warnings, forensic reference | Hashes recompute; status and risk values are supported. |
| Stage 3 post-gate -> Stage 4 | Approved Stage 2 fields, gate decision, `uploaded_at`, `run_profile_hash` | Decision is `CONTINUE`; version sequence remains current. |
| Stage 4 -> Stage 5 | Sealed record, `record_root`, labels, flags, provenance, `pii_ref` | `record_root` recomputes and chain reaches `clean_artifact_sha256`. |
| Stage 5 -> recruiter (JD) | Draft requirements, canonical IDs, families, ecosystems, related skills, taxonomy version | Every requirement keeps its source sentence. |
| Recruiter -> DRS sealer | Approved requirements, IDs, alternatives, taxonomy version, signed decisions | `drs_hash` and `run_profile_hash` are stored. |
| Stage 5 -> sealer | Normalized record, `stage5_root`, taxonomy version | `stage5_root` recomputes. |
| Sealer -> Part II | Signed seal, root, trace pointers, optional `drs_hash`, `run_profile_hash` | Signature is valid and corresponding log entry exists. |

The Stage 2 forensic reference is access-controlled and MUST NOT be treated as
claim text. Unknown fields are rejected to prevent silent contract drift.

## 2. Failure and review routing

Every stop is visible, auditable, and associated with a stable reason code.
The source specification requires a policy-configured deadline for human-wait
states and an automatic next step; a waiting item must never disappear.

| Condition | Required route |
|---|---|
| Wrong type, too large, or unopenable encrypted file | Stage 1 `REJECTED`; tell uploader the safe reason. |
| Malware or active-content risk | Stage 1 `BLOCKED`; hold for security review and do not parse. |
| Storage/scanner fault | Stage 1 `FAILED`; bounded retry then operations escalation. |
| Same bytes already registered | Stage 1 `DUPLICATE`; link existing version and stop duplicate work. |
| Serious hidden-content evidence | Stage 2 `QUARANTINE`; reviewer action; never auto-release or auto-reject. |
| Suspicious, non-serious visibility evidence | Stage 2 `REVIEW`; continue only under explicit policy and retain flags. |
| Some pages unreadable | `PARTIAL` or `PARSE_FAILED`; request a better file and represent application as incomplete. |
| Older version finishes after newer version accepted | Stage 3 `SUPERSEDED`; stop stale result. |
| Job closed/application withdrawn | Stage 3 `ARCHIVED_INACTIVE`; stop processing. |
| Similar but not identical new version | Stage 3 `NEAR_DUPLICATE`; reviewer decides; never auto-merge. |
| M1–M5 manipulation flag | Stage 4 `REVIEW`; flagged text is not used as a claim. |
| Conflict cannot be judged | Stage 4 `NOT_EVALUATED` plus reason. |
| Skill absent from taxonomy | Stage 5 `UNMAPPED`; route to taxonomy maintenance. |
| Hash or signature mismatch | `INTEGRITY_FAILURE`; stop and alert security/engineering. |
| Content already deleted under policy | Verifier reports `NOT_POSSIBLE_DELETED` for content checks; signature/tombstone/log checks remain possible. |

No stop or unknown state may be counted as a negative candidate outcome.
`NOT_EVALUATED`, `MISSING`, `UNMAPPED`, `NOT_ACCEPTED`, and
`NOT_POSSIBLE_DELETED` map downstream to `NOT_OBSERVED` with original reason
and state preserved.

## 3. Independent verifier requirements

The verifier is a small separate tool that trusts only the public signing key
and supplied records:

1. **Integrity:** check signature; recompute `stage5_root`, `record_root`,
   `clean_artifact_sha256`, each `block_hash`, and exact claim-span read-back.
   If original bytes are supplied, recompute their hash.
2. **Reproduce:** rerun deterministic Stages 4 and 5 using pinned rules and
   taxonomy and compare roots.
3. **Optional re-read:** rerun Stage 2 using pinned parser/OCR versions.
   Differences are informational because OCR implementations can vary.

The verifier returns PASS/FAIL per link and names the first broken link. For
deleted content it returns `NOT_POSSIBLE_DELETED` for content-dependent checks,
not PASS/FAIL.

Tamper tests change one element at a time: original byte, block text, record
field, normalized value, claim span, signature, and audit-log entry. The test
must fail at the correct chain link.

## 4. Evaluation requirements

Before making accuracy or safety claims, measure and report:

- Hidden-text detection rate and false alarms per attack against synthetic
  attack fixtures and real clean resumes.
- Triage share of frames that skip OCR and time saved against full OCR.
- Triage misses found by full-OCR audit sampling.
- Reading-order/section/column accuracy on hand-labeled multi-column resumes.
- Structuring/date accuracy and conservation-ledger completeness.
- Wrong `CONTRADICTION`/`CONFLICT` labels, reviewed against hand labels.
- Alias accuracy and incorrect skill-merge rates, including negative pairs.
- Tamper detection accuracy at the correct chain link.
- Reproducibility of `stage5_root` across repeated runs and machines.
- Claim trace completeness: percent of claims whose span reads back exactly.
- If the optional proposer is implemented: yield by layout type, proposal
  acceptance/rejection reasons, and error rate of accepted values. Any false
  label introduced by a proposal is a failure.
- Deletion test proving content checks become `NOT_POSSIBLE_DELETED` while
  signature/tombstone/log checks remain valid, and tampering with tombstone/log
  fails.

Every reported measurement includes corpus/dataset version and sample count,
format/layout coverage, software and rule versions, test environment, method,
observed results, and known limitations. A passing unit test alone does not
calibrate a production limit.

## 5. Recommended build order

The specification's thin slice is small-PDF end-to-end work. Its ten-step
expansion is:

1. Canonical hashing, domain tags, and verifier skeleton. Done when hash
   vectors pass on two machines.
2. Stage 1 PDF/DOCX checks, fingerprint, and version registry. Done when every
   Stage 1 outcome is reachable in tests.
3. Stage 2 Tier 0/Tier 1, frames, verdicts, and reading order. Done when hidden
   text is caught and clean samples pass.
4. Stage 4 core structuring/date rules. Done when spans read back exactly and
   test data has no false labels.
5. Stage 5 aliases, negative pairs, relations, and aggregator. Done when the
   labeled list has no wrong merges.
6. Seal, append-only log, and verifier levels 1 and 2. Done when tamper tests
   fail at the right link.
7. Stage 2 Tier 2/Tier 3 OCR and audit sample. Done when triage safety is
   measured against full OCR.
8. JD track and DRS workflow. Done when recruiter review works and `drs_hash`
   is stored.
9. Complete Stage 3 governance. Done when fencing, idempotency, and watcher
   tests pass. The Stage 3 pre-gate is built alongside Stage 1; this step
   completes the wider post-gate/governance behavior.
10. Run evaluations and publish the measured results.

The first implementation should complete steps 1–6 on a small PDF corpus.
Core Stage 4 rules are prioritized; optional rules and the proposer are
subsequent work. Production sizing and subscription cost are explicitly outside
the specification's evaluation scope.

## 6. Python application integration requirements

The source specification is service-provider neutral. The Python application
MUST define replaceable, tested boundaries for:

- Identity and authorization.
- Durable metadata, transactions, compare-and-swap, and transactional outbox.
- Queue/job dispatch and bounded retries.
- Write-once quarantine and restricted forensic storage.
- Malware scanning and scanner-health/error outcomes.
- Parser/OCR execution boundaries and resource controls.
- Signing-key custody, public-key distribution, and checkpoint export.
- Deletion, backup erasure, retention, and tombstone operations.

Production adapters MUST be selected and configured explicitly. A local
development adapter is not evidence that a production security boundary has
been satisfied. No endpoint may bypass authorization or make client metadata
authoritative.
