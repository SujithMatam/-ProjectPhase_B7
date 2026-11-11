# Dataset card: post-op triage messages (v1)

Single-message, 3-class triage (RED / YELLOW / GREEN) for patients after total knee (TKA) or
total hip (THA) replacement. Built to replace `backend/data/exports/triage_intent_*.jsonl`, whose
problems are measured in `AUDIT.md`. No model has been trained on it yet.

## Files

| file | what |
|---|---|
| `splits/train.jsonl`, `splits/val.jsonl`, `splits/test.jsonl` | the dataset, group-split by `scenario_id` |
| `challenge.jsonl` | 150-row stress test, written after the splits; never train or tune on it |
| `LABELLING_GUIDELINE.md` | the label definitions and rules |
| `RELABEL_CHANGES.md` | re-labelling of the 63 original sentences |
| `AUDIT.md`, `SPLIT_REPORT.md`, `CHALLENGE_REPORT.md`, `stats.json` | generated reports |
| `authored/*.tsv`, `challenge_source.tsv`, `source_relabelled.jsonl` | inputs to the builders |
| `audit_source.py`, `relabel_source.py`, `build_dataset.py`, `build_challenge.py` | scripts, run in that order |
| `source/`, `PROVENANCE.md` | original files copied unchanged, and where they came from |

Row fields (splits): `id, text, label, scenario_id, surgery (TKA|THA), tags, origin
(source_template|generated), source_template, old_label, generator, split`. Challenge rows have
`category` instead of `scenario_id`/`tags`. There is deliberately **no** structured temperature
or post-op-day field: the original `temperature_c` leaked the label (AUDIT.md section 4), so
temperatures appear only in the message text.

To rebuild (deterministic):
```
python backend/triage/data/audit_source.py
python backend/triage/data/relabel_source.py
HF_HUB_OFFLINE=1 backend/.venv/Scripts/python backend/triage/data/build_dataset.py
cd backend/triage/data && HF_HUB_OFFLINE=1 ../../.venv/Scripts/python build_challenge.py
```

## Sources

1. **The 63 distinct sentences** in the original exports (600 rows = 63 templates with
   Left/Right/day filled in; see `AUDIT.md`). Each was kept once, re-labelled against the guideline
   (6 labels changed), given a surgery that matches its wording, and marked
   `origin=source_template`, generator `backend/data/dataset_builder.py (relabelled by claude-opus-5-5)`.
2. **1,732 synthetic messages** written by claude-opus-5-5 (`origin=generated`), one file per
   scenario in `authored/`, following `authored/README.md` and the guideline. They were written by
   five parallel instances of the same model, each handed the same guideline and brief.
3. **Challenge set**: 150 messages written by claude-opus-5-5 after the splits were frozen.

The guideline is based on the warning-sign passages in `backend/eval/eval_corpus.json`
(EV-TKA-PAIN-01/06, EV-THA-PAIN-01/02/06, EV-THA-REC-04/05) and on the thresholds in
`backend/triage/safety_triage.py` (>= 38.5 °C RED, >= 37.8 °C YELLOW).

## Labels

- **RED**: needs same-day emergency or urgent assessment.
- **YELLOW**: contact the care team within about 24 hours / needs review.
- **GREEN**: routine or informational.

Rules: label what the patient reports experiencing, not the topic; pure information questions are
GREEN; negated symptoms do not count; highest finding wins; temperatures follow the thresholds;
when torn, pick the higher level. Full text: `LABELLING_GUIDELINE.md`.

## Counts

| split | rows | RED | YELLOW | GREEN | RED % | scenarios | source_template | generated |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| train | 1,240 | 474 | 305 | 461 | 38.2 | 21 | 51 | 1,189 |
| val | 280 | 108 | 62 | 110 | 38.6 | 5 | 8 | 272 |
| test | 275 | 105 | 62 | 108 | 38.2 | 5 | 4 | 271 |
| **all** | **1,795** | **687** | **429** | **679** | **38.3** | **31** | **63** | **1,732** |

Surgery: TKA 875, THA 920. Words per message: 3-38, median 15.

