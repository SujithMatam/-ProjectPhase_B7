# Provenance

Branch `feature/triage-classifier` was created from `origin/main` at
`9f60dfe7bc7668418c3825d8bd88f1efc3e2b3e3`.

## Copied unchanged into `source/`

| file in `source/` | copied from | last commit touching the original | sha256 |
|---|---|---|---|
| `triage_intent_train.jsonl` | `backend/data/exports/triage_intent_train.jsonl` @ 9f60dfe | 42b39aa (2026-09-29) | `cf04254622ddfa5ae097ea0b55ed7b727797172bfac3b4ebdeac76d671226980` |
| `triage_intent_test.jsonl` | `backend/data/exports/triage_intent_test.jsonl` @ 9f60dfe | 42b39aa (2026-09-29) | `53f0e5774b83f3907cbca96326a5788b5e4e4cbcfaf542aea1016ca0d7e4ffca` |
| `dataset_builder.py` | `backend/data/dataset_builder.py` @ 9f60dfe | 42b39aa (2026-09-29) | `cd853587ac038acb8941840f1a4df42ca749dd818157021333d9e8f73357ab71` |

## Exported

| file | how | source |
|---|---|---|
| `source/triage_intent_val.jsonl` | `SELECT * FROM triage_intent_cases WHERE split='val' ORDER BY case_id`, one JSON object per row, same keys as the other exports (90 rows) | `backend/data/datasets.sqlite3` @ 9f60dfe (last commit 42b39aa; sha256 `a7de5d4c2e084bc0455ae4aada6d5ce7f7ccf7fc11b4d04411477ccc321b9e81`). The sqlite file itself is not copied or committed here. |

sha256 of the exported file: `cd6135387ed32a0e5455308f001136eac52d792a515ba58ad79dc61c7bb72175`.

## Brought from another branch

| file | from | sha256 |
|---|---|---|
| `backend/eval/eval_corpus.json` | `origin/feature/llm-eval` @ `a753d0424d585fd70b4f02069f42cd4cc258e946` (commit a753d04, "Add local-LLM RAG evaluation harness, corpus, 60-query benchmark and results"); not on main | `a92d71a98410e59d02c0f280dd7daa055d0eb4a22197bd75e8012b2a18530b33` |

It is used only as the reference for the warning signs in `LABELLING_GUIDELINE.md`.

## Generated here

Everything else in `backend/triage/data/` was written on this branch: the scripts, the docs,
`authored/*.tsv` (patient messages written by claude-opus-5-5), the splits and `challenge.jsonl`.
See `DATASET_CARD.md`.
