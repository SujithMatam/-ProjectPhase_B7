""""
Deterministic Safety Triage Engine for Orthopedic Post-Op Recovery
Evaluates critical red-flag clinical symptoms using rule-based decision logic
per American Academy of Orthopaedic Surgeons (AAOS) & NHS Post-Op Protocols.
Runs BEFORE any generative LLM or agent to prevent hallucinations on medical emergencies.

REVISION NOTE (v3):
Exact multi-word phrase matching (e.g. "warm calf", "calf swelling") breaks
on any natural word-order variation a patient actually types (e.g. "my calf
is warm and swollen"). This version replaces fragile phrase lists with
CO-OCCURRENCE RULES: an anchor body-part/location word plus any one of a
set of symptom words, matched independently and in any order/position in
the message. This is far more robust to real patient phrasing than adding
phrase variants one at a time.

Plain multi-word phrases are still used where they are inherently
sequential/idiomatic (e.g. "shortness of breath", "coughing blood") since
those aren't naturally reordered by patients.
"""

import re
from typing import List, Dict, Any


def _build_pattern(terms: List[str]) -> re.Pattern:
    escaped = sorted((re.escape(t) for t in terms), key=len, reverse=True)
    return re.compile(r'\b(?:' + '|'.join(escaped) + r')\b', re.IGNORECASE)


