# Medication-symptom gate, Rehab/Daily prototypes, phase-4 rehab expectations: final report

Date: 2026-11-12. Branch `feature/agents-proactive`. Before = `932beaa`. After = `38a92fb`, which is these five commits:

| Step | Commit | What |
|---|---|---|
| 0 | `522fc22` | `eval/routing/heldout_v2.py`: 30 new messages, committed before any classifier change (max cosine to cases.py 0.833). Scored at `932beaa`. |
| 1 | `07e6774` | Main's 17 side-effect words stay in `_MEDICATION_KEYWORDS`, but count for medication only with a medication cue. 59 unit tests in `test_intent_medication_symptoms.py`. |
| 2 | `433a617` | Two Rehab and two Daily Activity prototypes; nothing deleted (diagnosis in `2026-11-12_step2-recovery-margins.md`). |
| 3 | `74b4c4d` | `test_phase4_agents.py`: the 4 failing checks now expect the reworked rehab flow (and, for THA, the reworked Recovery agent; see note 2). |
| 4 | `38a92fb` | `agents/REHAB_AGENT_CHANGES.md` §3 item 5 corrected. |

Setup for every run:
- every `SMTP*` / `DOCTOR_ALERT*` variable unset (checked: 0 left)
- temp `PATIENT_DATABASE_PATH`
- `TRIAGE_MODE=rules` (no effect on this branch)
- suites run one after the other, never in parallel

## Routing, before / after

Acceptance rule: no agent below its current number on either set. **It holds.** No agent drops on the classifier, lenient or strict score, on either set.

### cases.py (232 cases, 230 scored per agent)

| Agent | n | Classifier before | after | Orchestrator lenient before | after | Orchestrator strict before | after |
|---|---|---|---|---|---|---|---|
| Pain & Symptoms | 36 | 29/36 | 29/36 | 28/36 | 28/36 | 28/36 | 28/36 |
| Recovery Progress | 31 | 29/31 | 29/31 | 30/31 | 30/31 | 29/31 | 29/31 |
| Rehabilitation | 28 | 25/28 | 26/28 (+1) | 25/28 | 26/28 (+1) | 24/28 | 25/28 (+1) |
| Wound Care | 26 | 25/26 | 26/26 (+1) | 26/26 | 26/26 | 23/26 | 23/26 |
| Medication | 27 | 26/27 | 26/27 | 26/27 | 26/27 | 25/27 | 25/27 |
| Daily Activity | 25 | 19/25 | 22/25 (+3) | 19/25 | 22/25 (+3) | 19/25 | 22/25 (+3) |
| Nutrition | 24 | 19/24 | 20/24 (+1) | 20/24 | 20/24 | 15/24 | 16/24 (+1) |
| Mental Wellbeing | 25 | 18/25 | 18/25 | 20/25 | 20/25 | 16/25 | 16/25 |
| Intake / Context | 8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| **All** | 230 | **198/230** | **204/230** (+6) | **202/230** | **206/230** (+4) | **187/230** | **192/230** (+5) |

Agents below their before number: none

### heldout_v2 (30 cases)

| Agent | n | Classifier before | after | Orchestrator lenient before | after | Orchestrator strict before | after |
|---|---|---|---|---|---|---|---|
| Pain & Symptoms | 2 | 0/2 | 2/2 (+2) | 2/2 | 2/2 | 0/2 | 2/2 (+2) |
| Recovery Progress | 5 | 4/5 | 5/5 (+1) | 4/5 | 5/5 (+1) | 4/5 | 5/5 (+1) |
| Rehabilitation | 5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| Wound Care | 2 | 0/2 | 2/2 (+2) | 2/2 | 2/2 | 2/2 | 2/2 |
| Medication | 8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| Daily Activity | 4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 |
| Nutrition | 4 | 0/4 | 4/4 (+4) | 4/4 | 4/4 | 0/4 | 4/4 (+4) |
| **All** | 30 | **21/30** | **30/30** (+9) | **29/30** | **30/30** (+1) | **23/30** | **30/30** (+7) |

Agents below their before number: none

