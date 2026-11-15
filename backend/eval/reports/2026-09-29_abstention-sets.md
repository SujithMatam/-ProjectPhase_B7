# 2026-09-29: Claude calibration scores recorded, blind abstention sets exported

Scope: only `backend/eval/` changed (`scores/claude/calibration.jsonl`, `reports/2026-09-29_calibration-agreement.md`, `reports/abstention_set_part{1,2,3}.md`, `reports/abstention_key.json`, and this report). Nothing staged or committed. The mistral:7b judge was left running and wasn't touched.

## 1. Calibration scores and agreement

- **`scores/claude/calibration.jsonl`:** 20 rows with `id, letter, grounded, unsupported, embellished, unanswerable_handling, rater: "claude", blind: true`, plus `answerability`, `variant`, the calibration-set timestamp and `recorded_at`.
  - Values that weren't given are `null`, not 0.
  - `full` rows (q04, q10) have `unanswerable_handling: "n/a"`, as the rubric requires.
  - The file sits outside `scores/manual/` and `scores/judge/`, so `score.py summary` doesn't read it.
- **Agreement:** full detail is in `2026-09-29_calibration-agreement.md`.

| measure | Claude vs qwen2.5:7b |
|---|---|
| grounded, exact | 12/20 (60%) |
| grounded, within 1 | 20/20 |
| Cohen's κ | 0.41 |
| handling (partial/none) | 9/12 |

  The judge pulls scores towards 1: Claude gave 10 twos and the judge 6, and 5 of the 8 disagreements are Claude 2 → judge 1.

## 2. Abstention sets

These cover all 21 `partial`/`none` queries under project_abstain, 7 per file in `eval_queries.jsonl` order. MedGemma comes from `results_medgemma_2048/`. The format is the same as `calibration_set.md`: fields, reference, every frozen chunk in full, and four answers A-D.

| file | queries |
|---|---|
| `abstention_set_part1.md` | q06 (partial), q09 (none), q14 (partial), q16 (partial), q17 (partial), q18 (partial), q19 (none) |
| `abstention_set_part2.md` | r04 (partial), r07 (partial), r08 (none), r09 (none), r17 (partial), r18 (partial), r19 (none) |
| `abstention_set_part3.md` | r20 (partial), c10 (partial), c13 (partial), c17 (partial), c18 (partial), c19 (partial), c20 (none) |

- **Letter orders:** 21 distinct permutations out of the 24 possible, drawn with `random.SystemRandom`, so no two queries share an order across the three parts.
- **Key:** `reports/abstention_key.json` holds `note`, `encoding` and `key_b64` (base64 of JSON with the sources, the parts and the letter mapping). Nothing from it was printed.
- **Checks passed:**
  - no model names in the set files;
  - no plain model names in the key file;
  - the key decodes back to the mapping;
  - 84 answers in total.

**Limits of the blinding:**
- **q16, r09 and c19 are also in the calibration set, whose key is now open.** Their 12 answer texts are identical to the calibration ones, only relabelled, so a rater can recognise which model wrote each. Score them as not blind, or drop them from blind statistics (that leaves 18 queries, 72 answers).
- **q14 (part 1) has one empty answer**, shown as *(no answer was given)*: MedGemma used all 2048 tokens reasoning. Only MedGemma produces empty answers, so that one answer identifies its model.
- As before, writing style (curly apostrophes, "Okay," openers) can hint at the model.

## Mistral judge (not touched, observed only)

At 16:02 it had finished 36/60 of the first file (llama3.2 project_abstain), at about 13.6 s per response, and `ollama ps` showed `100% GPU`. The estimated finish is about **16:45-16:55**. **Invalid records:** at 38/60 there were 11 invalid on disk. I checked all 11, and all have the uncorrectable problem, `n/a` on a partial/none question (7 partial, 4 none). Only 13 partial/none questions had been judged at that point, so **mistral:7b answered `n/a` on 11 of 13**. Its handling scores will be almost entirely missing, and its grounded and claim scores on partial/none are excluded along with them. So as things stand, **mistral:7b can't serve as a second opinion on abstention.** Possible fixes, all for you to decide:
- a per-item JSON schema with enum `["correct","invented"]` for partial/none (option (ii) from before);
- re-asking only those invalid items with that schema;
- accepting mistral's grounded and claim scores and ignoring its handling.
