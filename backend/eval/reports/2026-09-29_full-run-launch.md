# 2026-09-29: full run launched (steps 7-8 of pre-run setup)

Scope: only `backend/eval/` changed (new `results/` and this report). Nothing staged or committed. This continues `2026-09-28_pre-run-setup.md`, which stopped at the GPU check.

## 1. GPU check: clear

| measurement | value |
|---|---|
| GPU | NVIDIA GeForce RTX 3050 6GB Laptop GPU, driver 616.92 |
| memory used | **0 MiB** of 6144 MiB |
| processes on the GPU (`nvidia-smi`) | none |
| Ollama models loaded (`/api/ps`) | none |

That is under the 1 GB limit. The VALORANT process from yesterday is gone.

## 2. Dry run

`python run_models.py --queries eval_queries.jsonl --contexts contexts_all_wf.jsonl --results-dir results --dry-run`

- Options: `temperature 0, num_predict 600, seed 0, num_ctx 4096`, `project_layout=system_user`, think off.
- **Without `--models` the dry run uses the 6-model default list**: llama3.2:latest, gemma3:4b, qwen3.5:4b, medgemma1.5:4b-it-q4_K_M, medgemma1.5:4b-it-q8_0, gemma4:e4b. That is 18 files × 60 = 1080 generations. The last two models are not installed and would be skipped at run time.
- The real run passes `--models` explicitly. I checked it with a second dry run using that list: **4 models × 3 variants (project, project_abstain, minimal) × 60 queries = 720 generations**, 12 results files, all 0 done / 60 to run / 0 stale, in the requested order.
- Installed (`ollama list`): llama3.2:latest `a80c4f17acd5`, gemma3:4b `a2af6cc3eb7f`, medgemma1.5:4b-it-q4_K_M `433252621ab1`, qwen3.5:4b `2a654d98e6fb`.

**Discrepancy to note:** the README ("Request settings") says `num_predict 300`, but `run_models.py` has `NUM_PREDICT = 600`, and its docstring agrees with 600. The run uses 600. The README was not changed; it should be updated to 600.

## 3. Detached run

Started 2026-09-29 09:10 via `Win32_Process.Create` (WMI). That process is not a child of the terminal and is outside its job object, so it survives the terminal closing. The launcher cmd.exe is PID 18820 and python is **PID 4532**. `PYTHONUTF8=1` and `PYTHONUNBUFFERED=1` are set, and stdout and stderr are **appended** to `results/run.log`.

Command (run from `backend/eval/`):

```
python -u run_models.py --queries eval_queries.jsonl --contexts contexts_all_wf.jsonl --results-dir results --models llama3.2:latest gemma3:4b medgemma1.5:4b-it-q4_K_M qwen3.5:4b --variants project project_abstain minimal
```

Checked about 30 s after launch: llama3.2:latest loaded in 6.7 s, fully on GPU (`/api/ps` 2436 MiB, all in VRAM; `nvidia-smi` 2537 MiB system-wide). The first 16 project requests were all `ok` at about 1.2-2.2 s each. I didn't wait any longer.

### Check progress (PowerShell, from `backend/eval/`)

```powershell
Get-Content results\run.log -Tail 20                  # last lines; add -Wait to follow live
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object CommandLine -like '*run_models.py*' | Select-Object ProcessId, CreationDate   # still running?
Get-ChildItem results\*.jsonl -Exclude _runs.jsonl | ForEach-Object { "{0,-50} {1}" -f $_.Name, (Get-Content $_).Count }   # records per file (60 = done; errored retries can add lines)
```

### Resume if interrupted

Re-run the same command. It skips ids that already have an `ok` record, retries errored ids and discards a torn last line. Detached, same as the launch:

```powershell
$py=(Get-Command python).Source; $dir=(Resolve-Path .).Path
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CurrentDirectory=$dir; CommandLine="cmd.exe /s /c `"cd /d `"$dir`" && set `"PYTHONUTF8=1`" && set `"PYTHONUNBUFFERED=1`" && `"$py`" -u run_models.py --queries eval_queries.jsonl --contexts contexts_all_wf.jsonl --results-dir results --models llama3.2:latest gemma3:4b medgemma1.5:4b-it-q4_K_M qwen3.5:4b --variants project project_abstain minimal >> results\run.log 2>&1`"" }
```

Or in the foreground, with the plain command above. Before resuming, check that nothing else is using the GPU (`nvidia-smi`), because a partly-filled GPU distorts the latency and VRAM figures of the requests that follow.

To stop it: `Stop-Process -Id 4532`. Finished records are already fsynced, so resume picks up from there.
