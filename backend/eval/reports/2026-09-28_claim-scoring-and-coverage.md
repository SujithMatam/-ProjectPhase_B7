# 2026-09-28: claim-level scoring, coverage report, reports folder

Scope: only `backend/eval/` changed. Nothing staged or committed. No generation runs; tests used scratch copies outside the repo.

## 1. Claim-level scoring in `score.py`

**Versioning:** results written by `run_models.py` are unchanged, so `HARNESS_VERSION` stays at `"2"`. Only the score-record schema changed, so `score.py` now has `SCORE_VERSION = "2"` (the old count-based rubric counts as v1). Every manual and judge score record now carries `score_version`.

**Rubric:** `unsupported_claims` (an integer) is replaced by `claims`, a list of `{"text", "label"}` with label one of:

- `supported`: in the frozen context with the same meaning
- `embellished`: in the context, but with added specifics (numbers, durations) or used for a different purpose
- `unsupported`: not in the context at all

`grounded`, `unanswerable_handling` and `followed_format` are unchanged. The list may be empty. A bare "I don't have that information, ask your care team" is not a claim, since `unanswerable_handling` already scores it.

**Manual mode:** the rater types each claim's text, then its label as `su`, `em` or `un` (or the full word). A blank claim text finishes the list. The rater is then shown the counts per label. A bare `s` still means skip and `q` still means quit, which is why the labels use two letters.

**Judge mode:** the JSON schema now asks for a `claims` array whose `label` is limited to the same three values. The judge's instructions define the labels the same way the manual rubric does, with the swelling-to-pain example.

**Validation:** `claims` must be a list. Each claim needs non-empty text and one of the three labels.

**Summary:** the single `unsupported/resp` column is replaced by three columns (`supported`, `embellished`, `unsupported`). Each shows `total (mean per response)`, and they are never added together. Scores from an older `score_version` are counted as excluded ("from an older rubric") and don't enter the table. `manual` and `judge` automatically re-score them.

**Also updated:** the rubric bullet in `README.md`.

**Tested** with scratch copies of three pilot results (harness version relabelled to 2), outside the repo:
- Manual entry of four claims, including one mistyped label that was rejected and asked again.
- A skipped response, and a response with no claims.
- Validation of bad labels, empty claim text and old-style records.
- A simulated judge output passing validation.
- A summary run that excluded one old-rubric record.
- Re-running `manual`, which queued that old-rubric record for re-scoring.

The judge was not called against Ollama.

## 2. `pilot/coverage_report.md`

This is last session's per-query table: chunk IDs and distances from both stores, full / partial / none for each, and notes. It adds a summary and ends with the p01 icing/elevation analysis, with each claim labelled under the new rubric:
- Elevation: embellished (the context gives it for swelling, not pain).
- Icing: embellished (the context gives it for swelling).
- 15–20 minutes after activity: embellished (the model added the duration and timing).
- "Pain when bending on day 3 is normal": unsupported.

## 3. Reports folder

From now on, every report is also written to `backend/eval/reports/` (this file is the first one). The preference is saved in memory so it carries over to future sessions.

## Not changed, but noticed

The "Prompt variants" section of `README.md` still lists only `project` and `minimal`; `project_abstain` is missing.
