"""Base Clinical Agent -- shared interface for Phase 4 specialized agents."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.chat_agent import ChatAgent
from lam.schemas import TargetAgent


class BaseClinicalAgent:
    TARGET_AGENT: TargetAgent
    DOMAIN_FOCUS: str

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
    ) -> Dict[str, Any]:
        return ChatAgent.answer_question(
            patient_id=patient_id,
            surgery_type=surgery_type,
            affected_limb=affected_limb,
            postop_day=postop_day,
            user_message=user_message,
            chat_history=chat_history,
            procedure=procedure,
            domain_instruction=cls.DOMAIN_FOCUS,
            precomputed_triage=precomputed_triage,
            surgery_date=surgery_date,
        )
from agents.base_clinical_agent import BaseClinicalAgent
from lam.schemas import TargetAgent

class IntakeContextAgent(BaseClinicalAgent):
    TARGET_AGENT = TargetAgent.INTAKE_CONTEXT_AGENT
    DOMAIN_FOCUS = (
        "You are the Intake & Context Agent. Consolidate the patient's postoperative information, "
        "recent interactions, and relevant clinical context before processing a task. "
        "Organize the relevant patient information required for downstream agent processing."
    )

class WoundCareAgent(BaseClinicalAgent):
    TARGET_AGENT = TargetAgent.WOUND_CARE_AGENT
    DOMAIN_FOCUS = (
        "You are the Wound Care & Imaging Agent. Provide guidance related to postoperative incision care. "
        "Assess observations for potentially concerning characteristics such as excessive redness, swelling, "
        "wound separation, or abnormal drainage."
    )

class DailyActivityAgent(BaseClinicalAgent):
    TARGET_AGENT = TargetAgent.DAILY_ACTIVITY_AGENT
    DOMAIN_FOCUS = (
        "You are the Daily Activity & ADL Agent. Provide guidance for safely performing Activities of "
        "Daily Living (ADL) such as walking, stair navigation, sleeping positions, and transfers. "
        "Apply procedure-specific precautions and postoperative restrictions."
    )

class SafetyTriageAgent(BaseClinicalAgent):
    TARGET_AGENT = TargetAgent.SAFETY_TRIAGE_AGENT
    DOMAIN_FOCUS = (
        "You are the Emergency Escalation Agent. Handle cases classified as high-risk RED. "
        "Provide immediate escalation guidance for the patient and forward the relevant emergency "
        "information to the Clinician Interface."
    )