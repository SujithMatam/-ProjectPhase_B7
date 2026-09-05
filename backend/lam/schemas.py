"""
LAM Schemas -- Enums, dataclasses, and shared helpers for the LAM pipeline.

Defines:
  - IntentLabel      : the 10 supported chatbot intents
  - ScopeStatus      : IN_SCOPE / OUT_OF_SCOPE / NOT_EVALUATED
  - TargetAgent      : future specialised agent names (Phase 2+)
  - ActionType       : action verbs, separate from intent labels
  - PROCEDURE_MAP    : surgery-type keyword -> ClinicalKnowledgeBase procedure code
  - resolve_procedure_code() : shared helper used by orchestrator AND ChatAgent
  - LAMContext       : patient context passed through the pipeline
  - LAMResult        : full orchestrator response (superset of /api/chat fields)
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional, List


# ---------------------------------------------------------------------------
# Intent vocabulary
# ---------------------------------------------------------------------------

class IntentLabel(enum.Enum):
    """Supported chatbot intent domains for orthopedic post-op care."""
    RECOVERY_PROGRESS  = "recovery_progress"
    PAIN_SYMPTOMS      = "pain_symptoms"
    REHABILITATION     = "rehabilitation"
    MEDICATION         = "medication"
    WOUND_CARE         = "wound_care"
    DAILY_ACTIVITY     = "daily_activity"
    NUTRITION          = "nutrition"
    MENTAL_WELLBEING   = "mental_wellbeing"
    EMERGENCY          = "emergency"
    OUT_OF_SCOPE       = "out_of_scope"


# ---------------------------------------------------------------------------
# Scope classification
# ---------------------------------------------------------------------------

class ScopeStatus(enum.Enum):
    """Whether the query falls within the orthopedic post-op care domain."""
    IN_SCOPE       = "in_scope"
    OUT_OF_SCOPE   = "out_of_scope"
    NOT_EVALUATED  = "not_evaluated"


# ---------------------------------------------------------------------------
# Target agents (Phase 2 specialised agents -- named here for routing)
# ---------------------------------------------------------------------------

class TargetAgent(enum.Enum):
    """
    Future specialised agent names.
    Phase 1: all non-emergency, in-scope queries are still handled by ChatAgent.
    Phase 2+: each intent will route to its dedicated specialist agent.
    """
    RECOVERY_AGENT     = "RecoveryProgressAgent"
    PAIN_AGENT         = "PainSymptomsAgent"
    REHAB_AGENT        = "RehabilitationAgent"
    MEDICATION_AGENT   = "MedicationAgent"
    WOUND_CARE_AGENT   = "WoundCareAgent"
    DAILY_ACTIVITY_AGENT = "DailyActivityAgent"
    NUTRITION_AGENT    = "NutritionAgent"
    MENTAL_HEALTH_AGENT = "MentalWellbeingAgent"
    SAFETY_TRIAGE_AGENT = "SafetyTriageAgent"   # handles EMERGENCY intent
    DEFLECTION_AGENT   = "DeflectionAgent"       # handles OUT_OF_SCOPE


# ---------------------------------------------------------------------------
# Action types  (separate from intent labels -- do not conflate)
# ---------------------------------------------------------------------------

class ActionType(enum.Enum):
    """
    Action verbs that describe what the selected agent should DO.
    These are orthogonal to intent labels.
    """
    INFORM   = "inform"    # provide educational information
    ASSESS   = "assess"    # gather/evaluate symptom data
    ADVISE   = "advise"    # give a specific clinical recommendation
    ESCALATE = "escalate"  # route to emergency protocol
    DEFLECT  = "deflect"   # politely redirect out-of-scope query


# ---------------------------------------------------------------------------
# Procedure mapping
# ---------------------------------------------------------------------------

PROCEDURE_MAP: dict[str, str] = {
    # TKA: explicit knee arthroplasty/replacement
    "total knee arthroplasty": "TKA",
    "knee arthroplasty":       "TKA",
    "knee replacement":        "TKA",
    "tka":                     "TKA",

    # THA: explicit hip arthroplasty/replacement
    "total hip arthroplasty":  "THA",
    "hip arthroplasty":        "THA",
    "hip replacement":         "THA",
    "tha":                     "THA",
}


def resolve_procedure_code(surgery_type: str) -> str:
    """
    Map a free-text surgery_type string to a ClinicalKnowledgeBase procedure code.

    Scans PROCEDURE_MAP keywords against the lowercased surgery_type string.
    Returns 'GEN' for any unknown or unsupported procedure type.

    NOTE: Never returns 'TKA' as a silent catch-all default.
    Unknown types are deliberately mapped to 'GEN' so that the knowledge base's
    procedure='All' documents are still surfaced without misleading protocol match.
    """
    lower = surgery_type.lower()
    for keyword, code in PROCEDURE_MAP.items():
        if keyword in lower:
            return code
    return "GEN"  # unknown / unsupported -- never silently TKA


# ---------------------------------------------------------------------------
# Pipeline context and result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class LAMContext:
    """Patient context threaded through the LAM pipeline."""
    patient_id:   str
    surgery_type: str
    affected_limb: str
    postop_day:   int
    user_message: str


@dataclass
class LAMResult:
    """
    Full orchestrator response.
    Preserved fields (backward-compatible with existing /api/chat response):
        reply, triage_level, is_escalated, engine, sources
    New LAM metadata fields:
        intent, target_agent, action, scope_status
    """
    # --- preserved fields (must always be present) ---
    reply:        str
    triage_level: str
    is_escalated: bool
    engine:       str
    sources:      List[str] = field(default_factory=list)

    # --- new LAM metadata fields ---
    intent:       str = IntentLabel.OUT_OF_SCOPE.value
    target_agent: str = TargetAgent.DEFLECTION_AGENT.value
    action:       str = ActionType.INFORM.value
    scope_status: str = ScopeStatus.IN_SCOPE.value

    def to_dict(self) -> dict:
        """Serialise to a plain dict suitable for FastAPI JSON responses."""
        return {
            "reply":        self.reply,
            "triage_level": self.triage_level,
            "is_escalated": self.is_escalated,
            "engine":       self.engine,
            "sources":      self.sources,
            "intent":       self.intent,
            "target_agent": self.target_agent,
            "action":       self.action,
            "scope_status": self.scope_status,
        }
