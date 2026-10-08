# 2026-09-29: calibration set reshuffled, judge forced onto the GPU, judge launched

Scope: only `backend/eval/` changed (`score.py`, `README.md`, `reports/`, and the new `scores/judge/`). Nothing staged or committed. `results/` and `results_medgemma_2048/` are untouched.

## 1. Calibration set regenerated

`reports/calibration_set.md` and `reports/calibration_key.json` were overwritten, using a fresh `random.SystemRandom` shuffle (seeded by the OS). Checks, done without printing the key:

- all 5 per-query orders differ from each other;
- **each query's order differs from its order in the previous key**;
- no model name or results path appears in the set file.

The content is otherwise the same as before: q04, q10, q16, r09, c19, project_abstain, MedGemma from `results_medgemma_2048/`. The key is only in `calibration_key.json`.

## 2. Judge option (b): works, 100% GPU

- `score.py judge` has a new flag, **`--num-gpu N`**, passed to Ollama as `options.num_gpu`. It is only added to the options when set, so judge fingerprints without the flag don't change. When set, it is part of `judge_options` and `judge_prompt_sha256`.
- Forced load: an empty `/api/generate` request (load only, `done_reason: load`) with `num_ctx` 4096 and `num_gpu` 99. GPU use was 0 MiB beforehand.

| | option (a), default fit (earlier today) | **option (b), `num_gpu` 99** |
|---|---|---|
| `ollama ps` | 5.1 GB, 16%/84% CPU/GPU | **4.7 GB, 100% GPU**, context 4096 |
| `/api/ps` size_vram / size | 84.4% | **100.0%** (4,748,056,984 B) |
| layers on GPU (server.log) | 26/29 | **29/29** |
| KV cache | 200 MiB GPU + 24 MiB CPU | 224 MiB, all on GPU |
| `nvidia-smi` | 4217 MiB | **4623 MiB** of 6144 (≈1.5 GiB left) |
| load time | 17.7 s | 3.3 s (the files were already cached) |

It was unloaded afterwards: `/api/ps` was empty and GPU use was 0 MiB. No fallback to (a) was needed. During the judge run, `ollama ps` again shows `100% GPU`, with 4635 MiB in `nvidia-smi`.

## 3. Judge: running, detached

Launched at **14:19:16** via WMI `Win32_Process.Create`. The launcher is cmd PID 13316, and a new python process starts for each file. It is one `cmd` `for` loop over 12 files, in this order:

- `results/`: llama3.2-latest, gemma3-4b, qwen3.5-4b × {project, project_abstain, minimal}
- `results_medgemma_2048/`: medgemma1.5-4b-it-q4_K_M × {project, project_abstain, minimal}

The 3 MedGemma files in `results/` are skipped. Each iteration runs:

```
python -u score.py --contexts contexts_all_wf.jsonl judge <file> --judge-model qwen2.5:7b --num-ctx 4096 --num-gpu 99
```

Output is appended to `scores/judge/run.log`. Scores go to `scores/judge/qwen2.5-7b/<file>`, with the MedGemma ones under `scores/judge/qwen2.5-7b/results_medgemma_2048/<file>`.

**Timing from the first completions:**
- The first response took 21 s after launch (process start plus model load).
- After that, the gaps between completions were 7, 6, 6, 6, 8, 7, 8 s. Over the first 11 responses the mean is **6.8 s per response**.
- For 720 responses that gives 720 × 6.8 s ≈ **82 min**, plus a few seconds of python start-up per file. The model stays loaded (`keep_alive` 30m).
- **Expected finish: about 15:40-15:50.**
- MedGemma's 2048-run answers and the minimal answers differ in length, so the per-file pace may vary.

### Progress (PowerShell, from `backend/eval/`)

```powershell
Get-Content scores\judge\run.log -Tail 5                    # current file and item; add -Wait to follow
Get-ChildItem scores\judge\qwen2.5-7b -Recurse -Filter *.jsonl | ForEach-Object { $r = Get-Content $_.FullName | ConvertFrom-Json; "{0,-60} {1,3}/60  invalid={2}" -f $_.FullName.Substring($_.FullName.IndexOf('qwen2.5-7b')+11), $r.Count, @($r | Where-Object { -not $_.valid }).Count }
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object CommandLine -like '*score.py*judge*' | Select-Object ProcessId, CommandLine   # still running?
```

### Resume

Re-run the same detached launch. For each file, the judge skips ids that already have a **valid** score for the same answer sha, prompt, options and score version, and appends the rest.

```powershell
$py=(Get-Command python).Source; $dir=(Resolve-Path .).Path
$files = @('llama3.2-latest','gemma3-4b','qwen3.5-4b') | ForEach-Object { $m=$_; 'project','project_abstain','minimal' | ForEach-Object { "results\${m}_$_.jsonl" } }
$files += 'project','project_abstain','minimal' | ForEach-Object { "results_medgemma_2048\medgemma1.5-4b-it-q4_K_M_$_.jsonl" }
$loop = "for %f in ($($files -join ' ')) do `"$py`" -u score.py --contexts contexts_all_wf.jsonl judge %f --judge-model qwen2.5:7b --num-ctx 4096 --num-gpu 99"
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CurrentDirectory=$dir; CommandLine="cmd.exe /s /c `"cd /d `"$dir`" && set `"PYTHONUTF8=1`" && set `"PYTHONUNBUFFERED=1`" && ($loop) >> scores\judge\run.log 2>&1`"" }
```

**Note:** because the judge is deterministic, a resume re-asks every *invalid* item and will most likely get the same invalid answer back, spending ~7 s each. See the next section.

## 4. ⚠ The judge often marks `full` questions as `correct`/`invented` instead of `n/a`

Of the first 11 llama3.2 project scores, **5 of 9 `full` questions are INVALID**. Every time, the judge set `unanswerable_handling` to `correct` or `invented`, although the rubric says `n/a` for `full`. The 2 partial/none items were valid. At 19/60 it was 6 invalid, all with this same problem. Everything else in the invalid records is still stored (`grounded`, `claims`, `rationale`, `raw_output`), but `summary` excludes invalid records. **At this rate, a third to a half of the `full` rows (39 of 60 queries per file) would be missing from the judge tables.**

The run continues because the other fields are still collected, and none of the options below requires re-judging the valid items. Options (your decision; nothing is changed yet):

- **(i) Normalise instead of rejecting.** For `full` questions, the rubric fixes `unanswerable_handling` to `n/a` whatever the judge says, as manual mode already does automatically. So `summary` could store or treat it as `n/a`, keeping the judge's raw value for audit, and accept these records. No re-judging is needed, and nothing is lost, because the judge's value carries no information for `full`. This is my recommendation.
- **(ii) Constrain the schema per item.** Send a JSON schema whose `unanswerable_handling` enum is `["n/a"]` for `full` and `["correct","invented"]` otherwise. This is cleaner going forward, but it changes `judge_prompt_sha256` for every `full` item, so all `full` items would be re-judged (~40 min).
- **(iii) Leave it.** Report the judge only on valid records. Not recommended, because it leaves out mostly `full` rows, and not at random.

**Early quality signal:** 10 of the first 11 grounded scores are `1`, and most rationales start "mostly supported by the context, but it adds unsupported…". That could be a judge that doesn't discriminate between answers. Your manual scores on `calibration_set.md` are the check for this, so it's worth doing that before relying on the judge tables.
