# 2026-09-28: in-window fixes for q09/q19, word count

Scope: only `backend/eval/` changed. Nothing staged or committed. No generation runs and no context rebuilds.

## Changes

- **`eval_queries.jsonl`:** 2 rows changed (q09, q19); nothing else in the file.

  | id | new second sentence | reference_passages |
  |---|---|---|
  | q09 | "Please ask your surgical team, and do not change your medicines on your own." | `EV-TKA-PAIN-03` (days 8-21), was `EV-TKA-PAIN-01` |
  | q19 | "For pain and swelling, the notes mention raising the leg slightly and applying ice for short periods." | `EV-THA-PAIN-02` (days 8-21), was `EV-THA-PAIN-01` |

  All 20 reference answers now pass the in-window rule: every listed passage's `days` range contains the query's `postop_day`. `load_queries` accepts the file.
- **`eval_corpus.json`:** EV-TKA-PAIN-01 `metadata.word_count` changed from 269 to 260, its actual count. The diff is 1 line. Corpus sha256 is now `b7756f7cd750a8c1`.
- **`corpus_review.md`:** regenerated.

## Notes

- **Contexts not rebuilt, as instructed.** Passage text is unchanged, so retrieval is unaffected. The three context files still record the previous corpus sha (`5b708a30e85bc715`). `run_models.py` checks staleness with the contexts' own digests and never re-reads the corpus file, so this only affects provenance. The next rebuild will record the new sha.
- **Two older word-count mismatches remain** (found in the first corpus review, not touched): EV-TKA-PAIN-06 stores 274 but has 273 words; EV-THA-PAIN-06 stores 268 but has 267.
