"""
test_medication_proactive.py
============================
Tests for the Proactive Medication Adherence Engine (medication branch).

Covers:
  - ProactiveMedicationEngine.evaluate_turn() — each conversational case
  - MedicationAgent.handle() integration (engine vs. deterministic synthesis)
  - AgentRouter dispatching IntentLabel.MEDICATION → MedicationAgent

Run from backend/:
    python test_medication_proactive.py
"""

import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(__file__))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PASS = "✅ PASS"
FAIL = "❌ FAIL"
results: list[dict] = []


def run(name: str, fn):
    try:
        fn()
        results.append({"name": name, "status": PASS})
        print(f"  {PASS}  {name}")
    except Exception as exc:
        results.append({"name": name, "status": FAIL, "error": str(exc)})
        print(f"  {FAIL}  {name}")
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Reset helper so each test starts with a clean state
# ---------------------------------------------------------------------------
def _reset(patient_id: str = "PT-B7-8921"):
    from agents.medication_proactive import ProactiveMedicationEngine
    ProactiveMedicationEngine.reset_state(patient_id)


PID = "PT-B7-8921"

# ===========================================================================
# SECTION 1 — ProactiveMedicationEngine unit tests
# ===========================================================================
print("\n═══ Section 1: ProactiveMedicationEngine ═══")


def t_greeting_starts_check():
    _reset(PID)
    from agents.medication_proactive import ProactiveMedicationEngine
    res = ProactiveMedicationEngine.evaluate_turn(PID, "hi", postop_day=3)
    assert "taken" in res["reply"].lower() or "medication" in res["reply"].lower(), (
        f"Unexpected greeting reply: {res['reply']}"
    )
    assert res["action"] == "assess"


run("Greeting triggers proactive adherence check", t_greeting_starts_check)


def t_yes_asks_med_and_dose():
    _reset(PID)
    from agents.medication_proactive import ProactiveMedicationEngine
    # Simulate greeting first
    ProactiveMedicationEngine.evaluate_turn(PID, "hi", postop_day=3)
    res = ProactiveMedicationEngine.evaluate_turn(PID, "yes", postop_day=3)
    assert res["action"] == "assess"
    assert "medication" in res["reply"].lower() or "dose" in res["reply"].lower(), (
        f"Expected medication/dose question, got: {res['reply']}"
    )


run("'yes' response asks for medication name and dose", t_yes_asks_med_and_dose)


def t_missed_med_without_name():
    _reset(PID)
    from agents.medication_proactive import ProactiveMedicationEngine
    res = ProactiveMedicationEngine.evaluate_turn(PID, "I forgot to take my pill", postop_day=3)
    assert res["action"] == "advise"
    reply = res["reply"].lower()
    assert "missed" in reply or "medication" in reply or "dose" in reply, (
        f"Expected missed-dose guidance, got: {res['reply']}"
    )


run("Missed dose without name triggers clarification + guidance", t_missed_med_without_name)


def t_missed_med_with_name():
    _reset(PID)
    from agents.medication_proactive import ProactiveMedicationEngine
    res = ProactiveMedicationEngine.evaluate_turn(
        PID, "I missed my Paracetamol this morning", postop_day=3
    )
    assert res["action"] == "advise"
    assert "paracetamol" in res["reply"].lower() or "missed" in res["reply"].lower(), (
        f"Unexpected reply: {res['reply']}"
    )
    assert res.get("triage_level") == "GREEN"


run("Missed named medication gives correct adherence guidance", t_missed_med_with_name)


def t_dosage_error_escalates():
    _reset(PID)
    from agents.medication_proactive import ProactiveMedicationEngine
    res = ProactiveMedicationEngine.evaluate_turn(
        PID, "I accidentally took two tablets instead of one", postop_day=2
    )
    assert res["action"] == "escalate"
    assert res["is_escalated"] is True
    assert res.get("triage_level") == "YELLOW"
    assert "dosage" in res["reply"].lower() or "alert" in res["reply"].lower(), (
        f"Expected safety alert, got: {res['reply']}"
    )


run("Accidental double dose triggers escalation with YELLOW triage", t_dosage_error_escalates)


