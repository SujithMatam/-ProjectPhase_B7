"""
Agent Router -- Phase 4 dispatcher from classified routable intent to its
specialized clinical agent.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Type, List

from agents.base_clinical_agent import BaseClinicalAgent
from agents.chat_agent import ChatAgent
from agents.specialized_agents import (
    DailyActivityAgent,
    MedicationAgent,
    MentalWellbeingAgent,
    NutritionAgent,
    PainSymptomsAgent,
    RecoveryProgressAgent,
    RehabilitationAgent,
    WoundCareAgent,
)
from lam.schemas import IntentLabel, WeightBearingStatus


_AGENT_BY_INTENT: Dict[IntentLabel, Type[BaseClinicalAgent]] = {
    IntentLabel.RECOVERY_PROGRESS: RecoveryProgressAgent,
    IntentLabel.PAIN_SYMPTOMS: PainSymptomsAgent,
    IntentLabel.REHABILITATION: RehabilitationAgent,
    IntentLabel.MEDICATION: MedicationAgent,
    IntentLabel.WOUND_CARE: WoundCareAgent,
    IntentLabel.DAILY_ACTIVITY: DailyActivityAgent,
    IntentLabel.NUTRITION: NutritionAgent,
    IntentLabel.MENTAL_WELLBEING: MentalWellbeingAgent,
}


class AgentRouter:
    @classmethod
    def dispatch(
        cls,
        *,
        intent_label: IntentLabel,
        patient_id: str,
        surgery_type: str,
        affected_limb: str,
        postop_day: int,
        user_message: str,
        procedure: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        surgery_date: Optional[str] = None,
        precomputed_triage: Optional[Dict[str, Any]] = None,
        pain_score: Optional[int] = None,
        pain_characteristics: Optional[str] = None,
        swelling_description: Optional[str] = None,
        temperature_c: Optional[float] = None,
        weight_bearing_status: Optional[WeightBearingStatus] = None,
        current_rom: Optional[str] = None,
        exercise_history: Optional[str] = None,
    ) -> Dict[str, Any]:
        agent_cls = _AGENT_BY_INTENT.get(intent_label)

        if agent_cls is None:
            return ChatAgent.answer_question(
                patient_id=patient_id,
                surgery_type=surgery_type,
                affected_limb=affected_limb,
                postop_day=postop_day,
                user_message=user_message,
                chat_history=chat_history,
                procedure=procedure,
                precomputed_triage=precomputed_triage,
                surgery_date=surgery_date,
            )

        if agent_cls is PainSymptomsAgent:
            # PainSymptomsAgent (Milestone Sec 2.6) is the only agent that
            # accepts structured symptom fields -- forwarded here rather
            # than added to BaseClinicalAgent.handle()'s shared signature,
            # which would otherwise force all 7 unrelated agents to carry
            # parameters they never use.
            return PainSymptomsAgent.handle(
                patient_id=patient_id,
                surgery_type=surgery_type,
                affected_limb=affected_limb,
                postop_day=postop_day,
                user_message=user_message,
                procedure=procedure,
                chat_history=chat_history,
                surgery_date=surgery_date,
                precomputed_triage=precomputed_triage,
                pain_score=pain_score,
                pain_characteristics=pain_characteristics,
                swelling_description=swelling_description,
                temperature_c=temperature_c,
            )

        if agent_cls is RehabilitationAgent:
            # RehabilitationAgent (Milestone Sec 2.7) is the only agent that
            # accepts structured rehab fields -- forwarded here rather than
            # added to BaseClinicalAgent.handle()'s shared signature, for
            # the same reason as PainSymptomsAgent above.
            return RehabilitationAgent.handle(
                patient_id=patient_id,
                surgery_type=surgery_type,
                affected_limb=affected_limb,
                postop_day=postop_day,
                user_message=user_message,
                procedure=procedure,
                chat_history=chat_history,
                surgery_date=surgery_date,
                precomputed_triage=precomputed_triage,
                weight_bearing_status=weight_bearing_status,
                current_rom=current_rom,
                exercise_history=exercise_history,
            )

        return agent_cls.handle(
            patient_id=patient_id,
            surgery_type=surgery_type,
            affected_limb=affected_limb,
            postop_day=postop_day,
            user_message=user_message,
            procedure=procedure,
            chat_history=chat_history,
            surgery_date=surgery_date,
            precomputed_triage=precomputed_triage,
        )
