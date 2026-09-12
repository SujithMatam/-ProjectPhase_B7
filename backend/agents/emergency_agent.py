"""
Emergency Escalation Agent.

Handles any query that reaches this point flagged as EMERGENCY - whether
by the Step 1 deterministic keyword triage (handled directly in the
orchestrator, never reaches here) OR by the Step 3 semantic intent
classifier catching something the keyword list missed.

CRITICAL DESIGN RULE: This agent's patient-facing response is 100%
deterministic, template-based text. It NEVER calls the LLM to generate
the emergency message itself. The whole point of a dedicated escalation
agent is that a patient's safety instruction cannot depend on model
output quality, hallucination risk, or inference latency.

The LLM/RAG pipeline may still be used AFTER this response is sent, e.g.
to draft supplementary context for the physician's alert - but never to
compose what the patient sees on a suspected emergency.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional


_ESCALATION_TEMPLATE = (
    "\U0001f6a8 **This may be a medical emergency.**\n\n"
    "Based on what you've described{trigger_clause}, please take the "
    "following steps right away:\n\n"
    "1. If you have any of the following: chest pain, difficulty breathing, "
    "sudden severe swelling, or loss of consciousness - call your local "
    "emergency number immediately.\n"
    "2. Otherwise, contact your hospital's emergency/orthopedic on-call line "
    "as soon as possible.\n"
    "3. Do not wait for a reply in this chat before seeking care.\n\n"
    "Your care team has been notified of this alert."
)


class EmergencyEscalationAgent:
    """
    Deterministic-only handler for EMERGENCY-classified queries that reach
    the specialized agent layer (i.e. did NOT already short-circuit via
    Step 1 keyword triage in the orchestrator).
    """

    @classmethod
    def handle(
        cls,
        *,
        patient_id: str,
        surgery_type: str,
        affected_limb: str,
        postop_day: int,
        user_message: str,
        procedure: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        surgery_date: Optional[str] = None,
        precomputed_triage: Optional[Dict[str, Any]] = None,
        **_ignored,
    ) -> Dict[str, Any]:

        trigger_reasons = []
        if precomputed_triage and precomputed_triage.get("reasons"):
            trigger_reasons = precomputed_triage["reasons"]

        trigger_clause = (
            f" ({', '.join(trigger_reasons)})" if trigger_reasons else ""
        )

        reply_text = _ESCALATION_TEMPLATE.format(trigger_clause=trigger_clause)

        cls._notify_care_team(
            patient_id=patient_id,
            user_message=user_message,
            trigger_reasons=trigger_reasons,
            postop_day=postop_day,
        )

        return {
            "reply": reply_text,
            "triage_level": "RED",
            "is_escalated": True,
            "engine": "Emergency Escalation Agent (deterministic)",
            "sources": [],
        }

    @classmethod
    def _notify_care_team(
        cls,
        *,
        patient_id: str,
        user_message: str,
        trigger_reasons: List[str],
        postop_day: int,
    ) -> None:
        """
        Placeholder - wire this to your actual EncryptedSQLite alert table
        and notification dispatcher.
        """
        print(
            f"[EMERGENCY ALERT QUEUED] patient={patient_id} "
            f"day={postop_day} reasons={trigger_reasons} "
            f"message={user_message!r}"
        )