# Merge of origin/main into feature/agents-proactive (PR #9): report

Date: 2026-11-12. Branch `feature/agents-proactive`:
- `32c67fe`: merge of `origin/main` `9f60dfe`
- `689d095`: my-files fixes
- the next commit: MERGE_NOTES.md and these results

## 1. Conflicts

There were no textual conflicts. Three files were changed on both sides and git merged them automatically:
- `lam/intent_classifier.py`
- `lam/orchestrator.py`
- `agents/specialized_agents.py`

Each merged file is main's version plus PR #9's own diff, with nothing edited by hand. `check_rehab_continuation` is intact. The summary line is in `recovery_integration.py` (my file; main didn't touch it). Hunk-by-hunk detail is in `/MERGE_NOTES.md`.

## 2. Before / after

Setup for every run:
- `TRIAGE_MODE=rules`. The variable doesn't exist on this branch or on main (only on `feature/triage-classifier`), so the rules engine is the only path.
- Every `SMTP*` / `DOCTOR_ALERT*` variable unset.
- A temporary `PATIENT_DATABASE_PATH`.

"Pre-merge re-run" means the same suites run today on a worktree of `origin/feature/agents-proactive` (`49c1098`) on this machine.

| Suite | Your pre-merge number | Pre-merge re-run | Post-merge | Δ |
|---|---|---|---|---|
| `run_agent_tests.py` | 110 | 110/110 | **109/110** | −1 (main's code, §3.1) |
| Conversation eval, direct | 282/282 | 282/282 | 282/282 | 0 |
| Conversation eval, via orchestrator | 271/306 | 271/306 | 271/306 | 0 (same 35 failing properties, same 10 misrouted turns) |
| Routing benchmark, classifier | 200/230 | 200/230 | **198/230** | −2 (§3.2) |
| Routing, orchestrator (lenient) | – | 202/230 | 201/230 | −1 (§3.2) |
| Routing, orchestrator (strict) | – | 189/230 | 186/230 | −3 (§3.2) |
| `test_multi_agent_orchestration.py` | – | 5/5 | 5/5 | 0 |
| `test_phase2_intent.py` | – | 18 failures (the known forced-fallback ones) | ALL CHECKS PASSED | +18 (main updated the test) |
| `test_phase4_agents.py` (main changed it) | – | 11 failures | **4 failures** (main alone: all pass) | +7 (§3.3) |
| `test_nutrition_wellbeing_agents.py` (new on main) | – | n/a | 9/9 | new |
| `data/test_filter_qwen_sft_triage.py` (new on main) | – | n/a | 8/8 + 3 subtests | new |

The first pre-merge run showed 2 failures in `run_agent_tests.py`. That was my mistake, not a real result: I ran the pre and post suites at the same time, and `test_pain_symptoms_agent.py` always uses the same `%TEMP%\pain_agent_test_patients.sqlite3`. Run one after the other, pre-merge gives 110/110.

**Reproducibility check (step 3b).** I ran the recovery conversations with `PYTHONHASHSEED=1` and again with `999`. Before the fix, 19 of 39 replies differed between the two runs. After it, 0 of 39 differ. Both runs pass 96/96.

## 3. Every drop explained

### 3.1 `test_no_duplicate_red_rules_outside_safety_engine` (110 → 109)

- **Cause:** on main, `NutritionAgent.handle()` and `MentalWellbeingAgent.handle()` in `specialized_agents.py` do `from triage.safety_triage import SafetyTriageEngine` and call `.evaluate()` when no triage result is passed in.
- **Why it only shows up now:** main already fails this check (it prints `!! FAILED` four times), but main's `_check()` doesn't raise. PR #9's `_check()` raises, so pytest now reports it.
- **Not fixed:** this is teammate code.

### 3.2 Routing benchmark (classifier 200 → 198, lenient 202 → 201, strict 189 → 186)

Twelve rows changed. Every change comes from main's additions to `intent_classifier.py` / `safety_triage.py`:

| Case | Text | Before → after | Cause (main) |
|---|---|---|---|
| R021 | "There's some fluid coming from my surgical cut, is that normal?" | miss → **fixed** | new wound keyword `surgical cut` |
| R030 | "I keep feeling down and unmotivated during this recovery." | miss → **fixed** | new mental keyword `feeling down` |
| R100 | "When will the knee feel like normal again?" | miss → **fixed** | new Recovery prototypes |
| R131 | "My incision is itching alot, is it normal?" | wound → **medication** | `itching` added to medication keywords, which are checked first |
| R199 | "I feel bloated after meals, any diet advice?" | nutrition → **medication** | `bloated` added to medication keywords |
| R110 | "How to straigten my knee fully, it is not going straight" | rehab → **recovery** | Recovery prototypes push the margin to 0.035, below 0.04, so the low-margin fallback picks the default |
| R172 | "When can I travel by bus or auto to the hospital?" | daily activity → **recovery** | same (margin 0.027) |
| R180 | "Is it ok to go for a short walk outside daily?" | daily activity → **recovery** | same (margin 0.016) |
| R013 | "I've got a burning sensation and some numbness in my foot." | orchestrator: pain → **RED emergency** | new Neurovascular RED rule (`foot` + `numbness`) |
| R051, R056, R102 | (pain answers / crutch question) | same correctness, different decision path | Recovery prototypes |

- Classifier: +3 −5 = −2.
- Orchestrator, lenient: +3 (R021, R030, R100), −4 (R013, R110, R172, R180) = −1.
- Orchestrator, strict: +2 (R021, R100), −5 (R013, R110, R172, R180, R199) = −3. R199 now goes to medication *and* nutrition.

None of the causes are in my files, so nothing was changed.

### 3.3 `test_phase4_agents.py`: 4 failures left (there were 11 before the merge, and main alone passes)

- The 7 failures that went away were fixed by main's edits to the test.
- The 4 that remain all go through `RehabilitationAgent` ("How many heel slides should I do?" and the TKA/THA procedure checks, which also use a rehab query). PR #9's rehab agent asks its two safety questions on the first turn instead of making one ChatAgent call with `DOMAIN_FOCUS`. The test therefore sees 0 generation calls and no `procedure`.
- This is not a merge regression; it was the same before the merge. The cause *is* in my file (`rehab_agent.py`), but it is the intended behaviour of PR #9, and the test is a teammate's.
- **Not changed.** This needs a decision (§4).

## 4. Needs a teammate's (or your) decision

1. **Nutrition/Wellbeing call `SafetyTriageEngine.evaluate()` directly.** Either those agents rely only on `precomputed_triage` (the orchestrator always passes it), or the invariant test is relaxed to allow calling the engine. (Calling the engine is not the same as defining new RED rules.)
2. **`itching`, `bloated` (and likely `dizzy`, `nausea`, `drowsy`, ...) in the medication keywords.** Medication is checked first, so these take wound and nutrition turns. Options: tie them to a drug word, or move them below wound and nutrition.
3. **The five new Recovery prototypes** push three rehab/daily-activity questions under the margin threshold. They fall back to the `recovery_progress` default.
4. **R013 foot numbness is now RED.** If that clinical call stands, the routing benchmark case should list `emergency` as acceptable. That case is in my `eval/routing/cases.py`, but I didn't change the expectation without a clinical sign-off.
5. **`test_phase4_agents.py` vs the reworked RehabilitationAgent.** Either update the phase-4 rehab expectations to the two-question flow, or have the rehab agent make the ChatAgent call on the first turn.
6. **`agents/REHAB_AGENT_CHANGES.md` §3** still says the orchestrator lacks a Rehabilitation hook. It's stale like the docstring was, but it isn't on your list of my files, so I left it.

Result files (all labelled `post_merge_main`):
- `eval/agents/results/post_merge_main*.{json,md}`
- `eval/routing/results/post_merge_main.{json,md}`
