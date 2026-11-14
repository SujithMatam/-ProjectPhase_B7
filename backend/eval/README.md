# Local-LLM RAG comparison harness

A standalone harness for comparing local Ollama models on **grounded RAG
answers** in the Recovery Progress, Pain & Symptoms, and Rehabilitation domains.
Retrieval is frozen once, then every model sees exactly the same context.

## Isolation: what this does *not* touch

Nothing here touches the orchestrator, safety triage, the doctor-alert email,
or the patient database.

- **Backend imports.** The only backend code imported is `backend/rag`, and
  only by `build_context.py`: `rag.knowledge_base`, which pulls in
  `rag.vector_store` and `rag.ingest`. Nothing from `agents/`, `lam/`,
  `triage/`, `doctor_alert.py`, `patient_database.py` or `main.py` is
  imported, so no RED triage can fire, no email can be sent, and no SQLite
  row can be written.
- **Chroma store.** `build_context.py` points the retriever at a **copy** of
  `rag/data/chroma_db` (`.chroma_copy/`, git-ignored). With `--corpus`, it
  points it at a fresh scratch collection (`.chroma_corpus/`, git-ignored)
  instead. It does this by overriding module globals in its own process only:
  `rag.vector_store.PERSIST_DIRECTORY` and `COLLECTION_NAME`, plus
  `rag.ingest._DATA_PATH` for `--corpus`. It fingerprints all of `rag/data/`
  before and after, and refuses to write output if anything there changed.
- **Prompt copies.** `prompts.py` *copies* the production prompt text. Its
  `--check-drift` mode reads `agents/chat_agent.py` and
  `agents/specialized_agents.py` as text/AST only. They are never imported or
  executed.
- **No pulls.** Nothing ever pulls a model. Models that aren't installed are
  skipped with a message.

## Hardware (detected 2026-09-28)

| | |
|---|---|
| GPU | NVIDIA GeForce RTX 3050 6GB Laptop GPU: 6144 MiB VRAM, ~588 MiB already in use at idle, driver 616.92 |
| System RAM | 15.7 GB total, ~4.7 GB free at the time of the check |
| CPU | Intel i7-13650HX, 14 cores / 20 threads |
| Ollama | 0.34.0. Installed: `llama3.2:latest` (2.0 GB, digest `a80c4f17acd5`) |

## Candidate models

Sizes are download sizes from the Ollama library. Runtime VRAM is somewhat
higher because of the KV cache and compute buffers (`num_ctx` is 4096 here).
After loading, `ollama ps` (PROCESSOR column) or the `loaded_model` field in
the results shows the real GPU/CPU split.

| Candidate | Exact tag | Size | Fits 6 GB VRAM? |
|---|---|---|---|
| llama3.2 3B | `llama3.2:3b`, same digest as the installed `llama3.2:latest` | 2.0 GB | Yes, fully on GPU. Already installed as `:latest`. |
| Gemma 3 4B (control) | `gemma3:4b` (= `gemma3:4b-it-q4_K_M`, digest `a2af6cc3eb7f`) | 3.3 GB | Yes |
| Qwen 3.5 4B | `qwen3.5:4b` (= `qwen3.5:4b-q4_K_M`) | 3.4 GB | Yes. It has a thinking mode; the harness sends `think:false`. |
| MedGemma 1.5 4B, Q4_K_M | `medgemma1.5:4b-it-q4_K_M` (= `medgemma1.5:latest`) | 3.3 GB | Yes |
| MedGemma 1.5 4B, Q8_0 | `medgemma1.5:4b-it-q8_0` | 5.0 GB | Borderline. Weights plus KV cache exceed the ~5.5 GB free VRAM, so expect a small CPU spill. |
| Gemma 4 E4B | `gemma4:e4b` (= `gemma4:e4b-it-q4_K_M`) | 9.6 GB | No. It runs split GPU/CPU and needs several GB of free system RAM, so it will be slow. `gemma4:e4b-it-qat` (6.1 GB) is closer but still over. |
| Qwen 3.5 9B | `qwen3.5:9b` | 6.6 GB | Excluded: the rule was to include it only if VRAM ≥ 12 GB |

**Why gemma3:4b is included.** MedGemma 1.5 4B is a fine-tune of Gemma 3 4B,
so `gemma3:4b` is the control that isolates the effect of medical tuning.
`gemma3:4b` and `medgemma1.5:4b-it-q4_K_M` share the same quantization
(Q4_K_M) and size, so any difference between them comes from the tuning, not
the quantization.

The official `medgemma1.5` library has no `q4_0` tag. Use the lowercase tags
above. To pull a model (not done by this harness):

```
ollama pull gemma3:4b
ollama pull qwen3.5:4b
ollama pull medgemma1.5:4b-it-q4_K_M
ollama pull medgemma1.5:4b-it-q8_0
ollama pull gemma4:e4b
```

