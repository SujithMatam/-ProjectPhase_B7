"""Focused deterministic tests for LAM multi-agent coordination."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from agents.agent_router import AgentRouter
from lam.orchestrator import LAMOrchestrator
from lam.schemas import IntentLabel


def _dispatch_calls(calls):
    def dispatch(**kwargs):
        calls.append(kwargs)
        intent = kwargs["intent_label"]
        return {
            "reply": f"{intent.value} response",
            "triage_level": "GREEN",
            "is_escalated": False,
            "engine": "test",
            "sources": [],
        }
    return dispatch


class MultiAgentOrchestrationTests(unittest.TestCase):
    def test_missed_medication_then_wound_handoff(self):
        calls = []
        message = "Since I didn't take my medicine yesterday, my knee wound is worse"
        with patch.object(AgentRouter, "dispatch", side_effect=_dispatch_calls(calls)):
            result = LAMOrchestrator.process(
                patient_id="TEST-PT",
                surgery_type="Total Knee Arthroplasty (TKA)",
                affected_limb="Right",
                postop_day=5,
                user_message=message,
            )

        self.assertEqual(
            [call["intent_label"] for call in calls],
            [IntentLabel.MEDICATION, IntentLabel.WOUND_CARE],
        )
        self.assertEqual(
            [step["intent"] for step in result["execution_plan"]],
            ["medication", "wound_care"],
        )
        self.assertIn("MedicationAgent", result["participating_agents"])
        self.assertIn("WoundCareAgent", result["participating_agents"])
        self.assertIn("[Clinical handoff context]", calls[1]["chat_history"][-1]["content"])

    def test_other_domains_are_ordered_and_share_context(self):
        calls = []
        with patch.object(AgentRouter, "dispatch", side_effect=_dispatch_calls(calls)):
            result = LAMOrchestrator.process(
                patient_id="TEST-PT",
                surgery_type="Total Knee Arthroplasty (TKA)",
                affected_limb="Right",
                postop_day=5,
                user_message="I am anxious, my knee hurts, and I need help with exercises",
            )

        self.assertEqual(
            [step["intent"] for step in result["execution_plan"]],
            ["pain_symptoms", "rehabilitation", "mental_wellbeing"],
        )
        self.assertIn("pain_symptoms response", calls[1]["chat_history"][-1]["content"])

    def test_emergency_precedes_all_agents(self):
        calls = []
        with patch.object(AgentRouter, "dispatch", side_effect=_dispatch_calls(calls)):
            result = LAMOrchestrator.process(
                patient_id="TEST-PT",
                surgery_type="Total Knee Arthroplasty (TKA)",
                affected_limb="Right",
                postop_day=5,
                user_message="I can't breathe and my knee wound is worse",
            )

        self.assertEqual(result["intent"], "emergency")
        self.assertEqual(calls, [])

    def test_single_domain_contract_is_unchanged(self):
        calls = []
        with patch.object(AgentRouter, "dispatch", side_effect=_dispatch_calls(calls)):
            result = LAMOrchestrator.process(
                patient_id="TEST-PT",
                surgery_type="Total Knee Arthroplasty (TKA)",
                affected_limb="Right",
                postop_day=5,
                user_message="How many heel slides should I do?",
            )

        self.assertNotIn("execution_plan", result)
        self.assertEqual(result["intent"], "rehabilitation")

    def test_non_medical_query_is_deflected(self):
        result = LAMOrchestrator.process(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=5,
            user_message="What is the weather like today?",
        )
        self.assertEqual(result["intent"], "out_of_scope")


if __name__ == "__main__":
    unittest.main()
