"""
Proactive Medication Adherence & Verification Engine.

Manages conversational state, medication verification, dosage analysis,
proactive follow-ups, and safety protocols for the Medication Agent within
the LAM multi-agent architecture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from agents.report_agent import ReportGenerationAgent


@dataclass
class MedicationCheckinState:
    patient_id: str
    stage: str = "awaiting_adherence"  # awaiting_adherence, awaiting_med_name_or_dose, awaiting_time, awaiting_other_meds, completed
    current_med_name: Optional[str] = None
    reported_dose: Optional[str] = None
    reported_time: Optional[str] = None
    adherence_status: Optional[str] = None  # "taken", "missed", "delayed", "dosage_error", "uncertain"
    verified_prescription: Optional[Dict[str, Any]] = None
    other_meds_checked: bool = False
    late_hours: Optional[float] = None
    reported_pain_score: Optional[int] = None
    turn_count: int = 0


# In-memory conversational state per patient (with session timeout / clean reset)
_PATIENT_MED_STATES: Dict[str, MedicationCheckinState] = {}


class ProactiveMedicationEngine:
    """
    Engine that inspects patient medication records, analyzes user utterance,
    tracks multi-turn conversational context, detects dosage and adherence anomalies,
    and returns contextual next questions or clinical escalations.
    """

    @classmethod
    def get_state(cls, patient_id: str) -> MedicationCheckinState:
        clean_id = (patient_id or "PT-B7-8921").strip().upper()
        if clean_id not in _PATIENT_MED_STATES:
            _PATIENT_MED_STATES[clean_id] = MedicationCheckinState(patient_id=clean_id)
        return _PATIENT_MED_STATES[clean_id]

    @classmethod
    def reset_state(cls, patient_id: str) -> None:
        clean_id = (patient_id or "PT-B7-8921").strip().upper()
        if clean_id in _PATIENT_MED_STATES:
            del _PATIENT_MED_STATES[clean_id]

    @classmethod
    def get_prescribed_medications(cls, patient_id: str) -> List[Dict[str, Any]]:
        record = ReportGenerationAgent.get_patient_record(patient_id)
        return record.get("current_medications", [])

    @classmethod
    def match_prescribed_medication(
        cls, med_mention: str, prescribed_meds: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        if not med_mention:
            return None
        m_lower = med_mention.lower()
        for med in prescribed_meds:
            name = med.get("name", "").lower()
            purpose = med.get("purpose", "").lower()
            if name in m_lower or m_lower in name:
                return med
            # Functional aliases
            if "pain" in m_lower and any(kw in name or kw in purpose for kw in ["paracetamol", "analgesia", "oxycodone", "tramadol"]):
                return med
            if ("blood thinner" in m_lower or "clot" in m_lower or "injection" in m_lower) and any(kw in name or kw in purpose for kw in ["enoxaparin", "aspirin", "dvt"]):
                return med
            if "antibiotic" in m_lower and "antibiotic" in (name + purpose):
                return med
            if "stool" in m_lower or "constipation" in m_lower:
                if "docusate" in name or "stool" in purpose:
                    return med
        return None

    @classmethod
    def extract_medication_entities(
        cls, text: str, prescribed_meds: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extracts medication name, dose, timing, and intent signals from patient text.
        """
        extracted: Dict[str, Any] = {
            "med_name": None,
            "dose": None,
            "time": None,
            "is_taken": None,
            "is_missed": None,
            "is_dosage_error": False,
            "dosage_error_detail": None,
            "is_uncertain": False,
            "is_stopped": False,
            "has_side_effects": False,
            "side_effect_detail": None,
            "matched_prescribed": None,
        }
        lower = text.lower()

        # Adherence status
        if (
            any(kw in lower for kw in ["i took", "taken", "i had", "already took", "finished my dose"])
            or re.search(r"\byes\b", lower)
        ):
            extracted["is_taken"] = True
        if (
            any(
                kw in lower
                for kw in [
                    "forgot", "missed", "haven't taken", "havent taken",
                    "didn't take", "did not take", "skipped", "not yet",
                ]
            )
            or re.search(r"\bno\b", lower)
        ):
            extracted["is_missed"] = True
            extracted["is_taken"] = False

        # Stopping medication
        if any(kw in lower for kw in ["stop taking", "stopped taking", "stopped my", "quit taking", "discontinue"]):
            extracted["is_stopped"] = True

        # Uncertainty about dose
        if any(kw in lower for kw in [
            "don't remember", "dont remember", "not sure what dose",
            "not sure about dose", "forgot the dose", "don't know the dose",
            "dont know the dose", "what dose am i supposed"
        ]):
            extracted["is_uncertain"] = True

        side_effect_terms = [
            "side effect", "adverse reaction", "rash", "hives", "itching",
            "vomiting", "vomit", "severe nausea", "dizzy", "dizziness",
            "very sleepy", "sleepiness", "confused", "swelling of my lips",
            "swelling of my face", "allergic",
        ]
        matched_side_effect = next(
            (term for term in side_effect_terms if term in lower), None
        )
        if matched_side_effect:
            extracted["has_side_effects"] = True
            extracted["side_effect_detail"] = matched_side_effect

        # Dosage errors (e.g. took two tablets instead of one, doubled dose, extra pill)
        if any(kw in lower for kw in [
            "took two tablets instead of one",
            "took 2 tablets instead of 1",
            "took extra",
            "double dose",
            "doubled the dose",
            "took more than",
            "took too much",
            "accidentally took two",
            "accidentally took 2",
            "two pills instead of one",
            "2 pills instead of 1",
        ]):
            extracted["is_dosage_error"] = True
            extracted["dosage_error_detail"] = "Reported taking higher than prescribed dosage"

        # Medication Name
        for med in prescribed_meds:
            name = med.get("name", "").lower()
            if name in lower:
                extracted["med_name"] = med.get("name")
                extracted["matched_prescribed"] = med
                break
        if not extracted["med_name"]:
            # Check generic terms
            if "blood thinner" in lower or "anticoagulant" in lower:
                extracted["med_name"] = "Blood Thinner (Anticoagulant)"
                matched = cls.match_prescribed_medication("blood thinner", prescribed_meds)
                extracted["matched_prescribed"] = matched
            elif "pain medicine" in lower or "painkiller" in lower or "pain medication" in lower:
                extracted["med_name"] = "Pain Medication"
                matched = cls.match_prescribed_medication("pain", prescribed_meds)
                extracted["matched_prescribed"] = matched
            elif "antibiotic" in lower:
                extracted["med_name"] = "Antibiotic"
                matched = cls.match_prescribed_medication("antibiotic", prescribed_meds)
                extracted["matched_prescribed"] = matched
            elif "aspirin" in lower:
                extracted["med_name"] = "Aspirin"
                matched = cls.match_prescribed_medication("aspirin", prescribed_meds)
                extracted["matched_prescribed"] = matched

        # Dose extraction (e.g. 500 mg, 650mg, 40mg, 1 tablet, 2 tablets, 5mg)
        dose_match = re.search(r"\b(\d+(?:\.\d+)?\s*(?:mg|g|mcg|ml|tablets?|pills?|capsules?))\b", lower)
        if dose_match:
            extracted["dose"] = dose_match.group(1).strip()

        # Time extraction (e.g. at 9 am, 9:00, morning, 8 pm)
        time_match = re.search(r"\b(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\bmorning\b|\bnight\b|\bafternoon\b|\bevening\b)\b", lower)
        if time_match and any(t in lower for t in ["am", "pm", ":", "morning", "night", "evening", "at "]):
            extracted["time"] = time_match.group(0).strip()

        return extracted

    @staticmethod
    def _extract_missed_dose_follow_up(text: str) -> Dict[str, Any]:
        hours_match = re.search(
            r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\s*(?:late|ago)?\b",
            text.lower(),
        )
        pain_match = re.search(
            r"\bpain(?:\s+level)?\s*(?:is|=|:)?\s*(10|[0-9])\b",
            text.lower(),
        )
        return {
            "hours": float(hours_match.group(1)) if hours_match else None,
            "pain": int(pain_match.group(1)) if pain_match else None,
        }

    @classmethod
    def _informational_reply(
        cls,
        message: str,
        state: MedicationCheckinState,
        prescribed: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Answer ordinary medication questions from the patient's record."""
        lower = message.lower()
        medication_question = any(
            marker in lower
            for marker in (
                "dose", "dosage", "when", "how often", "take", "medication",
                "medicine", "pill", "tablet", "prescription", "what is",
                "paracetamol", "enoxaparin", "aspirin", "antibiotic",
                "painkiller", "blood thinner", "anticoagulant", "anticoagulants",
                "anticaogulant", "anticaogulants",
                "interact", "interaction", "combine", "together", "safe with",
            )
        )
        if not medication_question:
            return None

        selected = None
        explicit_medication_reference = any(
            marker in lower
            for marker in (
                "paracetamol", "enoxaparin", "aspirin", "oxycodone", "tramadol",
                "docusate", "anticoagulant", "anticoagulants", "blood thinner",
                "anticaogulant", "anticaogulants", "antibiotic", "painkiller",
            )
        )
        if prescribed:
            selected = next(
                (
                    med for med in prescribed
                    if med.get("name", "").lower() in lower
                ),
                None,
            )
        if selected is None and not explicit_medication_reference and state.current_med_name:
            selected = next(
                (
                    med for med in prescribed
                    if med.get("name", "").lower() == state.current_med_name.lower()
                ),
                None,
            )

        asks_dose = any(marker in lower for marker in ("dose", "dosage"))
        asks_timing = any(
            marker in lower
            for marker in (
                "when", "how often", "take it", "next dose", "schedule",
                "what time", "at what time", "time should",
            )
        )
        asks_purpose = any(
            marker in lower for marker in ("what is", "used for", "why", "purpose")
        )

        asks_quantity = any(marker in lower for marker in ("how many", "how much", "number of"))

        if selected:
            name = selected.get("name", "this medication")
            dose = selected.get("dose") or "the dose printed on your prescription label"
            purpose = selected.get("purpose")
            if asks_timing:
                return (
                    f"For **{name}**, follow the timing and frequency on your "
                    f"prescription label ({dose}); I cannot safely infer exact clock "
                    "times from this chat. If you are unsure when the next dose is "
                    "due, confirm with your pharmacist or surgical team. Do not "
                    "take an extra dose to catch up."
                )
            if asks_dose:
                return (
                    f"Your postoperative record lists **{name}** as **{dose}**"
                    + (f" for {purpose.lower()}." if purpose else ".")
                    + " Please verify that against the label on your bottle before "
                    "taking it; do not change the dose based on this chat."
                )
            if asks_purpose:
                purpose_text = purpose.lower() if purpose else "your postoperative treatment"
                return (
                    f"**{name}** is listed for {purpose_text}. Take it only as prescribed, and "
                    "check with your clinician or pharmacist before changing it."
                )
            if asks_quantity:
                return (
                    f"Only take the number of **{name}** doses or tablets written on "
                    f"your prescription label ({dose}). Do not add another blood "
                    "thinner or take extra tablets unless your prescriber explicitly "
                    "tells you to. If the label is unclear, ask your pharmacist."
                )
            if any(marker in lower for marker in ("interact", "interaction", "combine", "together", "safe with")):
                return (
                    f"I can confirm that **{name}** is on your postoperative record, "
                    "but I cannot safely approve combining it with another medicine "
                    "without the complete medication list. Check with your pharmacist "
                    "before taking it with anything new."
                )
            return (
                f"I found **{name}** in your postoperative medication record. "
                f"It is listed as {dose}"
                + (f" for {purpose.lower()}." if purpose else ".")
                + " What would you like to know about its timing, purpose, or safety?"
            )

        if asks_dose or asks_timing or asks_quantity:
            if not prescribed:
                return (
                    "I cannot verify a medication or dose from your record. "
                    "Please check the prescription label or discharge instructions "
                    "and contact your pharmacist or surgical team before taking it."
                )
            medication_list = "; ".join(
                f"{med.get('name', 'Unnamed medication')}: "
                f"{med.get('dose') or 'see label'}"
                for med in prescribed
            )
            return (
                f"Your postoperative record lists: {medication_list}. "
                "Use each medicine only according to its own label and do not "
                "combine or double doses. Which medication are you asking about?"
            )

        return (
            "I can help explain a medication in your postoperative record. "
            "Tell me its name, or ask about its purpose, prescribed dose, timing, "
            "or a possible side effect."
        )

    @classmethod
    def evaluate_turn(
        cls,
        patient_id: str,
        user_message: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        postop_day: int = 1,
    ) -> Dict[str, Any]:
        """
        Main agentic reasoning loop for Medication Agent.
        Evaluates state, history, entities, and builds a contextual, proactive response.
        """
        state = cls.get_state(patient_id)
        prescribed = cls.get_prescribed_medications(patient_id)
        lower_msg = user_message.lower().strip()
        state.turn_count += 1

        # 1. Check history to populate state from previous turns if not yet populated
        if chat_history and state.turn_count <= 1:
            for turn in chat_history:
                if turn.get("role") == "user":
                    prev_ent = cls.extract_medication_entities(turn.get("content", ""), prescribed)
                    if prev_ent["med_name"] and not state.current_med_name:
                        state.current_med_name = prev_ent["med_name"]
                        state.verified_prescription = prev_ent["matched_prescribed"]
                    if prev_ent["dose"] and not state.reported_dose:
                        state.reported_dose = prev_ent["dose"]
                    if prev_ent["time"] and not state.reported_time:
                        state.reported_time = prev_ent["time"]

        # 2. Extract current turn entities
        current_ent = cls.extract_medication_entities(user_message, prescribed)
        missed_follow_up = cls._extract_missed_dose_follow_up(user_message)
        if missed_follow_up["hours"] is not None:
            state.late_hours = missed_follow_up["hours"]
        if missed_follow_up["pain"] is not None:
            state.reported_pain_score = missed_follow_up["pain"]

        # Merge extracted entities into state
        if current_ent["med_name"]:
            state.current_med_name = current_ent["med_name"]
            if current_ent["matched_prescribed"]:
                state.verified_prescription = current_ent["matched_prescribed"]
        if current_ent["dose"]:
            state.reported_dose = current_ent["dose"]
        if current_ent["time"]:
            state.reported_time = current_ent["time"]

        # =====================================================================
        # CASE A: DOSAGE ERROR / OVERDOSE SAFETY ESCALATION
        # =====================================================================
        if current_ent["is_dosage_error"]:
            state.adherence_status = "dosage_error"
            reply = (
                "⚠️ **Dosage Alert: Important Safety Protocol**\n\n"
                "You mentioned taking more than your prescribed dose (or taking two tablets instead of one). "
                "Please do **not** take any further medication until you speak with your clinician.\n\n"
                "1. Check the exact medication packaging right now.\n"
                "2. If you feel any dizziness, shortness of breath, nausea, or severe sleepiness, call emergency medical services immediately.\n"
                "3. Contact your orthopedic on-call team or pharmacist immediately to report the double dose so they can advise on when your next scheduled dose should resume.\n\n"
                "*I have flagged this dosage event for urgent care team review.*"
            )
            return {
                "reply": reply,
                "triage_level": "YELLOW",
                "is_escalated": True,
                "engine": "Medication Proactive Safety Engine",
                "action": "escalate",
                "state": state.__dict__,
            }

        # =====================================================================
        # CASE B: POSSIBLE MEDICATION SIDE EFFECT / ADVERSE REACTION
        # =====================================================================
        if current_ent["has_side_effects"]:
            state.adherence_status = "side_effect"
            detail = current_ent["side_effect_detail"]
            reply = (
                "Thank you for reporting a possible medication side effect"
                f" ({detail}). Do not start, stop, or change the medication on your own. "
                "Please contact your prescribing clinician or pharmacist promptly "
                "with the medication name, dose on the label, and when the symptom started. "
                "If symptoms are severe or rapidly worsening, seek urgent medical care."
            )
            return {
                "reply": reply,
                "triage_level": "YELLOW",
                "is_escalated": True,
                "engine": "Medication Proactive Safety Engine",
                "action": "escalate",
                "state": state.__dict__,
            }

        # =====================================================================
        # CASE C: UNCERTAINTY ABOUT PRESCRIBED DOSE
        # =====================================================================
        if current_ent["is_uncertain"]:
            state.adherence_status = "uncertain"
            if prescribed:
                med_list_str = "\n".join([f"- **{m['name']}**: {m.get('dose', 'See label')} ({m.get('purpose', 'Post-op care')})" for m in prescribed])
                reply = (
                    "It is very important never to guess your medication dosage. "
                    "According to your postoperative hospital record, your prescribed medications are:\n\n"
                    f"{med_list_str}\n\n"
                    "Please verify this against the label on your prescription bottle. "
                    "Which of these medications were you unsure about taking today?"
                )
            else:
                reply = (
                    "It is very important never to guess your medication dosage. "
                    "I cannot verify your exact prescription doses right now. "
                    "Please check the printed discharge instructions or the label on your medicine bottle, "
                    "or call your surgical team/pharmacist before taking the medicine. "
                    "What is the name of the medicine on your bottle?"
                )
            return {
                "reply": reply,
                "triage_level": "GREEN",
                "is_escalated": False,
                "engine": "Medication Proactive Adherence Engine",
                "action": "advise",
                "state": state.__dict__,
            }

        # =====================================================================
        # CASE C: PATIENT STOPPING MEDICATION INDEPENDENTLY
        # =====================================================================
        if current_ent["is_stopped"]:
            state.adherence_status = "stopped"
            reply = (
                "⚠️ **Medication Caution: Stopping Prescribed Treatment**\n\n"
                "Stopping postoperative medications prematurely—especially anticoagulants (blood thinners) "
                "or antibiotics—can significantly increase the risk of blood clots or surgical site infections.\n\n"
                "Could you tell me which medication you are considering stopping, and whether you are experiencing side effects like nausea or an upset stomach?"
            )
            return {
                "reply": reply,
                "triage_level": "YELLOW",
                "is_escalated": True,
                "engine": "Medication Proactive Adherence Engine",
                "action": "advise",
                "state": state.__dict__,
            }

        # =====================================================================
        # CASE D: MISSED MEDICATION
        # =====================================================================
        if current_ent["is_missed"] or any(kw in lower_msg for kw in ["i haven't taken", "havent taken", "forgot to take", "missed my"]):
            state.adherence_status = "missed"
            if state.current_med_name:
                reply = (
                    f"Thank you for letting me know that you missed your **{state.current_med_name}**. "
                    "General orthopedic safety protocol: take the missed dose as soon as you remember, "
                    "unless it is almost time for your next scheduled dose. **Never take a double dose** to make up for a missed one.\n\n"
                    f"How many hours late is this dose, and how is your pain level right now?"
                )
            else:
                # Proactively inquire which medicine was missed
                state.stage = "awaiting_med_name_or_dose"
                reply = (
                    "Thank you for letting me know. Managing your medications on time is essential for optimal recovery. "
                    "Which specific medication was missed, and was it your morning or evening dose?"
                )
            return {
                "reply": reply,
                "triage_level": "GREEN",
                "is_escalated": False,
                "engine": "Medication Proactive Adherence Engine",
                "action": "advise",
                "state": state.__dict__,
            }

        # Answer the follow-up requested by the medication agent itself. This
        # must remain on the medication route even when the reply mentions
        # pain, because it supplies missed-dose timing context rather than a
        # new standalone pain complaint.
        if (
            state.adherence_status == "missed"
            and (state.late_hours is not None or state.reported_pain_score is not None)
        ):
            med_name = state.current_med_name or "the missed medication"
            pain_text = (
                f" Your reported pain level is {state.reported_pain_score}/10."
                if state.reported_pain_score is not None
                else ""
            )
            timing_text = (
                f" You are about {state.late_hours:g} hour(s) late."
                if state.late_hours is not None
                else ""
            )
            return {
                "reply": (
                    f"Thanks for the update about **{med_name}**.{timing_text}{pain_text}\n\n"
                    "Because this is a missed dose, do not take an extra dose to catch up. "
                    "Check the prescription label for its missed-dose instructions; if the "
                    "next dose is due soon, or you are unsure, contact your pharmacist or "
                    "surgical team before taking it. If your pain is severe, worsening, or "
                    "not controlled by the prescribed plan, contact your care team."
                ),
                "triage_level": "GREEN",
                "is_escalated": False,
                "engine": "Medication Proactive Adherence Engine",
                "action": "advise",
                "state": state.__dict__,
            }

        # =====================================================================
        # CASE E: PURE GREETING / INITIATE PROACTIVE CHECK-IN
        # e.g., "Hi", "Hello", "Check-in"
        # =====================================================================
        if lower_msg in ["hi", "hello", "hey", "good morning", "good afternoon", "check in", "medication check"]:
            state.stage = "awaiting_adherence"
            reply = "Hi! I'd like to quickly check on your medication. Have you taken your prescribed medication today?"
            return {
                "reply": reply,
                "triage_level": "GREEN",
                "is_escalated": False,
                "engine": "Medication Proactive Adherence Engine",
                "action": "assess",
                "state": state.__dict__,
            }

        # =====================================================================
        # CASE F: PATIENT REPLIED "YES" TO ADHERENCE CHECK
        # =====================================================================
        if lower_msg in ["yes", "yeah", "yep", "i have", "yes i have", "yes i took it"]:
            state.stage = "awaiting_med_name_or_dose"
            state.adherence_status = "taken"
            reply = "Good. Which medication did you take, and what dose did you take?"
            return {
                "reply": reply,
                "triage_level": "GREEN",
                "is_escalated": False,
                "engine": "Medication Proactive Adherence Engine",
                "action": "assess",
                "state": state.__dict__,
            }

        # =====================================================================
        # CASE G: VAGUE MEDICATION (e.g. "I took the pain medicine")
        # Need specific name and dose
        # =====================================================================
        if (state.current_med_name and not state.reported_dose and not state.verified_prescription) or lower_msg in ["i took the pain medicine", "pain medicine", "pain meds"]:
            state.stage = "awaiting_med_name_or_dose"
            reply = "Thanks. Do you know the name of the medication and the prescribed dose?"
            return {
                "reply": reply,
                "triage_level": "GREEN",
                "is_escalated": False,
                "engine": "Medication Proactive Adherence Engine",
                "action": "assess",
                "state": state.__dict__,
            }

        # =====================================================================
        # CASE H: PATIENT PROVIDED SPECIFIC MEDICATION + DOSE (or time missing)
        # e.g. "I took Paracetamol 500 mg at 9 AM" or "At 9 AM. I took 500 mg."
        # =====================================================================
        if state.reported_dose and state.reported_time and not state.other_meds_checked:
            state.other_meds_checked = True
            state.stage = "awaiting_other_meds"
            med_display = state.current_med_name or "your medication"
            # Find if there are other medications in prescription
            other_names = [m["name"] for m in prescribed if m.get("name", "").lower() not in (state.current_med_name or "").lower()]
            other_hint = f" (such as {', '.join(other_names)})" if other_names else ""
            reply = (
                f"Thanks. I've recorded that you took {med_display} ({state.reported_dose}) at {state.reported_time}. "
                f"Do you still have any other scheduled medication to take today{other_hint}?"
            )
            return {
                "reply": reply,
                "triage_level": "GREEN",
                "is_escalated": False,
                "engine": "Medication Proactive Adherence Engine",
                "action": "assess",
                "state": state.__dict__,
            }

        if state.stage == "awaiting_other_meds":
            if "yes" in lower_msg or any(kw in lower_msg for kw in ["antibiotic", "blood thinner", "aspirin", "enoxaparin"]):
                specific = "your antibiotic" if "antibiotic" in lower_msg else "that medication"
                reply = f"Have you taken today's {specific} dose?"
                state.stage = "completed"
                return {
                    "reply": reply,
                    "triage_level": "GREEN",
                    "is_escalated": False,
                    "engine": "Medication Proactive Adherence Engine",
                    "action": "assess",
                    "state": state.__dict__,
                }
            elif "no" in lower_msg or "none" in lower_msg or "all done" in lower_msg:
                reply = "Great job staying consistent with your medication schedule today. Keeping regular timing is key to smooth recovery and keeping pain well managed."
                state.stage = "completed"
                return {
                    "reply": reply,
                    "triage_level": "GREEN",
                    "is_escalated": False,
                    "engine": "Medication Proactive Adherence Engine",
                    "action": "inform",
                    "state": state.__dict__,
                }

        # Ordinary medication questions should be answered by the stateful
        # medication agent rather than the generic repeated chat fallback.
        informational_reply = cls._informational_reply(
            user_message,
            state,
            prescribed,
        )
        if informational_reply:
            return {
                "reply": informational_reply,
                "triage_level": "GREEN",
                "is_escalated": False,
                "engine": "Medication Proactive Information Engine",
                "action": "inform",
                "state": state.__dict__,
            }

        # If dose is known but time is missing
        if state.reported_dose and not state.reported_time:
            reply = f"Good. What time did you take it, and did you take the prescribed dose?"
            return {
                "reply": reply,
                "triage_level": "GREEN",
                "is_escalated": False,
                "engine": "Medication Proactive Adherence Engine",
                "action": "assess",
                "state": state.__dict__,
            }

        # =====================================================================
        # DEFAULT PROACTIVE / CLINICAL RESPONSE
        # =====================================================================
        reply = (
            "I'm keeping track of your postoperative medication adherence. "
            "Please confirm if you have taken your scheduled doses for today, and let me know if you have any questions about timing or missed doses."
        )
        return {
            "reply": reply,
            "triage_level": "GREEN",
            "is_escalated": False,
            "engine": "Medication Proactive Adherence Engine",
            "action": "inform",
            "state": state.__dict__,
        }