`run_models.py` defaults to `llama3.2:latest` rather than `llama3.2:3b`,
because `:3b` isn't a local tag yet. Both have the same digest, so they are
the same model.

## How to run

All commands are run from `backend/eval/`. `build_context.py` needs the
backend virtualenv (chromadb + sentence-transformers). The other scripts use
only the standard library. psutil is optional and gives better process-memory
readings.

1. **Write queries** in `eval_queries.jsonl`, one JSON object per line:

   ```json
   {"id": "rehab-tka-01", "domain": "rehab", "procedure": "TKA", "postop_day": 7, "answerability": "full", "query": "...", "reference_answer": "..."}
   ```

   - `domain` is `recovery`, `pain` or `rehab`.
   - `procedure` is `TKA` or `THA`.
   - `postop_day` is **required** on every row, as an integer ≥ 0. There is
     no default: `build_context.py`, `run_models.py` and `score.py` all stop
     with an error naming the row if it is missing or null.
   - `answerability` is `full`, `partial` or `none`.
   - `affected_limb` is optional. It defaults to "Right", the backend's
     `ChatRequest` default.
   - `reference_passages` is optional: a list of the corpus passage IDs
     (e.g. `"EV-TKA-PAIN-01"`) that the `reference_answer` was written from.
     It is documentation for raters. Retrieval and scoring do not read it.
   - The all-empty template row is ignored and can be deleted.

2. **Freeze retrieval:**

   ```
   ..\.venv\Scripts\python.exe build_context.py
   ```

   This writes `eval_contexts.jsonl` with top_k=4 per query. Check each
   `answerability` label against the chunks that were actually retrieved.
   The retriever drops chunks whose cosine distance is above 0.75, so some
   queries get fewer than 4 chunks, or none. Re-run with `--refresh-copy` to
   re-copy the Chroma store.

   **Alternative corpus:**

   ```
   ..\.venv\Scripts\python.exe build_context.py --corpus my_corpus.json --out contexts_mycorpus.jsonl
   ```

   The file must use the same schema as `rag/data/seed_knowledge.json`: a
   list of `{id, topic, procedure (TKA|THA|All), days, content, keywords}`.
   It is validated and indexed into a separate scratch Chroma collection
   under `.chroma_corpus/<sha>/`, rebuilt on every run so it holds exactly
   that file's documents. The embedding model, procedure filter and 0.75
   distance threshold are the same as `backend/rag`, because it is the same
   code. Nothing under `rag/data/` is touched; the whole directory is
   fingerprinted and the run aborts if it changes. Without `--corpus`,
   behaviour is unchanged.

   **Context digest:** every context record has a `context_sha256` covering
   the corpus identity (file sha256), retriever settings and retrieved
   chunks. `run_models.py` compares it on resume, so switching corpus marks
   earlier results as stale even when a query happens to retrieve the same
   chunks. Re-running `build_context.py` can also change the prompts;
   `run_models.py` will then refuse to mix old and new results.

3. **Check the plan** without contacting Ollama:

   ```
   python run_models.py --dry-run
   python prompts.py --check-drift      # the copied prompt still matches production
   ```

4. **Run:**

   ```
   python run_models.py                                  # default models, all three variants
   python run_models.py --models qwen3.5:4b --variants minimal --limit 3
   ```

   Output goes to `results/<model>_<variant>.jsonl`. Model load events and a
   hardware snapshot go to `results/_runs.jsonl`.

5. **Score:**

   ```
   python score.py manual results/qwen3.5-4b_project.jsonl --rater <name>
   python score.py judge  results/qwen3.5-4b_project.jsonl --judge-model <other-model>
   python score.py summary [--by domain|procedure|answerability]
   python score.py summary --results-dir results results_medgemma_2048
   ```

   Pass `--contexts contexts_all_wf.jsonl` to `manual`/`judge` for the
   60-query set, because the default is `eval_contexts.jsonl`. `summary` takes
   one or more results dirs and reads them together. Every table has a
   `num_predict` column, plus a `results dir` column when more than one dir is
   given, so the 600- and 2048-token MedGemma rows stay apart. Scores for
   files outside `results/` are stored one level deeper, e.g.
   `scores/judge/<judge>/results_medgemma_2048/<model>_<variant>.jsonl`.
   That way two dirs with the same file name never share a score file.

   **Judge on the 6 GB GPU:** use `--judge-model qwen2.5:7b --num-ctx 4096
   --num-gpu 99`. Left to itself, Ollama keeps about 1 GiB of VRAM free and
   puts only 26 of 29 layers on the GPU (84%). `--num-gpu 99` forces all
   layers onto the GPU (100%, ~4.6 GiB in `nvidia-smi`). `num_gpu` is part of
   the judge options, so it is included in `judge_prompt_sha256`.

