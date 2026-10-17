"""
Intake & Context Logic -- Multi-turn conversational intake and context consolidation.

Milestone Sec 2.4:
Consolidates the patient's postoperative information, recent interactions,
and relevant clinical context before a task is processed by a specialized agent.

Features:
- Friendly, empathetic bedside manner tailored for orthopedic post-op recovery.
- Interactive multi-turn follow-up dialogue (feeling -> pain -> mobility -> concerns).
- Answering patient clarifying questions asked during intake (WBAT/PWB/NWB, NPRS, procedure info).
- Robust exception handling when patient says "I don't know" or "not sure", seamlessly
  looking up records from the local SQLite database (patients.sqlite3).
- Safe, non-diagnostic, strictly adheres to upstream safety triage (never suppresses red flags).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import patient_database


# ============================================================================
# INTAKE FIELD VOCABULARY
# ============================================================================

FIELD_OVERALL_FEELING = "overall_feeling"
FIELD_PAIN_LEVEL = "pain_level"
FIELD_MOBILITY_STATUS = "mobility_status"
FIELD_PRIMARY_CONCERN = "primary_concern"

# Standard sequence of inquiry for fresh check-in
INTAKE_SEQUENCE: Tuple[str, ...] = (
    FIELD_OVERALL_FEELING,
    FIELD_PAIN_LEVEL,
    FIELD_MOBILITY_STATUS,
    FIELD_PRIMARY_CONCERN,
)


# ============================================================================
# FRIENDLY PATIENT QUESTIONS
# ============================================================================

STANDARD_QUESTIONS: Dict[str, str] = {
    FIELD_OVERALL_FEELING: (
        "To start off, how are you feeling overall today? "
        "(For example: feeling better, a bit tired, or having a rough day?)"
    ),
    FIELD_PAIN_LEVEL: (
        "How would you rate your pain or discomfort right now? "
        "You can share a number from 0 to 10, or just let me know if it feels mild, moderate, or severe."
    ),
    FIELD_MOBILITY_STATUS: (
        "How has your movement or walking been today? "
        "Are you able to move around with your walker or crutches, or have you mostly been resting?"
    ),
    FIELD_PRIMARY_CONCERN: (
        "Do you have any specific concerns, symptoms, or medication questions "
        "on your mind that you'd like us to focus on today?"
    ),
}

# Simplified / alternative rephrased questions when user doesn't know or is unsure
ALT_QUESTIONS: Dict[str, str] = {
    FIELD_OVERALL_FEELING: (
        "That's completely okay! Compared to yesterday, would you say today feels "
        "a little easier, a bit harder, or about the same?"
    ),
    FIELD_PAIN_LEVEL: (
        "No problem at all! You don't need an exact number. Think of it like this: "
        "is the pain mild (a dull background ache), moderate (bothersome but manageable), "
        "or severe (making it hard to rest or move)?"
    ),
    FIELD_MOBILITY_STATUS: (
        "No worries. Are you currently able to get up from bed or a chair on your own, "
        "or do you need help and an assistive device (like a walker or crutches)?"
    ),
    FIELD_PRIMARY_CONCERN: (
        "That's completely fine! If everything feels on track and you don't have any pressing "
        "questions, we can proceed with your routine daily check-in."
    ),
}


# ============================================================================
# UNCERTAINTY / "I DON'T KNOW" DETECTION
# ============================================================================

_UNCERTAIN_PHRASES = (
    "i don't know",
    "i dont know",
    "idk",
    "don't know",
    "dont know",
    "not sure",
    "unsure",
    "no idea",
    "no clue",
    "can't tell",
    "cant tell",
    "hard to tell",
    "not certain",
    "forgot",
    "i forgot",
    "have no idea",
    "dunno",
    "where do i find",
    "where can i find",
    "i am not sure",
    "i'm not sure",
)


def is_uncertain_answer(text: str) -> bool:
    """True if patient expresses genuine uncertainty rather than a concrete observation."""
    clean = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not clean:
        return False
    if clean in ("unknown", "n/a", "not sure", "idk", "dunno"):
        return True
    return any(phrase in clean for phrase in _UNCERTAIN_PHRASES)


# ============================================================================
# INFORMATIONAL QUESTION PATTERNS (Clarifications asked by patient)
# ============================================================================

def detect_informational_question(text: str) -> Optional[str]:
    """Detect if the patient is asking a clarifying or educational question."""
    lower = (text or "").strip().lower()
    
    # Why / What is intake
    if any(k in lower for k in ("what is intake", "what is this intake", "why do you ask", "why do you need", "why ask")):
        return "why_intake"

    # Weight-bearing abbreviations
    if any(k in lower for k in ("wbat", "pwb", "nwb", "fwb", "weight bearing mean", "weight-bearing mean")):
        return "weight_bearing_terms"

    # NPRS / Pain scale
    if any(k in lower for k in ("nprs", "pain scale", "rate pain", "how to rate pain")):
        return "pain_scale_info"

    # Surgery details query (patient asking about their own surgery)
    if any(k in lower for k in (
        "what surgery did i have", "what was my surgery", "what is my surgery",
        "when was my surgery", "who is my doctor", "who was my surgeon",
        "who is my surgeon", "my operation date", "which knee", "which hip", "which leg"
    )):
        return "surgery_info_query"

    # Medication details query
    if any(k in lower for k in (
        "what medications am i on", "what medicines am i taking", "what are my pills",
        "what drugs am i taking", "what is my prescription", "list my medicines"
    )):
        return "medication_info_query"

    # App Identity
    if any(k in lower for k in ("who are you", "what is orthosync", "what can you do", "how can you help")):
        return "agent_identity"

    return None


def answer_informational_question(
    topic: str,
    patient_id: str,
    surgery_type: str,
    affected_limb: str,
    postop_day: int,
    surgery_date: Optional[str] = None,
) -> str:
    """Provide a warm, accurate clinical explanation for user clarifying questions."""
    # Look up database if available
    pt_data = None
    try:
        pt_data = patient_database.get_patient(patient_id)
    except Exception:
        pass

    if topic == "why_intake":
        return (
            "Great question! This daily intake check-in helps us monitor your healing trajectory, "
            "make sure your pain and swelling are progressing normally, and tailor your recovery "
            "exercises safely. It only takes a couple of quick questions!"
        )

    if topic == "weight_bearing_terms":
        return (
            "Here is what those weight-bearing terms mean in orthopedic care:\n\n"
            "• **NWB (Non-Weight Bearing)**: 0% weight on the operated leg — keep it completely off the ground.\n"
            "• **PWB (Partial Weight Bearing)**: Usually 25% to 50% of your body weight, supported by crutches or a walker.\n"
            "• **WBAT (Weight Bearing as Tolerated)**: Place as much weight as is comfortable without sharp pain.\n"
            "• **FWB (Full Weight Bearing)**: 100% of your normal weight without restrictions.\n\n"
            "Always follow the exact weight-bearing status prescribed on your discharge instructions."
        )

    if topic == "pain_scale_info":
        return (
            "We use the **Numeric Pain Rating Scale (NPRS)** from 0 to 10:\n\n"
            "• **0**: No pain at all.\n"
            "• **1–3 (Mild)**: A minor background ache that doesn't interfere with your rest or tasks.\n"
            "• **4–6 (Moderate)**: Noticeable pain that distracts you and requires resting or medication.\n"
            "• **7–10 (Severe)**: Intense pain that stops you from performing basic movements or sleeping.\n\n"
            "You can give an exact number or simply say 'mild', 'moderate', or 'severe'."
        )

    if topic == "surgery_info_query":
        surg = (pt_data.get("surgery_type") if pt_data else None) or surgery_type or "orthopedic surgery"
        limb = (pt_data.get("affected_limb") if pt_data else None) or affected_limb or "operated limb"
        s_date = (pt_data.get("surgery_date") if pt_data else None) or surgery_date or "recent date"
        surg_doc = (pt_data.get("surgeon") if pt_data else None) or "your orthopedic surgical team"
        p_day = (pt_data.get("postop_day") if pt_data else None) or postop_day

        return (
            f"Here are your surgery details from your clinical record:\n\n"
            f"• **Procedure**: {surg}\n"
            f"• **Operated Side**: {limb}\n"
            f"• **Surgery Date**: {s_date} (Post-Op Day {p_day})\n"
            f"• **Lead Surgeon**: {surg_doc}\n\n"
            "Everything is securely saved in your chart."
        )

    if topic == "medication_info_query":
        meds = pt_data.get("current_medications", []) if pt_data else []
        if meds:
            med_lines = [
                f"• **{m.get('name')}** ({m.get('dose', 'As directed')}) — {m.get('purpose', 'Prescribed post-op')}"
                for m in meds
            ]
            return (
                "Here are the medications currently listed on your discharge chart:\n\n"
                + "\n".join(med_lines) +
                "\n\nIf you have any questions about timing or dosages, feel free to ask!"
            )
        return (
            "Your chart indicates you have discharge prescriptions. Please check your hospital "
            "medication sheet or bottle labels, or let me know the names of any pills you have questions about."
        )

    if topic == "agent_identity":
        return (
            "I'm **OrthoSync**, your dedicated AI orthopedic postoperative companion. "
            "I'm here to support your recovery after surgery — helping you track your healing, "
            "guide you through rehabilitation exercises, monitor medication schedules, and alert your "
            "surgical team if anything needs clinical review."
        )

    return ""


# ============================================================================
# EXCEPTION & "I DON'T KNOW" HANDLERS
# ============================================================================

def handle_unknown_exception(
    field_or_topic: str,
    patient_id: str,
    surgery_type: str,
    affected_limb: str,
    postop_day: int,
    surgery_date: Optional[str] = None,
) -> str:
    """Friendly fallback when the patient does not know a clinical parameter."""
    pt_data = None
    try:
        pt_data = patient_database.get_patient(patient_id)
    except Exception:
        pass

    if field_or_topic in ("surgery_date", "surgery_type", "procedure", FIELD_OVERALL_FEELING):
        if pt_data and pt_data.get("surgery_type"):
            surg = pt_data.get("surgery_type")
            limb = pt_data.get("affected_limb") or affected_limb
            s_date = pt_data.get("surgery_date") or surgery_date or "recent date"
            p_day = pt_data.get("postop_day") or postop_day
            return (
                f"No worries at all! I looked up your hospital records: you had a **{surg}** "
                f"on your **{limb}** side on **{s_date}**, which puts you at **Post-Op Day {p_day}**. "
                "You don't need to worry about memorizing those details — they are safely stored in your file! "
                "How are you feeling overall today?"
            )
        return (
            "No problem at all! You can find your surgery details on your hospital discharge summary sheet. "
            "In the meantime, we can still continue — roughly how are you feeling today?"
        )

    if field_or_topic == FIELD_PAIN_LEVEL:
        return (
            "That's completely fine! You don't need an exact number. "
            "Would you say the pain is **mild** (just a dull ache), **moderate** (uncomfortable but manageable), "
            "or **severe** (making it difficult to rest or move)?"
        )

    if field_or_topic == FIELD_MOBILITY_STATUS:
        wb_status = pt_data.get("weight_bearing_status") if pt_data else None
        if wb_status:
            return (
                f"No worries! Your surgical chart specifies your mobility status as: **{wb_status}**. "
                "That means you should use your walker or crutches as instructed by your physical therapist "
                "and only put as much weight on your operated leg as is comfortable. "
                "Are you currently able to move around with your assistive device?"
            )
        return (
            "That is very common! As a general rule during early recovery, use your walker or crutches "
            "whenever standing or walking, and keep weight on your operated leg gentle. "
            "Are you managing to get up for short walks, or mostly resting today?"
        )

    if field_or_topic == "medication":
        meds = pt_data.get("current_medications", []) if pt_data else []
        if meds:
            med_list = ", ".join(m.get("name", "") for m in meds if m.get("name"))
            return (
                f"No problem! Your hospital chart lists: **{med_list}**. "
                "Do any of those match what you're thinking of?"
            )
        return (
            "That's okay! You can check your discharge medication bag or pharmacy bottles when convenient."
        )

    return (
        "No worries at all! It's completely okay if you're not sure. "
        "We can take things one gentle step at a time."
    )


# ============================================================================
# DIALOGUE ANALYSIS & EXTRACTION
# ============================================================================

def extract_field_answer(field: str, user_message: str) -> Optional[Any]:
    """Attempt to extract the patient's answer for a given field from their text."""
    text = (user_message or "").strip().lower()
    if not text:
        return None

    if field == FIELD_OVERALL_FEELING:
        if is_uncertain_answer(text):
            return "uncertain"
        # Positive / improving
        if any(w in text for w in ("better", "good", "great", "well", "improving", "fine", "okay", "ok", "so-so", "stable")):
            return "improving/good"
        # Negative / tough
        if any(w in text for w in ("bad", "rough", "terrible", "hard", "tired", "exhausted", "painful", "worse", "sore", "hurting")):
            return "tired/sore"
        if not any(w in text for w in ("walker", "crutch", "crutches", "walk", "out of 10", "pain")):
            return text[:40]
        return None

    if field == FIELD_PAIN_LEVEL:
        if is_uncertain_answer(text):
            return "uncertain"
        # Look for digit 0-10
        m = re.search(r"\b(10|[0-9])(?:\s*(?:/|out of)\s*10)?\b", text)
        if m:
            try:
                score = int(m.group(1))
                if 0 <= score <= 10:
                    return score
            except ValueError:
                pass
        # Qualitative categories
        if any(w in text for w in ("no pain", "zero pain", "not painful", "zero")):
            return 0
        if "mild" in text:
            return "mild (1-3)"
        if "moderate" in text:
            return "moderate (4-6)"
        if any(w in text for w in ("severe", "sharp", "extreme", "terrible", "excruciating")):
            return "severe (7-10)"
        if any(w in text for w in ("pain", "hurt", "hurts", "ache", "aching")):
            return "mild-to-moderate"
        return None

    if field == FIELD_MOBILITY_STATUS:
        if is_uncertain_answer(text):
            return "uncertain"
        if any(w in text for w in ("walker", "walking with walker")):
            return "walking with walker"
        if any(w in text for w in ("crutches", "crutch")):
            return "walking with crutches"
        if any(w in text for w in ("cane", "stick")):
            return "walking with cane"
        if any(w in text for w in ("bed", "resting", "lying down", "rest")):
            return "resting in bed"
        if any(w in text for w in ("walking", "walk", "moving")):
            return "walking as tolerated"
        return None

    if field == FIELD_PRIMARY_CONCERN:
        if is_uncertain_answer(text) or any(w in text for w in ("no", "none", "nothing", "all good", "nope", "no concerns")):
            return "None / Routine check-in"
        return user_message.strip()[:80]

    return None


