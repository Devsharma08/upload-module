# Stage 4 and Stage 5 Requirements

## Stage 4: Rule-based structuring

Stage 4 turns Stage 2 verified blocks into a structured, traceable record.
Rules are the authority; the output contains claims only and is not an
assessment.

### Structure and extraction

- **S4-001:** Accept only content approved by the Stage 3 post-gate.
- **S4-002:** Build sections and entries and maintain a conservation ledger:
  every verified character MUST either be assigned to a field or explicitly
  recorded as unplaced. No silent loss is allowed.
- **S4-003:** Extract supported roles, organizations, dates, skills, links, and
  numbers. Every value MUST carry a source span
  `(block_id, start_character, end_character)`.
- **S4-004:** Store dates as intervals. A month-only date covers the whole
  month. “Present” is resolved using the immutable `uploaded_at` timestamp,
  never the current clock. An end and start in the same month do not count as
  overlap.
- **S4-005:** Keep identity data separate behind `pii_ref`.
- **S4-006:** Apply the specified deterministic rule families: core date/role
  rules R1–R11, format/field rules F1–F6, and JD checks J1–J3 as scheduled in
  the build plan. Pin exact rule versions in every output.

### Labels and flags

Use labels only when fully certain:

| Label | Required meaning |
|---|---|
| `CONTRADICTION` | Two claims cannot both be true even under a generous reading. |
| `CONFLICT` | Claims disagree in a way a reviewer should inspect. |
| `FACT` | Plain extracted statement with no identified issue. |
| `NOT_EVALUATED` | Unable to judge; retain a reason such as extraction, imprecise, ambiguous, identity, scale_unknown, or parse_ocr. |

Uncertainty MUST NOT be upgraded into a contradiction.

The following manipulation flags set risk to `REVIEW`; flagged text is never
turned into a skill claim and MUST NOT automatically reject a candidate:

| Flag | Detection target |
|---|---|
| `M1 INSTRUCTION_LIKE` | Visible text addressed to a screener/AI, such as instructions to ignore prior directions or rate a candidate highly. |
| `M2 WRONG_DOCUMENT` | Resume track contains a non-resume document, such as an invoice or form. |
| `M3 STUFFING` | Long context-free skill lists or repeated keywords. |
| `M4 UNICODE_ANOMALY` | Look-alike characters, zero-width characters, or mixed scripts inside a word. |
| `M5 LINK_MISMATCH` | Visible link text does not match the stored target. Never fetch the URL. |

### Optional tagger agreement gate

The first implementation MUST be rules-only. If a fixed, non-generative CPU
tagger is added later:

1. It may run only on text the rules left unplaced or `NOT_EVALUATED`.
2. It must not run on blocks carrying M1–M5 flags.
3. Its proposal must read back exactly from the verified block at the supplied
   span.
4. At least one independent rule must agree.
5. It must not contradict a rule-extracted value.
6. On disagreement, rules win and the disagreement is logged.
7. An accepted value is `PROPOSED_AGREED` and includes tagger ID, weights hash,
   and agreeing rule IDs in the pinned run profile and record hash.
8. Rejected proposals remain `NOT_EVALUATED`; measure accepted-proposal error
   rate rather than assuming it is zero.

### Stage 4 output and acceptance

Emit fields, spans, labels, flags, provenance, unplaced text, `record_root`,
`pii_ref`, and version metadata. Tests must verify exact span read-back,
conservation-ledger completeness, deterministic results, conservative label
behavior, M1–M5 handling, and zero promotion of flagged text into normalized
skills.

## Stage 5: Normalization

Stage 5 maps explicit source terms to a versioned canonical vocabulary without
guessing or scoring.

### Normalization rules

- **S5-001:** Verify `record_root` and the preceding hash chain before
  processing.
- **S5-002:** Match exact canonical terms first, then explicit aliases.
  `alias_of` entries are the only basis for merging terms.
- **S5-003:** Maintain negative pairs so lookalikes such as Java/JavaScript
  and C/C# remain distinct.
- **S5-004:** Normalize units/values such as duration, degrees, grades, and
  numeric ranges while preserving ranges as ranges.
- **S5-005:** Preserve original wording beside any canonical ID. Normalization
  is a matching key and MUST NOT rewrite source intent.
- **S5-006:** Assign provenance: `STATED`, `NORMALIZED`, or
  `PROPOSED_AGREED`; reserve `INFERRED` as empty in v1.
- **S5-007:** Assign item status `PRESENT`, `UNMAPPED`, `NOT_ACCEPTED`, or
  `MISSING`. Unknown skills remain `UNMAPPED`; flagged text is
  `NOT_ACCEPTED`.
- **S5-008:** Count each canonical skill once, regardless of repeated
  occurrences. Self-rated levels may pass through as stated but are not
  treated as trusted assessments.
- **S5-009:** Store versioned relation classes only:
  `SAME_FAMILY_SAME_ECOSYSTEM`,
  `SAME_ECOSYSTEM_DIFFERENT_FAMILY`,
  `SAME_FAMILY_DIFFERENT_ECOSYSTEM`, and `PREREQUISITE`. Relations carry no
  score and never satisfy a mandatory job requirement.
- **S5-010:** Record taxonomy version on every output. A taxonomy change
  creates a new `stage5_root`; old outputs remain valid for their old version.
- **S5-011:** Flagged M1–M5 text MUST remain flagged and MUST NOT become a
  normalized skill.

### Job-description requirements

- **S5-012:** Normalize draft requirements through the same taxonomy as resume
  skills, retaining the original requirement sentence beside every canonical
  ID, family, ecosystem, and related-skill suggestion.
- **S5-013:** Relations are suggestions only. A relation becomes an approved
  alternative only after recruiter approval.
- **S5-014:** Record each requirement origin as `EXTRACTED`,
  `RECRUITER_EDITED`, `RECRUITER_ADDED`, or `RECRUITER_APPROVED`. Recruiter
  actions include actor ID and time; earlier values remain in the audit log.
- **S5-015:** Seal the finalized requirement set (DRS) only after recruiter
  review. Store `drs_hash`, taxonomy version, and approved alternatives.
- **S5-016:** Freeze a per-job `run_profile_hash` covering parser, OCR, policy,
  rule-set, optional tagger/weights, taxonomy, and hashing-spec versions.
  Candidates for that job use the frozen profile. Version changes require a
  new profile and batch rerun; old results/seals remain available.

### Stage 5 acceptance

- A labeled alias/negative-pair corpus produces no incorrect merges.
- No term merges without an explicit alias, and negative pairs always remain
  distinct.
- Reprocessing with the same record/taxonomy versions yields the same
  `stage5_root`; a taxonomy update yields a new root without invalidating the
  prior one.
- Relations never produce scores or satisfy requirements absent explicit
  recruiter approval.
- JD original sentences, requirement origins, recruiter decisions, DRS hash,
  and frozen run profile are all traceable and sealed.