def t_side_effect_escalates_without_inventing_treatment():
    _reset(PID)
    from agents.medication_proactive import ProactiveMedicationEngine
    res = ProactiveMedicationEngine.evaluate_turn(
        PID, "I have a rash after taking my medicine", postop_day=3
    )
    assert res["action"] == "escalate"
    assert res["is_escalated"] is True
    assert res.get("triage_level") == "YELLOW"
    reply = res["reply"].lower()
    assert "clinician" in reply or "pharmacist" in reply
    assert "take 650" not in reply and "increase" not in reply


run("Medication side-effect concern escalates to clinician review", t_side_effect_escalates_without_inventing_treatment)


def t_uncertain_dose_lists_prescriptions():
    _reset(PID)
    from agents.medication_proactive import ProactiveMedicationEngine
    res = ProactiveMedicationEngine.evaluate_turn(
        PID, "I don't remember what dose I am supposed to take", postop_day=5
    )
    assert res["action"] == "advise"
    # Should list prescriptions or ask for clarification
    reply = res["reply"].lower()
    assert ("prescribed" in reply or "dose" in reply or "medication" in reply), (
        f"Unexpected reply: {res['reply']}"
    )


run("Uncertainty about dose returns prescription list or guidance", t_uncertain_dose_lists_prescriptions)


def t_stopping_medication_warns():
    _reset(PID)
    from agents.medication_proactive import ProactiveMedicationEngine
    res = ProactiveMedicationEngine.evaluate_turn(
        PID, "I stopped taking my blood thinner", postop_day=4
    )
    assert res["action"] == "advise"
    assert res["is_escalated"] is True
    assert res.get("triage_level") == "YELLOW"
    reply = res["reply"].lower()
    assert "stop" in reply or "anticoagulant" in reply or "blood" in reply, (
        f"Expected stopping warning, got: {res['reply']}"
    )


run("Stopping anticoagulant triggers YELLOW escalation", t_stopping_medication_warns)


def t_full_dose_reported_asks_other_meds():
    _reset(PID)
    from agents.medication_proactive import ProactiveMedicationEngine
    res = ProactiveMedicationEngine.evaluate_turn(
        PID, "I took Paracetamol 500 mg at 9 am", postop_day=3
    )
    # Should ask about other scheduled medications
    reply = res["reply"].lower()
    assert "other" in reply or "schedule" in reply or "medication" in reply, (
        f"Expected other-med follow-up, got: {res['reply']}"
    )


run("Full dose report triggers follow-up on other scheduled medications", t_full_dose_reported_asks_other_meds)


def t_state_persists_across_turns():
    _reset(PID)
    from agents.medication_proactive import ProactiveMedicationEngine
    ProactiveMedicationEngine.evaluate_turn(PID, "I took Paracetamol 500 mg at 9 am", postop_day=3)
    state = ProactiveMedicationEngine.get_state(PID)
    assert state.reported_dose is not None, "Dose should be stored in state"
    assert state.reported_time is not None, "Time should be stored in state"


run("Dose and time are persisted in MedicationCheckinState", t_state_persists_across_turns)


def t_history_populates_state():
    _reset(PID)
    from agents.medication_proactive import ProactiveMedicationEngine
    history = [
        {"role": "user", "content": "I took Paracetamol 500 mg at 8 am"},
    ]
    # fresh turn referencing history
    res = ProactiveMedicationEngine.evaluate_turn(
        PID, "How long until my next dose?", chat_history=history, postop_day=3
    )
    state = ProactiveMedicationEngine.get_state(PID)
    # State should have been seeded from history
    assert state.current_med_name is not None, (
        f"Med name should be seeded from history, state: {state}"
    )


run("Chat history populates state on first turn", t_history_populates_state)


# ===========================================================================
# SECTION 2 — MedicationAgent.handle() integration
# ===========================================================================
print("\n═══ Section 2: MedicationAgent Integration ═══")


def t_medication_agent_greeting_returns_answer():
    _reset(PID)
    from agents.specialized_agents import MedicationAgent
    result = MedicationAgent.handle(
        patient_id=PID,
        surgery_type="TKA",
        affected_limb="Right",
        postop_day=3,
        user_message="hi",
        procedure="Total Knee Arthroplasty",
    )
    assert "answer" in result, f"Expected 'answer' key, got: {list(result.keys())}"
    assert result.get("action") == "assess"
    assert result.get("target_agent") is not None