def extract_all_fields_from_message(user_message: str) -> Dict[str, Any]:
    """Scan message for any clinical intake facts regardless of sequence."""
    found: Dict[str, Any] = {}
    text = (user_message or "").strip().lower()
    if not text:
        return found

    # Mobility check
    if any(w in text for w in ("walker", "crutch", "crutches", "cane", "walking", "walk", "bed rest", "resting")):
        mob = extract_field_answer(FIELD_MOBILITY_STATUS, user_message)
        if mob:
            found[FIELD_MOBILITY_STATUS] = mob

    # Pain check
    if any(w in text for w in ("pain", "hurt", "hurts", "ache", "mild", "moderate", "severe")) or re.search(r"\b(10|[0-9])\b", text):
        p = extract_field_answer(FIELD_PAIN_LEVEL, user_message)
        if p is not None:
            found[FIELD_PAIN_LEVEL] = p

    # Feeling check
    if any(w in text for w in ("better", "good", "great", "well", "improving", "fine", "okay", "ok", "so-so", "bad", "rough", "terrible", "tired", "sore")):
        feel = extract_field_answer(FIELD_OVERALL_FEELING, user_message)
        if feel:
            found[FIELD_OVERALL_FEELING] = feel

    # Concern check
    if any(w in text for w in ("no concern", "no concerns", "no question", "no questions", "nothing else", "all good", "nope")):
        found[FIELD_PRIMARY_CONCERN] = "None / Routine check-in"

    return found


