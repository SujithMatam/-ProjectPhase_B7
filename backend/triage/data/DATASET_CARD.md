# Dataset card: post-op triage messages (v1.1)

Single-message, 3-class triage (RED / YELLOW / GREEN) for patients after total knee (TKA) or
total hip (THA) replacement. Built to replace `backend/data/exports/triage_intent_*.jsonl`, whose
problems are measured in `AUDIT.md`. v1.1 = v1 with 12 labels adjudicated (`ADJUDICATION.md`); no
row moved between splits. **v2** (2026-11-12) adds a second held-out set (`challenge_v2.jsonl`, 90
rows) and 380 training-only rows (`train_v2_extra.jsonl`, origin `generated_v2`); val, test,
challenge and every existing label and row are unchanged (see "v2 additions" below). Models
trained on it: `backend/triage/REPORT.md`.

## Files

| file | what |
|---|---|
| `splits/train.jsonl`, `splits/val.jsonl`, `splits/test.jsonl` | **main split**: within-scenario cluster split; every scenario in all three splits |
| `splits_unseen_scenario/*.jsonl` | **secondary split**: same rows, group-split by `scenario_id` (val/test scenarios never seen in train) |
| `challenge.jsonl` | 150-row stress test, written after the splits; never train or tune on it |
| `challenge_v2.jsonl` | **v2**: 90-row held-out set (negation, YELLOW/RED wound minimal pairs, routine multi-topic), written and committed (f340dc1) before any v2 training data; never train or tune on it |
| `train_v2_extra.jsonl` | **v2**: 380 training-only rows (`origin: generated_v2`); `model/common.py load_train(split, "v2")` appends them to train |
| `challenge_v2_source.tsv`, `build_challenge_v2.py`, `CHALLENGE_V2_REPORT.md` | v2 held-out set: source, builder (near-duplicate check), report |
| `authored_v2/*.tsv`, `build_train_v2.py`, `TRAIN_V2_REPORT.md` | v2 training rows: source, builder (near-duplicate drops), report with every dropped row |
| `LABELLING_GUIDELINE.md` | the label definitions and rules (v1.1) |
| `ADJUDICATION.md`, `adjudication.tsv` | v1.1 label changes; applied by the builders after split assignment |
| `RELABEL_CHANGES.md` | re-labelling of the 63 original sentences |
| `AUDIT.md`, `SPLIT_REPORT.md`, `CHALLENGE_REPORT.md`, `stats.json` | generated reports (`SPLIT_REPORT.md`/`stats.json` describe the main split) |
| `SPLIT_REPORT_unseen_scenario.md`, `stats_unseen_scenario.json` | reports for the secondary split |
| `ANNOTATION_AGREEMENT.md`, `ANNOTATION_DISAGREEMENTS.md`, `annotation/` | blind second annotation: agreement numbers, every disagreement, sample and scripts |
| `ANNOTATION_AGREEMENT_V2.md`, `annotation/v2/`, `annotation/build_annotation_sample_v2.py` | blind second annotation of challenge_v2 (`compute_agreement.py --v2`) |
| `authored/*.tsv`, `challenge_source.tsv`, `source_relabelled.jsonl` | inputs to the builders |
| `audit_source.py`, `relabel_source.py`, `build_dataset.py`, `build_split_clustered.py`, `build_challenge.py` | scripts, run in that order |
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
cd backend/triage/data
HF_HUB_OFFLINE=1 ../../.venv/Scripts/python build_split_clustered.py
HF_HUB_OFFLINE=1 ../../.venv/Scripts/python build_challenge.py
python annotation/build_annotation_sample.py   # blind sample for the second annotator
python annotation/compute_agreement.py         # after annotation/second_labels.tsv exists
```
`adjudication.tsv` is applied inside `build_dataset.py`, `build_split_clustered.py` and
`build_challenge.py`; split assignment always uses the pre-adjudication labels.

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

There are two splits of the same 1,795 rows. Both are frozen; report which one a score is on.

**Main split (`splits/`)**: within-scenario cluster split. Every scenario appears in train, val and
test with about the same label mix, so this split measures generalisation to new messages about
known topics. Details in `SPLIT_REPORT.md`.

| split | rows | RED | YELLOW | GREEN | RED % | scenarios | source_template | generated |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| train | 1,253 | 480 | 289 | 484 | 38.3 | 31 | 44 | 1,209 |
| val | 276 | 103 | 67 | 106 | 37.3 | 31 | 9 | 267 |
| test | 266 | 104 | 62 | 100 | 39.1 | 31 | 10 | 256 |
| **all** | **1,795** | **687** | **418** | **690** | **38.3** | **31** | **63** | **1,732** |

Surgery: TKA 875, THA 920. Words per message: 3-38, median 15.

| scenario_id | lead | rows | train R/Y/G | val R/Y/G | test R/Y/G |
|---|---|---:|---|---|---|
| ALLERGIC_REACTION | RED | 51 | 28/4/3 | 6/1/1 | 6/1/1 |
| BLEEDING_ANTICOAG | RED | 73 | 40/2/8 | 9/1/1 | 9/1/2 |
| COMPARTMENT | RED | 73 | 40/3/8 | 8/1/2 | 9/1/1 |
| DISLOCATION | RED | 73 | 40/2/10 | 9/0/2 | 8/0/2 |
| DVT_CALF | RED | 73 | 41/2/8 | 9/0/2 | 9/1/1 |
| FALL_INJURY | RED | 60 | 34/3/5 | 7/1/1 | 7/1/1 |
| HIGH_FEVER | RED | 70 | 35/6/8 | 7/1/2 | 8/2/1 |
| NEUROVASCULAR | RED | 73 | 40/3/8 | 9/0/2 | 9/1/1 |
| PE_CHEST | RED | 74 | 42/2/8 | 9/0/2 | 9/1/1 |
| SEPSIS_WOUND | RED | 73 | 40/2/8 | 9/1/2 | 9/1/1 |
| WOUND_OPEN | RED | 60 | 34/4/4 | 7/1/1 | 7/1/1 |
| CLEAR_DRAINAGE | YELLOW | 62 | 4/30/10 | 1/6/2 | 1/6/2 |
| CONSTIPATION | YELLOW | 55 | 4/22/12 | 1/5/3 | 1/5/2 |
| IMPLANT_NOISE | YELLOW | 54 | 5/21/12 | 1/5/2 | 1/4/3 |
| LOW_FEVER | YELLOW | 58 | 3/26/11 | 1/6/3 | 1/5/2 |
| MED_SIDE_EFFECT | YELLOW | 52 | 6/20/10 | 2/4/2 | 1/5/2 |
| MINOR_BLEEDING | YELLOW | 52 | 4/18/14 | 1/4/3 | 1/4/3 |
| MISSED_DOSE | YELLOW | 52 | 5/22/10 | 1/5/2 | 1/4/2 |
| UNCONTROLLED_PAIN | YELLOW | 57 | 6/26/8 | 1/5/2 | 1/6/2 |
| WOUND_IRRITATION | YELLOW | 53 | 3/24/9 | 1/6/2 | 1/4/3 |
| WOUND_REDNESS | YELLOW | 58 | 6/25/10 | 1/6/2 | 1/5/2 |
| DAILY_ACTIVITY | GREEN | 48 | 2/2/31 | 0/0/6 | 0/0/7 |
| FOLLOWUP_ADMIN | GREEN | 48 | 2/3/28 | 0/1/6 | 1/1/6 |
| HIP_PRECAUTIONS | GREEN | 49 | 2/1/31 | 1/1/7 | 0/0/6 |
| MED_TIMING | GREEN | 49 | 2/3/29 | 1/1/6 | 0/1/6 |
| MOOD_SLEEP | GREEN | 49 | 3/3/28 | 0/1/6 | 1/1/6 |
| NORMAL_SWELLING | GREEN | 49 | 2/3/30 | 1/1/6 | 0/0/6 |
| NUTRITION | GREEN | 50 | 2/2/31 | 0/1/7 | 0/0/7 |
| REHAB_EXERCISE | GREEN | 48 | 1/2/30 | 0/1/7 | 1/0/6 |
| STIFFNESS | GREEN | 49 | 2/2/31 | 0/0/7 | 0/0/7 |
| WALKING_AIDS | GREEN | 50 | 2/1/31 | 0/1/7 | 1/0/7 |

Every RED-led scenario has at least 6 RED rows in val and in test (minimum: ALLERGIC_REACTION, 6/6).
Minority labels inside a scenario are small: a non-RED scenario typically has 0-2 RED rows in val
or test, so per-scenario scores on minority labels are not meaningful.

Author-assigned tags in the main split (a row can have several):

| tag | train | val | test | all |
|---|---:|---:|---:|---:|
| hard_pos | 180 | 38 | 38 | 256 |
| hard_neg | 170 | 36 | 36 | 242 |
| negation | 68 | 15 | 15 | 98 |
| indian_english | 212 | 45 | 46 | 303 |
| typo | 132 | 29 | 29 | 190 |
| temp_in_text | 110 | 25 | 24 | 159 |
| carer | 110 | 24 | 24 | 158 |

**Secondary split (`splits_unseen_scenario/`)**: group split by `scenario_id`, so val and test
scenarios never appear in train. This measures transfer to unseen topics; for example, test RED
is mostly ALLERGIC_REACTION and HIGH_FEVER. It is the v1 split unchanged. Details in
`SPLIT_REPORT_unseen_scenario.md`.

| split | rows | RED | YELLOW | GREEN | RED % | scenarios |
|---|---:|---:|---:|---:|---:|---:|
| train | 1,240 | 474 | 294 | 472 | 38.2 | 21 |
| val | 280 | 108 | 62 | 110 | 38.6 | 5 (CLEAR_DRAINAGE, FALL_INJURY, MED_TIMING, NORMAL_SWELLING, WOUND_OPEN) |
| test | 275 | 105 | 62 | 108 | 38.2 | 5 (ALLERGIC_REACTION, FOLLOWUP_ADMIN, HIGH_FEVER, MOOD_SLEEP, UNCONTROLLED_PAIN) |

Challenge set (`challenge.jsonl`, 150 rows):

| category | rows | RED | YELLOW | GREEN |
|---|---:|---:|---:|---:|
| negation | 20 | 4 | 4 | 12 |
| keyword_free_red | 20 | 20 | 0 | 0 |
| indian_english | 21 | 7 | 7 | 7 |
| typo_or_slang | 21 | 8 | 7 | 6 |
| numeric_in_text | 21 | 7 | 7 | 7 |
| multi_symptom | 20 | 9 | 8 | 3 |
| benign_scary_word | 20 | 0 | 3 | 17 |
| audit_regression | 7 | 3 | 2 | 2 |
| **all** | **150** | **58** | **38** | **54** |

The 7 `audit_regression` rows are exactly the cases named in the task, including the curly
apostrophe in "I can’t breathe".

## v2 additions (training-only data and challenge_v2)

Why: the hybrid pipeline over-triaged (YELLOW->RED 34/62 and GREEN->RED 6 on test), called negated
RED symptoms RED ("I don't have shortness of breath") and turned two routine multi-topic messages
in `test_multi_agent_orchestration.py` RED (REPORT.md, Finding S4).

Order, so the held-out set could not be shaped by the new training data:
1. `challenge_v2.jsonl` (90 rows) was written by claude-opus-5-5 from the guideline v1.1, checked
   (0 exact and 0 cosine > 0.92 matches with train/val/test/challenge; highest 0.903) and
   committed alone (f340dc1). SHA-256 in `CHALLENGE_V2_REPORT.md`.
2. Then three claude-opus-5-5 writers, one per category, were given only `LABELLING_GUIDELINE.md`
   and `authored/README.md` (and told not to open any challenge, split, report or test file) and
   wrote 382 rows (`authored_v2/`). Each row also lists the scenario topics it touches.
3. `build_train_v2.py` dropped exact duplicates, rows with cosine > 0.92 to any row of main val,
   main test, challenge or challenge_v2, rows with cosine > 0.92 to the two orchestration-test
   messages, and rows labelled below their stated temperature. One row was also dropped on label
   review as ambiguous. Result: 2 dropped, **380 kept**; highest cosine of a kept row to a
   protected row 0.898, to an orchestration-test message 0.713.

| set | rows | RED | YELLOW | GREEN | notes |
|---|---:|---:|---:|---:|---|
| challenge_v2 | 90 | 26 | 32 | 32 | negation 30 (6/8/16), wound_minimal_pair 36 (18/18/0, 18 pairs), routine_multi_topic 24 (2/6/16) |
| train_v2_extra | 380 | 97 | 135 | 148 | negation 127, wound_minimal_pair 124, routine_multi_topic 129 |

Main-split train for v2 = the 1,253 frozen train rows + 380 = 1,633 rows (RED 577, YELLOW 424,
GREEN 632). For the unseen-scenario split only the 157 v2 rows flagged `unseen_split_ok` are added
(no topic among that split's val/test scenarios and cosine <= 0.92 to every row of them), so its
val/test scenarios stay unseen. The v2 rows are not tagged with a single `scenario_id`
(`scenario_id: null`, `scenarios: [...]`).

Limitations specific to v2: the same model family wrote the v2 training rows, challenge_v2 and the
guideline, so a gain on challenge_v2 is partly a gain on the same author's phrasing, even with the
near-duplicate filter and the separate writers. The v2 training labels were reviewed by the same model, not by a
clinician or a blind second annotator. challenge_v2 was blind-annotated by a fresh claude-sonnet
subagent (guideline + shuffled texts only): 90/90 agreement, kappa 1.000 overall and in every
category (`ANNOTATION_AGREEMENT_V2.md`; no label changed). That shows the guideline is reproducible
on these prototypical messages, not that the labels are clinically right.

## Split and leakage checks

Main split (`build_split_clustered.py`, `SPLIT_REPORT.md`):

- Within each scenario, rows were clustered with all-MiniLM-L6-v2 embeddings: agglomerative,
  single linkage, cosine distance threshold 0.15. With single linkage, no two rows of the same
  scenario in different clusters have cosine > 0.85 (measured max 0.848). Whole clusters were
  assigned to splits by a seeded search targeting 70/15/15 of each label inside each scenario.
  The 0.85 threshold groups very little: 1,780 clusters are single rows, 6 have 2 rows and 1 has 3.
  In practice this is a near-paraphrase-aware stratified split, so val/test share topics and
  vocabulary with train.
- One cross-scenario pair above 0.92 (two apixaban nosebleed messages, BLEEDING_ANTICOAG /
  MINOR_BLEEDING, 0.933) was forced into the same split (test).
- No identical sentence (after lower-casing and stripping punctuation) appears in two splits.
- Cross-split pairs with cosine > 0.92: **0**; highest cross-split cosine **0.917**.
- Closest train row for each val/test row: median cosine 0.663 (val) and 0.668 (test).
- Challenge vs all split rows (re-run on the new splits): 0 exact matches, 0 above 0.92 (highest
  0.910, median nearest 0.724). The challenge set itself is unchanged.
- Temperatures in text vs labels: 2 rows are labelled below the stated temperature, both
  intended (a "what if it goes above 38.5" question; a 37.9 reading that a doctor has since seen).
  See `SPLIT_REPORT_unseen_scenario.md`.

Secondary split (`build_dataset.py`, `SPLIT_REPORT_unseen_scenario.md`): group split by
`scenario_id` (70/15/15 by rows, label mix balanced by a seeded search; val and test each hold at
least one RED-led and one non-RED-led scenario). No scenario is in two splits, 0 cross-split
pairs above 0.92, highest 0.917.

## Annotation agreement

A blind second annotation was run (`ANNOTATION_AGREEMENT.md`). One claude-sonnet subagent saw only
`LABELLING_GUIDELINE.md` and texts with opaque ids. The sample was 300 main-split rows (100 per
label, all 31 scenarios) plus all 150 challenge rows.

| subset | n | agreement | Cohen's kappa (95% CI) |
|---|---:|---:|---|
| all | 450 | 98.7% | 0.980 (0.963-0.993) |
| split rows | 300 | 98.7% | 0.980 (0.960-0.995) |
| challenge rows | 150 | 98.7% | 0.980 (0.948-1.000) |

There are 6 disagreements: 5 YELLOW->GREEN and 1 GREEN->YELLOW (ours -> second); none involves RED.
They are listed with the deciding guideline rule in `ANNOTATION_DISAGREEMENTS.md`. The numbers above
are against the **pre-adjudication** labels and are kept as measured. Adjudication (`ADJUDICATION.md`)
changed 5 of the 6 to the second annotator's label (`CH-102` stayed YELLOW), added three guideline
rules, and applied those rules to 7 further rows found by searching every row. Treat the agreement as
an upper bound: the messages were written to fit the guideline and both annotators are Claude models.

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
- **Pick the split to match the question.** On the main split, test messages are new but their
  topics are all in train, so it measures within-topic generalisation and will score higher.
  The unseen-scenario split is harsh by design: its test scenarios (e.g. HIGH_FEVER,
  ALLERGIC_REACTION) never appear in train. Train there has only 21 rows whose stated temperature
  is >= 38.5 °C, while test has 28, mostly from HIGH_FEVER.
- **Label prevalence is not real-world.** 38% RED is far above what a deployed triage line sees;
  calibrate thresholds separately before use.
- Single messages only: no conversation history, no patient record, no post-op day.
- Within a scenario, messages share a topic and some phrasing. On the main split, val/test rows
  have same-scenario paraphrases in train up to cosine 0.85. Scenario lead label correlates
  strongly with the label, so a model can score well on the main split by learning topic -> label.
  Compare the hard_pos / hard_neg / negation subsets and the challenge set.
- **Second annotation is LLM vs LLM.** 98.7% agreement (kappa 0.98) with a blind Sonnet annotator
  shows that the guideline is reproducible. It does not show that the labels are clinically correct.
- Tags were assigned by the authors and were spot-checked, not verified row by row.
- For `ANY` messages the surgery (TKA/THA) is chosen at random from the text hash; it is not
  meaningful for those rows.
- English only; procedures other than TKA/THA are out of scope.