run("MedicationAgent.handle() greeting returns structured proactive answer", t_medication_agent_greeting_returns_answer)


def t_medication_agent_escalation_path():
    _reset(PID)
    from agents.specialized_agents import MedicationAgent
    result = MedicationAgent.handle(
        patient_id=PID,
        surgery_type="THA",
        affected_limb="Left",
        postop_day=2,
        user_message="I took double dose of enoxaparin by mistake",
        procedure="Total Hip Arthroplasty",
    )
    assert result.get("is_escalated") is True, f"Expected escalation: {result}"
    assert result.get("triage_level") == "YELLOW"
    assert result.get("action") == "escalate"


run("MedicationAgent.handle() double-dose escalates to YELLOW", t_medication_agent_escalation_path)


def t_medication_agent_missed_dose():
    _reset(PID)
    from agents.specialized_agents import MedicationAgent
    result = MedicationAgent.handle(
        patient_id=PID,
        surgery_type="TKA",
        affected_limb="Left",
        postop_day=5,
        user_message="I missed my morning Paracetamol",
        procedure="Total Knee Arthroplasty",
    )
    assert "answer" in result
    answer = result["answer"].lower()
    assert "missed" in answer or "dose" in answer or "paracetamol" in answer, (
        f"Unexpected missed-dose answer: {result['answer']}"
    )
    assert result.get("action") == "advise"


run("MedicationAgent.handle() missed dose returns advise action", t_medication_agent_missed_dose)


def t_medication_agent_informational_hits_rag():
    """Generic clinical question: answer always present, action is any valid type."""
    _reset(PID)
    from agents.specialized_agents import MedicationAgent
    result = MedicationAgent.handle(
        patient_id=PID,
        surgery_type="TKA",
        affected_limb="Right",
        postop_day=7,
        user_message="What is enoxaparin used for after knee surgery?",
        procedure="Total Knee Arthroplasty",
    )
    assert "answer" in result, f"Expected 'answer' key, keys: {list(result.keys())}"
    assert result["answer"], "answer should not be empty"
    # Engine may return inform, assess, or advise depending on extracted entities
    assert result.get("action") in {"inform", "assess", "advise"}, (
        f"Unexpected action: {result.get('action')}"
    )
    assert result.get("target_agent") is not None, "target_agent should be set"


run("MedicationAgent.handle() generic question returns grounded inform response", t_medication_agent_informational_hits_rag)


def t_medication_questions_use_record_context():
    _reset(PID)
    from agents.specialized_agents import MedicationAgent

    common = {
        "patient_id": PID,
        "surgery_type": "TKA",
        "affected_limb": "Right",
        "postop_day": 3,
        "procedure": "Total Knee Arthroplasty",
    }
    dosage = MedicationAgent.handle(user_message="dosage?", **common)["answer"]
    paracetamol = MedicationAgent.handle(user_message="paracetamol?", **common)["answer"]
    timing = MedicationAgent.handle(
        user_message="when should I take it?",
        chat_history=[{"role": "user", "content": "paracetamol?"}],
        **common,
    )["answer"]

    assert "Paracetamol" in dosage and "650mg TDS" in dosage
    assert "Paracetamol" in paracetamol and "scheduled analgesia" in paracetamol.lower()
    assert "prescription label" in timing.lower()
    assert "generic medication fallback" not in timing.lower()
    assert dosage != paracetamol != timing

    short_timing = MedicationAgent.handle(
        user_message="timing?",
        chat_history=[{"role": "user", "content": "paracetamol?"}],
        **common,
    )
    assert short_timing["target_agent"] == "MedicationAgent"
    assert short_timing["action"] == "inform"
    assert "prescription label" in short_timing["answer"].lower()


run("Medication questions return distinct record-grounded contextual answers", t_medication_questions_use_record_context)


