# EGCA Phase 1 Requirements

These documents translate **EGCA Phase 1 Specification v2: Trusted and
Traceable Data Preparation (Stages 1-5)** into implementation-facing
requirements for the Python upload and preparation application.

The source specification is
[`EGCA_Phase1_Specification_v2.pdf`](../../../Downloads/EGCA_Phase1_Specification_v2.pdf)
in the author's Downloads folder. Keep the source PDF as the authority when an
interpretation here is disputed. These notes organize and clarify its
requirements; they do not silently make product, policy, or vendor decisions.

## Requirement set

1. [Product scope and system-wide rules](01-product-and-trust.md)
2. [Stage 1: upload and quarantine](02-stage-1-upload.md)
3. [Stages 2 and 3: verification and governance](03-stages-2-and-3.md)
4. [Stages 4 and 5: structuring and normalization](04-stages-4-and-5.md)
5. [Contracts, failures, operations, and acceptance](05-contracts-and-acceptance.md)

## How to read these requirements

- **MUST** identifies behavior required by the source specification.
- **SHOULD** identifies a recommended implementation practice that supports a
  stated requirement but is not itself a separately mandated product decision.
- **Open decision** means the source leaves a value, provider, or policy
  unresolved. Do not treat an example, placeholder, or local development choice
  as an approved production value.
- Requirement IDs are stable references for implementation issues and tests.
- The project is being implemented in Python. These documents intentionally do
  not select an identity provider, database vendor, queue, object-storage
  provider, malware-scanner deployment, KMS, or production hosting provider.

## Product boundary

Phase 1 accepts resume and job-description material and produces faithful,
reproducible, traceable, tamper-evident records for downstream use. It records
what a document says; it does not determine whether those claims are true or
evaluate a candidate.

The intended pipeline is:

```text
Stage 1 Upload and quarantine
  -> Stage 3 pre-gate
  -> Stage 2 parse and visual verification
  -> Stage 3 post-gate
  -> Stage 4 rule-based structuring
  -> Stage 5 normalization
  -> signed seal and independent verification
```

Stage 3 deliberately gates work both before and after Stage 2. Stages 4 and 5
are deterministic for fixed inputs and pinned versions. A small non-generative
tagger is optional and must remain behind the agreement gate defined in the
source specification; it is not part of the initial rules-only thin slice.
