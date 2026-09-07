"""
Deterministic Safety Triage Engine for Orthopedic Post-Op Recovery
Evaluates critical red-flag clinical symptoms using rule-based decision logic
per American Academy of Orthopaedic Surgeons (AAOS) & NHS Post-Op Protocols.
Runs BEFORE any generative LLM or agent to prevent hallucinations on medical emergencies.
"""

from typing import List, Dict, Any

class SafetyTriageEngine:
    # High-risk trigger phrases
    RED_FLAG_PATTERNS = {
        "DVT / Thromboembolism": [
            "calf pain", "calf swelling", "calf tenderness", "warm calf", 
            "leg clot", "swollen lower leg", "pain in back of lower leg",
            "dvt", "deep vein"
        ],
        "Pulmonary Embolism": [
            "shortness of breath", "difficulty breathing", "chest pain", 
            "rapid breathing", "coughing blood", "sudden breathlessness", "cant breathe"
        ],
        "Severe Joint Infection / Sepsis": [
            "high fever", "chills", "purulent drainage", "foul smelling pus", 
            "wound opening", "wound gaping", "severe spreading redness",
            "pus coming out", "drainage smelling bad"
        ],
        "Neurovascular Impairment": [
            "foot cold", "toes pale", "toes blue", "loss of feeling in foot", 
            "drop foot", "cannot move toes", "numbness in entire leg"
        ]
    }

    YELLOW_FLAG_PATTERNS = {
        "Moderate Persistent Wound Drainage": [
            "clear fluid leaking", "serosanguinous", "bandage soaked", 
            "yellow fluid", "drainage after day 5"
        ],
        "Persistent Moderate Fever": [
            "mild fever", "temperature 38", "feeling hot", "feverish"
        ],
        "Significant Joint Swelling / ROM Regression": [
            "knee cannot bend", "stiffness getting worse", "swelling increasing",
            "cannot bear weight anymore", "sudden severe pain increase"
        ]
    }

    @classmethod
    def evaluate(cls, symptoms: str, temperature_c: float = None, post_op_day: int = 1) -> Dict[str, Any]:
        symptom_lower = symptoms.lower()
        red_flags_detected = []
        yellow_flags_detected = []

        # Check objective temperature threshold
        if temperature_c is not None:
            if temperature_c >= 38.5:
                red_flags_detected.append(f"High fever detected ({temperature_c}°C ≥ 38.5°C)")
            elif temperature_c >= 37.8:
                yellow_flags_detected.append(f"Low-grade / moderate fever ({temperature_c}°C)")

        # Evaluate Red Flags
        for category, triggers in cls.RED_FLAG_PATTERNS.items():
            for trigger in triggers:
                if trigger in symptom_lower:
                    red_flags_detected.append(f"{category} indicator: '{trigger}'")
                    break

        # Evaluate Yellow Flags
        for category, triggers in cls.YELLOW_FLAG_PATTERNS.items():
            for trigger in triggers:
                if trigger in symptom_lower:
                    yellow_flags_detected.append(f"{category} indicator: '{trigger}'")
                    break

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
                "is_escalated": True
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
                "is_escalated": True
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
                "is_escalated": False
            }
