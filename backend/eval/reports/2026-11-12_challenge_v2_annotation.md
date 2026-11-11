# challenge_v2 blind second annotation (2026-11-12)

Method as in v1 (`backend/triage/data/annotation/`): the 90 challenge_v2 texts shuffled (seed
20261112) and renamed B01-B90; a fresh claude-sonnet subagent got only `LABELLING_GUIDELINE.md`
v1.1 and `annotation/v2/blind_items.tsv` (no labels, ids, categories). Kappa from
`compute_agreement.py --v2`. Full report: `backend/triage/data/ANNOTATION_AGREEMENT_V2.md`.

| subset | n | dataset R/Y/G | agreement | Cohen's kappa | 95% CI (bootstrap) |
|---|---:|---|---:|---:|---|
| all | 90 | 26/32/32 | 100.0% | 1.000 | 1.000-1.000 |
| negation | 30 | 6/8/16 | 100.0% | 1.000 | 1.000-1.000 |
| routine_multi_topic | 24 | 2/6/16 | 100.0% | 1.000 | 1.000-1.000 |
| wound_minimal_pair | 36 | 18/18/0 | 100.0% | 1.000 | 1.000-1.000 |

Disagreements: none. No challenge_v2 label was changed (file SHA-256 unchanged).

Caveats: the set was written to fit the guideline (explicit RED features in each minimal pair,
plain negations), so perfect agreement shows reproducibility on prototypical messages, not on
borderline cases; both annotators are Claude models; the annotator's file reads are self-reported
(it reported reading only the two allowed files, and used two shell commands instead of the one
allowed, to rewrite a labels file that was missing B90).