## Request settings (run_models.py)

- **Call:** `/api/chat`, streaming, `temperature 0`, `num_predict 600`,
  `seed 0`, `num_ctx 4096`, with no client-side timeout. `num_ctx` is pinned
  because Ollama's default differs between versions and models, and a
  silently truncated prompt would invalidate the comparison.
- **Budget:** `num_predict` defaults to 600 and can be changed with
  `--num-predict N`. It is part of the options fingerprint, so results from
  different budgets must go to different `--results-dir`s (resume refuses to
  mix them). The main run (`results/`) used 600 for all four models.
  MedGemma 1.5 spends much of that on its `<unused94>` reasoning block, so it
  was re-run alone at `--num-predict 2048` into `results_medgemma_2048/`.
  `results/` is kept unchanged as the 600-token evidence (see
  `reports/2026-09-29_run-summary.md`).
- **Thinking:** off (`think:false`) for models that report the capability.
  Otherwise the 300-token budget can be spent on reasoning. `--think`
  switches it on. Gemma 4's thinking is triggered by a `<|think|>` token in
  the system prompt, which neither variant contains.
- **One model at a time:** each model is loaded once, runs all its variants
  and queries, then is unloaded so the next model gets the whole GPU.

### Recorded per request

- **Response:** the response text (and any thinking text), `done_reason`, and
  an empty-response flag.
- **Latency:** seconds to first streamed chunk, to first content token, and
  total wall time.
- **Ollama counters:** `load_duration`, `prompt_eval_count`/`_duration`,
  `eval_count`/`_duration`, and tokens/s.
- **Peak GPU memory:** from `nvidia-smi`, sampled every 0.25 s. This is
  **system-wide**: compare against `gpu_used_at_start_mib`.
- **Peak ollama-process memory:** from psutil RSS, or `tasklist` working set
  as a fallback. Both memory peaks are sampled, so very short spikes can be
  missed.
- **GPU/CPU split:** `/api/ps` total size and VRAM-resident size.
- **Fingerprints:** hashes of the prompt, context (including corpus
  identity), query and options, plus the model digest. These are what make
  resume safe.

### Resume

Results files are append-only, and every finished request is `fsync`ed as one
line. Re-running the same command:

- skips ids that already have an `ok` record,
- retries ids that errored,
- discards an incomplete last line left by an interruption.

If the prompt, context, options or model digest differ from an existing `ok`
record, the run **stops** rather than mixing results. Use a new
`--results-dir`, or `--rerun-stale`; the newest record per id wins.

## Prompt variants (prompts.py)

- **project:** mirrors the `domain_instruction` branch of
  `ChatAgent._query_llama()`, with the same wording, the same `- topic:
  content` context lines, and the same `DOMAIN_FOCUS` text per domain.
  Production sends this as one prompt to `/api/generate`. Here the default
  `system_user` layout sends the template as the system message, with the
  `User's Question:` block as the user message.
  `--project-layout single_user` sends the verbatim single-prompt layout
  instead. The layout is part of the prompt hash, so the two are never mixed.
- **project_abstain:** the `project` prompt plus exactly one added sentence
  (`prompts.ABSTAIN_SENTENCE`), placed as its own paragraph right after the
  "Write a friendly, 2-3 sentence answer..." instruction: *"Whenever the
  discharge notes above do not cover the user's question, say that you do
  not have that information and ask the patient to check with their surgeon
  or physiotherapist."* Everything else, including the layouts, is the same
  as `project`, so comparing the two isolates the effect of that sentence on
  partial and unanswerable questions. `python prompts.py --check-drift`
  verifies that removing the sentence gives back the `project` rendering
  exactly. Its format expectation for scoring also accepts a "not covered,
  ask your surgeon or physiotherapist" answer.
