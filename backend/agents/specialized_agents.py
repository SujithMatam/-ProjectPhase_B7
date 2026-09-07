"""
Specialized Clinical Agents -- Phase 4.

One class per routable clinical intent, matching the TargetAgent names
already produced by the LAM orchestrator's routing table (lam/orchestrator.py
_ROUTING_TABLE / lam/schemas.py TargetAgent). Each agent is a thin subclass
of BaseClinicalAgent carrying only its TARGET_AGENT identity and a concise
DOMAIN_FOCUS instruction -- these are domain INSTRUCTIONS steering how the
existing RAG + local-LLM pipeline frames its answer, not new clinical facts
or a second knowledge store. All actual retrieval, generation, and fallback
logic is inherited unchanged from BaseClinicalAgent.handle() ->
ChatAgent.answer_question().

EMERGENCY and OUT_OF_SCOPE intentionally have no corresponding class here:
those are deterministic upstream paths (SafetyTriageEngine / ScopeValidator)
that short-circuit in the orchestrator before a specialized agent is ever
dispatched (see agent_router.py).
"""

from __future__ import annotations

from agents.base_clinical_agent import BaseClinicalAgent
from lam.schemas import TargetAgent


class RecoveryProgressAgent(BaseClinicalAgent):
    TARGET_AGENT = TargetAgent.RECOVERY_AGENT
    DOMAIN_FOCUS = (
        "Focus on recovery milestones, expected postoperative progression, and "
        "realistic healing timelines. Do not present an exact recovery date as "
        "guaranteed -- frame timelines as typical ranges, not promises."
    )


class PainSymptomsAgent(BaseClinicalAgent):
    TARGET_AGENT = TargetAgent.PAIN_AGENT
    DOMAIN_FOCUS = (
        "Focus on interpreting postoperative pain, swelling, stiffness, numbness, "
        "and tingling in the context of expected healing. Do not perform emergency "
        "triage or red-flag screening -- that has already been handled upstream."
    )


class RehabilitationAgent(BaseClinicalAgent):
    TARGET_AGENT = TargetAgent.REHAB_AGENT
    DOMAIN_FOCUS = (
        "Focus on physiotherapy, exercises, range of motion, and mobility "
        "progression. Do not invent a specific exercise prescription beyond what "
        "the retrieved clinical context supports."
    )


class MedicationAgent(BaseClinicalAgent):
    TARGET_AGENT = TargetAgent.MEDICATION_AGENT
    DOMAIN_FOCUS = (
        "Focus on medication timing, adherence, and general information questions. "
        "Do not independently prescribe, stop, increase, or decrease any "
        "medication -- defer dosing changes to the patient's clinician."
    )


class WoundCareAgent(BaseClinicalAgent):
    TARGET_AGENT = TargetAgent.WOUND_CARE_AGENT
    DOMAIN_FOCUS = (
        "Focus on incision care, dressings, drainage, and staples/stitches. Do not "
        "perform emergency red-flag detection -- that has already been handled "
        "upstream."
    )


class DailyActivityAgent(BaseClinicalAgent):
    TARGET_AGENT = TargetAgent.DAILY_ACTIVITY_AGENT
    DOMAIN_FOCUS = (
        "Focus on daily activities such as walking, stairs, sleeping position, "
        "bathing, transfers, and driving during recovery."
    )


class NutritionAgent(BaseClinicalAgent):
    TARGET_AGENT = TargetAgent.NUTRITION_AGENT
    DOMAIN_FOCUS = (
        "Focus on postoperative diet, protein intake, hydration, and nutrition "
        "supporting recovery."
    )


class MentalWellbeingAgent(BaseClinicalAgent):
    TARGET_AGENT = TargetAgent.MENTAL_HEALTH_AGENT
    DOMAIN_FOCUS = (
        "Focus on recovery-related anxiety, fear of movement, frustration, and "
        "motivation. Keep guidance supportive and non-diagnostic, staying within "
        "postoperative-support scope."
    )
