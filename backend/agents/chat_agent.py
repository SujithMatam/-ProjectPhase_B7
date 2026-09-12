"""
LLM Chatbot Agent for Orthopedic Post-Op Recovery
Powered by Local Offline LLM (Ollama / Llama 3.2) + Clinical RAG + Safety Guardrails.
"""

import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

from triage.safety_triage import SafetyTriageEngine
from rag.knowledge_base import ClinicalKnowledgeBase
from lam.schemas import resolve_procedure_code

OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = "llama3.2"


class ChatAgent:

    @classmethod
    def answer_question(
        cls,
        patient_id: str,
        surgery_type: str,
        affected_limb: str,
        postop_day: int,
        user_message: str,
        chat_history: List[Dict[str, str]] = None,
        procedure: str = None,
        domain_instruction: Optional[str] = None,
        precomputed_triage: Optional[Dict[str, Any]] = None,
        surgery_date: Optional[str] = None,

        # ============================================================
        # These are used only when WoundCareAgent has completed its
        # multi-turn assessment and needs one final answer.
        # ============================================================
        final_wound_assessment: bool = False,
        wound_assessment_summary: Optional[str] = None,
    ) -> Dict[str, Any]:

        # ============================================================
        # SAFETY TRIAGE
        # ============================================================
        triage = (
            precomputed_triage
            if precomputed_triage is not None
            else SafetyTriageEngine.evaluate(
                symptoms=user_message,
                post_op_day=postop_day
            )
        )

        if triage["triage_level"] == "RED":
            reply_text = (
                f"⚠️ **CRITICAL EMERGENCY ALERT**\n\n"
                f"Your symptoms require urgent medical evaluation: "
                f"**{', '.join(triage['reasons'])}**.\n\n"
                f"{triage['action_protocol']}\n\n"
                f"Please contact your hospital emergency line or visit "
                f"the nearest emergency department right away."
            )

            return {
                "reply": reply_text,
                "triage_level": "RED",
                "is_escalated": True,
                "engine": "Deterministic Safety Triage",
                "sources": []
            }

        # ============================================================
        # PROCEDURE
        # ============================================================
        procedure = procedure or resolve_procedure_code(surgery_type)

        # ============================================================
        # RAG
        # ============================================================
        rag_docs = ClinicalKnowledgeBase.query(
            user_message,
            procedure=procedure,
            limit=2
        )

        rag_context = "\n".join(
            [
                f"- {d['topic']}: {d['content']}"
                for d in rag_docs
            ]
        )

        # ============================================================
        # LLM
        # ============================================================
        llm_response = cls._query_llama(
            user_message=user_message,
            patient_id=patient_id,
            surgery_type=surgery_type,
            affected_limb=affected_limb,
            postop_day=postop_day,
            rag_context=rag_context,
            triage=triage,
            chat_history=chat_history or [],
            domain_instruction=domain_instruction,
            surgery_date=surgery_date,

            final_wound_assessment=final_wound_assessment,
            wound_assessment_summary=wound_assessment_summary,
        )

        # ============================================================
        # VALID LLM RESPONSE
        # ============================================================
        if llm_response and not any(
            r in llm_response.lower()
            for r in [
                "can't provide medical advice",
                "cannot provide medical advice",
                "cannot give medical advice",
            ]
        ):
            return {
                "reply": llm_response,
                "triage_level": triage["triage_level"],
                "is_escalated": triage["is_escalated"],
                "engine": f"Local LLM ({DEFAULT_MODEL})",
                "sources": [
                    d["topic"]
                    for d in rag_docs
                ]
            }

        # ============================================================
        # IMPORTANT:
        # If the wound assessment is already COMPLETE, NEVER send the
        # request into the generic _generate_smart_reply() fallback.
        #
        # That generic fallback was responsible for responses such as:
        #
        # "Clear to slightly pink (serosanguinous) drainage is normal..."
        #
        # because it only looked at the current final user_message and
        # then selected generic RAG/symptom content.
        # ============================================================
        if final_wound_assessment:
            return cls._generate_final_wound_fallback(
                patient_id=patient_id,
                surgery_type=surgery_type,
                affected_limb=affected_limb,
                postop_day=postop_day,
                chat_history=chat_history or [],
                wound_assessment_summary=wound_assessment_summary or "",
                rag_docs=rag_docs,
                precomputed_triage=precomputed_triage,
            )

        # ============================================================
        # EXISTING GENERIC FALLBACK
        # ============================================================
        fallback_reply = cls._generate_smart_reply(
            user_message=user_message,
            patient_id=patient_id,
            surgery_type=surgery_type,
            affected_limb=affected_limb,
            postop_day=postop_day,
            rag_docs=rag_docs
        )

        return {
            "reply": fallback_reply,
            "triage_level": triage["triage_level"],
            "is_escalated": triage["is_escalated"],
            "engine": "Clinical Synthesis Engine",
            "sources": [
                d["topic"]
                for d in rag_docs
            ]
        }

    # ================================================================
    # LLM QUERY
    # ================================================================

    @classmethod
    def _query_llama(
        cls,
        user_message: str,
        patient_id: str,
        surgery_type: str,
        affected_limb: str,
        postop_day: int,
        rag_context: str,
        triage: Dict[str, Any],
        chat_history: List[Dict[str, str]],
        domain_instruction: Optional[str] = None,
        surgery_date: Optional[str] = None,

        final_wound_assessment: bool = False,
        wound_assessment_summary: Optional[str] = None,
    ) -> str:

        # ============================================================
        # PREVIOUS CONVERSATION
        # ============================================================
        history_lines = []

        for turn in chat_history[-10:]:
            role = turn.get("role", "user")
            content = turn.get("content", "").strip()

            if content:
                history_lines.append(
                    f"{role}: {content}"
                )

        history_text = (
            "\n".join(history_lines)
            if history_lines
            else "No previous conversation turns."
        )

        surgery_date_text = surgery_date or "Not provided"

        # ============================================================
        # FINAL WOUND-ASSESSMENT PROMPT
        # ============================================================
        if final_wound_assessment:

            assessment_text = (
                wound_assessment_summary.strip()
                if wound_assessment_summary
                else "No structured wound assessment supplied."
            )

            prompt = f"""
You are the final response generator for an orthopedic postoperative
wound-care assessment.

The wound assessment has ALREADY been completed.

DO NOT ask another question.
DO NOT restart the assessment.
DO NOT request additional information.

Patient context:
- Postoperative day: {postop_day}
- Surgery: {surgery_type}
- Affected limb: {affected_limb}
- Surgery date: {surgery_date_text}

Retrieved orthopedic knowledge:
{rag_context}

Previous conversation:
{history_text}

Completed structured wound assessment:
{assessment_text}

Your job is to generate ONE final patient-facing response using
the COMPLETE previous conversation AND the completed structured
assessment.

The patient's actual reported findings are the primary context.

Adapt the response to the overall combination of findings.

If the findings are generally improving or reassuring, explicitly
recognize that improvement.

If findings are stable, explain that context appropriately.

If any findings are worsening or concerning, explicitly recognize
those findings and explain the appropriate next step.

If findings are mixed, acknowledge both the reassuring and concerning
parts instead of giving an oversimplified conclusion.

Do not focus on one isolated symptom while ignoring the other
information already provided.

The response should:
1. Briefly acknowledge what the patient reported.
2. Summarize the important findings.
3. Give a cautious preliminary interpretation of the overall wound
   status.
4. Explain what the patient should do next.
5. Explain what changes they should monitor and when to contact
   their surgical team.

Use the retrieved orthopedic knowledge when giving guidance.
Do not invent medical facts, thresholds, medication doses,
treatment instructions, or unsupported timelines.

Write in plain, everyday language a patient without a medical
background would understand. Avoid clinical jargon where a simpler
word works, and briefly explain any medical term you do need to use.

The deterministic safety-triage result is authoritative.
Do not perform independent emergency triage.

Return ONLY the final patient-facing response.

Do not mention:
- LLM
- RAG
- agents
- prompts
- structured assessment
- internal system logic
- safety engine
"""

        # ============================================================
        # NORMAL CHAT PROMPT
        # ============================================================
        elif domain_instruction:

            prompt = f"""
Read the provided physical therapy discharge reference for Day
{postop_day} after {surgery_type} ({affected_limb}):

{rag_context}

Patient surgery date:
{surgery_date_text}

Previous conversation:
{history_text}

Specialist focus for this answer:
{domain_instruction}

User's Question:
"{user_message}"

Write a friendly, 2-3 sentence answer directly answering the
user's question based on the discharge notes and relevant
conversation context.

Write in plain, everyday language a patient without a medical
background would understand.

Mention Day {postop_day} goals, icing, and limb elevation
only when relevant:
"""

        else:

            prompt = f"""
Read the provided physical therapy discharge reference for Day
{postop_day} after {surgery_type} ({affected_limb}):

{rag_context}

Patient surgery date:
{surgery_date_text}

Previous conversation:
{history_text}

User's Question:
"{user_message}"

Write a friendly, 2-3 sentence answer directly answering the
user's question based on the discharge notes and relevant
conversation context.

Write in plain, everyday language a patient without a medical
background would understand.

Mention Day {postop_day} goals, icing, and limb elevation
only when relevant:
"""

        # ============================================================
        # OLLAMA PAYLOAD
        # ============================================================
        payload = {
            "model": DEFAULT_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,

                # Slightly larger final-answer budget.
                "num_predict": 220
                if final_wound_assessment
                else 150
            }
        }

        try:
            req = urllib.request.Request(
                OLLAMA_API_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json"
                }
            )

            with urllib.request.urlopen(
                req,
                timeout=12
            ) as resp:

                data = json.loads(
                    resp.read().decode("utf-8")
                )

                return data.get(
                    "response",
                    ""
                ).strip()

        except Exception:
            return None

    # ================================================================
    # FINAL WOUND FALLBACK
    # ================================================================

    @classmethod
    def _generate_final_wound_fallback(
        cls,
        patient_id: str,
        surgery_type: str,
        affected_limb: str,
        postop_day: int,
        chat_history: List[Dict[str, str]],
        wound_assessment_summary: str,
        rag_docs: List[Dict[str, Any]],
        precomputed_triage: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        """
        Fallback specifically for a COMPLETED wound assessment.

        This must not use the normal generic symptom fallback because
        that fallback can ignore the completed assessment and return
        unrelated generic RAG text.
        """

        summary = (
            wound_assessment_summary.strip()
            if wound_assessment_summary
            else ""
        )

        # ============================================================
        # FIX: signal detection must only scan the patient's actual
        # ANSWERS, never the field LABELS.
        #
        # wound_assessment_summary is formatted like:
        #     - separation: closed
        #     - drainage: nope
        #
        # The word "separation" is itself in worsening_signals below
        # (it's meant to catch answers like "the incision is
        # separating"), but it is also the field's own label -- so it
        # appeared in every summary regardless of the patient's actual
        # answer, permanently forcing has_worsening=True even when the
        # patient said "closed". Stripping the "- fieldname:" prefix
        # from each line before scanning fixes this: only the value
        # after the colon (the patient's real answer) is checked
        # against the signal-word lists.
        # ============================================================
        values_only_lines = []
        for line in summary.splitlines():
            line = line.strip()
            if line.startswith("-") and ":" in line:
                values_only_lines.append(line.split(":", 1)[1].strip())
            else:
                values_only_lines.append(line)

        lower_summary = " ".join(values_only_lines).lower()

        # ============================================================
        # CONTEXT SIGNALS
        #
        # These are only used to make the fallback response contextual.
        # Emergency classification remains upstream.
        # ============================================================

        improving_signals = [
            "improving",
            "better",
            "decreasing",
            "less red",
            "less redness",
            "less warm",
            "less warmth",
            "reduced",
            "getting better",
            "not getting worse",
            "not worsening",
        ]

        worsening_signals = [
            "worsening",
            "getting worse",
            "increasing",
            "more red",
            "more redness",
            "more warm",
            "more warmth",
            "increasing swelling",
            "more painful",
            "opened",
            "open",
            "separated",
            "separation",
            "spreading",
        ]

        reassuring_signals = [
            "closed",
            "no drainage",
            "no pus",
            "no discharge",
            "no fever",
            "no odor",
            "dry",
            "clean",
        ]

        has_improvement = any(
            signal in lower_summary
            for signal in improving_signals
        )

        has_worsening = any(
            signal in lower_summary
            for signal in worsening_signals
        )

        has_reassuring = any(
            signal in lower_summary
            for signal in reassuring_signals
        )

        # ============================================================
        # UNCERTAINTY
        #
        # wound_care_agent.py writes "not sure" for any field the
        # patient still couldn't answer even after being offered a
        # simpler way to check. This must never be silently absorbed
        # into a "reassuring" verdict -- an unresolved field is a
        # reason for a light check-in, not something to ignore just
        # because the OTHER fields looked fine.
        # ============================================================

        has_uncertain = "not sure" in lower_summary

        # ============================================================
        # OVERALL CONTEXT
        #
        # Emoji are only added on the "good news" branches -- a happy or
        # reassuring emoji next to "contact your surgical team" would
        # feel wrong, so worsening/mixed branches stay emoji-free.
        # ============================================================

        if has_worsening and has_improvement:
            overall_context = (
                "The findings are mixed: some reported features are "
                "improving, while at least one reported feature is "
                "changing in a potentially concerning direction."
            )

        elif has_worsening:
            overall_context = (
                "The reported findings include a potentially worsening "
                "change that should not be ignored."
            )

        elif has_uncertain:
            # Uncertainty takes priority over "reassuring" -- a field
            # that's genuinely unknown must not get glossed over just
            # because everything else looked fine.
            overall_context = (
                "Most of what you described sounds okay, but you "
                "weren't able to tell about one or more things even "
                "after trying an easier way to check."
            )

        elif has_improvement and has_reassuring:
            overall_context = (
                "Overall, that's a reassuring picture 😊 the wound "
                "genuinely looks like it's healing well."
            )

        elif has_improvement:
            overall_context = (
                "That sounds like a good sign 🙂 the findings you "
                "described point to an improving trend."
            )

        elif has_reassuring:
            overall_context = (
                "That's reassuring to hear 🙂 though it's still worth "
                "keeping an eye on things as you continue to recover."
            )

        else:
            overall_context = (
                "The reported findings should be considered together "
                "with your postoperative stage."
            )

        # ============================================================
        # ACTION
        # ============================================================

        if has_worsening:
            next_step = (
                "Because you reported a worsening or changing finding, "
                "please contact your surgical team for guidance, "
                "especially if the change continues or becomes more "
                "pronounced."
            )
        elif has_uncertain:
            next_step = (
                "Since a couple of things weren't clear, it's worth "
                "asking someone to take a look at the area for you, or "
                "mentioning it the next time you're in touch with your "
                "surgical team -- just so nothing gets missed."
            )
        else:
            next_step = (
                "Keep following the wound-care instructions from your "
                "surgical team, and you're doing the right thing by "
                "tracking how it's healing 👍"
            )

        # ============================================================
        # RESPONSE
        # ============================================================

        if has_worsening:
            watch_for = (
                "Keep an eye on whether the change continues, spreads, "
                "or is joined by new symptoms such as fever, increasing "
                "pain, or new drainage."
            )
        else:
            watch_for = (
                "Contact your surgical team promptly if you later notice "
                "increasing redness, warmth, swelling, new or worsening "
                "drainage, the incision opening, increasing pain, or "
                "feeling feverish."
            )

        opening = (
            "Thanks for walking me through that 🩹"
            if not has_worsening and not has_uncertain
            else "Thanks for walking me through that."
        )

        reply = (
            f"{opening} Based on what you reported on postoperative "
            f"Day {postop_day}, here's what you told me:\n\n"
            f"{summary}\n\n"
            f"{overall_context}\n\n"
            f"{next_step}\n\n"
            f"{watch_for}"
        )

        return {
            "reply": reply,
            "triage_level": (
                precomputed_triage.get(
                    "triage_level",
                    "GREEN"
                )
                if precomputed_triage
                else "GREEN"
            ),
            "is_escalated": (
                precomputed_triage.get(
                    "is_escalated",
                    False
                )
                if precomputed_triage
                else False
            ),
            "engine": "Wound Assessment Fallback",
            "sources": [
                d["topic"]
                for d in rag_docs
                if d.get("topic")
            ]
        }

    # ================================================================
    # EXISTING GENERIC FALLBACK
    # ================================================================

    @classmethod
    def _generate_smart_reply(
        cls,
        user_message: str,
        patient_id: str,
        surgery_type: str,
        affected_limb: str,
        postop_day: int,
        rag_docs: List[Dict[str, Any]]
    ) -> str:

        lower = user_message.lower()

        if (
            "exercise" in lower
            or "workout" in lower
            or "physio" in lower
        ):
            if postop_day <= 2:
                return (
                    f"For Post-Op Day {postop_day}, your focus is "
                    "gentle in-bed mobility: ankle pumps (10 every hour) "
                    "to prevent blood clots, gentle quad sets pushing your "
                    "knee flat into the bed, and short assisted transfers "
                    "with your walker."
                )

            elif postop_day <= 7:
                return (
                    f"On Day {postop_day}, your targets are active-assisted "
                    "heel slides aiming for 70°–90° flexion, straight leg "
                    "raises to rebuild quadriceps strength, and walking "
                    "5–10 minutes with your walker every 2 hours."
                )

            else:
                return (
                    f"At Day {postop_day}, work on progressing your passive "
                    "flexion past 90°, standing calf raises, seated knee "
                    "extension, and increasing your independent walking "
                    "endurance as tolerated."
                )

        if "swell" in lower or "puff" in lower:
            return (
                f"Swelling in your {affected_limb} "
                f"{('knee' if 'knee' in surgery_type.lower() else 'hip')} "
                f"on Day {postop_day} is normal due to increased "
                "circulation during healing. Lie down with your foot "
                "elevated above heart level and apply an ice pack for "
                "20 minutes."
            )

        if "pain" in lower or "hurt" in lower:
            return (
                f"Mild to moderate soreness is typical on Day "
                f"{postop_day}. Take your prescribed pain medication "
                "30-45 minutes before starting physical therapy to keep "
                "your discomfort manageable."
            )

        if rag_docs:
            return (
                f"Based on your Day {postop_day} protocol for "
                f"{surgery_type}: {rag_docs[0]['content']}"
            )

        return (
            f"Hello! On Day {postop_day} of your recovery from "
            f"{surgery_type} ({affected_limb}), make sure to keep up "
            "with your daily physical therapy routine, elevate your leg "
            "when resting, and stay hydrated."
        )