- **minimal:** a short system prompt ("answer only from the context; say so
  if it isn't there; 2–3 sentences"), with numbered context and the
  procedure name.

## Scoring (score.py)

The rubric (full definitions are in the `score.py` docstring):

- `grounded`: 0–2
- `claims`: a list of the answer's factual/clinical claims, each labelled
  `supported` (in the context, same meaning), `embellished` (in the context,
  but with added numbers/durations or used for another purpose) or
  `unsupported` (not in the context). Summaries report the three counts in
  separate columns and never add them together. Score records carry
  `score_version`; scores from an older rubric are excluded and re-scored.
- `unanswerable_handling`: `correct`, `invented` or `n/a`. It is always
  `n/a` when answerability is `full`.
- `followed_format`: true or false

Manual and judge scores are **stored separately** and **reported
separately**. They are never averaged together:

- **Manual:** `scores/manual/<results file>`, with `score_source: "manual"`
  and a `scorer` field.
- **LLM judge:** `scores/judge/<judge model>/<results file>`, with
  `score_source: "llm_judge"`, `judge_model`, the judge's digest and prompt
  hash, the rationale, and a validity flag. The judge uses Ollama JSON-schema
  output at temperature 0. It refuses to grade a model's own answers unless
  `--allow-self-judge` is passed.
- **Staleness:** every score records the sha256 of the response it scored.
  If a result is re-run and the response changes, the old score is excluded
  as stale.

## Pilot

`pilot_queries.jsonl` holds 10 pipeline-check queries with empty reference
answers. Keep its outputs out of the real eval files:

```
..\.venv\Scripts\python.exe build_context.py --queries pilot_queries.jsonl --out pilot\contexts.jsonl
python run_models.py --queries pilot_queries.jsonl --contexts pilot\contexts.jsonl --results-dir pilot\results ^
    --models llama3.2:latest gemma3:4b medgemma1.5:4b-it-q4_K_M qwen3.5:4b
```

## Test-set notes

These apply to the 60 queries in `eval_queries.jsonl` (pain q01-q20, rehab
r01-r20, recovery c01-c20), built against `eval_corpus.json` with
`--window-filter` (`contexts_all_wf.jsonl`).

- **In-window rule for reference answers.** A `reference_answer` is written
  only from corpus passages whose `days` range contains the query's
  `postop_day`, and those passages are listed in `reference_passages`.
  Window-filtered retrieval ranks out-of-window passages last, so a reference
  that relied on them would ask for content the model may never be shown.
  This is why the "two to three months" clause was dropped from q06: it came
  from days 43+ passages, and q06 is at day 35. When a passage quotes two
  sources with different figures, the reference quotes both. `none`
  references are a short deferral.
- **q09 and q19 test abstention with distractor context, not empty
  context.** Neither question is covered by the corpus, but each retrieves
  four unrelated chunks just under the 0.75 distance threshold. They check
  whether a model declines when irrelevant text is present. The pilot's p04
  retrieves nothing and is the empty-context case.
- **q18 is a known retrieval miss, kept on purpose.** The corpus covers
  flying in two in-window passages (EV-THA-PAIN-05, EV-THA-REC-04). Retrieval
  instead returns sports and discharge chunks, so the frozen context has
  nothing on flying. Its label (`partial`) reflects the corpus, not the
  retrieval. Read q18 scores as a retrieval failure, not a model failure.
- **q19 and heat advice.** The corpus leaves out the AAOS advice on heat for
  hips on purpose. OrthoInfo "Activities after hip replacement", a listed
  source for several THA entries, says to apply heat (heating pad or hot,
  damp towel, 15-20 minutes) before exercising. q19 is labelled `none`
  against the corpus. An answer that recommends heat may match the original
  source but is still unsupported by the context, so score it that way.
- **More known retrieval misses: r10, c07, c10, c12.** Each has an in-window
  passage that answers it, but that passage isn't retrieved. r10 gets only
  wrong-window chunks. c07 gets one wrong-window chunk. c10 and c12 get
  nothing. As with q18, their labels reflect the corpus, and low scores here
  are retrieval failures.
- **Fragile retrievals: c02, c11, c18, c20, r12.** The relevant chunk comes
  back at distance 0.69-0.73, just inside the 0.75 threshold. Small changes
  to corpus wording, chunking or the embedding model can drop it, so check
  these first if their results change between builds.
- **Thin coverage after day 84.** Only EV-TKA-REC-06 and EV-THA-REC-06
  (days 43-365) are in window after day 84. Queries there (r10, r20, c05,
  c17, c18) depend on those two passages, and details such as the
  dislocation warning signs, return-to-sport advice and high-impact
  activity guidance aren't repeated in them.
- **The 0.75 threshold looks too tight for patient phrasing.** c12 ("is it
  normal to still need the stick at 6 weeks, my son says I should stop using
  it") retrieves nothing, although three in-window passages answer it
  (EV-THA-REHAB-04, EV-THA-REC-05, EV-THA-REC-03). Casual, conversational
  questions land further from the passages in embedding space than the
  threshold allows. The threshold is backend/rag's
  `SEMANTIC_MAX_DISTANCE` and applies to the app as well, so this is a
  finding about production retrieval, not just the harness.

## Differences from production

Keep these in mind when drawing conclusions:

- **top_k:** the harness retrieves 4 chunks; production `ChatAgent` uses 2.
- **Endpoint:** `/api/chat` here versus `/api/generate` in production.
  Production also uses a 12 s timeout and `num_predict` 150.
- **Single turn:** each query is one turn with no chat history. In
  production, **TKA recovery answers never reach an LLM** (they are
  deterministic), and Pain reaches the LLM only after its multi-turn
  interview, with a longer instruction. This harness measures the
  grounded-answer step in isolation.
- **Knowledge base:** 8 documents, of which only 1 is THA-specific. Expect
  many THA queries to be `partial` or `none`.
