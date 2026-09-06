"""
LAM Orchestrator -- controls the full LAM pipeline for /api/chat.
Execution order (safety-first):
  1. Deterministic safety triage.
  2. Scope validation.
  3. Intent classification.
  4. Agent/action routing.
  5. Specialized agent execution.
"""

from __future__ import annotations

from typing import Optional, List, Dict

from triage.safety_triage import SafetyTriageEngine
from agents.agent_router import AgentRouter
from lam.schemas import (
    IntentLabel, ScopeStatus, TargetAgent, ActionType,
    LAMContext, LAMResult, resolve_procedure_code,
)
from lam.scope_validator import ScopeValidator
from lam.intent_classifier import IntentClassifier


_ROUTING_TABLE: dict[IntentLabel, tuple[TargetAgent, ActionType]] = {
    IntentLabel.RECOVERY_PROGRESS: (TargetAgent.RECOVERY_AGENT,       ActionType.INFORM),
    IntentLabel.PAIN_SYMPTOMS:     (TargetAgent.PAIN_AGENT,            ActionType.ASSESS),
    IntentLabel.REHABILITATION:    (TargetAgent.REHAB_AGENT,           ActionType.ADVISE),
    IntentLabel.MEDICATION:        (TargetAgent.MEDICATION_AGENT,      ActionType.INFORM),
    IntentLabel.WOUND_CARE:        (TargetAgent.WOUND_CARE_AGENT,      ActionType.ADVISE),
    IntentLabel.DAILY_ACTIVITY:    (TargetAgent.DAILY_ACTIVITY_AGENT,  ActionType.INFORM),
    IntentLabel.NUTRITION:         (TargetAgent.NUTRITION_AGENT,       ActionType.INFORM),
    IntentLabel.MENTAL_WELLBEING:  (TargetAgent.MENTAL_HEALTH_AGENT,   ActionType.ADVISE),
    IntentLabel.EMERGENCY:         (TargetAgent.SAFETY_TRIAGE_AGENT,   ActionType.ESCALATE),
    IntentLabel.OUT_OF_SCOPE:      (TargetAgent.DEFLECTION_AGENT,      ActionType.DEFLECT),
}

_OUT_OF_SCOPE_REPLY = (
    "I'm OrthoSync, a specialised assistant for orthopedic post-operative recovery. "
    "Your question doesn't appear to be related to your surgical recovery or orthopedic care. "
    "For general health questions, please consult your GP or a relevant healthcare professional. "
    "If you have a question about your recovery, wound, pain, medication, or rehabilitation, "
    "I'm here to help!"
)


class LAMOrchestrator:
    @classmethod
    def process(
        cls,
        patient_id: str,
        surgery_type: str,
        affected_limb: str,
        postop_day: int,
        user_message: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        surgery_date: Optional[str] = None,
    ) -> dict:
        # The context is passed through the LAM, but deterministic triage below
        # always evaluates the CURRENT user message first.
        context = LAMContext(
            patient_id=patient_id,
            surgery_type=surgery_type,
            affected_limb=affected_limb,
            postop_day=postop_day,
            user_message=user_message,
            surgery_date=surgery_date,
            chat_history=chat_history or [],
        )

        # STEP 1 -- Deterministic Safety Triage (ALWAYS FIRST)
        triage = SafetyTriageEngine.evaluate(
            symptoms=user_message,
            post_op_day=postop_day,
        )

        if triage["triage_level"] == "RED":
            reply_text = (
                "\U0001f6a8 **CRITICAL EMERGENCY ALERT**\n\n"
                f"Your symptoms require urgent medical evaluation: "
                f"**{', '.join(triage['reasons'])}**.\n\n"
                f"{triage['action_protocol']}\n\n"
                "Please contact your hospital emergency line or visit the nearest "
                "emergency department right away."
            )
            return LAMResult(
                reply=reply_text,
                triage_level="RED",
                is_escalated=True,
                engine="Deterministic Safety Triage",
                sources=[],
                intent=IntentLabel.EMERGENCY.value,
                target_agent=TargetAgent.SAFETY_TRIAGE_AGENT.value,
                action=ActionType.ESCALATE.value,
                scope_status=ScopeStatus.NOT_EVALUATED.value,
            ).to_dict()

        # STEP 2 -- Scope Validation
        scope_status, scope_reason = ScopeValidator.validate(
            query=user_message,
            surgery_type=surgery_type,
        )

        if scope_status == ScopeStatus.OUT_OF_SCOPE:
            return LAMResult(
                reply=_OUT_OF_SCOPE_REPLY,
                triage_level=triage["triage_level"],
                is_escalated=triage["is_escalated"],
                engine="Scope Validator",
                sources=[],
                intent=IntentLabel.OUT_OF_SCOPE.value,
                target_agent=TargetAgent.DEFLECTION_AGENT.value,
                action=ActionType.DEFLECT.value,
                scope_status=ScopeStatus.OUT_OF_SCOPE.value,
            ).to_dict()

        # STEP 3 -- Intent Classification
        intent_label: IntentLabel = IntentClassifier.classify(
            query=user_message,
            context=context,
        )

        # STEP 4 -- Agent / Action Routing
        target_agent, action_type = cls._route(intent_label)

        # STEP 5 -- Specialized Agent Execution
        resolved_procedure = resolve_procedure_code(surgery_type)
        chat_result = AgentRouter.dispatch(
            intent_label=intent_label,
            patient_id=patient_id,
            surgery_type=surgery_type,
            affected_limb=affected_limb,
            postop_day=postop_day,
            user_message=user_message,
            procedure=resolved_procedure,
            chat_history=context.chat_history,
            surgery_date=surgery_date,
            precomputed_triage=triage,
        )

        return LAMResult(
            reply=chat_result["reply"],
            triage_level=chat_result["triage_level"],
            is_escalated=chat_result["is_escalated"],
            engine=chat_result["engine"],
            sources=chat_result.get("sources", []),
            intent=intent_label.value,
            target_agent=target_agent.value,
            action=action_type.value,
            scope_status=ScopeStatus.IN_SCOPE.value,
        ).to_dict()

    @classmethod
    def _route(
        cls,
        intent_label: IntentLabel,
    ) -> tuple[TargetAgent, ActionType]:
        return _ROUTING_TABLE.get(
            intent_label,
            (TargetAgent.DEFLECTION_AGENT, ActionType.INFORM),
        )
