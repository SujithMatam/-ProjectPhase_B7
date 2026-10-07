# Pain / Recovery / Rehab Agents — Baseline (before rework)

The "before" record for the `feature/agents-proactive` rework, taken from
`main` at `6e63cbf` ("Repair pain follow-up routing and symptom history").
Nothing in the code was changed to produce it.

All three agents live in `agents/specialized_agents.py` and are reached through
`LAMOrchestrator.process()` → `AgentRouter`. All three are **reactive**: each
one runs only when the patient sends a message. None of them starts a
conversation, schedules anything, or reads the patient's stored clinical record.

---

## 1. PainSymptomsAgent

Code: `specialized_agents.py::PainSymptomsAgent`, plus `pain_logic.py` (fields,
questions, next-field decision), `pain_integration.py` (wording, final turn,
persistence) and `pain_state.py` (pending-question bookkeeping).

### Question list (`pain_logic.QUESTIONS`)

| Field | Question |
|---|---|
| `pain_score` | On a scale from 0 to 10, how bad is the pain right now? |
| `onset` | Did it come on suddenly, or has it been building up gradually? |
| `location` | Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else? |
| `worsening_or_improving` | Is it getting worse, getting better, or staying about the same? |
| `pain_characteristics` | How would you describe the pain -- sharp, dull, throbbing, or something else? |
| `swelling` | Have you noticed any swelling in that area? |
| `warmth_or_redness` | Does the area feel warmer than usual, or look red? |
| `stiffness` | Does the joint feel stiff, especially when you try to move it? |
| `numbness_or_weakness` | Any numbness or weakness in that leg? |
| `fever_or_temperature` | Have you felt feverish at all, or checked your temperature? |
| `medication_effect` | Did taking your pain medication help, or not really? |

Every field also has a simpler rephrase in `ALT_QUESTIONS`. It is used once,
after an "I don't know" answer. A second uncertain answer records the field as
`"unknown"`.

How the next question is chosen (`pain_logic.select_next_field`), one question per turn:

1. The three required fields come first, in this order: `pain_score` → `onset` → `location`.
2. **Calf branch** (location is in the calf): `swelling` → `warmth_or_redness` →
   `numbness_or_weakness`, then `fever_or_temperature` if the pain is moderate or severe.
3. **Joint branch** (anywhere else):
   - severe pain: `worsening_or_improving` → `stiffness`
   - moderate pain: `worsening_or_improving`
   - mild pain: no further questions
4. If the patient mentioned medication in this assessment, the last question is `medication_effect`.
5. When no field is left, the agent runs its final turn: RAG + `ChatAgent` LLM
   synthesis, with a deterministic fallback summary.

`pain_characteristics` has a question, but `select_next_field` never picks it.
It can only be filled from free text or from the structured
`pain_characteristics` request field.

### Reads from the DB

- **Medication names: not read by this agent.** `LAMOrchestrator.process()`
  (`lam/orchestrator.py:668`) reads them through
  `ReportGenerationAgent.get_patient_record()` and puts them in
  `LAMContext.medication_names`. That list is used only by the intent
  classifier. It is never passed to any of the three agents.
  `medication_effect` is triggered by keywords in the patient's own messages
  (`pain_logic.mentions_medication`), not by the medication record.
- **Prior symptom assessments: read by this agent.** This goes beyond
  medication names. On the final turn,
  `pain_integration.load_recent_assessments()` →
  `patient_database.get_recent_symptom_assessments(patient_id, limit=3)` reads
  the last 3 rows of `symptom_assessments`. Only the trend note
  (`build_trend_note`) uses them.
- **Nothing else.** The agent reads nothing from `patients`, `surgeries`,
  `medications`, `metrics` or `triage_events`. Surgery type, limb, post-op day
  and surgery date all come from the client's `/api/chat` payload.

### What it persists

- **DB:** when an assessment completes, it inserts one row into
  `symptom_assessments` (`pain_integration.persist_completed_assessment` →
  `patient_database.save_symptom_assessment`).
  - Columns: `postop_day`, `pain_score` *or* `pain_severity_category` (never
    both), `onset`, `location`, `worsening_or_improving`, `pain_characteristics`,
    `swelling`, `warmth_or_redness`, `stiffness`, `numbness_or_weakness`,
    `fever_or_temperature`, `temperature_c`, `triage_level`.
  - Persistence is best-effort: a failure is logged and the turn continues.
    An unknown `patient_id` fails the foreign key check.
  - `medication_effect` is collected but **not** stored. The table has no column for it.
