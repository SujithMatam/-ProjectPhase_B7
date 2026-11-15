# 2026-09-29: calibration agreement, Claude (blind) vs the qwen2.5:7b judge

Scope: wrote `scores/claude/calibration.jsonl` (20 rows) and this report. Nothing staged or committed. The running mistral:7b judge was not touched.

## Inputs

- **Claude's scores:** 20 rows (5 queries × A-D) against `reports/calibration_set.md` as generated at 2026-09-29T08:56:04Z, the current file. Its key (`calibration_key.json`, base64) was decoded only after the scores were recorded.
- **Fields not given are stored as `null`, not 0:** `embellished` on q04 (all four) and on q10 B; `unsupported`/`embellished` on every q16, r09 and c19 row except c19 C. q04 and q10 are `full`, so their `unanswerable_handling` is stored as `n/a`, as the rubric requires (it wasn't given).
- **Judge scores:** `scores/judge/qwen2.5-7b/`, with the `full` handling rule applied. For every one of the 20 responses, the judge's `response_sha256` matches the calibration response exactly. mistral:7b is still running, so its column is filled only where it had already scored that response and is otherwise `-`.

## Per response

| query | ans. | letter | model | Claude g | qwen g | Δ | Claude handling | qwen handling (raw) | Claude un/em | qwen un/em | mistral g / handling |
|---|---|---|---|---|---|---|---|---|---|---|---|
| q04 | full | A | qwen3.5 | 2 | 1 | -1 | n/a | n/a | 0/- | 0/1 | - |
| q04 | full | B | gemma3 | 1 | 1 | +0 | n/a | n/a (invented) | 1/- | 0/1 | - |
| q04 | full | C | llama3.2 | 2 | 2 | +0 | n/a | n/a | 0/- | 0/0 | 2 / n/a |
| q04 | full | D | medgemma (2048) | 2 | 1 | -1 | n/a | n/a | 0/- | 0/0 | - |
| q10 | full | A | llama3.2 | 1 | 1 | +0 | n/a | n/a (correct) | 0/1 | 0/1 | 1 / n/a |
| q10 | full | B | gemma3 | 1 | 1 | +0 | n/a | n/a (correct) | 1/- | 0/1 | - |
| q10 | full | C | qwen3.5 | 2 | 1 | -1 | n/a | n/a | 0/1 | 0/2 | - |
| q10 | full | D | medgemma (2048) | 1 | 2 | +1 | n/a | n/a | 0/1 | 0/0 | - |
| q16 | partial | A | llama3.2 | 2 | 1 | -1 | correct | correct | -/- | 1/0 | 2 / correct |
| q16 | partial | B | gemma3 | 0 | 1 | +1 | invented | invented | -/- | 0/1 | - |
| q16 | partial | C | medgemma (2048) | 0 | 0 | +0 | invented | invented | -/- | 0/2 | - |
| q16 | partial | D | qwen3.5 | 0 | 0 | +0 | invented | invented | -/- | 1/2 | - |
| r09 | none | A | gemma3 | 0 | 1 | +1 | invented | correct | -/- | 0/1 | - |
| r09 | none | B | medgemma (2048) | 0 | 0 | +0 | invented | invented | -/- | 1/2 | - |
| r09 | none | C | llama3.2 | 2 | 1 | -1 | correct | correct | -/- | 0/1 | 0 / n/a ⚠invalid |
| r09 | none | D | qwen3.5 | 2 | 2 | +0 | correct | correct | -/- | 1/0 | - |
| c19 | partial | A | gemma3 | 2 | 2 | +0 | correct | correct | -/- | 0/0 | - |
| c19 | partial | B | llama3.2 | 2 | 2 ⚠invalid | +0 | correct | n/a | -/- | 0/0 | - |
| c19 | partial | C | qwen3.5 | 1 | 1 | +0 | correct | invented | 1/1 | 0/2 | - |
| c19 | partial | D | medgemma (2048) | 2 | 2 | +0 | correct | correct | -/- | 0/0 | - |

## Agreement (Claude vs qwen2.5:7b)

| measure | result |
|---|---|
| grounded, exact | **12/20 (60%)** |
| grounded, within 1 | **20/20 (100%)** |
| grounded, Cohen's κ (unweighted) | 0.41 (chance agreement 0.33; n=20, so treat as indicative) |
| handling, partial/none responses | **9/12 (75%)** |
| handling, full responses | 8/8 after normalisation (trivially `n/a`). Before it, the judge answered `correct`/`invented` on 3/8 |

Grounded confusion matrix (rows = Claude, columns = qwen2.5:7b):

| Claude \ qwen | 0 | 1 | 2 |
|---|---|---|---|
| **0** | 3 | 2 | 0 |
| **1** | 0 | 4 | 1 |
| **2** | 0 | 5 | 5 |

Handling on the 12 partial/none responses (rows = Claude, columns = qwen2.5:7b):

| Claude \ qwen | correct | invented |
|---|---|---|
| **correct** | 5 | 1 |
| **invented** | 1 | 4 |

The matrix leaves out c19 B (judge `n/a`, record invalid). That response counts as a handling disagreement in the 9/12 above, and its grounded score is still compared.

Per query: q04 (full): grounded exact 2/4; q10 (full): grounded exact 2/4; q16 (partial): grounded exact 2/4, handling 4/4; r09 (none): grounded exact 2/4, handling 3/4; c19 (partial): grounded exact 4/4, handling 2/4.

Grounded scores given by each rater across these 20: Claude 0/1/2 = 5/5/10, qwen2.5:7b 0/1/2 = 3/11/6.

mistral:7b so far (3 valid of the 20): grounded exact with Claude 3/3, within 1 3/3. Too few for a comparison; this will be revisited when it finishes.

## Reading

- **Grounded:** the judge never disagrees by more than 1 point, but it pulls scores towards 1. Claude gave 10 twos and 5 zeros; the judge gave 6 twos and 3 zeros. All 8 grounded disagreements are ±1. Five of them are Claude 2 → judge 1, which matches the judge's overall habit (61.7% of all its grounded scores are 1).
- **Handling on partial/none:** the judge agrees on 9 of 12. Its misses are r09 A (Claude `invented`, judge `correct`), c19 C (Claude `correct`, judge `invented`), and c19 B (judge `n/a`, invalid).
- **Ranking:** Claude's per-model means order the models llama3.2 1.8 > qwen3.5 1.4 > medgemma 1.0 > gemma3 0.8. The judge's means on the same 20 order them llama3.2 1.4 > gemma3 1.2 > medgemma 1.0 = qwen3.5 1.0. They agree only on the top model, and five queries per model is far too few for a ranking in any case.
- **Size:** 20 responses from 5 queries. κ ≈ 0.4 is 'moderate' agreement, not enough to trust the judge's small differences between models (grounded means of 1.17-1.32). The abstention set (21 queries) would add a larger sample.

## Claude's scores per model (key opened)

| model | grounded per query (q04, q10, q16, r09, c19) | mean grounded | handling on q16 / r09 / c19 | unsupported (where given) | embellished (where given) | qwen2.5 mean grounded on the same 5 |
|---|---|---|---|---|---|---|
| llama3.2 | 2, 1, 2, 2, 2 | 1.8 | correct / correct / correct | 0 (over 2) | 1 (over 1) | 1.4 |
| gemma3 | 1, 1, 0, 0, 2 | 0.8 | invented / invented / correct | 2 (over 2) | 0 (over 0) | 1.2 |
| medgemma (2048) | 2, 1, 0, 0, 2 | 1.0 | invented / invented / correct | 0 (over 2) | 1 (over 1) | 1.0 |
| qwen3.5 | 2, 2, 0, 2, 1 | 1.4 | invented / correct / correct | 1 (over 3) | 2 (over 2) | 1.0 |

Letters per query (key, decoded):

| query | A | B | C | D |
|---|---|---|---|---|
| q04 | qwen3.5 | gemma3 | llama3.2 | medgemma (2048) |
| q10 | llama3.2 | gemma3 | qwen3.5 | medgemma (2048) |
| q16 | llama3.2 | gemma3 | medgemma (2048) | qwen3.5 |
| r09 | gemma3 | medgemma (2048) | llama3.2 | qwen3.5 |
| c19 | gemma3 | llama3.2 | qwen3.5 | medgemma (2048) |

