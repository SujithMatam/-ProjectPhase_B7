# 2026-09-29: MedGemma re-run at 2048 tokens, judge choice, and a two-directory summary

Scope: only `backend/eval/` changed. `results/` is untouched and remains the 600-token evidence. Nothing staged or committed. The judge was **not** run, and nothing generated on the GPU apart from the MedGemma run.

Files changed: `run_models.py` (new `--num-predict` flag), `score.py` (score layout and summary), `README.md`, and this report. New: `results_medgemma_2048/`.

## 1. MedGemma re-run at num_predict 2048 (running, detached)

`run_models.py` had `NUM_PREDICT = 600` hard-coded, so I added **`--num-predict N`** (default 600). There are two code changes: `options["num_predict"]` now takes the flag's value, and the `context_may_be_truncated` check uses the run's budget instead of the constant. The default leaves the options fingerprint unchanged. A dry run against `results/` still shows all 12 files as 60 done / 0 stale.

- **Context fit:** MedGemma's longest prompt in `results/` is 930 tokens (`prompt_eval_count`). 930 + 2048 = 2978, which is within `num_ctx` 4096, so `num_ctx` is unchanged.
- **Launch:** 2026-09-29 13:33:56, via WMI (`Win32_Process.Create`) like the first run. The python process is **PID 2684**. `PYTHONUTF8=1` and `PYTHONUNBUFFERED=1` are set, and output is appended to `results_medgemma_2048/run.log`. GPU use was 0 MiB before launch.

  ```
  python -u run_models.py --queries eval_queries.jsonl --contexts contexts_all_wf.jsonl --results-dir results_medgemma_2048 --models medgemma1.5:4b-it-q4_K_M --variants project project_abstain minimal --num-predict 2048
  ```
- **Progress at 13:39:** 22/180 done, all `ok`. Project requests take about 11-26 s (575-1308 raw tokens, of which 38-64 are visible). One of the first 19 project answers **still hit 2048** with no visible answer, so the larger budget doesn't fix every case.
- **Estimate:** about 16 s per request for project and project_abstain, and about 2-3 s for minimal. The run should finish around **14:05-14:15**.

Check progress (from `backend/eval/`):

```powershell
Get-Content results_medgemma_2048\run.log -Tail 20      # add -Wait to follow
Get-ChildItem results_medgemma_2048\*.jsonl -Exclude _runs.jsonl | ForEach-Object { "{0,-50} {1}" -f $_.Name, (Get-Content $_).Count }
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object CommandLine -like '*results_medgemma_2048*' | Select-Object ProcessId   # still running?
```

Resume: re-run the command above; it's the same detached `Invoke-CimMethod` pattern as in `2026-09-29_full-run-launch.md`, with this command line.

## 2. Judge: llama3.1:8b doesn't fit fully, so qwen2.5:7b is recommended and pulled

Sizes are the GGUF model layer from the Ollama registry manifests (metadata only). The KV cache is f16 at `num_ctx` 4096: layers × KV heads × head dim × 2 (K, V) × 2 bytes × 4096. A model can't be test-loaded while MedGemma is running, so these are **estimates**.

| model (Q4_K_M) | weights | KV @ 4096 | estimated total (with graph and CUDA context) | fully on a 6 GB laptop GPU? |
|---|---|---|---|---|
| llama3.1:8b (`667b0c1932bc`, same as `-instruct-q4_K_M`) | 4.58 GiB | 512 MiB (32 layers × 8 KV heads) | ~5.5-5.8 GiB | **No, not reliably.** Ollama's placement estimate counts the full compute graph (128k vocabulary, so ~0.25-0.3 GiB of logits alone), and the usable VRAM under WDDM is ~5.3-5.6 GiB. Expect a few layers on CPU. |
| **qwen2.5:7b** (`2bada8a74506`) | 4.36 GiB | 224 MiB (28 layers × 4 KV heads) | ~4.9-5.1 GiB | **Yes**, with ~0.5 GiB of headroom |
| mistral:7b (v0.3) | 4.07 GiB | 512 MiB | ~4.8 GiB | Yes |
| qwen3:8b / granite3.3:8b | 4.87 / 4.60 GiB | 576 / 640 MiB | ≥ 5.7 GiB | No |
| olmo-3:7b | 4.16 GiB | up to ~2 GiB if, like OLMo 2 7B, it has no GQA (not verified) | likely > 6 GiB | Probably not; not checked further |
| phi4-mini (3.8B) | 2.32 GiB | 384 MiB | ~3.1 GiB | Yes, but it's smaller than the models it would judge |

