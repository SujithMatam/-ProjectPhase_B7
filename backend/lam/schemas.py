"""
LAM Schemas -- Enums, dataclasses, and shared helpers for the LAM pipeline.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict


class IntentLabel(enum.Enum):
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


class ScopeStatus(enum.Enum):
    IN_SCOPE       = "in_scope"
    OUT_OF_SCOPE   = "out_of_scope"
    NOT_EVALUATED  = "not_evaluated"


class TargetAgent(enum.Enum):
    RECOVERY_AGENT       = "RecoveryProgressAgent"
    PAIN_AGENT           = "PainSymptomsAgent"
    REHAB_AGENT          = "RehabilitationAgent"
    MEDICATION_AGENT     = "MedicationAgent"
    WOUND_CARE_AGENT     = "WoundCareAgent"
    DAILY_ACTIVITY_AGENT = "DailyActivityAgent"
    NUTRITION_AGENT      = "NutritionAgent"
    MENTAL_HEALTH_AGENT  = "MentalWellbeingAgent"
    SAFETY_TRIAGE_AGENT  = "SafetyTriageAgent"
    DEFLECTION_AGENT     = "DeflectionAgent"


class ActionType(enum.Enum):
    INFORM   = "inform"
    ASSESS   = "assess"
    ADVISE   = "advise"
    ESCALATE = "escalate"
    DEFLECT  = "deflect"


PROCEDURE_MAP: dict[str, str] = {
    "total knee arthroplasty": "TKA",
    "knee arthroplasty":       "TKA",
    "knee replacement":        "TKA",
    "tka":                     "TKA",
    "total hip arthroplasty":  "THA",
    "hip arthroplasty":        "THA",
    "hip replacement":         "THA",
    "tha":                     "THA",
}


def resolve_procedure_code(surgery_type: str) -> str:
    lower = surgery_type.lower()
    for keyword, code in PROCEDURE_MAP.items():
        if keyword in lower:
            return code
    return "GEN"


@dataclass
class LAMContext:
    patient_id: str
    surgery_type: str
    affected_limb: str
    postop_day: int
    user_message: str
    surgery_date: Optional[str] = None
    chat_history: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class LAMResult:
    reply:        str
    triage_level: str
    is_escalated: bool
    engine:       str
    sources:      List[str] = field(default_factory=list)
    intent:       str = IntentLabel.OUT_OF_SCOPE.value
    target_agent: str = TargetAgent.DEFLECTION_AGENT.value
    action:       str = ActionType.INFORM.value
    scope_status: str = ScopeStatus.IN_SCOPE.value

    def to_dict(self) -> dict:
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
