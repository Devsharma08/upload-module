# EGCA Pipeline — Stage 1 Policy and Limits

**Status:** Baseline targets. No values in this document are calibrated
(`Measured`) unless evidence is linked in the final column. Values inherited
from the initial design are marked **Placeholder** until validated against a
representative test corpus and production-like worker profile.

## File and Format Limits

| Policy | PDF | DOCX | TXT | Status | Evidence / notes |
|---|---:|---:|---:|---|---|
| Maximum uploaded bytes | 10 MB | 10 MB | 10 MB | Placeholder | Initial generic client-side limit; enforce independently while streaming or at quarantine storage. No corpus evidence yet. |
| Page count | TBD | N/A | N/A | Placeholder | No page cap or measurement specified. |
| Character count | N/A | TBD | TBD | Placeholder | Stage 1 does not extract text; any character cap requires a narrowly defined validation method that does not expand Stage 1 into content extraction. |
| Archive expansion ratio | N/A | `< 20:1` | N/A | Placeholder | Initial DOCX ZIP guard target; validate calculation, total expanded bytes, and corpus coverage. |
| Macro indicator | N/A | Reject if `vbaProject.bin` is present | N/A | Placeholder | Initial design rule; verify exact package-part matching and approved DOCX variants. |
| Encoding | N/A | N/A | Strict UTF-8 | Placeholder | Initial design rule; define BOM and invalid-sequence behavior in tests. |
| Accepted extensions | `.pdf` | `.docx` | `.txt` | Placeholder | Extension is not authoritative; require server-side signature/structure and media-type agreement. |

`N/A` means the policy does not apply to that format. `TBD` means no limit has
been selected. An unset limit must not be treated as unlimited in a production
implementation.

## Worker and Processing Limits

| Resource / control | Baseline value | Status | Evidence / notes |
|---|---:|---|---|
| Worker memory | 512 MB | Placeholder | Illustrative initial target; no benchmark dataset or measurement supplied. Enforce with the container/cgroup boundary. |
| Worker wall-clock timeout | 10 seconds | Placeholder | Illustrative initial target; no benchmark evidence supplied. Timeout must terminate the isolated process. |
| CPU quota | TBD | Placeholder | Must be set before production; validate under parallel load and hostile inputs. |
| Outbound network | Disabled | Placeholder | Required isolation property in the design; verify through deployment configuration/tests. |
| Temporary storage | Ephemeral volume/tmpfs | Placeholder | Design requirement; capacity, encryption-at-rest behavior, and cleanup tests are TBD. |
| Antivirus | ClamAV (`clamd`) | Placeholder | Engine/version, signature freshness, timeout, and error disposition are not specified. |
| PDF probe | `pikepdf` in capped subprocess | Placeholder | Page/password/`/JS`/`/Font` probes are proposed; supported versions and safe failure rules are TBD. |
| Archive probe | ZIP central-directory inspection | Placeholder | Must avoid unbounded extraction; expansion and entry-count caps need validation. |

## API, Session, and Rate Limits

| Control | Baseline value | Status | Evidence / notes |
|---|---:|---|---|
| Session TTL | 15 minutes | Placeholder | Initial design target for abandoned sessions; verify cleanup and retry behavior. |
| Pre-signed quarantine URL TTL | 15 minutes | Placeholder | Optimized-flow target; enforce object key, method, size, and expiry restrictions. |
| Per-uploader rate limit | TBD requests/minute | Placeholder | Tier 1 is required; numeric quota is unset. |
| Per-SHA-256 rate limit | TBD requests/hour | Placeholder | Tier 2 is required; numeric quota is unset. |
| Duplicate response latency | `< 50 ms` | Placeholder | Target only; measure with the authoritative server-side hash lookup under expected scale/load. |
| Upload byte ceiling | 10 MB initial generic cap | Placeholder | Must be enforced server-side while streaming, or by quarantine storage policy in optimized flow. |

## Calibration Evidence Requirements

No representative test dataset or measured benchmark results were provided for
this baseline. Before changing any row to **Calibrated (Measured)**, record:

- Dataset name/version, sample count, formats, and relevant edge-case coverage.
- Test environment and versions of parsers, antivirus engine/signatures, and
  worker isolation settings.
- Measurement method and observed results, including worst-case resource use
  and error behavior.
- Date and test/report reference.

Do not label a threshold calibrated based solely on a successful unit test or
an illustrative target.
