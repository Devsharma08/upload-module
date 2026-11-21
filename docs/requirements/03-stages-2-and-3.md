# Stage 2 and Stage 3 Requirements

## Stage 2: Parse and visually verify

Stage 2 extracts text and positions, then determines whether extracted words
are actually visible to a human. It produces a clean artifact containing only
verified claim text, plus a restricted forensic bundle and explicit parse/risk
outcomes.

### Parsing and layout

- **S2-001:** Accept only a `READY` version forwarded by the Stage 3 pre-gate.
- **S2-002:** Pin and record parser and OCR engine versions. Save OCR output so
  later verification can reuse it instead of repeating expensive work.
- **S2-003:** Extract text-layer words and relevant font, size, colour, position,
  and render-mode information.
- **S2-004:** Keep links, annotations, and document metadata in a separate
  `side_channel`; never mix them into claim text.
- **S2-005:** Render pages and split each into 4–8 section-based frames using
  visible ink and whitespace in the rendered image, not text-layer positions.
  Hidden text MUST NOT move frame boundaries.
- **S2-006:** Frames are the unit of rendering/OCR so that re-checks and
  failures can be limited to affected frames.

### Visibility triage

The pipeline MUST run inexpensive checks first and expensive OCR only where
needed:

| Tier | Scope | Required checks |
|---|---|---|
| 0 | Every word | Invisible render mode, very small font, off-page position, colour close to background, coverage by shape/image, and odd font mapping. |
| 1 | Every frame | Differential rendering with/without text layer; compare extracted words with visible ink. |
| 2 | Doubtful frames | Per-word OCR and comparison against extracted text. |
| 3 | Scanned or still-uncertain pages | Full-page OCR for pages with no usable text layer, mostly vector/image coverage, odd font maps, or remaining uncertainty. |

- **S2-007:** Scanned pages and odd-font-map pages MUST NOT be skipped by OCR.
- **S2-008:** Run a random audit sample of pages that passed triage through full
  OCR. Full OCR is the measured reference baseline for triage safety.
- **S2-009:** When no usable text layer exists, OCR may supply text and
  positions; mark it `OCR_ONLY`.
- **S2-010:** Rebuild reading order after visibility checks using verified
  words only (XY-cut on verified word positions). Hidden words cannot affect
  layout or column order.

### Verdicts and outputs

| Verdict | Meaning | Claim use |
|---|---|---|
| `CORROBORATED` | Text-layer word appears in the render. | May be used. |
| `CORROBORATED_FUZZY` | Render corroborates with minor differences such as ligatures/accents. | May be used with recorded verdict. |
| `UNCORROBORATED_NOT_VISIBLE` | Extracted but not visible. | Do not use; drop and log. |
| `UNCORROBORATED_TEXT_MISMATCH` | Visible content reads differently from text layer. | Do not use; route to review. |
| `ICON_GLYPH` | Symbol/icon font rather than text. | Ignore as a claim. |
| `OCR_ONLY` | Read by OCR from a scanned page. | May be used with parse-quality note. |

“Doubtful” is an intermediate triage state only, never a final verdict.

- **S2-011:** Assign risk `CLEAN`, `REVIEW`, or `QUARANTINE`. Serious hidden
  content produces `QUARANTINE`; suspicious but non-serious evidence produces
  `REVIEW`; uncertain cases are not silently promoted to clean.
- **S2-012:** Assign parse status `PARSED`, `PARSED_WITH_WARNINGS`, `PARTIAL`,
  or `PARSE_FAILED`.
- **S2-013:** Emit block records with `block_id`, `block_hash`, page, frame ID,
  integer bounding box, column ID, reading order, and verdict reference.
- **S2-014:** Compute `clean_artifact_sha256` over verified text and required
  parser/policy version metadata. Include the separate side channel, parse
  status, risk tier, warnings, and restricted `forensic_ref`.
- **S2-015:** Store rendered/OCR forensic material in restricted storage,
  separate from normal claim access.

## Stage 3: Ingestion and governance

Stage 3 controls whether work is current, wanted, and safe to continue. It runs
twice: a pre-gate after Stage 1 and a post-gate after Stage 2.

### Pre-gate

- **S3-001:** Compute an idempotency key from
  `SHA256(version_id + ':' + parser_build_id)`. The same version/build pair is
  accepted once; retries return the previous result.
- **S3-002:** Apply epoch fencing using `version_seq`. If a newer version has
  already been accepted, mark the older one `SUPERSEDED` and stop it. A stale
  worker MUST NOT overwrite newer output.
- **S3-003:** Check state watchers, including job closed and application
  withdrawn events. Move waiting work to `ARCHIVED_INACTIVE` and stop further
  work.
- **S3-004:** Verify the Stage 1 outcome is `READY`, the original bytes match
  `original_sha256`, the version remains current, and the job/application is
  open before dispatching Stage 2.

### Post-gate

- **S3-005:** Stop Stage 4 processing for `PARTIAL`, `PARSE_FAILED`,
  `QUARANTINE`, and policy-defined blocking warnings.
- **S3-006:** Apply warning policy by severity and track; resume and JD warning
  dispositions may differ.
- **S3-007:** Check near-duplicates within the same owner/job slot. Flag
  `NEAR_DUPLICATE` for reviewer action; never auto-merge.
- **S3-008:** Recheck job/application active state and version fencing before
  forwarding to Stage 4.
- **S3-009:** Append every pre/post-gate decision to the audit log and write
  the outgoing message in the same transaction through a transactional outbox.
- **S3-010:** Forward the decision, reasons, block hashes, clean-artifact hash,
  upload timestamp, track, risk tier, and warnings.

### Stage 3 acceptance

- Concurrent upload tests prove compare-and-swap and latest-version semantics.
- Repeated work for a version/parser build is idempotent.
- A newer version fences out old workers, including workers that finish late.
- Closing a job or withdrawing an application stops waiting work at both gates.
- Gate decisions and emitted messages survive crash injection without
  divergence.
- Near-duplicate detection flags for review and never merges records.