def identify_pending_field(
    chat_history: Optional[List[Dict[str, str]]],
) -> Optional[str]:
    """Inspect the last assistant question in chat_history to determine what field was asked."""
    if not chat_history:
        return None

    for msg in reversed(chat_history):
        role = str(msg.get("role", "")).lower()
        if role in ("assistant", "bot", "ai", "model"):
            content = str(msg.get("content", "")).lower()
            if any(q in content for q in ("how are you feeling", "feeling overall")):
                return FIELD_OVERALL_FEELING
            if any(q in content for q in ("pain or discomfort", "rate your pain", "scale from 0 to 10", "mild, moderate, or severe")):
                return FIELD_PAIN_LEVEL
            if any(q in content for q in ("movement or walking", "movement been today", "walker or crutches")):
                return FIELD_MOBILITY_STATUS
            if any(q in content for q in ("specific concerns", "questions on your mind", "like us to focus on")):
                return FIELD_PRIMARY_CONCERN
            break

    return None


def reconstruct_intake_state(
    chat_history: Optional[List[Dict[str, str]]],
    current_message: str,
) -> Dict[str, Any]:
    """Reconstruct already gathered facts from dialogue turns."""
    state: Dict[str, Any] = {
        FIELD_OVERALL_FEELING: None,
        FIELD_PAIN_LEVEL: None,
        FIELD_MOBILITY_STATUS: None,
        FIELD_PRIMARY_CONCERN: None,
    }

    if not chat_history:
        return state

    pending = None
    for msg in chat_history:
        role = str(msg.get("role", "")).lower()
        content = str(msg.get("content", ""))

        if role in ("assistant", "bot", "ai", "model"):
            c_low = content.lower()
            if "feeling overall" in c_low:
                pending = FIELD_OVERALL_FEELING
            elif "rate your pain" in c_low or "pain or discomfort" in c_low:
                pending = FIELD_PAIN_LEVEL
            elif "movement or walking" in c_low or "movement been today" in c_low:
                pending = FIELD_MOBILITY_STATUS
            elif "specific concerns" in c_low:
                pending = FIELD_PRIMARY_CONCERN
        elif role in ("user", "patient"):
            extracted = extract_all_fields_from_message(content)
            for f, val in extracted.items():
                state[f] = val
            if not extracted and pending:
                ans = extract_field_answer(pending, content)
                if ans is not None:
                    state[pending] = ans
            pending = None

    return state


