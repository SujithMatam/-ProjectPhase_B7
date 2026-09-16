"""Deterministic coordinator for turns that contain multiple clinical domains."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.agent_router import AgentRouter
from lam.schemas import ActionType, IntentLabel, TargetAgent


# Lower values run first.  Medication is intentionally before wound care:
# adherence and missed-dose precautions must be established before assessing
# deterioration that may be related to treatment.
_DOMAIN_PRIORITY = {
    IntentLabel.MEDICATION: 10,
    IntentLabel.WOUND_CARE: 20,
    IntentLabel.PAIN_SYMPTOMS: 30,
    IntentLabel.REHABILITATION: 40,
    IntentLabel.DAILY_ACTIVITY: 50,
    IntentLabel.NUTRITION: 60,
    IntentLabel.MENTAL_WELLBEING: 70,
    IntentLabel.RECOVERY_PROGRESS: 80,
    IntentLabel.INTAKE_CONTEXT: 90,
}

_TARGETS = {
    IntentLabel.RECOVERY_PROGRESS: TargetAgent.RECOVERY_AGENT,
    IntentLabel.PAIN_SYMPTOMS: TargetAgent.PAIN_AGENT,
    IntentLabel.REHABILITATION: TargetAgent.REHAB_AGENT,
    IntentLabel.MEDICATION: TargetAgent.MEDICATION_AGENT,
    IntentLabel.WOUND_CARE: TargetAgent.WOUND_CARE_AGENT,
    IntentLabel.DAILY_ACTIVITY: TargetAgent.DAILY_ACTIVITY_AGENT,
    IntentLabel.NUTRITION: TargetAgent.NUTRITION_AGENT,
    IntentLabel.MENTAL_WELLBEING: TargetAgent.MENTAL_HEALTH_AGENT,
    IntentLabel.INTAKE_CONTEXT: TargetAgent.INTAKE_CONTEXT_AGENT,
}

_ACTIONS = {
    IntentLabel.PAIN_SYMPTOMS: ActionType.ASSESS,
    IntentLabel.REHABILITATION: ActionType.ADVISE,
    IntentLabel.WOUND_CARE: ActionType.ADVISE,
    IntentLabel.MENTAL_WELLBEING: ActionType.ADVISE,
}


class MultiAgentCoordinator:
    """Runs applicable agents serially with an auditable shared handoff."""

    @classmethod
    def order_intents(cls, intents: tuple[IntentLabel, ...]) -> list[IntentLabel]:
        unique = list(dict.fromkeys(intents))
        return sorted(unique, key=lambda intent: _DOMAIN_PRIORITY.get(intent, 999))

    @classmethod
    def execute(
        cls,
        *,
        intents: tuple[IntentLabel, ...],
        dispatch_kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        ordered = cls.order_intents(intents)
        shared_history: List[Dict[str, str]] = list(
            dispatch_kwargs.get("chat_history") or []
        )
        results: list[dict[str, Any]] = []
        handoffs: list[dict[str, Any]] = []

        for index, intent in enumerate(ordered, start=1):
            agent_history = list(shared_history)
            if handoffs:
                agent_history.append({
                    "role": "assistant",
                    "content": (
                        "[Clinical handoff context] Prior agent findings are "
                        "provided for continuity. Do not repeat questions already "
                        "answered; do not contradict a safety precaution. "
                        + " | ".join(
                            f"{item['agent']}: {item['summary']}"
                            for item in handoffs
                        )
                    ),
                })

            call_kwargs = dict(dispatch_kwargs)
            call_kwargs["intent_label"] = intent
            call_kwargs["chat_history"] = agent_history
            result = AgentRouter.dispatch(**call_kwargs)
            result = dict(result or {})
            agent_name = _TARGETS.get(intent, TargetAgent.DEFLECTION_AGENT).value
            summary = str(result.get("reply", "")).strip()
            handoffs.append({
                "step": index,
                "intent": intent.value,
                "agent": agent_name,
                "summary": summary,
            })
            results.append(result)

        replies = []
        for item in handoffs:
            replies.append(f"**{item['agent']}**\n{item['summary']}")

        return {
            "ordered_intents": ordered,
            "results": results,
            "handoffs": handoffs,
            "reply": "\n\n".join(replies),
            "engine": "Deterministic Multi-Agent Coordinator",
            "target_agent": ",".join(_TARGETS[intent].value for intent in ordered),
            "action": ",".join(
                _ACTIONS.get(intent, ActionType.INFORM).value for intent in ordered
            ),
        }