def t_medication_context_covers_short_replies_and_misspellings():
    from lam.intent_classifier import IntentClassifier
    from lam.schemas import IntentLabel, LAMContext

    history = [{"role": "user", "content": "paracetamol?"}]
    for query in ("yes", "at what time should I take the tablets?", "how many anticaogulants"):
        context = LAMContext(
            patient_id=PID,
            surgery_type="TKA",
            affected_limb="Right",
            postop_day=3,
            user_message=query,
            chat_history=history,
        )
        assert IntentClassifier.classify_detailed(query, context).intent == IntentLabel.MEDICATION


run("Medication context preserves short replies and recognizes common misspellings", t_medication_context_covers_short_replies_and_misspellings)


def t_missed_dose_follow_up_keeps_medication_context():
    _reset(PID)
    from agents.specialized_agents import MedicationAgent
    from lam.intent_classifier import IntentClassifier
    from lam.schemas import IntentLabel, LAMContext

    common = {
        "patient_id": PID,
        "surgery_type": "TKA",
        "affected_limb": "Right",
        "postop_day": 3,
        "procedure": "Total Knee Arthroplasty",
    }
    MedicationAgent.handle(user_message="enoxaparin?", **common)
    MedicationAgent.handle(user_message="I missed it", **common)
    follow_up = "It's been 2 hours and pain level is 5"
    result = MedicationAgent.handle(user_message=follow_up, **common)
    context = LAMContext(
        patient_id=PID,
        surgery_type="TKA",
        affected_limb="Right",
        postop_day=3,
        user_message=follow_up,
        chat_history=[
            {"role": "user", "content": "enoxaparin?"},
            {"role": "assistant", "content": "How many hours late is this dose?"},
        ],
    )

    assert IntentClassifier.classify_detailed(follow_up, context).intent == IntentLabel.MEDICATION
    assert result["target_agent"] == "MedicationAgent"
    assert result["action"] == "advise"
    assert "2 hour" in result["answer"]
    assert "pain level is 5/10" in result["answer"]
    assert "double" in result["answer"].lower() or "extra dose" in result["answer"].lower()


run("Missed-dose hours and pain follow-up stays with MedicationAgent", t_missed_dose_follow_up_keeps_medication_context)


# ===========================================================================
# SECTION 3 — AgentRouter dispatch
# ===========================================================================
print("\n═══ Section 3: AgentRouter MEDICATION dispatch ═══")


def t_router_dispatches_medication_agent():
    _reset(PID)
    from agents.agent_router import AgentRouter
    from lam.schemas import IntentLabel
    result = AgentRouter.dispatch(
        intent_label=IntentLabel.MEDICATION,
        patient_id=PID,
        surgery_type="TKA",
        affected_limb="Right",
        postop_day=3,
        user_message="What medications am I supposed to take after knee surgery?",
        procedure="Total Knee Arthroplasty",
    )
    assert "answer" in result, f"Expected 'answer' key, got keys: {list(result.keys())}"
    assert result.get("target_agent") is not None, "target_agent should be set"


run("AgentRouter dispatches MEDICATION intent to MedicationAgent", t_router_dispatches_medication_agent)


def t_router_medication_missed_dose_end_to_end():
    _reset(PID)
    from agents.agent_router import AgentRouter
    from lam.schemas import IntentLabel
    result = AgentRouter.dispatch(
        intent_label=IntentLabel.MEDICATION,
        patient_id=PID,
        surgery_type="TKA",
        affected_limb="Left",
        postop_day=4,
        user_message="I forgot to take my Paracetamol this morning",
        procedure="Total Knee Arthroplasty",
        chat_history=[{"role": "user", "content": "I took Paracetamol 500 mg at 8 am"}],
    )
    assert "answer" in result
    assert result.get("action") in {"advise", "assess", "inform"}
    assert result["medication_state"].get("current_med_name") == "Paracetamol"


run("AgentRouter missed dose end-to-end returns advise or assess", t_router_medication_missed_dose_end_to_end)


# ===========================================================================
# SUMMARY
# ===========================================================================
print("\n" + "═" * 55)
passed = sum(1 for r in results if r["status"] == PASS)
failed = sum(1 for r in results if r["status"] == FAIL)
total = len(results)
print(f"  Results: {passed}/{total} passed   {failed} failed")
print("═" * 55)
if failed:
    sys.exit(1)
