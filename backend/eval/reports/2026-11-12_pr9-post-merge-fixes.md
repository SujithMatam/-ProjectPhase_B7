# PR #9 post-merge fixes: report (2026-11-12)

Branch `feature/agents-proactive`, one commit on top of `1643828`.

Test setup:
- every `SMTP*` / `DOCTOR_ALERT*` variable unset
- `TRIAGE_MODE=rules`
- a temporary `PATIENT_DATABASE_PATH`

## 1. RED-rule invariant test narrowed

Test: `test_pain_symptoms_agent.py::test_no_duplicate_red_rules_outside_safety_engine`

- **Now allowed:** importing `SafetyTriageEngine` and calling `.evaluate()`. That uses the single source of truth; it doesn't copy it.
- **Still flagged**, in `pain_logic`, `pain_integration` and `specialized_agents`, via an AST walk:
  - an assignment to one of the engine's table names (`RED_FLAG*`, `RED_COOCCURRENCE*`, `YELLOW_FLAG*`, `COMPOUND_ESCALATION*`, `SELF_HARM_PATTERNS`);
  - a list, tuple or set literal holding two or more of the engine's exact RED phrases;
  - a regex alternation string containing two or more of them;
  - a dict with both `anchor` and `symptom` keys (the engine's co-occurrence rule shape).
- A single RED word in passing (e.g. `chills` in a pain symptom-word list) is not a rule and is not flagged.

**Proof.** The script `prove_red_rule_check.py` (in the session scratchpad) copied `agents/specialized_agents.py` to a temp file and planted one duplicate at a time. It then ran the real test function against that copy by patching `inspect.getsource`. The real agent file was never edited.

| Planted in the temp copy | Test result |
|---|---|
| `_URGENT_SIGNS = ("chest pain", "shortness of breath", "coughing blood")` | FAILED: copies SafetyTriageEngine RED phrases |
| `re.compile(r"\b(?:chest pain\|can't breathe\|high fever)\b")` | FAILED: regex alternation copying RED phrases |
| `RED_FLAG_PATTERNS = {"PE": ["chest pain"]}` | FAILED: defines its own red-flag rule table |
| `[{"anchor": ["calf"], "symptom": ["swollen", "hot"]}]` | FAILED: own anchor/symptom co-occurrence rule |
| temp copy removed; real module (imports and calls `SafetyTriageEngine.evaluate`) | PASSED |

## 2. Routing case R013 accepts pain or emergency

- `eval/routing/cases.py`: R013 ("I've got a burning sensation and some numbness in my foot.") now accepts `pain_symptoms` or `emergency`. A comment says the emergency outcome comes from main's Neurovascular RED rule, that it is a cautious escalation rather than a routing error, and that there is no clinical sign-off either way.
- `eval/routing/run_routing_benchmark.py`: the scorer used to drop `emergency` / `out_of_scope` before checking the acceptable set, so the new label alone would have had no effect. A single pre-emption now counts as correct when the case lists it as acceptable. R013 is the only case that does.
- `eval/routing/REPORT.md`: new section "Update 2026-11-12: R013 accepts pain or emergency". The same text is in `build_report.py`, so a rebuild keeps it. I checked that a rebuild reproduces the report byte-for-byte.

## 3. `agents/REHAB_AGENT_CHANGES.md` section 3, item 1

Item 1 now says the hook exists (`check_rehab_continuation` in `lam/orchestrator.py`, `b6c1730`) and describes what it does.

## Numbers

| Suite | Before (1643828) | After |
|---|---|---|
| `run_agent_tests.py` | 109/110 | **110/110** |
| Routing, classifier | 198/230 | 198/230 (R013 was already classified as pain) |
| Routing, orchestrator lenient | 201/230 | **202/230** |
| Routing, orchestrator strict | 186/230 | **187/230** |

R013 is the only row that differs between `post_merge_main` and `post_merge_r013`.

## Not changed

Section 3, item 5 of `REHAB_AGENT_CHANGES.md` says "What hip exercises are safe for me?" is classified as `medication` because of "safe". That is probably stale too, since `safe` was removed from the medication keywords in `6b67373`. I didn't touch it because it wasn't part of this request.
