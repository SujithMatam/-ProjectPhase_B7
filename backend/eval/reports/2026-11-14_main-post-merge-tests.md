# main after PR #9 + PR #10 merges: test run (2026-11-14)

HEAD `7fee34e` (Merge PR #10). Nothing in the code was changed. `git clean` was not run. The untracked weights under `triage/model/artifacts` are still there.
Every run: SMTP*/DOCTOR_ALERT* unset (0 left), a new temporary `PATIENT_DATABASE_PATH` per suite, suites run one at a time.

## 1. Server startup
`uvicorn main:app` (TRIAGE_MODE unset) printed
`[TRIAGE][HYBRID] classifier loaded: M2:m2_main_v2_it3_seed0 (t_red=0.354 t_yel=0.363 t_alert=0.684)`
before `Application startup complete`. No fallback warning. **Confirmed.**

## 2. Matches the known lists (not new)
- Hybrid only: phase4 (3 checks, "My knee is more swollen today and hurts."), nutrition_wellbeing 3, orchestration 1 (V7), doctor_alert G (2 checks).
- Both modes: fallback_procedure_isolation 5/10 failing, specialized_assigned 3/4 failing.
- Passing in both modes: medication_proactive 21/21, medication_schedule, phase2_intent, intent_medication_symptoms 59/59, triage unit tests 153/153.
- Rules mode: run_agent_tests 110/110, and pain, recovery, rehab, symptom_assessment, phase4, nutrition, orchestration and doctor_alert all pass.

## 3. NEW failures

### A. Hybrid only. PR #9's agent suites had never run under hybrid. They fail now because hybrid is the default on main.
`run_agent_tests.py`: **9 failed / 101 passed** (rules: 110/110). The same failures show when the suites run as scripts.

| test | message | rules | hybrid | p(RED) | email |
|---|---|---|---|---|---|
| test_pain_symptoms_agent.py::test_wound_message_overrides_pain | My incision hurts and there is yellow fluid coming out. | YELLOW | RED | 0.894 | yes |
| ::test_topic_switch_not_hijacked, ::test_abandoned_pain_session_reset_after_topic_switch, ::test_detour_then_bare_answer_resumes_pending_question | My knee pain suddenly got much worse today. | GREEN | RED | 0.762 | yes |
| ::test_orchestrator_cumulative_safety_scoped_to_active_boundary | My pain suddenly got much worse today. | GREEN | RED | 0.739 | yes |
| ::test_swelling_ownership_routing (A) | My knee is swollen. | YELLOW | RED | 0.721 | yes |
| ::test_pain_trend_followup_not_stolen_by_wound | My knee pain is 6 out of 10, it started suddenly behind the knee and it is swollen. | YELLOW | RED | 0.877 | yes |
| test_recovery_progress_agent.py::test_conversational_style_and_grounding (G) | My wound looks more red today and it's leaking some fluid. | YELLOW | RED | 0.740 | yes |
| **test_rehabilitation_agent.py::test_red_bypasses_agent** | **I have severe calf pain and swelling, can I still do my exercises?** | **RED** | **GREEN** | **0.011** | no |

`test_symptom_assessment_agent.py`: **19 failed checks** (rules: all pass). All of them come from over-triage to RED, which sends the turn to SafetyTriageAgent so PainSymptomsAgent never runs.
"My knee is more swollen today and hurts." (0.809), "My knee is sore and a bit tender. It started suddenly..." (0.864),
"My pain suddenly got worse today, and it's mostly behind the knee." (0.544), "My hip has started aching today." (0.665),
"My knee/hip/ankle is swollen and sore." (0.740 / 0.771 / 0.844). No override fired on any of them.

**Cause:** the M2 classifier scores ordinary pain or swelling text as RED, and in hybrid that wins (`max(overrides, classifier)`).
The one exception is under-triage: rules mode says RED for a calf pain plus swelling (DVT) message, but hybrid says GREEN. The rules RED is not among the hybrid overrides, and the classifier gives p(RED) 0.011.

### B. Both modes. One extra check in test_phase3_rag.py: 5 failures, 4 were known.
Section 8: `!! FAILED: end-to-end chat response returned no sources` for "What exercises should I do after my knee replacement?".
**Cause:** PR #9's reworked RehabilitationAgent (`agents/rehab_agent.py`, 86c40ab) answers the first turn with the two-question safety check (`ENGINE_ASK` "Exercise Check") before it retrieves anything, so `sources == []`. Triage is GREEN in both modes, so this is not caused by hybrid.
