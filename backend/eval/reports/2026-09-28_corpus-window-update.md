# 2026-09-28: corpus window and URL update (item 1); items 2-4 blocked

Scope: only `backend/eval/` changed. Nothing staged or committed. No generation or retrieval runs.

## Done

- **`eval_corpus.json` windows:** 8 entries now have `days` "43-84" and `metadata.postop_window` "weeks 7-12". Previously:

  | id | days | window |
  |---|---|---|
  | EV-TKA-PAIN-05 | 56-84 | weeks 8-12 |
  | EV-THA-PAIN-05 | 56-84 | weeks 8-12 |
  | EV-TKA-REHAB-06 | 56-84 | weeks 8-12 |
  | EV-THA-REHAB-06 | 56-84 | weeks 8-12 |
  | EV-TKA-REC-04 | 56-84 | weeks 8-12 |
  | EV-THA-REC-04 | 56-84 | weeks 8-12 |
  | EV-TKA-REC-06 | 56-365 | week 8 onwards |
  | EV-THA-REC-06 | 56-365 | week 8 onwards |

- **`eval_corpus.json` URL:** every occurrence of the NHS knee URL now uses its redirect target, `https://www.nhs.uk/tests-and-treatments/knee-replacement/recovery/`. That is 12 occurrences: 4 `source_url` and 8 `additional_source_urls`.
- **Unchanged in the corpus:** every entry's status is still "draft - needs review", and content, topics and word counts were not touched.
- **How the edit was checked:** the file was rewritten with its original formatting (2-space indent, CRLF line endings), and the diff is exactly those 28 lines. It passes `build_context.py`'s corpus schema check. The pre-edit copy is saved outside the repo in the session scratchpad (`eval_corpus.before-window-edit.json`).
- **Corpus sha256:** `7fcb7bedbdfbc8af…` → `0909fbaa80468594…`.
- **`corpus_review.md`:** regenerated, 36 rows.
- **`README.md`:** the example at line 147 now says "all three variants".

## Consequences to review

1. **Nothing covers days after 84 any more.** EV-TKA-REC-06 ("The months ahead") and EV-THA-REC-06 ("The longer term") used to cover days 56-365 and now end at 84. A query at day 100 or later matches no entry's window: `window_match` is false for every chunk, and the window filter falls back to plain distance order. If the intent was only to close the days 43-55 gap, `43-365` for these two would keep their long-term reach.
2. **Wording vs window:** the six "two to three months" entries now also apply to week 7 (days 43-49), while their text still says "two to three months" / "By two to three months…".
3. **Existing contexts and reports are out of date:** `pilot/contexts_evalcorpus.jsonl`, `pilot/contexts_evalcorpus_wf.jsonl` and the window-filter / coverage / audit reports were built from the previous corpus (sha `7fcb7bed…`). `run_models.py` will treat those contexts as stale for any new corpus build. Rebuild them before comparing.

## Blocked

Items 2-4 (append 20 queries, review labels and draft reference answers, build window-filter coverage) need the 20 query lines. The request contained the placeholder "[paste the 20 lines above]" instead of the rows, and no file under `backend/eval/` holds them. `eval_queries.jsonl` is unchanged.