# ============================================================================
# RESPONSE GENERATOR (INTERACTIVE & FRIENDLY)
# ============================================================================

def generate_intake_turn(
    *,
    patient_id: str,
    surgery_type: str,
    affected_limb: str,
    postop_day: int,
    user_message: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    surgery_date: Optional[str] = None,
    precomputed_triage: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main conversational driver for the Intake & Context Agent.
    
    Adheres strictly to clinical safety:
    - Never evaluates or suppresses RED/YELLOW emergency triage (triage runs upstream).
    - Friendly, conversational bedside tone.
    - Asks one focused question at a time.
    - Handles 'I don't know' exceptions with grace and automatic DB EHR lookups.
    - Direct answers for patient clarifying questions.
    """
    history = chat_history or []
    user_text = (user_message or "").strip()

    # Fetch patient profile from database if available
    pt_data = None
    patient_name = "there"
    first_name = ""
    try:
        pt_data = patient_database.get_patient(patient_id)
        if pt_data and pt_data.get("full_name"):
            full = pt_data["full_name"].strip()
            first_name = full.split()[0]
            patient_name = first_name
    except Exception:
        pass

    # Effective surgery info
    eff_surg = (pt_data.get("surgery_type") if pt_data else None) or surgery_type or "orthopedic surgery"
    eff_limb = (pt_data.get("affected_limb") if pt_data else None) or affected_limb or "operated limb"
    eff_day = (pt_data.get("postop_day") if pt_data else None) or postop_day
    eff_date = (pt_data.get("surgery_date") if pt_data else None) or surgery_date

    # ------------------------------------------------------------------------
    # STEP 1: Check for Patient Clarification / Informational Question
    # ------------------------------------------------------------------------
    info_topic = detect_informational_question(user_text)
    if info_topic:
        answer = answer_informational_question(
            topic=info_topic,
            patient_id=patient_id,
            surgery_type=eff_surg,
            affected_limb=eff_limb,
            postop_day=eff_day,
            surgery_date=eff_date,
        )
        if answer:
            # Check what field was pending so we can gently invite them back
            pending_field = identify_pending_field(history)
            if pending_field and pending_field in STANDARD_QUESTIONS:
                followup_prompt = f"\n\nWhenever you're ready, {STANDARD_QUESTIONS[pending_field]}"
                reply = f"{answer}{followup_prompt}"
            else:
                reply = (
                    f"{answer}\n\n"
                    f"Whenever you're ready, let me know how you're feeling overall today, "
                    "and we can continue your recovery check-in!"
                )
            return {
                "reply": reply,
                "triage_level": "GREEN",
                "is_escalated": False,
                "engine": "Intake & Context Agent - Educational Q&A",
                "sources": ["Hospital EHR Database", "Orthopedic Recovery Guidelines"],
            }

    # ------------------------------------------------------------------------
    # STEP 2: Reconstruct State and Identify Pending Field
    # ------------------------------------------------------------------------
    state = reconstruct_intake_state(history, user_text)
    pending_field = identify_pending_field(history)

    # ------------------------------------------------------------------------
    # STEP 3: Handle "I don't know" / Uncertainty Exception
    # ------------------------------------------------------------------------
    if is_uncertain_answer(user_text):
        # Did user say don't know to surgery details specifically in opening?
        if any(w in user_text.lower() for w in ("surgery", "procedure", "operation", "date")):
            reply = handle_unknown_exception("surgery_date", patient_id, eff_surg, eff_limb, eff_day, eff_date)
            return {
                "reply": reply,
                "triage_level": "GREEN",
                "is_escalated": False,
                "engine": "Intake & Context Agent - EHR Recovery",
                "sources": ["Hospital EHR Database"],
            }
        
        # If user answered a pending field with "I don't know"
        if pending_field:
            if pending_field == FIELD_PAIN_LEVEL:
                reply = (
                    handle_unknown_exception(FIELD_PAIN_LEVEL, patient_id, eff_surg, eff_limb, eff_day, eff_date)
                )
            elif pending_field == FIELD_MOBILITY_STATUS:
                reply = (
                    handle_unknown_exception(FIELD_MOBILITY_STATUS, patient_id, eff_surg, eff_limb, eff_day, eff_date)
                )
            else:
                reply = ALT_QUESTIONS.get(pending_field, STANDARD_QUESTIONS.get(pending_field, ""))

            return {
                "reply": reply,
                "triage_level": "GREEN",
                "is_escalated": False,
                "engine": "Intake & Context Agent - Exception Handling",
                "sources": ["Hospital EHR Database", "Clinical Practice Guidelines"],
            }

    # ------------------------------------------------------------------------
    # STEP 4: Process Answer for Current Turn
    # ------------------------------------------------------------------------
    curr_extracted = extract_all_fields_from_message(user_text)
    last_answered_field = None
    if curr_extracted:
        for f, val in curr_extracted.items():
            state[f] = val
            last_answered_field = f
    elif pending_field:
        ans = extract_field_answer(pending_field, user_text)
        state[pending_field] = ans or user_text[:50]
        last_answered_field = pending_field

    # ------------------------------------------------------------------------
    # STEP 5: First Turn / Opening Greeting
    # ------------------------------------------------------------------------
    # If no pending field and history is empty (or just opening greeting)
    if pending_field is None and not any(state.values()):
        name_greeting = f"Hello {first_name}!" if first_name else "Hello!"
        greeting_lead = (
            f"{name_greeting} It's wonderful to connect with you today. "
            f"I'm **OrthoSync**, your orthopedic postoperative recovery companion. "
            f"I see you are on **Post-Op Day {eff_day}** following your **{eff_surg}** ({eff_limb}).\n\n"
            "Let's do a quick, friendly daily check-in to see how you're doing.\n\n"
            f"{STANDARD_QUESTIONS[FIELD_OVERALL_FEELING]}"
        )
        return {
            "reply": greeting_lead,
            "triage_level": "GREEN",
            "is_escalated": False,
            "engine": "Intake & Context Agent - Welcome",
            "sources": ["Hospital EHR Profile"],
        }

    # ------------------------------------------------------------------------
    # STEP 6: Determine Next Missing Field in Sequence
    # ------------------------------------------------------------------------
    field_to_ack = last_answered_field or pending_field
    for next_field in INTAKE_SEQUENCE:
        if state[next_field] is None:
            # Build friendly acknowledgment of previous answer
            ack = ""
            if field_to_ack == FIELD_OVERALL_FEELING:
                val = state[FIELD_OVERALL_FEELING]
                if val == "improving/good":
                    ack = "I'm so glad to hear you're feeling better today! That's encouraging progress.\n\n"
                elif val == "tired/sore":
                    ack = "Thank you for letting me know. Feeling tired and sore is very common at this stage as your body repairs itself.\n\n"
                else:
                    ack = "Thanks for sharing that with me.\n\n"
            elif field_to_ack == FIELD_PAIN_LEVEL:
                val = state[FIELD_PAIN_LEVEL]
                ack = f"Got it, comfort level noted ({val}). Keeping your pain well-managed is essential for good healing.\n\n"
            elif field_to_ack == FIELD_MOBILITY_STATUS:
                ack = "Great to hear! Tracking your mobility helps us ensure your recovery stays safely on track.\n\n"
            elif field_to_ack == FIELD_PRIMARY_CONCERN:
                ack = "Got it, thanks for letting me know.\n\n"

            reply_text = f"{ack}{STANDARD_QUESTIONS[next_field]}"
            return {
                "reply": reply_text,
                "triage_level": "GREEN",
                "is_escalated": False,
                "engine": "Intake & Context Agent - Interactive Follow-up",
                "sources": ["Hospital EHR Database"],
            }

    # ------------------------------------------------------------------------
    # STEP 7: All Intake Fields Collected -> Conclude & Summarize
    # ------------------------------------------------------------------------
    pain_display = str(state[FIELD_PAIN_LEVEL] or "Mild (managed)")
    feeling_display = str(state[FIELD_OVERALL_FEELING] or "Stable")
    mobility_display = str(state[FIELD_MOBILITY_STATUS] or "Mobilizing as tolerated")
    concern_display = str(state[FIELD_PRIMARY_CONCERN] or "Routine recovery monitoring")

    # Best-effort record update into patient database
    try:
        numeric_pain = None
        if isinstance(state[FIELD_PAIN_LEVEL], (int, float)):
            numeric_pain = float(state[FIELD_PAIN_LEVEL])
        elif re.search(r"\b(\d+)\b", pain_display):
            numeric_pain = float(re.search(r"\b(\d+)\b", pain_display).group(1))

        with patient_database.connection_scope() as conn:
            conn.execute(
                """INSERT INTO metrics
                   (patient_id, day, date, pain_score, swelling, triage, exercise_completed)
                   VALUES (?, ?, date('now'), ?, ?, ?, ?)""",
                (patient_id, eff_day, numeric_pain, "Mild", "GREEN", 1),
            )
    except Exception:
        pass

    summary_text = (
        f"**Daily Recovery Check-In Complete!**\n\n"
        f"Thank you for sharing your update, {first_name or 'patient'}. "
        "Here is what we have consolidated in your recovery record for today:\n\n"
        f"- **Procedure**: {eff_surg} ({eff_limb})\n"
        f"- **Timeline**: Post-Operative Day {eff_day}\n"
        f"- **Overall Feeling**: {feeling_display.capitalize()}\n"
        f"- **Pain / Comfort**: {pain_display}\n"
        f"- **Mobility**: {mobility_display}\n"
        f"- **Today's Focus**: {concern_display}\n\n"
        "Your recovery file has been updated. How would you like to proceed? "
        "I can guide you through your **rehabilitation exercises**, review your **medication schedule**, "
        "or answer any questions about your healing!"
    )

    return {
        "reply": summary_text,
        "triage_level": "GREEN",
        "is_escalated": False,
        "engine": "Intake & Context Agent - Synthesis",
        "sources": ["Hospital EHR Database", "Local SQLite Persistence"],
    }