For calibration, llama3.2:3b in this run used 2436 MiB according to `/api/ps` and 2531 MiB in `nvidia-smi` (+~95 MiB). llama3.1:8b is the same architecture, so the same method gives roughly 5.4-5.6 GiB actual use. Ollama's placement estimate is higher than actual use, and the estimate is what decides the GPU/CPU split.

The judge's own load is small. The longest judge prompt over all 720 results is 8,687 characters (MedGemma minimal q07), about 1,800 tokens at the 4.86 characters/token measured in this run. Adding `num_predict` 512 comes to about 2,300 tokens, so **`--num-ctx 4096` is enough**. score.py's judge default is 8192, so pass `--num-ctx 4096` explicitly, as the fit above assumes.

**Why qwen2.5:7b:**
- It is the strongest model in this list that fits entirely on the GPU. It follows instructions and produces structured output well, which matters for the claim-by-claim labels.
- It isn't one of the four candidates. It shares a family with qwen3.5:4b, but llama3.1:8b would share one with llama3.2:3b just as much, and more directly, because Llama 3.2 3B was distilled from Llama 3.1 8B. No judge that fits is free of family overlap and still as strong. mistral:7b is the neutral option, but it is noticeably weaker at following rubrics.
- **To manage the bias:** read qwen3.5:4b's judge scores with a self-preference caveat, and compare a manual sample of qwen3.5 rows against the judge. If you want a second opinion, mistral:7b could judge the qwen3.5 files only (not pulled).

**Pulled:** `ollama pull qwen2.5:7b` finished at about 13:44. `ollama list` shows ID `845dbda0ea48`, 4.7 GB, and `ollama show` reports qwen2 architecture, 7.6B parameters, Q4_K_M, with capabilities completion and tools (no thinking). The pull was the only thing done with it: afterwards `/api/ps` listed only MedGemma, so the judge was never loaded and generated nothing. Checking the real fit needs one load after the MedGemma run finishes, then `ollama ps` should show `100% GPU`.

## 3. score.py summary reads several results dirs

- `summary --results-dir` now takes one or more dirs (default `results/`):
  `python score.py summary --results-dir results results_medgemma_2048`.
- The performance table has a **`num_predict`** column for every row, taken from each record's `options`. A mixed file would show e.g. `600/2048`. When more than one dir is given, a **`results dir`** column is added too. Cold starts are read from each dir's own `_runs.jsonl`.
- **Score storage (a necessary fix):** scores were keyed only by the results *file name*, and the MedGemma files have the same names in both dirs. Their scores would have gone into the same score file and overwritten each other. Now scores for `results/` keep the flat layout, and any other dir goes one level deeper: `scores/{manual,judge/<judge>}/results_medgemma_2048/<file>`. Score records also carry `results_dir` and `num_predict`. Score tables group by (results dir, model, variant, num_predict). Score files for dirs not passed to `summary` are counted in the "excluded" line, not silently dropped. No scores existed yet, so nothing needed migrating.
- **Tests:**
  - `summary` on `results/` alone gives the same table as before, with the new `num_predict` column.
  - On both dirs, the 600 and 2048 MedGemma rows appear side by side.
  - Synthetic manual scores, written only to a scratch `--scores-dir` and then deleted, landed in separate files and separate rows for the two dirs, and matched their responses by sha.
  - Nothing was written to `scores/`.

For judging the 60-query set, `manual` and `judge` still need `--contexts contexts_all_wf.jsonl`, because the default is `eval_contexts.jsonl`. This is now in the README.

## 4. README

- "Request settings": `num_predict 300` is corrected to **600**. It now describes the `--num-predict` flag, the separate-dir rule, and the MedGemma 2048 re-run.
- "Score": documents the multi-dir `summary`, the `num_predict` and `results dir` columns, the nested score layout, and the `--contexts` reminder.