Rows that changed on cases.py:
- R131 (wound) and R199 (nutrition): step 1
- R110 (rehab), R172, R178 and R180 (daily activity): step 2

Every other row has the same prediction and decision path. Main's fixes still hold: R100 (recovery, semantic), R021 (wound, `surgical cut`) and R030 (mental wellbeing, `feeling down`).

## Every suite

| Suite | Before | After |
|---|---|---|
| Routing, cases.py: classifier / lenient / strict | 198 / 202 / 187 of 230 | **204 / 206 / 192** of 230 |
| Routing, heldout_v2: classifier / lenient / strict | 21 / 29 / 23 of 30 | **30 / 30 / 30** of 30 |
| `run_agent_tests.py` | 110/110 | 110/110 |
| Conversation eval, direct | 282/282 | 282/282 |
| Conversation eval, via orchestrator | 271/306 | 271/306 (same failing properties and same misrouted turns in each conversation: c05, c11, c13, c15) |
| `test_multi_agent_orchestration.py` | 5/5 | 5/5 |
| `test_phase2_intent.py` | ALL CHECKS PASSED | ALL CHECKS PASSED |
| `test_phase4_agents.py` | 4 failures | **ALL CHECKS PASSED** |
| `test_nutrition_wellbeing_agents.py` (main) | 9/9 | 9/9 |
| `data/test_filter_qwen_sft_triage.py` (main) | 8/8 + 3 subtests | 8/8 + 3 subtests |
| `test_intent_medication_symptoms.py` (new) | n/a | 59/59 |

## Notes

1. **Held-out discipline.**
   - `heldout_v2` was committed (`522fc22`) before any classifier edit.
   - Step 1's gate was written from the rule in the request, not from held-out results.
   - In step 2, one early prototype candidate was scored on both sets before candidates were restricted to `cases.py`. That candidate was rejected: it broke R058 on cases.py and H029 on held-out. The final four were scored on held-out once.
   - **H029 is weaker.** "My neighbour was walking freely by now, am I slow?" is still correct, but its margin fell from 0.046 to 0.022, so it now gets `recovery_progress` from the low-margin default, not from a semantic win.
2. **The 4th phase-4 failure was not a Rehab turn.** "What movements should I avoid after my hip replacement?" (THA procedure check):
   - It routes to `recovery_progress` through the low-margin default (top-1 Recovery 0.488, margin 0.023). This was the same at `932beaa` and on main.
   - On main it passed because main's RecoveryProgressAgent fell through to a ChatAgent call that carried the procedure. The reworked Recovery agent abstains without a surgery date and makes no generation call.
   - The check now reads the procedure from `AgentRouter.dispatch`, which receives `THA`.
   - It is arguably a misroute: hip precautions are a Rehab or Daily Activity question. It is **not fixed here**, because that would mean tuning the classifier against a test sentence.
3. **Hidden coupling in phase 4.** Section 7a ("How many heel slides should I do?", one generation call expected) passes only because section 1's `TEST-PT` rehab session already holds the safety answer. Section 1 keeps `TEST-PT` for that reason, and the section-4 TKA flow uses its own patient id. 7a was not changed.
4. **Log line in phase 4.** `[MEMORY] today's metrics write failed: FOREIGN KEY constraint failed` appears during the new section-4 TKA flow. The rehab agent tries to log "exercises done today: yes" for `TEST-PT-REHAB-TKA`, which has no patient row in the temp DB. The agent catches it, and the test passes.
5. **Medication cue list:**
   - every non-symptom medication keyword except `purpose` and `precaution`
   - plus `meds`, `doses`, `painkillers`, `pain killer(s)`, `antibiotics`, `capsule(s)`, `injection(s)`, `side effects`, `since i started`, `since starting`, `since i began`, `after taking`, `started taking`

   The extra cues only unlock the symptom words; they are not new medication keywords. R152 "pain killer on empty stomach" still goes to Pain, as before.

Results:
- `eval/routing/results/{before_v2_steps,final_v2_steps,heldout_v2_before,heldout_v2_final}.{json,md}`
- `eval/agents/results/final_v2_steps*.{json,md}`
