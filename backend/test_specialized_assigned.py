"""
Test suite for the assigned specialized agents (Medication, Nutrition, Mental Wellbeing, Report Generation)
Milestone 2 Sections 2.8, 2.11, 2.12, 2.14.

Plain-Python test script runnable directly:
    python test_specialized_assigned.py
"""

from __future__ import annotations

import sys
from typing import Any, Dict
from unittest.mock import patch

from lam.orchestrator import LAMOrchestrator
from lam.schemas import IntentLabel, TargetAgent
from agents.agent_router import AgentRouter
from agents.specialized_agents import (
    MedicationAgent,
    NutritionAgent,
    MentalWellbeingAgent,
)
from agents.report_agent import ReportGenerationAgent

_FAILURES: list[str] = []


def _check(condition: bool, message: str) -> None:
    if not condition:
        _FAILURES.append(message)
        print(f"    !! FAILED: {message}")
    else:
        print(f"    ✓ OK: {message}")


def _stub_answer(reply: str = "stubbed reply"):
    calls = []

    def _fn(**kwargs):
        calls.append(kwargs)
        return {
            "reply": reply,
            "triage_level": "GREEN",
            "is_escalated": False,
            "engine": "Clinical Synthesis Engine",
            "sources": ["Stub Clinical Knowledge Chunk"],
        }
    return _fn, calls


def test_medication_agent():
    print("=" * 78)
    print("1 -- Medication Adherence Agent (Milestone Sec 2.8)")
    print("=" * 78)

    fn, calls = _stub_answer()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        res = LAMOrchestrator.process(
            patient_id="PT-B7-8921",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=4,
            user_message="I forgot my morning blood thinner tablet. Can I double the dose now?",
        )

    _check(res["intent"] == IntentLabel.MEDICATION.value, f"intent should be medication, got {res['intent']}")
    _check(res["target_agent"] == TargetAgent.MEDICATION_AGENT.value, f"target_agent should be MedicationAgent, got {res['target_agent']}")
    _check(len(calls) == 1, "exactly 1 agent dispatch call")
    _check(calls[0].get("domain_instruction") == MedicationAgent.DOMAIN_FOCUS, "MedicationAgent.DOMAIN_FOCUS forwarded")
    _check("never advise a double dose" in MedicationAgent.DOMAIN_FOCUS, "missed-dose protocol included in domain focus")
    _check("not a new prescription" in MedicationAgent.DOMAIN_FOCUS, "strict non-prescribing disclaimer in domain focus")


def test_nutrition_agent():
    print("=" * 78)
    print("2 -- Nutrition & Recovery Diet Agent (Milestone Sec 2.11)")
    print("=" * 78)

    fn, calls = _stub_answer()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        res = LAMOrchestrator.process(
            patient_id="PT-B7-8921",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=5,
            user_message="What high protein foods and vitamins should I eat to heal my knee?",
        )

    _check(res["intent"] == IntentLabel.NUTRITION.value, f"intent should be nutrition, got {res['intent']}")
    _check(res["target_agent"] == TargetAgent.NUTRITION_AGENT.value, f"target_agent should be NutritionAgent, got {res['target_agent']}")
    _check(len(calls) == 1, "exactly 1 agent dispatch call")
    _check(calls[0].get("domain_instruction") == NutritionAgent.DOMAIN_FOCUS, "NutritionAgent.DOMAIN_FOCUS forwarded")
    _check("1.2-1.5 g/kg/day" in NutritionAgent.DOMAIN_FOCUS, "protein target pacing in domain focus")
    _check("constipation" in NutritionAgent.DOMAIN_FOCUS, "opioid constipation guidance in domain focus")


def test_mental_wellbeing_agent():
    print("=" * 78)
    print("3 -- Mental Wellbeing Agent (Milestone Sec 2.12)")
    print("=" * 78)

    fn, calls = _stub_answer()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        res = LAMOrchestrator.process(
            patient_id="PT-B7-8921",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=6,
            user_message="I feel scared to put weight on my knee and frustrated with my progress.",
        )

    _check(res["intent"] == IntentLabel.MENTAL_WELLBEING.value, f"intent should be mental_wellbeing, got {res['intent']}")
    _check(res["target_agent"] == TargetAgent.MENTAL_HEALTH_AGENT.value, f"target_agent should be MentalWellbeingAgent, got {res['target_agent']}")
    _check(len(calls) == 1, "exactly 1 agent dispatch call")
    _check(calls[0].get("domain_instruction") == MentalWellbeingAgent.DOMAIN_FOCUS, "MentalWellbeingAgent.DOMAIN_FOCUS forwarded")
    _check("kinesiophobia" in MentalWellbeingAgent.DOMAIN_FOCUS, "kinesiophobia handling in domain focus")
    _check("Days 3 and 10" in MentalWellbeingAgent.DOMAIN_FOCUS, "recovery dip normalization in domain focus")


def test_report_generation_agent():
    print("=" * 78)
    print("4 -- Report Generation Agent (Milestone Sec 2.14)")
    print("=" * 78)

    summary = ReportGenerationAgent.generate_patient_summary("PT-B7-8921", days=7)
    _check(summary["patient_id"] == "PT-B7-8921", f"patient_id is PT-B7-8921, got {summary['patient_id']}")
    _check("pain_trend" in summary, "summary has pain_trend")
    _check("mobility_progression" in summary, "summary has mobility_progression")
    _check("medication_adherence" in summary, "summary has medication_adherence")
    _check("safety_triage" in summary, "summary has safety_triage")
    _check(len(summary["surgeon_actionable_insights"]) > 0, "summary has actionable insights")

    pdf_bytes = ReportGenerationAgent.export_pdf_report("PT-B7-8921", days=7)
    _check(isinstance(pdf_bytes, bytes), "pdf is bytes")
    _check(len(pdf_bytes) > 500, f"pdf size is substantial ({len(pdf_bytes)} bytes)")
    _check(pdf_bytes.startswith(b"%PDF"), "pdf header starts with %PDF")


def main() -> int:
    test_medication_agent()
    test_nutrition_agent()
    test_mental_wellbeing_agent()
    test_report_generation_agent()

    print("=" * 78)
    if _FAILURES:
        print(f"RESULT: {len(_FAILURES)} FAILURE(S)")
        for f in _FAILURES:
            print(f"  - {f}")
        return 1
    print("RESULT: ALL 4 SPECIALIZED AGENTS VERIFIED SUCCESSFULLY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
