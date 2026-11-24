# EGCA Upload Module Requirements

These documents define requirements for the **Python upload module only**,
based on Stage 1 (Upload and Quarantine) of the final **EGCA Phase 1
Specification: Trusted and Traceable Data Preparation (Stages 1-5)** dated
November 23, 2026. This final DOCX replaces Phase 1 Specification v2.
They are not a specification for the complete five-stage pipeline.

The source specification is
[the final EGCA Phase 1 specification (DOCX)](../../../Downloads/EGCA%20Phase%201%20Final%20Specification%20Trusted%20and%20Traceable%20Data%20Preparation%20%28Stages.docx)
in the author's Downloads folder. Keep this final source DOCX as the authority
when an interpretation here is disputed. These notes organize and clarify its
requirements; they do not silently make product, policy, or vendor decisions.

## Documents

1. [Upload module scope and trust requirements](01-product-and-trust.md)
2. [Stage 1 upload and quarantine requirements](02-stage-1-upload.md)
3. [Upload API, service boundaries, and acceptance](03-upload-api-and-acceptance.md)

## How to read these requirements

- **MUST** identifies behavior required by the source specification.
- **SHOULD** identifies a recommended implementation practice that supports a
  stated requirement but is not itself a separately mandated product decision.
- **Open decision** means the source leaves a value, provider, or policy
  unresolved. Do not treat an example, placeholder, or local development choice
  as an approved production value.
- Requirement IDs are stable references for implementation issues and tests.
- The project is being implemented in Python. These documents do not select an
  identity provider, database vendor, queue, object-storage provider,
  malware-scanner deployment, KMS, or production hosting provider.

## Scope boundary

In scope: authenticated upload requests, upload sessions, streaming bytes into
quarantine, intake checks, authoritative file hashing, duplicate detection,
version registration, upload outcomes, and reliable handoff to the next
processing stage.

Out of scope for this requirements set: PDF text/visibility parsing (Stage 2),
pipeline governance after intake (Stage 3), resume/JD content structuring
(Stage 4), skill normalization (Stage 5), candidate evaluation, and the full
signed-record verifier. The upload module must provide stable handoff fields
for downstream components without implementing those components.

## Implementation order

Implementation proceeds in small, verifiable checkpoints:

1. Establish the Python project, supported interpreter range, and local
   virtual environment. Keep the initial project free of application
   dependencies.
2. Add only the runtime and test dependencies needed for a runnable API shell.
   Lock them and verify a health endpoint and one test.
3. Define upload contracts and unresolved policy decisions before implementing
   service behavior.
4. Implement bounded quarantine streaming and cleanup, then select and add
   database/storage/scanner adapters only when each module is reached.
5. Add intake inspection, session/version persistence, and API integration in
   individually tested steps.
6. Add real authentication/authorization and distributed rate limiting after
   the local upload flow works, before any shared or public deployment.

Authentication integration and API rate limiting are deferred, but hard upload
byte limits and bounded processing resources are required from the first
intake implementation. The upload-only milestone does not include Stages 2–5.
