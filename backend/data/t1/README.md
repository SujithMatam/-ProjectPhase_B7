# T1 triage seed audit

This pipeline creates an immutable, versioned copy of the triage-intent seed
exports and two reproducible evaluation partitions. It does **not** train a
model, alter the deterministic `SafetyTriageEngine`, or validate that the
source labels are clinically correct.

The source exports contain 420 train and 90 test rows labeled RED/YELLOW/GREEN
and also carry `expected_intent` labels. They are distinct from the separate
Qwen SFT dataset; no Qwen SFT rows are included here. The original seed files
are copied byte-for-byte into `seed_v1/`. Their SHA-256 hashes, row counts,
source commit, output hashes, and split configuration are recorded in
`build_v1/manifest.json`.

## Audit findings

The original train split has 82 exact and 63 normalized unique `user_message`
values; the original test split has 55 exact and 51 normalized unique values.
There are 52 exact unique messages shared by the two splits (52/55 test
messages) and 51 normalized messages shared (51/51). The audit normalization
case-folds, replaces whole-word `left`/`right` with `{side}`, replaces
post-op/day-number expressions with `{day}`, and collapses whitespace. Other
wording and punctuation are retained. The source split also shares all 21
provisional rationale groups.

The builder groups rows using normalized `clinical_rationale` values only as a
conservative, auditable *provisional* scenario key; it does not assert that a
rationale is a clinical guideline or a verified scenario taxonomy. Every
scenario group is flagged `needs_manual_scenario_review`. The wording split
groups on normalized user messages. Both partitions keep all rows belonging to
each grouping key together, with deterministic SHA-256 ordering within the
source triage-label strata.

## Clinical review status

No standalone written clinical triage guideline was found in the repository.
The deterministic triage implementation is code, not a clinical guideline.
Consequently, all source labels in generated data have
`label_review_status: needs_clinical_review`; the clinical review queue
contains every source row, and `label_corrections.csv` is header-only. No
label corrections, synthetic examples, paraphrases, or hard cases were
generated. A clinician must review the source labels and provisional groups
against an approved written guideline before the outputs are used for training
or clinical performance claims.

The scenario-held-out evaluation measures generalization to rationale-based
provisional groups not present in its training partition. The separate
wording-held-out evaluation measures generalization to normalized wording
groups not present in its training partition; it may contain another wording
of a scenario represented in training, by design. These are dataset partitions
only—not evidence of model performance. Production safety decisions must
remain with the existing deterministic triage system.

## Build and test

From the repository root:

```bash
python backend/data/t1/build_t1_dataset.py
python backend/data/t1/test_build_t1_dataset.py
```

The versioned seed directory is immutable: if a source export changes, the
builder refuses to replace `seed_v1/`. Create a new versioned seed directory
and update the provenance rather than mutating an existing seed.
