"""
Test suite for the interactive Intake & Context Agent.
Milestone Section 2.4: Intake & Context Agent.

Tests:
1. Friendly welcome greeting acknowledging patient EHR and surgery.
2. Sequential multi-turn follow-up dialogue (feeling -> pain -> mobility -> concerns -> summary).
3. Exception handling: 'I don't know my surgery date / procedure' (fetches from SQLite).
4. Exception handling: 'I don't know how to rate my pain' (explains NPRS scale).
5. Exception handling: 'I don't know what medications I take' / queries medications from SQLite.
6. Informational Q&A: Answering weight-bearing terms (WBAT/PWB), why intake is needed, OrthoSync role.
7. Vague / ambiguous inputs handled with bedside empathy.
8. End-to-end LAMOrchestrator integration and multi-turn continuation.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List

from lam.orchestrator import LAMOrchestrator
from lam.schemas import IntentLabel, TargetAgent
from agents.agent_router import AgentRouter
from agents.specialized_agents import IntakeContextAgent
from agents import intake_logic

_FAILURES: List[str] = []


def _check(condition: bool, message: str) -> None:
    if not condition:
        _FAILURES.append(message)
        print(f"    !! FAILED: {message}")
    else:
        print(f"    [OK] {message}")


def test_intake_welcome_greeting():
    print("=" * 78)
    print("1 -- Friendly Welcome Greeting with EHR Recognition")
    print("=" * 78)

    # PT-B7-8921 is pre-loaded as Rishi Priyan V N in patients.sqlite3
    res = IntakeContextAgent.handle(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=7,
        user_message="Hello, I want to do my check in",
        procedure="TKA",
        chat_history=[],
    )

    reply = res["reply"]
    print("Agent Reply Preview:\n", reply[:200], "...\n")

    _check("Rishi" in reply or "Hello" in reply, "greets patient warmly")
    _check("Total Knee Arthroplasty" in reply or "TKA" in reply, "acknowledges surgery type")
    _check("Post-Op Day 7" in reply or "Day 7" in reply, "acknowledges post-op day")
    _check("how are you feeling overall today" in reply.lower(), "asks first question (overall feeling)")
    _check(res["engine"] == "Intake & Context Agent - Welcome", f"engine is {res['engine']}")


def test_intake_sequential_followups():
    print("=" * 78)
    print("2 -- Multi-Turn Sequential Follow-Up Questions")
    print("=" * 78)

    history: List[Dict[str, str]] = []

    # Turn 1: Welcome
    res1 = IntakeContextAgent.handle(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=7,
        user_message="Hi",
        procedure="TKA",
        chat_history=history,
    )
    history.append({"role": "user", "content": "Hi"})
    history.append({"role": "assistant", "content": res1["reply"]})
    _check("how are you feeling overall today" in res1["reply"].lower(), "Turn 1 asks overall feeling")

    # Turn 2: User answers feeling -> Agent acknowledges and asks pain
    res2 = IntakeContextAgent.handle(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=7,
        user_message="I'm feeling a bit tired and sore today",
        procedure="TKA",
        chat_history=history,
    )
    history.append({"role": "user", "content": "I'm feeling a bit tired and sore today"})
    history.append({"role": "assistant", "content": res2["reply"]})
    _check("pain or discomfort" in res2["reply"].lower() or "rate your pain" in res2["reply"].lower(), "Turn 2 asks pain level")

    # Turn 3: User answers pain -> Agent acknowledges and asks mobility
    res3 = IntakeContextAgent.handle(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=7,
        user_message="My pain is about 3 out of 10",
        procedure="TKA",
        chat_history=history,
    )
    history.append({"role": "user", "content": "My pain is about 3 out of 10"})
    history.append({"role": "assistant", "content": res3["reply"]})
    _check("movement or walking" in res3["reply"].lower() or "walker or crutches" in res3["reply"].lower(), "Turn 3 asks mobility")

    # Turn 4: User answers mobility -> Agent acknowledges and asks concerns
    res4 = IntakeContextAgent.handle(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=7,
        user_message="I've been walking short distances with my walker",
        procedure="TKA",
        chat_history=history,
    )
    history.append({"role": "user", "content": "I've been walking short distances with my walker"})
    history.append({"role": "assistant", "content": res4["reply"]})
    _check("specific concerns" in res4["reply"].lower() or "medication questions" in res4["reply"].lower(), "Turn 4 asks concerns")

    # Turn 5: User answers concerns -> Conclude & Summarize
    res5 = IntakeContextAgent.handle(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=7,
        user_message="No specific concerns right now, thank you",
        procedure="TKA",
        chat_history=history,
    )
    reply5 = res5["reply"]
    print("Conclusion Summary Preview:\n", reply5, "\n")
    _check("daily recovery check-in complete" in reply5.lower() or "summary" in reply5.lower(), "Turn 5 summarizes check-in")
    _check("3" in reply5, "summary contains reported pain score (3)")
    _check("walker" in reply5.lower(), "summary contains reported mobility (walker)")


def test_exception_unknown_surgery_date():
    print("=" * 78)
    print("3 -- Exception Handling: Patient Doesn't Know Surgery Date / Procedure")
    print("=" * 78)

    # PT-B7-8922 is Sujith Matam with Total Hip Arthroplasty on 2026-09-02
    res = IntakeContextAgent.handle(
        patient_id="PT-B7-8922",
        surgery_type="",
        affected_limb="",
        postop_day=0,
        user_message="I don't know my surgery date or what surgery I had",
        procedure="",
        chat_history=[],
    )

    reply = res["reply"]
    print("Exception Fallback Reply:\n", reply, "\n")

    _check("no worries" in reply.lower() or "no problem" in reply.lower(), "reassures patient warmly")
    _check("Total Hip Arthroplasty" in reply or "THA" in reply, "retrieves surgery type from SQLite database")
    _check("2026-09-02" in reply, "retrieves exact surgery date from SQLite database")
    _check("Left" in reply, "retrieves affected limb from SQLite database")


def test_exception_unknown_pain():
    print("=" * 78)
    print("4 -- Exception Handling: Patient Doesn't Know How to Rate Pain")
    print("=" * 78)

    history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "How are you feeling overall today?"},
        {"role": "user", "content": "Feeling okay"},
        {"role": "assistant", "content": "How would you rate your pain or discomfort right now from 0 to 10?"},
    ]

    res = IntakeContextAgent.handle(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=7,
        user_message="I don't know how to rate it, I am not sure",
        procedure="TKA",
        chat_history=history,
    )

    reply = res["reply"]
    print("Pain Exception Guidance:\n", reply, "\n")

    _check("mild" in reply.lower() and "moderate" in reply.lower() and "severe" in reply.lower(), "offers simple mild/moderate/severe tiers")
    _check("don't need an exact number" in reply.lower() or "completely fine" in reply.lower(), "relieves patient pressure")


def test_exception_unknown_medications():
    print("=" * 78)
    print("5 -- Exception Handling & Query: Patient Doesn't Know Their Medications")
    print("=" * 78)

    # PT-B7-8921 has Paracetamol, Enoxaparin, Oxycodone, Docusate Sodium in database
    res = IntakeContextAgent.handle(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=7,
        user_message="What medications am I on? I forgot the names",
        procedure="TKA",
        chat_history=[],
    )

    reply = res["reply"]
    print("Medication Lookup Reply:\n", reply, "\n")

    _check("Paracetamol" in reply, "lists Paracetamol from SQLite database")
    _check("Enoxaparin" in reply, "lists Enoxaparin from SQLite database")
    _check("Oxycodone" in reply, "lists Oxycodone from SQLite database")


def test_informational_qa_during_intake():
    print("=" * 78)
    print("6 -- Informational Q&A During Intake (Gives Answers)")
    print("=" * 78)

    # Question 1: What is WBAT / PWB?
    res_wbat = IntakeContextAgent.handle(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=7,
        user_message="What does WBAT or weight-bearing mean?",
        procedure="TKA",
        chat_history=[],
    )
    _check("weight bearing as tolerated" in res_wbat["reply"].lower() or "wbat" in res_wbat["reply"].lower(), "explains WBAT accurately")
    _check("nwb" in res_wbat["reply"].lower() or "pwb" in res_wbat["reply"].lower(), "defines clinical weight-bearing levels")

    # Question 2: Why do you need this intake?
    res_why = IntakeContextAgent.handle(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=7,
        user_message="Why do you ask for an intake check-in?",
        procedure="TKA",
        chat_history=[],
    )
    _check("monitor your healing" in res_why["reply"].lower() or "recovery" in res_why["reply"].lower(), "explains purpose of intake check-in")

    # Question 3: Who are you?
    res_who = IntakeContextAgent.handle(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=7,
        user_message="Who are you and what is OrthoSync?",
        procedure="TKA",
        chat_history=[],
    )
    _check("orthosync" in res_who["reply"].lower(), "introduces OrthoSync assistant role")


def test_vague_answers_bedside_manner():
    print("=" * 78)
    print("7 -- Vague Answers Handled with Bedside Empathy")
    print("=" * 78)

    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "How are you feeling overall today?"},
    ]

    res = IntakeContextAgent.handle(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=7,
        user_message="meh, just so-so I guess",
        procedure="TKA",
        chat_history=history,
    )

    reply = res["reply"]
    print("Vague Answer Response:\n", reply, "\n")

    _check("pain or discomfort" in reply.lower() or "rate your pain" in reply.lower(), "advances smoothly to pain check without error")
    _check("thanks" in reply.lower() or "sharing" in reply.lower() or "letting me know" in reply.lower(), "acknowledges politely and empathetically")


def test_orchestrator_integration():
    print("=" * 78)
    print("8 -- LAMOrchestrator End-to-End Integration & Multi-turn Continuation")
    print("=" * 78)

    # 1. Fresh intake opening query
    res_open = LAMOrchestrator.process(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=7,
        user_message="Hi, I am ready for my initial intake check-in",
    )
    _check(res_open["intent"] == IntentLabel.INTAKE_CONTEXT.value, f"intent is {res_open['intent']}")
    _check(res_open["target_agent"] == TargetAgent.INTAKE_CONTEXT_AGENT.value, f"target_agent is {res_open['target_agent']}")
    _check("how are you feeling overall today" in res_open["reply"].lower(), "orchestrator delivers intake greeting")

    # 2. Multi-turn continuation through orchestrator
    history = [
        {"role": "user", "content": "Hi, I am ready for my initial intake check-in"},
        {"role": "assistant", "content": res_open["reply"]},
    ]

    res_turn2 = LAMOrchestrator.process(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=7,
        user_message="Feeling much better today!",
        chat_history=history,
    )
    _check(res_turn2["intent"] == IntentLabel.INTAKE_CONTEXT.value, f"continuation intent is {res_turn2['intent']}")
    _check(res_turn2["target_agent"] == TargetAgent.INTAKE_CONTEXT_AGENT.value, f"continuation target is {res_turn2['target_agent']}")
    # 3. Out-of-order response: Bot asks pain, user answers with walker/mobility
    history.append({"role": "user", "content": "Feeling much better today!"})
    history.append({"role": "assistant", "content": res_turn2["reply"]})

    res_turn3 = LAMOrchestrator.process(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=7,
        user_message="I've been walking short distances with my walker",
        chat_history=history,
    )
    _check(res_turn3["intent"] == IntentLabel.INTAKE_CONTEXT.value, f"out-of-order walker reply stays in intake, got {res_turn3['intent']}")
    _check(res_turn3["target_agent"] == TargetAgent.INTAKE_CONTEXT_AGENT.value, f"target stays IntakeContextAgent, got {res_turn3['target_agent']}")
    _check("pain or discomfort" in res_turn3["reply"].lower() or "rate your pain" in res_turn3["reply"].lower(), "re-prompts for missing pain score")
    _check("tracking your mobility" in res_turn3["reply"].lower() or "great to hear" in res_turn3["reply"].lower(), "acknowledges reported walker mobility")


def main() -> int:
    test_intake_welcome_greeting()
    test_intake_sequential_followups()
    test_exception_unknown_surgery_date()
    test_exception_unknown_pain()
    test_exception_unknown_medications()
    test_informational_qa_during_intake()
    test_vague_answers_bedside_manner()
    test_orchestrator_integration()

    print("=" * 78)
    if _FAILURES:
        print(f"RESULT: {len(_FAILURES)} FAILURE(S)")
        for f in _FAILURES:
            print(f"  - {f}")
        return 1
    print("RESULT: ALL INTAKE & CONTEXT AGENT TESTS PASSED SUCCESSFULLY!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