- **In memory only:** `pain_state._STORE` keeps one `PainSessionState` per
  patient. It holds the pending field, ask counts, the active-history boundary
  and cached structured facts. It is process-scoped, capped at 500 entries,
  and lost on restart.

---

## 2. RecoveryProgressAgent

Code: `specialized_agents.py::RecoveryProgressAgent`, plus `recovery_state.py`,
`recovery_logic.py` and `recovery_integration.py`.

### Question list (`recovery_integration._ASK_QUESTIONS`)

| Field | Question | Ever asked? |
|---|---|---|
| `rom_flexion_degrees` | About how many degrees can you currently bend your knee? | Yes (TKA) |
| `rom_extension_degrees` | Do you know your current knee extension measurement in degrees (how close to fully straight)? | Yes (TKA) |
| `mobility_status` | How are you currently getting around -- walking independently, or using a walker, cane, or crutches? | No (defined but unreachable) |
| `pain_score` | On a scale of 0 to 10, what is your current pain level? | No (defined but unreachable) |

When a question is re-asked, it gets a short lead-in that rotates between a few
phrasings: retry ("No worries."), ambiguous answer ("Just want to make sure I've
got that right.") or pending question ("Just circling back to this --").

How it decides what to do on each turn:

- **TKA only.** `SUPPORTED_METRICS_BY_PROCEDURE` contains only TKA →
  flexion, then extension. The agent runs a deterministic loop each turn:
  observe → decide (`decide_progress_verdict_action`) → act. The action is one of:
  - ask
  - await an answer
  - decline, with a reason code
  - assess against the milestone source (TKA-03)
- **Retry limit:** a field is asked at most `MAX_ASKS_PER_FIELD = 2` times.
  After that it is marked unavailable.
- **THA / GEN:** the loop is skipped entirely. The message goes straight to
  `ChatAgent.answer_question` with `DOMAIN_FOCUS`. These procedures get no
  questions and no state.

### Reads from the DB

- **Nothing.** Neither the agent nor `recovery_*` imports `patient_database`.
  It does not read medication names either (see §1 for where those go).
- The post-op day comes from the client's `surgery_date`
  (`derive_effective_postop_day`). The client's `postop_day` value is stored
  for diagnostics only.
- Its only other external read is RAG: `ClinicalKnowledgeBase.retrieve_detailed`.

### What it persists

- **DB: nothing.** Range-of-motion values the patient reports are never written
  to `metrics` or any other table.
- **In memory only:** `recovery_state._STORE` keeps one `RecoverySessionState`
  per patient. It holds facts, the pending field, ask counts, and the
  unknown/unavailable markers. It has a session/interview TTL, is capped at
  500 entries, and is lost on restart.

---

## 3. RehabilitationAgent

Code: `specialized_agents.py::RehabilitationAgent` and `_rehab_context_note`.

### Question list

**None.** This agent is single-shot. It builds a domain instruction and calls
`ChatAgent.answer_question` once, so it has no field list, no next-question
logic and no multi-turn state.

It accepts three optional structured fields, which it restates into the
instruction as untrusted context:

- `weight_bearing_status` (NWB / PWB / WBAT / FWB)
- `current_rom`
- `exercise_history`

When none of the three is supplied, it behaves like plain `ChatAgent` with
`DOMAIN_FOCUS`.

### Reads from the DB

- **Nothing.** It does not import `patient_database` and does not read
  medication names. All its inputs are request fields.
- Its only external read is the RAG/LLM path inside `ChatAgent`.

### What it persists

- **Nothing, in the DB or in memory.**

---

## 4. Test baseline

### Setup

The run was isolated from real data:

- **Database:** `PATIENT_DATABASE_PATH` pointed to a fresh temp sqlite file.
  `test_pain_symptoms_agent.py` also overrides this with its own temp file.
  - The real `backend/patients.sqlite3` had the same MD5 before and after the
    run (`a5d11b75fd455dae6dfe5d6c21f9613b`).
- **Email:** every `*SMTP*` environment variable and `DOCTOR_ALERT_EMAIL` was
  unset. `SMTP_PASSWORD` was set in the shell beforehand.
- **Interpreter:** `backend/.venv` (Python 3.11), with pytest 9.1.1 installed
  into it for this baseline.
- **Files run:** only `test_pain_symptoms_agent.py`,
  `test_recovery_progress_agent.py` and `test_rehabilitation_agent.py`.

These files are plain-Python scripts. A failed `_check()` adds to a
module-level `_FAILURES` list instead of raising. Run as-is, pytest would
therefore mark a test as passed even when a check failed. To fix this, the run
used a small out-of-tree pytest plugin. It fails a test if that test added to
`_FAILURES`.

The results were cross-checked by running each file's own `main()`. Both
runners gave the same result.

### Results: 66 passed, 1 failed (67 tests)

| File | Passed | Failed |
|---|---|---|
| `test_pain_symptoms_agent.py` | 39 / 39 | 0 |
| `test_recovery_progress_agent.py` | 17 / 18 | 1 |
| `test_rehabilitation_agent.py` | 9 / 9 | 0 |

**The one failure:**
`test_recovery_progress_agent.py::test_real_keyword_fallback_retrieval`

- **Cause:** the test environment, not a code fault. `chromadb 1.5.9` and
  `sentence-transformers 6.0.1` are now installed in `.venv`, so retrieval
  takes the `semantic_chroma` path.
- **What the test expects:** its final check requires `retrieval_path ==
  "keyword_fallback"`. The test itself says the environment has no chromadb
  installed, which is no longer true.
- **What still works:** the checks on behaviour all pass:
  - the bare "80 degrees" query returns 0 results
  - the augmented query retrieves TKA-03

<details>
<summary>Per-test results</summary>

**test_pain_symptoms_agent.py** — all PASSED:
- `test_fresh_independent_prompt_works`
- `test_multiple_facts_extracted_from_one_sentence`
- `test_short_reply_attribution`
- `test_known_values_never_reasked`
- `test_exactly_one_question_per_turn`
- `test_uncertainty_then_unknown`
- `test_adaptive_branching`
- `test_completion_stops_questions`
- `test_wound_message_overrides_pain`
- `test_red_overrides_pain`
- `test_medication_ownership_unchanged`
- `test_topic_switch_not_hijacked`
- `test_no_diagnosis_or_unsupported_reassurance`
- `test_no_robotic_wording`
- `test_structured_api_fields_still_work`
- `test_historical_persistence_and_trend`
- `test_cumulative_safety_reaches_red`
- `test_cumulative_safety_stale_state_not_hijacked`
- `test_no_duplicate_red_rules_outside_safety_engine`
- `test_swelling_ownership_routing`
- `test_deterministic_summary_uses_action_protocol`
- `test_untrusted_data_framing_in_final_turn`
- `test_pain_state_thread_safety`
- `test_ask_counts_reset_after_assessment_concludes`
- `test_pain_state_last_updated_locked_reads`
- `test_chat_request_patient_id_validation`
- `test_completed_assessment_not_contaminating_fresh_complaint`
- `test_orchestrator_cumulative_safety_scoped_to_active_boundary`
- `test_abandoned_pain_session_reset_after_topic_switch`
- `test_authoritative_final_triage_overrides_chat_agent`
- `test_final_turn_retrieval_hint_fenced_end_to_end`
- `test_medication_mentioned_scoped_to_active_user_turns`
- `test_pain_score_persistence_numeric_and_category`
- `test_foreign_key_enforcement_on_symptom_assessments`
- `test_final_turn_chat_history_scoped_to_active_assessment`
- `test_final_turn_rejects_ungrounded_unreported_symptom`
- `test_pain_trend_followup_not_stolen_by_wound`
- `test_final_reply_consistency_with_assessment_and_triage`
- `test_location_extraction_prefers_more_specific_phrase`

**test_recovery_progress_agent.py**:
- `test_postop_day_derivation`: PASSED
- `test_checkpoint_day_6_7_8_boundary`: PASSED
- `test_assessment_wording_and_negative_assertions`: PASSED
- `test_decline_reasons`: PASSED
- `test_extraction_regressions`: PASSED
- `test_executor_state_transitions`: PASSED
- `test_immediate_metric_assessment_end_to_end`: PASSED
- `test_multi_fact_one_action`: PASSED
- `test_single_retrieval_per_turn`: PASSED
- `test_real_keyword_fallback_retrieval`: **FAILED** (environment; see above)
- `test_continuation_helper`: PASSED
- `test_real_classifier_bend_misroute_regression`: PASSED
- `test_safety_and_scope_precedence`: PASSED
- `test_procedure_isolation`: PASSED
- `test_client_reported_postop_day_is_diagnostic_only`: PASSED
- `test_routing_and_response_shape`: PASSED
- `test_postop_day_procedure_and_chat_history_reach_grounded_guidance`: PASSED
- `test_conversational_style_and_grounding`: PASSED

**test_rehabilitation_agent.py** — all PASSED:
- `test_routing`
- `test_postop_day_reaches_agent`
- `test_weight_bearing_status_handling`
- `test_rom_context_handling`
- `test_exercise_history_handling`
- `test_backward_compatibility`
- `test_red_bypasses_agent`
- `test_procedure_isolation`
- `test_no_unsupported_advancement_with_restriction`

</details>
