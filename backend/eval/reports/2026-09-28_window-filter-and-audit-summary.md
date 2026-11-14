# 2026-09-28: window filter, coverage rebuild, corpus audit, README

Scope: only `backend/eval/` changed. Nothing staged or committed. No model generation was run. The only runs were `build_context.py` retrieval, which embeds the query and does not generate, and a `run_models.py --dry-run`.

## 1. `--window-filter` in `build_context.py`

- **What it does:** it asks the same retriever for 8 candidates instead of 4. This is still read-only and still uses the scratch copy / scratch collection. It then puts chunks whose `days` range contains the query's `postop_day` first, ordered by distance within each group (then by original rank), and keeps `--top-k` (4).
- **Missing `days`:** a chunk with no usable `days` counts as matching. That covers an empty value, or anything that isn't `N` or `N-M`; such chunks are listed in the console output.
- **Recorded in every context record, in both modes:**
  - `window_filter` (true/false) and `candidate_k` (8 or 4)
  - `n_window_mismatch`
  - per chunk: `window_match` (true/false)
  - in filter mode only, per chunk: `retriever_rank`, the chunk's rank among the 8 candidates
- **Digest:** `window_filter` and `candidate_k` are part of the digest, so contexts from the two modes never compare equal.
- **Console:** a `*` marks each wrong-window chunk.
- **Tests:** unit checks of the day parsing, the matching and the reordering. Both real builds verified that `backend/rag/data` was unchanged.
- **Compatibility:** `run_models.py --dry-run` accepts the new file.

## 2. Rebuilt pilot contexts and the window-filter comparison

- `pilot/contexts_evalcorpus.jsonl` (default) was rebuilt. Its chunk IDs and distances are identical to the previous file; only the digests changed, because of the new fields.
- `pilot/contexts_evalcorpus_wf.jsonl` is new, built with `--window-filter`.
- Report: `reports/2026-09-28_window-filter-coverage.md`.
- **Result:** wrong-window chunks drop from 19 to 12 (of 36 retrieved in each mode). Full coverage goes from 6/10 to 7/10: p09 moves from partial to full. No query got worse.
- **What's left:** p02 still has 3 wrong-window chunks, because only one window-matching chunk was among its 8 candidates.

## 3. Corpus audit

Report: `reports/2026-09-28_corpus-audit.md`.

- **URLs:** all 9 distinct `source_url`s resolve (HTTP 200) and match their entries' subjects. The OrthoInfo URLs and the NHS knee URL redirect, and the NHS knee link is out of date.
- **Topic terms:** the three entries with terms missing from the primary page (EV-TKA-PAIN-05, EV-THA-PAIN-05, EV-THA-REHAB-02) have them in their listed additional sources. Every organisation a passage cites appears in its source list.
- **Drugs:** no drug appears with a dose or frequency. Mentions are class-level only: opioids, blood-thinning medicine, antibiotics before dental work, and generic pain relief.
- **Conflicts:** none are flat contradictions. Within single passages, two sources are quoted with different figures for return to work (EV-TKA-REC-04, EV-THA-REC-03) and for driving after TKA (EV-TKA-REC-03). There are also three low-severity framing differences.
- **Windows:** 8 entries don't match their window text. Six are labelled "weeks 8-12" and two "week 8 onwards", but their `days` start at 56 rather than 50. This leaves days 43-55 with no stage-specific entry.

## 4. README

The "Prompt variants" section now describes `project_abstain`: the added sentence, where it goes, what the drift check verifies, and its format expectation.

**Not changed:** the pilot command example at README line 147 still says "both variants". It is outside the "Prompt variants" section.
