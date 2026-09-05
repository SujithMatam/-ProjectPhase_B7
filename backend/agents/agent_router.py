"""
Agent Router -- Phase 4 dispatcher from a classified routable intent to its
specialized clinical agent.

Called by LAMOrchestrator AFTER deterministic safety triage, scope
validation, and semantic intent classification have already run and the
query has already been determined to be a normal, in-scope, non-emergency
clinical question. This dispatcher is never reached for EMERGENCY or
OUT_OF_SCOPE -- those short-circuit upstream in the orchestrator before
Step 5, and this module has no code path that can produce either label.

This mapping only covers the 8 routable clinical intents on purpose --
EMERGENCY and OUT_OF_SCOPE are handled exclusively by SafetyTriageEngine and
ScopeValidator respectively, upstream of this dispatcher.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Type

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
from lam.schemas import IntentLabel

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
    """Looks up and executes the specialized agent for a classified intent."""

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
        precomputed_triage: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the specialized agent mapped to `intent_label`.

        `precomputed_triage`: the LAM orchestrator's already-computed
        SafetyTriageEngine result for this request (RED already
        short-circuited upstream if it applied), passed straight through so
        neither this dispatcher nor the agent it invokes re-runs safety
        triage a second time for the same request.

        Defensive fallback: if `intent_label` has no mapped specialized
        agent (not expected for the 8 routable intents, which is all that
        can legitimately reach this method -- EMERGENCY/OUT_OF_SCOPE never
        do), degrade to the plain generic ChatAgent path rather than
        crashing or fabricating a result. This fallback never produces
        EMERGENCY or OUT_OF_SCOPE; it is simply the unspecialized generic
        response for an ordinary in-scope query.
        """
        agent_cls = _AGENT_BY_INTENT.get(intent_label)
        if agent_cls is None:
            return ChatAgent.answer_question(
                patient_id=patient_id,
                surgery_type=surgery_type,
                affected_limb=affected_limb,
                postop_day=postop_day,
                user_message=user_message,
                procedure=procedure,
                precomputed_triage=precomputed_triage,
            )

        return agent_cls.handle(
            patient_id=patient_id,
            surgery_type=surgery_type,
            affected_limb=affected_limb,
            postop_day=postop_day,
            user_message=user_message,
            procedure=procedure,
            precomputed_triage=precomputed_triage,
        )
