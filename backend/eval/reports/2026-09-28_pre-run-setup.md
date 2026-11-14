# 2026-09-28: pre-run setup — stopped at the GPU check (step 6)

Scope: only `backend/eval/` changed. Nothing staged or committed. **No dry run and no model run were started**, because step 6's condition (more than 1 GB of GPU memory used by other processes) was met.

## Done (steps 1-6)

1. **Corpus:** EV-TKA-REHAB-02 now has `days` "1-42" and `postop_window` "weeks 1-6" (was 8-42 / weeks 2-6). The diff is 2 lines; the schema check passes. Corpus sha256 is now `d5051b7b68e86438`. `corpus_review.md` was regenerated.
2. **Labels:** r07, r20, c18 and c19 are now `partial`; r02 stays `full`. The label counts across all 60 queries are full 39, partial 15, none 6.
3. **References:** all 40 drafts and their `reference_passages` are written into `eval_queries.jsonl` as drafted, except r02, which was re-drafted from EV-TKA-REHAB-02 (3 sentences):
   > Getting the knee fully straight is especially important for walking well, and as a general guide the Hospital for Special Surgery guideline looks for the knee to straighten to within 10 degrees of fully straight, with about 80 degrees of bending, before moving on from the first-week phase. Progression is based on reaching these criteria and is adjusted for each patient, and your surgeon may set different targets, so treat the numbers as a guide rather than a deadline. To help the knee straighten, do not rest with a pillow under it; practise lying with the heel propped on a small rolled towel, and mention it to your physiotherapist early if your range of motion stops improving.

   `reference_passages`: `EV-TKA-REHAB-02`. All 60 rows pass the checks: `load_queries` accepts them, every reference passage is in-window, and every number traces to a cited passage.
4. **Contexts:** `contexts_all_wf.jsonl` (60 queries), `pilot/contexts_evalcorpus.jsonl` and `pilot/contexts_evalcorpus_wf.jsonl` were rebuilt; `backend/rag/data` was unchanged each time. `contexts_pain_wf.jsonl` was deleted. Corpus hash per file:

   | file | corpus | sha256 |
   |---|---|---|
   | `contexts_all_wf.jsonl` | eval corpus | `d5051b7b68e86438` |
   | `pilot/contexts_evalcorpus.jsonl` | eval corpus | `d5051b7b68e86438` |
   | `pilot/contexts_evalcorpus_wf.jsonl` | eval corpus | `d5051b7b68e86438` |
   | `pilot/contexts.jsonl` | app store (`seed_knowledge.json`) | `35996f41a8bce0a2` |

   Every eval-corpus context file has the same hash. `pilot/contexts.jsonl` is the old app-store baseline behind the v1 pilot results; it is built from a different corpus by design, so it can't share the hash.

   **Coverage changes:**

   | id | before | after |
   |---|---|---|
   | r02 | EV-TKA-REHAB-01-c1, ✗EV-TKA-REC-05-c1, ✗EV-TKA-PAIN-04-c0, ✗EV-TKA-REHAB-02-c0; 3 wrong-window; the target was only in a wrong-window chunk | EV-TKA-REHAB-02-c0, EV-TKA-REHAB-02-c1, EV-TKA-REHAB-01-c1, ✗EV-TKA-REC-05-c1; 1 wrong-window; **full**, with the target now in-window |
   | r03 | EV-TKA-REHAB-02-c1, -c0, EV-TKA-REHAB-04-c2, EV-TKA-REHAB-05-c1; 0 wrong-window; full | same chunks and distances, still 0 wrong-window; **unchanged** |

   (Outside the requested scope, and only to flag it: the new window also changed q02 and r01, which are at days 5 and 3. Each swapped a wrong-window chunk for an EV-TKA-REHAB-02 chunk; both keep their answering chunks. No other query changed.)
5. **README "Test-set notes":** added the known misses (r10, c07, c10, c12), the fragile retrievals (c02, c11, c18, c20, r12), thin coverage after day 84, and c12 as evidence that the 0.75 threshold (backend/rag `SEMANTIC_MAX_DISTANCE`) is too tight for patient phrasing. The section intro now covers all 60 queries and `contexts_all_wf.jsonl`.
6. **Models:** `gemma3:4b` is already installed (digest `a2af6cc3eb7f`), so nothing was pulled. All four run models are present: llama3.2:latest, gemma3:4b, medgemma1.5:4b-it-q4_K_M, qwen3.5:4b.

## Stopped: GPU memory in use by other processes

| measurement | value |
|---|---|
| GPU | NVIDIA GeForce RTX 3050 6GB Laptop GPU |
| memory used | **2013 MiB** of 6144 MiB |
| Ollama models loaded (`/api/ps`) | none |
| processes on the GPU (`nvidia-smi`) | **PID 3808 `VALORANT-Win64-Shipping.exe`** (E:\Riot Games\VALORANT\…, type C+G) |

With nothing loaded in Ollama, the whole ~2 GB belongs to other processes. VALORANT is the only process `nvidia-smi` lists. Windows (WDDM) doesn't report per-process GPU memory, so the split between VALORANT and the desktop can't be measured. For comparison, the pilot run logged `gpu_used_before_load_mib: 0`. That leaves about 4.1 GB for the models, which are 2.0-3.4 GB plus KV cache at num_ctx 4096. Some could spill to CPU, which would distort the latency and VRAM measurements.

**Not done:** step 7 (dry run), step 8 (detached run). Close VALORANT (and its Vanguard anti-cheat tray app if it holds the GPU), then ask to continue from step 7.