| scenario_id | split | rows | RED | YELLOW | GREEN |
|---|---|---:|---:|---:|---:|
| BLEEDING_ANTICOAG | train | 73 | 58 | 5 | 10 |
| COMPARTMENT | train | 73 | 57 | 5 | 11 |
| CONSTIPATION | train | 55 | 6 | 32 | 17 |
| DAILY_ACTIVITY | train | 48 | 2 | 2 | 44 |
| DISLOCATION | train | 73 | 57 | 2 | 14 |
| DVT_CALF | train | 73 | 59 | 3 | 11 |
| HIP_PRECAUTIONS | train | 49 | 3 | 2 | 44 |
| IMPLANT_NOISE | train | 54 | 7 | 30 | 17 |
| LOW_FEVER | train | 58 | 5 | 37 | 16 |
| MED_SIDE_EFFECT | train | 52 | 9 | 29 | 14 |
| MINOR_BLEEDING | train | 52 | 6 | 33 | 13 |
| MISSED_DOSE | train | 52 | 7 | 31 | 14 |
| NEUROVASCULAR | train | 73 | 58 | 4 | 11 |
| NUTRITION | train | 50 | 2 | 3 | 45 |
| PE_CHEST | train | 74 | 60 | 3 | 11 |
| REHAB_EXERCISE | train | 48 | 2 | 3 | 43 |
| SEPSIS_WOUND | train | 73 | 58 | 5 | 10 |
| STIFFNESS | train | 49 | 2 | 2 | 45 |
| WALKING_AIDS | train | 50 | 3 | 2 | 45 |
| WOUND_IRRITATION | train | 53 | 5 | 36 | 12 |
| WOUND_REDNESS | train | 58 | 8 | 36 | 14 |
| CLEAR_DRAINAGE | val | 62 | 6 | 42 | 14 |
| FALL_INJURY | val | 60 | 48 | 5 | 7 |
| MED_TIMING | val | 49 | 3 | 5 | 41 |
| NORMAL_SWELLING | val | 49 | 3 | 4 | 42 |
| WOUND_OPEN | val | 60 | 48 | 6 | 6 |
| ALLERGIC_REACTION | test | 51 | 40 | 6 | 5 |
| FOLLOWUP_ADMIN | test | 48 | 3 | 5 | 40 |
| HIGH_FEVER | test | 70 | 50 | 9 | 11 |
| MOOD_SLEEP | test | 49 | 4 | 5 | 40 |
| UNCONTROLLED_PAIN | test | 57 | 8 | 37 | 12 |

Author-assigned tags (a row can have several):

| tag | train | val | test | all |
|---|---:|---:|---:|---:|
| hard_pos | 179 | 37 | 40 | 256 |
| hard_neg | 168 | 42 | 32 | 242 |
| negation | 63 | 17 | 18 | 98 |
| indian_english | 207 | 48 | 48 | 303 |
| typo | 131 | 30 | 29 | 190 |
| temp_in_text | 89 | 11 | 59 | 159 |
| carer | 103 | 27 | 28 | 158 |

Challenge set (`challenge.jsonl`, 150 rows):

| category | rows | RED | YELLOW | GREEN |
|---|---:|---:|---:|---:|
| negation | 20 | 4 | 4 | 12 |
| keyword_free_red | 20 | 20 | 0 | 0 |
| indian_english | 21 | 7 | 7 | 7 |
| typo_or_slang | 21 | 8 | 7 | 6 |
| numeric_in_text | 21 | 7 | 7 | 7 |
| multi_symptom | 20 | 9 | 8 | 3 |
| benign_scary_word | 20 | 0 | 2 | 18 |
| audit_regression | 7 | 3 | 2 | 2 |
| **all** | **150** | **58** | **37** | **55** |

The 7 `audit_regression` rows are exactly the cases named in the task, including the curly
apostrophe in "I can’t breathe".

## Split and leakage checks

- Group split by `scenario_id` (70/15/15 by rows; label mix balanced by a seeded search, and val
  and test each hold at least one RED-led and one non-RED-led scenario). No scenario is in two splits.
- No identical sentence (after lower-casing and stripping punctuation) appears in two splits.
- Near-duplicates: all-MiniLM-L6-v2 embeddings, cosine > 0.92 between rows of different splits:
  **0 pairs** (none needed removing; highest cross-split cosine 0.917).
- Challenge vs all split rows: 0 exact matches, 0 above 0.92 (highest 0.910, median nearest 0.724).
- Temperatures in text vs labels: 2 rows are labelled below the stated temperature, both
  intended (a "what if it goes above 38.5" question; a 37.9 reading that a doctor has since seen).
  See `SPLIT_REPORT.md`.

## What is synthetic

Everything. The 63 source sentences came from a template generator; every other message was
written by claude-opus-5-5. No message comes from a real patient. The Indian-English, slang and
typo messages imitate those styles; they were not collected from Indian patients or real chats.

## Known limitations

- **No clinician review.** The guideline, every label and the challenge set were written by an
  LLM from a public-education corpus. Treat labels as a reasonable first pass, not ground truth.
  The borderline calls the authors flagged (e.g. widespread hives, head knock on anticoagulants,
  falls without injury, numbness beside the scar) were resolved by adding rules to the guideline.
- **Same model wrote the text and the labels**, so its errors and style are shared across all
  splits and the challenge set. Scores on test/challenge will overstate performance on real
  patient messages.
- **Unseen-scenario evaluation is harsh by design.** Test scenarios (e.g. HIGH_FEVER,
  ALLERGIC_REACTION) never appear in train. Train has only 21 rows whose stated temperature is
  >= 38.5 °C (inside SEPSIS_WOUND, LOW_FEVER, etc.), while test has 28 of them, mostly from HIGH_FEVER.
- **Label prevalence is not real-world.** 38% RED is far above what a deployed triage line sees;
  calibrate thresholds separately before use.
- Single messages only: no conversation history, no patient record, no post-op day.
- Within a scenario, messages share a topic and some phrasing (1 within-split pair above 0.92);
  scenario lead label correlates strongly with the label.
- Tags were assigned by the authors and were spot-checked, not verified row by row.
- For `ANY` messages the surgery (TKA/THA) is chosen at random from the text hash; it is not
  meaningful for those rows.
- English only; procedures other than TKA/THA are out of scope.
