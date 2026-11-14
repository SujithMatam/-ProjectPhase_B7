# 2026-09-29: judge GPU check failed, blind calibration set exported, judge not launched

Scope: only `backend/eval/reports/` changed: this report, `calibration_set.md` and `calibration_key.json`. Nothing staged or committed. `results/` and `results_medgemma_2048/` are untouched. `scores/` doesn't exist yet.

## 1. MedGemma 2048 run: finished

Checked at 14:13: 3 files × 60/60 `ok`, 0 errors, no python process left, nothing loaded in Ollama, 0 MiB of GPU in use.

| variant | with trace | empty (trace still hit 2048) | cut off mid-answer | complete | latency mean / median (s) | raw / visible tokens (mean) | peak VRAM |
|---|---|---|---|---|---|---|---|
| project | 60 | 3: q18, r10, c13 | 0 | **57/60** (was 19/60 at 600) | 15.7 / 14.5 | 782 / 52.2 | 3733 MiB |
| project_abstain | 54 | 4: q14, r10, c12, c15 | 0 | **56/60** (was 24/60) | 14.7 / 13.5 | 725 / 55.0 | 3733 MiB |
| minimal | 5 | 0 | 0 | **60/60** (was 58/60) | 2.2 / 1.5 | 95 / 64.1 | 3733 MiB |

In the 7 requests that still produced nothing, MedGemma reasoned for the full 2048 tokens (~41 s each). r10 fails under both project variants. r10, c12 and q18 are all known retrieval misses (README "Test-set notes"), so MedGemma reasons longest when the context doesn't contain the answer. No record has `context_may_be_truncated` set.

## 2. Judge GPU check: FAILED, qwen2.5:7b is 84% GPU / 16% CPU

I loaded it once with an empty `/api/generate` request (`options.num_ctx` 4096). That only loads the model (`done_reason: load`) and generates nothing. Afterwards it was unloaded with `keep_alive: 0`, and `/api/ps` was empty and GPU use back to 0 MiB.

| | value |
|---|---|
| `ollama ps` | `qwen2.5:7b  845dbda0ea48  5.1 GB  16%/84% CPU/GPU  4096` |
| `/api/ps` | size 5,123,835,164 B, size_vram 4,325,281,627 B (84.4%), context 4096 |
| layers | **26/29 on GPU** (25 repeating layers plus the output layer). KV cache: 200 MiB on the GPU, 24 MiB on the CPU. |
| `nvidia-smi` while loaded | 4217 MiB of 6144 MiB |
| load time | 17.7 s |

**Why, from Ollama's `server.log`:** CUDA reported **5161 MiB free**. A test allocation with all 29 layers needed **4528 MiB**, so the model *physically fits*, leaving ~630 MiB. But Ollama's parameter fitter (`common_params_fit_impl`) keeps about **1 GiB free** as a safety margin. So it dropped to 26 layers (4124 MiB used, 1036 MiB free).

**My estimate last turn was wrong.** I checked the model's size against total VRAM but didn't allow for that 1 GiB margin. The same margin rules out every 7-8B judge on this GPU at default settings: anything needing more than about 4.1 GiB gets split. mistral:7b (~4.7-4.8 GiB) would also spill. Under the default margin, only models of about ≤ 4 B (e.g. phi4-mini) would load fully, and those are no stronger than the models being judged.

### Decision needed (step 4 not launched)

Step 4 depended on this check, so I didn't start the judge. Options:

- **(a) Run as is, at 84/16.** The judge's latency isn't one of the measurements, and at temperature 0 with a fixed seed and the same placement every time, its output is still deterministic. The only cost is speed: 3 of 29 layers run on the CPU, which I'd guess slows decoding by roughly 1.5-2×. That isn't measured.
- **(b) Force all layers onto the GPU.** Ollama's `num_gpu` request option (e.g. `99`) sets how many layers to offload and overrides the fitter's choice. `score.py judge` doesn't pass it yet; that would be a small change adding a `--num-gpu` flag and including it in `judge_options`. It needs one more verification load. Expected use is ~4.6 GiB in `nvidia-smi`, with ~0.5 GiB left. The risk is that another GPU user (a game, the browser) could cause an out-of-memory error during the long judge run.
- **(c) Change the judge.** A model that fits under the margin would be ≤ 4 B and a weaker grader. Not recommended.

**Recommendation: (b)**, with (a) as the fallback if the forced load fails or looks tight. It meets your 100%-GPU requirement without changing the judge.

### Judge command once decided (not run)

`score.py judge` takes one results file per call, so the detached launch runs a loop over the 12 files. The 3 MedGemma files in `results/` are skipped:

```
results\llama3.2-latest_{project,project_abstain,minimal}.jsonl
results\gemma3-4b_{project,project_abstain,minimal}.jsonl
results\qwen3.5-4b_{project,project_abstain,minimal}.jsonl
results_medgemma_2048\medgemma1.5-4b-it-q4_K_M_{project,project_abstain,minimal}.jsonl
```

Each call: `python -u score.py --contexts contexts_all_wf.jsonl judge <file> --judge-model qwen2.5:7b --num-ctx 4096`, appending to `scores/judge/run.log`. Scores go to `scores/judge/qwen2.5-7b/<file>` and `scores/judge/qwen2.5-7b/results_medgemma_2048/<file>`. The judge already resumes: it skips ids with a valid score for the same answer sha, prompt and options. So resuming means re-running the same loop.

`--contexts` is a top-level option and has to come **before** the `judge` subcommand.

## 3. Blind calibration set: exported

- `reports/calibration_set.md` covers q04, q10, q16, r09 and c19 under **project_abstain**. For each query it gives:
  - the query, procedure, postop_day, domain, answerability, and the reference answer with its passages;
  - every frozen context chunk from `contexts_all_wf.jsonl` in full, with chunk id, days, in/out of window and distance;
  - the four visible answers, labelled **A-D**.
- The answers are shown the way `score.py` shows them to the judge (`visible_answer`, verbatim).
- MedGemma comes from `results_medgemma_2048/`, the other three from `results/`. All 20 answers ended with `done_reason: stop` and none are empty, so no truncation notes were needed (such a note would have given MedGemma away).
- The letter order was shuffled with `random.SystemRandom`, separately for each query. I checked that all 5 orders differ from each other, and that no model name or results path appears in the set file.
- The key (letter → model per query, plus source files) is **only** in `reports/calibration_key.json`. It isn't in this report or in the chat.
- **Limits of the blinding:** the answers are verbatim, so style can give models away. One model consistently uses curly apostrophes and dashes (’ –), and some open with "Okay,". I kept the text exactly as the models wrote it rather than normalising typography, so the calibration scores the text the judge will see. Keep this in mind when reading agreement numbers.

## 4. What wasn't done

- Judge not launched (see section 2). No duration estimate, because there are no judge completions to time.
- No code changed this turn.