class SafetyTriageEngine:
    # Exact-phrase RED patterns -- kept for genuinely idiomatic/sequential
    # phrases that aren't naturally said in a different word order.
    RED_FLAG_PATTERNS = {
        "Pulmonary Embolism": [
            "shortness of breath", "difficulty breathing", "chest pain",
            "rapid breathing", "coughing blood", "sudden breathlessness",
            "cant breathe", "can't breathe",
        ],
        "Severe Joint Infection / Sepsis": [
            "high fever", "chills", "purulent drainage", "foul smelling pus",
            "wound opening", "wound gaping", "severe spreading redness",
            "pus coming out", "drainage smelling bad", "pus", "oozing pus",
        ],
        "Neurovascular Impairment": [
            "foot cold", "toes pale", "toes blue", "loss of feeling in foot",
            "drop foot", "cannot move toes", "numbness in entire leg",
        ],
    }

    # Co-occurrence rules: fires when an ANCHOR term (body location) AND at
    # least one SYMPTOM term both appear anywhere in the message, regardless
    # of order or exact phrasing. Far more robust than exact phrase lists.
    RED_COOCCURRENCE_RULES = [
        {
            "category": "DVT / Thromboembolism",
            "anchor": ["calf", "lower leg", "shin"],
            "symptom": [
                "warm", "warmth", "swollen", "swelling", "tender",
                "tenderness", "pain", "painful", "ache", "aching", "hot",
                "hard", "firm", "clot",
            ],
        },
    ]

    YELLOW_FLAG_PATTERNS = {
        "Moderate Persistent Wound Drainage": [
            "clear fluid leaking", "serosanguinous", "bandage soaked",
            "yellow fluid", "drainage after day 5", "fluid leaking",
        ],
        "Persistent Moderate Fever": [
            "mild fever", "temperature 38", "feeling hot", "feverish",
        ],
        "Significant Joint Swelling / ROM Regression": [
            "knee cannot bend", "stiffness getting worse", "swelling increasing",
            "cannot bear weight anymore", "sudden severe pain increase",
        ],
        "Wound Redness or Warmth": [
            "redness", "red and swollen", "red around", "warm to touch",
            "hot to touch", "red",
        ],
        "General Swelling Report": [
            "swelling", "swollen", "puffy", "puffiness",
        ],
    }

    # Compound-signal escalation: if 2+ of these categories fire together,
    # bump the result up one level (YELLOW -> RED) since co-occurring
    # signals near the surgical site are a stronger indicator than either
    # alone (e.g. redness + swelling together suggests infection more
    # strongly than swelling alone, which is common and often benign).
    _COMPOUND_ESCALATION_CATEGORIES = {
        "Wound Redness or Warmth",
        "General Swelling Report",
    }
    _COMPOUND_MIN_CATEGORIES_TO_ESCALATE = 2

    @classmethod
    def evaluate(cls, symptoms: str, temperature_c: float = None, post_op_day: int = 1) -> Dict[str, Any]:
        symptom_lower = symptoms.lower()
        red_flags_detected: List[str] = []
        yellow_flags_detected: List[str] = []
        yellow_categories_hit: set = set()

        # Check objective temperature threshold
        if temperature_c is not None:
            if temperature_c >= 38.5:
                red_flags_detected.append(f"High fever detected ({temperature_c}°C >= 38.5°C)")
            elif temperature_c >= 37.8:
                yellow_flags_detected.append(f"Low-grade / moderate fever ({temperature_c}°C)")

        # Evaluate exact-phrase Red Flags
        for category, triggers in cls.RED_FLAG_PATTERNS.items():
            pattern = _build_pattern(triggers)
            match = pattern.search(symptom_lower)
            if match:
                red_flags_detected.append(f"{category} indicator: '{match.group()}'")

        # Evaluate co-occurrence Red Flags (anchor + symptom, any order)
        for rule in cls.RED_COOCCURRENCE_RULES:
            anchor_pattern = _build_pattern(rule["anchor"])
            symptom_pattern = _build_pattern(rule["symptom"])
            anchor_match = anchor_pattern.search(symptom_lower)
            symptom_match = symptom_pattern.search(symptom_lower)
            if anchor_match and symptom_match:
                red_flags_detected.append(
                    f"{rule['category']} indicator: "
                    f"'{anchor_match.group()}' + '{symptom_match.group()}'"
                )

        # Evaluate Yellow Flags
        for category, triggers in cls.YELLOW_FLAG_PATTERNS.items():
            pattern = _build_pattern(triggers)
            match = pattern.search(symptom_lower)
            if match:
                yellow_flags_detected.append(f"{category} indicator: '{match.group()}'")
                yellow_categories_hit.add(category)

        # Compound-signal escalation: 2+ co-occurring moderate-concern
        # categories (e.g. redness AND swelling together) escalate YELLOW -> RED.
        compound_hit_count = len(yellow_categories_hit & cls._COMPOUND_ESCALATION_CATEGORIES)
        should_escalate_compound = (
            not red_flags_detected
            and compound_hit_count >= cls._COMPOUND_MIN_CATEGORIES_TO_ESCALATE
        )

        # Triage Assignment
        if red_flags_detected:
            return {
                "triage_level": "RED",
                "urgency": "EMERGENCY - IMMEDIATE CLINICAL ESCALATION REQUIRED",
                "status_code": 3,
                "reasons": red_flags_detected,
                "action_protocol": (
                    "Immediate contact with hospital emergency triage or operating surgeon. "
                    "Do NOT wait. Suspected complication requires physical examination and immediate Doppler/bloodwork."
                ),
                "is_escalated": True,
            }

        if should_escalate_compound:
            return {
                "triage_level": "RED",
                "urgency": "EMERGENCY - IMMEDIATE CLINICAL ESCALATION REQUIRED",
                "status_code": 3,
                "reasons": yellow_flags_detected + [
                    "Multiple co-occurring wound-site warning signs detected "
                    "(e.g. redness combined with swelling) - treated as a possible "
                    "surgical site infection indicator requiring urgent review."
                ],
                "action_protocol": (
                    "Contact your hospital emergency triage or operating surgeon promptly. "
                    "Co-occurring redness and swelling near the surgical site should be "
                    "evaluated the same day."
                ),
                "is_escalated": True,
            }

        elif yellow_flags_detected:
            return {
                "triage_level": "YELLOW",
                "urgency": "MODERATE RISK - SAME DAY / NEXT MORNING SURGEON CONTACT",
                "status_code": 2,
                "reasons": yellow_flags_detected,
                "action_protocol": (
                    "Contact the orthopedic nursing hotline or schedule same-day follow-up. "
                    "Elevate limb, apply cold therapy (20 mins per session), and closely monitor wound."
                ),
                "is_escalated": True,
            }
        else:
            return {
                "triage_level": "GREEN",
                "urgency": "NORMAL RECOVERY PROTOCOL",
                "status_code": 1,
                "reasons": ["Symptoms within normal expected postoperative trajectory."],
                "action_protocol": (
                    "Continue prescribed home rehabilitation exercises, cryotherapy, elevation, "
                    "and oral medication schedule. Log next check-in as scheduled."
                ),
                "is_escalated": False,
            }

