# Merge notes: `origin/main` → `feature/agents-proactive` (PR #9)

- Merge commit: `32c67fe` (parents: PR #9 `49c1098`, main `9f60dfe`; merge base `6e63cbf`)
- Method: `git merge origin/main`. No rebase, no force-push, nothing merged into main.
- Follow-up commit (my files only): `689d095`. It fixes the stale `rehab_state.py` docstring and replaces `hash()` with `zlib.crc32` for the recovery acknowledgement opener.

## 1. Conflicted hunks

**None.** Git auto-merged every file. Only three files were changed on both sides:

| File | Main's change | PR #9's change | Overlap |
|---|---|---|---|
| `backend/lam/intent_classifier.py` | Five new Recovery prototype sentences. New keywords: drug names and side-effect words (medication), topical words (wound), carry/lift/errands (daily activity), mood/sleep/self-harm words (mental), milestone/aid-weaning words (recovery). New "STEP 1b" compound pre-checks in `_deterministic_intent` (wound-topical, mood+sleep, pain-during-exercise, milestone framing). | Removed `safe`/`safety`/`schedule`/`timing`/`warning` from medication keywords. Added `_contains_word`. "I am X" no longer counts as an introduction without an intake cue. The semantic step cannot pick intake without an intake cue. The raw query is passed to the deterministic and fallback steps. Added the `SEMANTIC_FIRST` experiment (off by default). | Different lines of the same `_MEDICATION_KEYWORDS` set (main appended after `"precaution"`, PR #9 deleted five lines above it). Main's STEP 1b sits directly below PR #9's edited intake call in `_deterministic_intent`. |
| `backend/lam/orchestrator.py` | Imports `MENTAL_HEALTH_CRISIS_TEMPLATE`. A RED triage with `category == "mental_health_crisis"` replies with that template instead of the generic emergency alert. | `check_rehab_continuation()` hook and its helpers, the docstring paragraph, the comment in the continuation chain, and the `elif check_rehab_continuation(...)` branch after the Recovery check. | Adjacent import lines only. The RED-reply hunk and the continuation hunk are about 300 lines apart. |
| `backend/agents/specialized_agents.py` | New `NutritionAgent.handle()` and `MentalWellbeingAgent.handle()`, plus stricter `DOMAIN_FOCUS` text. | The Recovery, Pain and Rehab rework: `RehabilitationAgent` moved to `agents/rehab_agent.py` and re-exported, and the imports changed. | None. Different classes. The merged file still imports `Any` and `Optional`, which main's new methods use. |

**What was kept:** main's code exactly as it is on main, plus PR #9's own diff exactly as it was. I checked this two ways:
- `git diff origin/main HEAD` on each of the three files gives the same line count as PR #9's own diff against the merge base (227 lines in `intent_classifier.py`, 152 in `orchestrator.py`).
- `git diff origin/feature/agents-proactive HEAD` on these files contains only main's lines.

No teammate logic was deleted or rewritten. Nothing was hand-edited during the merge.

`check_rehab_continuation` and its `elif` branch are in the merged orchestrator unchanged. The recovery summary line lives in `agents/recovery_integration.py` (my file), which main did not touch.

## 2. Behavioural interactions (not textual conflicts)

The test runs found these. All of them come from main's code. None was changed here, because changing any of them would change teammate behaviour.

1. **Main's new keywords take turns that PR #9 routed correctly.** Medication is checked first, so `itching` steals R131 "My incision is itching alot, is it normal?" (now medication; was wound). `bloated` steals R199 "I feel bloated after meals, any diet advice?" (now medication; was nutrition). PR #9 removed `safe`/`schedule` from the medication list for exactly this reason (eval/routing/REPORT.md, "overbroad keyword").
2. **Main's five new Recovery prototypes narrow the semantic margins.** R110 (rehab), R172 and R180 (daily activity) used to win semantically. Their margins now fall below `SEMANTIC_MIN_MARGIN` (0.04), so they drop to `fallback_low_margin`, which defaults to `recovery_progress`. The same prototypes fix R100. Main's `surgical cut` and `feeling down` keywords fix R021 and R030.
3. **Main's new Neurovascular RED rule** (anchor `foot`/`leg`/`toe` + `numb`/`numbness`/...) sends R013 "I've got a burning sensation and some numbness in my foot." to emergency. Before the merge it went to the Pain agent.
4. **Main's `NutritionAgent.handle()` and `MentalWellbeingAgent.handle()` import and call `SafetyTriageEngine.evaluate()`** when no triage result is passed in. That breaks the invariant in `test_pain_symptoms_agent.py::test_no_duplicate_red_rules_outside_safety_engine`, a test that predates PR #9. On main the same check prints `!! FAILED` four times, but main's `_check()` only records the failure, so pytest reports a pass. PR #9's `_check()` raises, so the failure is now visible.

Section 2 of `backend/eval/reports/2026-11-12_merge-main-into-pr9.md` has the full before/after numbers.
