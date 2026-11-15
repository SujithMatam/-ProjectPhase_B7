# 2026-09-29: abstention results, 21 partial/none queries × 4 models (project_abstain)

Scope: wrote `scores/claude/abstention.jsonl` (84 rows) and this report. Nothing staged or committed. The mistral:7b judge was left alone.

## Inputs

- **Claude's blind scores:** from `abstention_set_part{1,2,3}.md`. The key (`abstention_key.json`) was decoded after the scores were recorded.
  - Unstated `unsupported`/`embellished` are stored as `null` and count as 0 in the totals.
  - `followed_format` defaults to true, and `fmt0` makes it false.
  - The one `empty` answer is stored with `grounded: null`, `unanswerable_handling: "empty"` and `followed_format: null`.
  - **q16, r09 and c19 (marked †)** were also in the calibration set, whose key was already open, so their rows have `blind: false`.
- **Models:** llama3.2, gemma3 and qwen3.5 come from `results/` (num_predict 600), and MedGemma from `results_medgemma_2048/` (num_predict 2048).
- **Empty check:** the answer Claude marked `empty` is the only empty response among the 84 in the results (`empty_response`): **consistent**.
- **Judge:** qwen2.5:7b scores from `scores/judge/qwen2.5-7b/`, with the `full` rule applied (it doesn't affect partial/none). All 84 `response_sha256` values match the scored responses.

## Key findings

- **Invented answers (Claude, out of 21):** medgemma (2048) 4, llama3.2 6, qwen3.5 9, gemma3 10. Fewest is best. On the 18 blind queries: medgemma (2048) 2/18, llama3.2 6/18, qwen3.5 8/18, gemma3 8/18.
- **MedGemma at 2048 invents least** (4/21, and 1 empty answer, q14), and gemma3 invents most (10/21). gemma3 and MedGemma share a base model and a quantisation, so on this small sample the medical tuning goes with fewer invented answers. But MedGemma's 2048 budget gives a median of 13.6 s per answer, against 2.3 s for gemma3.
- **The judge agrees with Claude on handling 64/81 times (79%, κ 0.52), but it's too lenient on llama3.2:** it calls 1 of llama3.2's answers invented, where Claude found 6 (κ 0.22 for llama3.2). For gemma3 and qwen3.5 its invented totals are the same as Claude's (10 and 9), though not always on the same answers (handling agreement 17/21 and 13/20). The two rankings differ only in where llama3.2 and MedGemma fall.
- **Grounded:** the judge again compresses towards 1. Exact agreement is 60% and within one point 99% (κ 0.38). Of Claude's 18 zeros the judge made 13 into 1s, and of Claude's 34 twos it made 15 into 1s. The judge flags few claims as `unsupported` and many as `embellished`, while Claude does the reverse, so the claim columns aren't comparable between the two raters.
- **Format:** llama3.2 fails the format 5 times (Claude), more than any other model. The judge disagrees and marks only 1.
- **Latency:** llama3.2 is fastest (1.4 s median), then gemma3/qwen3.5 (~2.3 s), then MedGemma (12-14 s, because of the reasoning trace). MedGemma completes only 56% of answers at 600 tokens, against 96% at 2048.
- **Caveats:** 21 queries per model, one rater, and 3 of the 21 queries weren't blind. With counts this small, a difference of 1-2 invented answers isn't meaningful.

## Claude, per model

| model | n | invented | correct | empty | mean grounded | grounded = 0 | unsupported | embellished | format fails |
|---|---|---|---|---|---|---|---|---|---|
| llama3.2 | 21 | **6/21** | 15 | 0 | 1.48 | 3 | 6 | 3 | 5 |
| gemma3 | 21 | **10/21** | 11 | 0 | 0.90 | 7 | 18 | 8 | 1 |
| medgemma (2048) | 21 | **4/21** | 16 | 1 | 1.30 | 3 | 9 | 4 | 2 |
| qwen3.5 | 21 | **9/21** | 12 | 0 | 1.14 | 5 | 14 | 7 | 0 |

### Claude, `partial` only (15 queries)

| model | n | invented | correct | empty | mean grounded | grounded = 0 | unsupported | embellished | format fails |
|---|---|---|---|---|---|---|---|---|---|
| llama3.2 | 15 | **4/15** | 11 | 0 | 1.47 | 3 | 4 | 2 | 5 |
| gemma3 | 15 | **8/15** | 7 | 0 | 0.80 | 5 | 13 | 8 | 1 |
| medgemma (2048) | 15 | **3/15** | 11 | 1 | 1.36 | 1 | 4 | 4 | 1 |
| qwen3.5 | 15 | **8/15** | 7 | 0 | 1.00 | 4 | 11 | 6 | 0 |

### Claude, `none` only (6 queries)

| model | n | invented | correct | empty | mean grounded | grounded = 0 | unsupported | embellished | format fails |
|---|---|---|---|---|---|---|---|---|---|
| llama3.2 | 6 | **2/6** | 4 | 0 | 1.50 | 0 | 2 | 1 | 0 |
| gemma3 | 6 | **2/6** | 4 | 0 | 1.17 | 2 | 5 | 0 | 0 |
| medgemma (2048) | 6 | **1/6** | 5 | 0 | 1.17 | 2 | 5 | 0 | 1 |
| qwen3.5 | 6 | **1/6** | 5 | 0 | 1.50 | 1 | 3 | 1 | 0 |

### Claude, blind queries only (18 queries; q16, r09 and c19 left out)

| model | n | invented | correct | empty | mean grounded | grounded = 0 | unsupported | embellished | format fails |
|---|---|---|---|---|---|---|---|---|---|
| llama3.2 | 18 | **6/18** | 12 | 0 | 1.39 | 3 | 6 | 3 | 4 |
| gemma3 | 18 | **8/18** | 10 | 0 | 0.94 | 5 | 15 | 8 | 1 |
| medgemma (2048) | 18 | **2/18** | 15 | 1 | 1.41 | 1 | 5 | 4 | 2 |
| qwen3.5 | 18 | **8/18** | 10 | 0 | 1.17 | 4 | 11 | 6 | 0 |

### Per-query grid (Claude): handling · grounded

| query | label | llama3.2 | gemma3 | medgemma (2048) | qwen3.5 |
|---|---|---|---|---|---|
| q06 | partial | **invented** · g0 | **invented** · g0 | correct · g1 | **invented** · g1 |
| q09 | none | correct · g2 | correct · g2 | correct · g2 | correct · g2 |
| q14 | partial | correct · g2 | correct · g2 | empty | correct · g2 |
| q16 † | partial | correct · g2 | **invented** · g0 | **invented** · g0 | **invented** · g0 |
| q17 | partial | **invented** · g0 | **invented** · g0 | correct · g1 | correct · g2 |
| q18 | partial | correct · g2 | correct · g1 | correct · g2 | **invented** · g0 |
| q19 | none | correct · g1 | **invented** · g0 | correct · g0 | correct · g2 |
| r04 | partial | correct · g2 | **invented** · g0 | correct · g2 | correct · g1 |
| r07 | partial | **invented** · g1 | **invented** · g1 | correct · g1 | **invented** · g1 |
| r08 | none | correct · g2 | correct · g2 | correct · g2 | correct · g2 |
| r09 † | none | correct · g2 | **invented** · g0 | **invented** · g0 | correct · g2 |
| r17 | partial | correct · g2 | **invented** · g1 | correct · g2 | **invented** · g1 |
| r18 | partial | correct · g2 | **invented** · g1 | **invented** · g1 | **invented** · g1 |
| r19 | none | **invented** · g1 | correct · g2 | correct · g1 | **invented** · g0 |
| r20 | partial | correct · g1 | correct · g1 | **invented** · g1 | correct · g1 |
| c10 | partial | **invented** · g0 | **invented** · g0 | correct · g1 | **invented** · g0 |
| c13 | partial | correct · g2 | correct · g1 | correct · g1 | **invented** · g0 |
| c17 | partial | correct · g2 | correct · g1 | correct · g2 | correct · g2 |
| c18 | partial | correct · g2 | correct · g1 | correct · g2 | correct · g2 |
| c19 † | partial | correct · g2 | correct · g2 | correct · g2 | correct · g1 |
| c20 | none | **invented** · g1 | correct · g1 | correct · g2 | correct · g1 |

## qwen2.5:7b judge on the same 84 responses

The judge's invalid records (`n/a` on a partial question) are left out of the handling, grounded, claim and format columns and counted under `invalid`. The `empty` column comes from the results, not the judge.

| model | n | invented | correct | empty | mean grounded | grounded = 0 | unsupported | embellished | format fails | invalid |
|---|---|---|---|---|---|---|---|---|---|---|
| llama3.2 | 21 | **1/21** | 19 | 0 | 1.40 | 1 | 3 | 13 | 1 | 1 |
| gemma3 | 21 | **10/21** | 11 | 0 | 1.05 | 1 | 3 | 25 | 5 | 0 |
| medgemma (2048) | 21 | **6/21** | 15 | 1 | 1.19 | 3 | 1 | 14 | 4 | 0 |
| qwen3.5 | 21 | **9/21** | 11 | 0 | 1.15 | 1 | 5 | 26 | 4 | 1 |

### Judge, `partial` only

| model | n | invented | correct | empty | mean grounded | grounded = 0 | unsupported | embellished | format fails | invalid |
|---|---|---|---|---|---|---|---|---|---|---|
| llama3.2 | 15 | **0/15** | 14 | 0 | 1.50 | 0 | 2 | 8 | 0 | 1 |
| gemma3 | 15 | **8/15** | 7 | 0 | 1.07 | 1 | 3 | 18 | 3 | 0 |
| medgemma (2048) | 15 | **5/15** | 10 | 1 | 1.07 | 2 | 0 | 11 | 3 | 0 |
| qwen3.5 | 15 | **7/15** | 7 | 0 | 1.00 | 1 | 1 | 22 | 2 | 1 |

### Judge, `none` only

| model | n | invented | correct | empty | mean grounded | grounded = 0 | unsupported | embellished | format fails | invalid |
|---|---|---|---|---|---|---|---|---|---|---|
| llama3.2 | 6 | **1/6** | 5 | 0 | 1.17 | 1 | 1 | 5 | 1 | 0 |
| gemma3 | 6 | **2/6** | 4 | 0 | 1.00 | 0 | 0 | 7 | 2 | 0 |
| medgemma (2048) | 6 | **1/6** | 5 | 0 | 1.50 | 1 | 1 | 3 | 1 | 0 |
| qwen3.5 | 6 | **2/6** | 4 | 0 | 1.50 | 0 | 4 | 4 | 2 | 0 |

### Per-query grid (judge): handling · grounded

| query | label | llama3.2 | gemma3 | medgemma (2048) | qwen3.5 |
|---|---|---|---|---|---|
| q06 | partial | correct · g1 | **invented** · g1 | **invented** · g1 | correct · g1 |
| q09 | none | correct · g2 | correct · g1 | correct · g2 | correct · g2 |
| q14 | partial | correct · g1 | correct · g1 | **invented** · g0 (empty answer) | correct · g1 |
| q16 † | partial | correct · g1 | **invented** · g1 | **invented** · g0 | **invented** · g0 |
| q17 | partial | correct · g1 | correct · g1 | correct · g1 | **invented** · g1 |
| q18 | partial | correct · g2 | correct · g2 | correct · g2 | **invented** · g1 |
| q19 | none | correct · g1 | **invented** · g1 | correct · g2 | correct · g1 |
| r04 | partial | correct · g2 | **invented** · g1 | correct · g1 | correct · g1 |
| r07 | partial | correct · g1 | **invented** · g1 | correct · g1 | ⚠ invalid (n/a) · g1 |
| r08 | none | correct · g2 | correct · g1 | correct · g2 | correct · g2 |
| r09 † | none | correct · g1 | correct · g1 | **invented** · g0 | correct · g2 |
| r17 | partial | correct · g2 | **invented** · g1 | correct · g1 | correct · g1 |
| r18 | partial | correct · g2 | **invented** · g1 | **invented** · g1 | **invented** · g1 |
| r19 | none | **invented** · g0 | correct · g1 | correct · g1 | **invented** · g1 |
| r20 | partial | correct · g1 | correct · g1 | **invented** · g1 | correct · g1 |
| c10 | partial | correct · g1 | **invented** · g0 | correct · g1 | correct · g1 |
| c13 | partial | correct · g2 | correct · g1 | correct · g2 | **invented** · g1 |
| c17 | partial | correct · g2 | correct · g1 | correct · g1 | correct · g2 |
| c18 | partial | correct · g2 | **invented** · g1 | correct · g1 | **invented** · g1 |
| c19 † | partial | ⚠ invalid (n/a) · g2 | correct · g2 | correct · g2 | **invented** · g1 |
| c20 | none | correct · g1 | **invented** · g1 | correct · g2 | **invented** · g1 |

## Agreement: Claude vs qwen2.5:7b

Compared only where both gave a value. That leaves out the 1 empty answer (no Claude grounded or handling) and the 2 invalid judge record(s).

| subset | handling agree | handling κ | grounded exact | grounded within 1 | grounded κ |
|---|---|---|---|---|---|
| all 84 | 64/81 (79%) | 0.52 | 49/81 (60%) | 80/81 (99%) | 0.38 |
| blind only (18 queries) | 55/70 (79%) | 0.50 | 42/70 (60%) | 69/70 (99%) | 0.34 |
| partial | 44/57 (77%) | 0.51 | 35/57 (61%) | 57/57 (100%) | 0.37 |
| none | 20/24 (83%) | 0.56 | 14/24 (58%) | 23/24 (96%) | 0.35 |
| llama3.2 | 15/20 (75%) | 0.22 | 13/20 (65%) | 20/20 (100%) | 0.41 |
| gemma3 | 17/21 (81%) | 0.62 | 10/21 (48%) | 21/21 (100%) | 0.12 |
| medgemma (2048) | 19/20 (95%) | 0.86 | 14/20 (70%) | 19/20 (95%) | 0.51 |
| qwen3.5 | 13/20 (65%) | 0.29 | 12/20 (60%) | 20/20 (100%) | 0.38 |

Handling confusion (rows = Claude, columns = judge):

| Claude \ judge | correct | invented |
|---|---|---|
| **correct** | 46 | 7 |
| **invented** | 10 | 18 |

Grounded confusion (rows = Claude, columns = judge):

| Claude \ judge | 0 | 1 | 2 |
|---|---|---|---|
| **0** | 4 | 13 | 1 |
| **1** | 1 | 26 | 2 |
| **2** | 0 | 15 | 19 |

Ranking by invented count (fewest first):
- Claude: medgemma (2048) 4 < llama3.2 6 < qwen3.5 9 < gemma3 10
- judge: llama3.2 1 < medgemma (2048) 6 < qwen3.5 9 < gemma3 10

## Latency, project_abstain (from the run files)

Median over all 60 project_abstain requests per model. Time to first visible token is the median over requests that produced visible text (n shown where fewer than 60). `latency_s.total` is wall time. Cold start is excluded (it's measured separately in `_runs.jsonl`).

| model | results | num_predict | median total (s) | median first visible token (s) | complete answers |
|---|---|---|---|---|---|
| llama3.2 | `results/` | 600 | 1.36 | 0.14 | 60/60 |
| gemma3 | `results/` | 600 | 2.28 | 0.50 | 60/60 |
| medgemma | `results/` | 600 | 12.14 | 8.26 (n=29) | 24/60 |
| medgemma | `results_medgemma_2048/` | 2048 | 13.55 | 12.09 (n=56) | 56/60 |
| qwen3.5 | `results/` | 600 | 2.35 | 0.66 | 60/60 |

### MedGemma completion rate by budget

A complete answer is non-empty and not truncated (`done_reason: stop`).

| variant | 600 tokens (`results/`) | 2048 tokens (`results_medgemma_2048/`) |
|---|---|---|
| project | 19/60 (32%) | 57/60 (95%) |
| project_abstain | 24/60 (40%) | 56/60 (93%) |
| minimal | 58/60 (97%) | 60/60 (100%) |
| **all** | **101/180 (56%)** | **173/180 (96%)** |

## mistral:7b second judge: state and why it failed

At 16:11 the mistral:7b judge was **still running** (launched 15:53:57, python PID 11444; it wasn't touched and won't be relaunched). It had scored 73 of its 240 project_abstain responses: llama3.2 60/60 and gemma3 13/60, with qwen3.5 and MedGemma still to come. It was at 100% GPU, ~13.7 s per response, and should finish around 16:50. **55 of the 73 records are valid.** All 18 invalid records have the same problem: `unanswerable_handling` = `n/a` on a partial/none question. Of the 23 partial/none responses it had judged, **18 were `n/a`**, so only 5 have a usable handling score. The rule that fixes `n/a` on `full` questions can't help here, because nothing tells us whether `correct` or `invented` was meant. Mistral mostly ignores the ANSWERABILITY line and treats `n/a` as the default. **For abstention, the question this report is about, mistral:7b gives almost no data** and can't act as a second judge in its current form. Its grounded and claim scores on `full` questions are unaffected. A usable second judge would need a per-item JSON schema that forbids `n/a` on partial/none, which would mean a new run.

