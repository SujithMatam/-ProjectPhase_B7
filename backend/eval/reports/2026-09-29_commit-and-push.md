# 2026-09-29: pull main, commit backend/eval on feature/llm-eval, push

## Git steps

1. `git status -sb`: `## main...origin/main`, with only `?? backend/eval/`. Nothing outside `backend/eval/` was modified.
2. `git pull --ff-only origin main`: **Already up to date**. HEAD stayed at `6e63cbf` ("Repair pain follow-up routing and symptom history").
3. **The pull changed nothing:** no files, and neither `backend/agents/chat_agent.py` nor `backend/rag/`. `prompts.py --check-drift` was not required and was not run.
4. Branch `feature/llm-eval` was created from main. Everything under `backend/eval/` is committed with the message "Add local-LLM RAG evaluation harness, corpus, 60-query benchmark and results" and pushed to origin. The commit hash and file count are in the chat reply, because a report inside the commit can't contain its own hash.

**Checks before the commit:**
- `backend/eval/.gitignore` already lists `.chroma_copy/`, `.chroma_corpus/`, `__pycache__/` and `*.tmp`. No change was needed.
- No file is over 5 MB. The largest is `results_medgemma_2048/medgemma1.5-4b-it-q4_K_M_project.jsonl` at 555 KB.
- The `run.log` files (`results/`, `results_medgemma_2048/`, `scores/judge/run.log`, `scores/judge/run_mistral-7b.log`) are ignored by a `*.log` rule outside `backend/eval/`, so they are **not** committed.

**Timing:** the mistral:7b judge was still writing into `scores/judge/mistral-7b/` when this started. As agreed, the commit waited until it finished (16:52), so its score files are complete.

## mistral:7b judge: final state

It finished at 16:52: 240/240 project_abstain responses scored, at 100% GPU, about 14 s each. **171 of 240 records are valid.** All 69 invalid records have the same problem: `unanswerable_handling` = `n/a` on a partial/none question. That is **69 of its 84 partial/none judgements (82%)**, split 51 partial and 18 none.

| file | valid / 60 |
|---|---|
| llama3.2 | 42 |
| gemma3 | 44 |
| qwen3.5 | 41 |
| MedGemma (2048) | 44 |

Its `full`-question scores are usable, since the `n/a` rule applies there. But it gives almost no abstention data, so it can't act as a second judge on the question the abstention set asks. It wasn't run again.
