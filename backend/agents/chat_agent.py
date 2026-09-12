"""Deterministic clinical chat agent for orthopedic post-op recovery."""

from __future__ import annotations

from typing import Dict, Any, List, Optional

from triage.safety_triage import SafetyTriageEngine
from rag.knowledge_base import ClinicalKnowledgeBase
from lam.schemas import resolve_procedure_code


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
    ) -> Dict[str, Any]:

        # ====================================================
        # STEP 1
        # SAFETY TRIAGE
        # ====================================================

        triage = (
            precomputed_triage
            if precomputed_triage is not None
            else SafetyTriageEngine.evaluate(
                symptoms=user_message,
                post_op_day=postop_day
            )
        )

        # RED bypasses LLM.
        if triage["triage_level"] == "RED":

            reply_text = (
                "⚠️ **CRITICAL EMERGENCY ALERT**\n\n"
                f"Your symptoms require urgent medical evaluation: "
                f"**{', '.join(triage['reasons'])}**.\n\n"
                f"{triage['action_protocol']}\n\n"
                "Please contact your hospital emergency line or visit "
                "the nearest emergency department right away."
            )

            return {
                "reply": reply_text,
                "triage_level": "RED",
                "is_escalated": True,
                "engine": "Deterministic Safety Triage",
                "sources": []
            }

        # ====================================================
        # STEP 2
        # RAG
        # ====================================================

        procedure = (
            procedure
            or resolve_procedure_code(surgery_type)
        )

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

        if not rag_context:
            rag_context = (
                "No relevant clinical reference was retrieved."
            )

        # ====================================================
        # STEP 3
        # DETERMINISTIC CLINICAL SYNTHESIS
        # ====================================================

        reply = cls._generate_smart_reply(
            user_message=user_message,
            patient_id=patient_id,
            surgery_type=surgery_type,
            affected_limb=affected_limb,
            postop_day=postop_day,
            rag_docs=rag_docs,
            procedure=procedure,
            domain_instruction=domain_instruction,
            surgery_date=surgery_date,
        )

        return {
            "reply": reply,
            "triage_level": triage["triage_level"],
            "is_escalated": triage["is_escalated"],
            "engine": "Clinical Synthesis Engine",
            "sources": [
                d["topic"]
                for d in rag_docs
            ]
        }

    # ============================================================
    # FALLBACK HELPERS
    # ============================================================

    _WEIGHT_BEARING_RESTRICTION_MARKER = (
        "Prescribed weight-bearing status:"
    )

    _SWELLING_BODY_REGION_BY_PROCEDURE = {
        "TKA": "knee",
        "THA": "hip",
    }

    _NEUTRAL_BODY_REGION = "operative area"
    # ============================================================
    # SMART FALLBACK
    # ============================================================

    @classmethod
    def _generate_smart_reply(
        cls,
        user_message: str,
        patient_id: str,
        surgery_type: str,
        affected_limb: str,
        postop_day: int,
        rag_docs: List[Dict[str, Any]],
        procedure: Optional[str] = None,
        domain_instruction: Optional[str] = None,
        surgery_date: Optional[str] = None,
    ) -> str:

        lower = user_message.lower().strip()

        # ========================================================
        # INTAKE FALLBACK
        # ========================================================

        if (
            domain_instruction
            and "Intake & Context Agent" in domain_instruction
        ):

            return cls._intake_fallback_reply(
                user_message=user_message,
                surgery_type=surgery_type,
                affected_limb=affected_limb,
                postop_day=postop_day,
                surgery_date=surgery_date,
            )

        # ========================================================
        # REHABILITATION
        # ========================================================

        if (
            "exercise" in lower
            or "workout" in lower
            or "physio" in lower
            or "physiotherapy" in lower
            or "rehab" in lower
        ):


            return cls._rehab_fallback_reply(
                postop_day=postop_day,
                rag_docs=rag_docs,
                domain_instruction=domain_instruction,
            )

        # ========================================================
        # MEDICATION
        # ========================================================

        if any(
            word in lower
            for word in [
                "medication",
                "medicine",
                "pill",
                "tablet",
                "dose",
                "painkiller",
                "enoxaparin",
                "blood thinner",
                "aspirin",
                "paracetamol",
                "nsaid",
                "ibuprofen",
                "antibiotic",
                "forgot",
                "missed",
            ]
        ):

            return cls._medication_fallback_reply(
                postop_day=postop_day,
                rag_docs=rag_docs,
            )

        # ========================================================
        # NUTRITION
        # ========================================================

        if any(
            word in lower
            for word in [
                "nutrition",
                "diet",
                "food",
                "protein",
                "eat",
                "eating",
                "vitamin",
                "calcium",
                "zinc",
                "hydration",
                "water",
                "constipation",
                "fiber",
                "fibre",
            ]
        ):

            return cls._nutrition_fallback_reply(
                postop_day=postop_day,
                rag_docs=rag_docs,
            )

        # ========================================================
        # MENTAL WELLBEING
        # ========================================================

        if any(
            word in lower
            for word in [
                "anxious",
                "anxiety",
                "fear",
                "scared",
                "afraid",
                "depressed",
                "sad",
                "frustrated",
                "frustration",
                "mood",
                "stress",
                "kinesiophobia",
            ]
        ):

            return cls._mental_wellbeing_fallback_reply(
                postop_day=postop_day,
                rag_docs=rag_docs,
            )

        # ========================================================
        # SWELLING
        # ========================================================

        if (
            "swell" in lower
            or "puff" in lower
        ):

            body_region = (
                cls._SWELLING_BODY_REGION_BY_PROCEDURE.get(
                    procedure,
                    cls._NEUTRAL_BODY_REGION
                )
            )

            return cls._symptom_fallback_reply(
                symptom_label=(
                    f"swelling in your "
                    f"{affected_limb} "
                    f"{body_region}"
                ),
                postop_day=postop_day,
                rag_docs=rag_docs,
            )

        # ========================================================
        # PAIN
        # ========================================================

        if (
            "pain" in lower
            or "hurt" in lower
            or "ache" in lower
        ):

            return cls._symptom_fallback_reply(
                symptom_label="pain",
                postop_day=postop_day,
                rag_docs=rag_docs,
            )

        # ========================================================
        # GENERAL RAG FALLBACK
        # ========================================================

        if rag_docs:
            return (
                f"Based on your Day {postop_day} "
                f"protocol for {surgery_type}: "
                f"{rag_docs[0]['content']}"
            )

        # ========================================================
        # FINAL GENERAL FALLBACK
        # ========================================================

        return (
            "I don't have enough specific information to answer "
            "that yet. Please provide a little more detail about "
            "what you would like help with during your recovery."
        )

    # ============================================================
    # INTAKE FALLBACK
    # ============================================================

    @classmethod
    def _intake_fallback_reply(
        cls,
        user_message: str,
        surgery_type: str,
        affected_limb: str,
        postop_day: int,
        surgery_date: Optional[str] = None,
    ) -> str:

        text = user_message.strip()
        lower = text.lower()

        # --------------------------------------------------------
        # Simple greeting
        # --------------------------------------------------------

        simple_greetings = {
            "hi",
            "hello",
            "hey",
            "good morning",
            "good afternoon",
            "good evening",
        }

        if lower.strip("!. ") in simple_greetings:

            return (
                "Hi! I'm OrthoSync. "
                "How can I help you today?"
            )

        # --------------------------------------------------------
        # Patient introduction / intake
        # --------------------------------------------------------

        # Do not echo the complete user message.
        # Do not give generic recovery instructions.
        # Keep the response conversational.

        if any(
            phrase in lower
            for phrase in [
                "i am ",
                "i'm ",
                "my name is ",
                "this is ",
            ]
        ):

            return (
                "Hi! Nice to meet you. "
                "I’ll keep the information you share in mind "
                "during our conversation. "
                "How can I help you today?"
            )

        # --------------------------------------------------------
        # Other intake/context information
        # --------------------------------------------------------

        return (
            "Thanks for sharing that information. "
            "I’ll keep it in mind during our conversation. "
            "How can I help you today?"
        )

    # ============================================================
    # REHABILITATION FALLBACK
    # ============================================================

    @classmethod
    def _rehab_fallback_reply(
        cls,
        postop_day: int,
        rag_docs: List[Dict[str, Any]],
        domain_instruction: Optional[str] = None,
    ) -> str:

        has_weight_bearing_restriction = (
            domain_instruction is not None
            and cls._WEIGHT_BEARING_RESTRICTION_MARKER
            in domain_instruction
        )

        restriction_note = (
            " A weight-bearing restriction is on record for you; "
            "follow it exactly and do not exceed what your care team "
            "has prescribed."
            if has_weight_bearing_restriction
            else ""
        )

        if rag_docs:

            return (
                f"Based on your Day {postop_day} retrieved "
                f"rehabilitation guidance: "
                f"{rag_docs[0]['content']}"
                f"{restriction_note}"
            )

        if has_weight_bearing_restriction:

            return (
                f"On Day {postop_day}, a weight-bearing restriction "
                "is on record for you, and I don't have a matching "
                "retrieved exercise protocol for this question right "
                "now. Please follow your prescribed restriction exactly "
                "and check with your surgical or physical therapy team "
                "before starting or progressing any exercise."
            )

        return (
            f"On Day {postop_day}, I don't have a specific retrieved "
            "exercise protocol for this question right now. Please "
            "follow your surgical team's prescribed rehabilitation "
            "plan and check with your physical therapist before "
            "starting or progressing any exercise."
        )

    # ============================================================
    # SYMPTOM FALLBACK
    # ============================================================

    @classmethod
    def _symptom_fallback_reply(
        cls,
        symptom_label: str,
        postop_day: int,
        rag_docs: List[Dict[str, Any]],
    ) -> str:

        if rag_docs:


            return (
                f"You reported {symptom_label} on Day "
                f"{postop_day}. Based on your retrieved "
                f"clinical guidance: "
                f"{rag_docs[0]['content']}"
            )

        return (
            f"You reported {symptom_label} on Day {postop_day}. "
            "I don't have a matching retrieved protocol for this "
            "right now, so please follow your existing care-team "
            "or discharge instructions and contact your surgical "
            "or physical therapy team if you're unsure or if "
            "the symptom changes."
        )

    # ============================================================
    # MEDICATION FALLBACK
    # ============================================================

    @classmethod
    def _medication_fallback_reply(
        cls,
        postop_day: int,
        rag_docs: List[Dict[str, Any]],
    ) -> str:

        if rag_docs:

            return (
                f"Regarding your medication on Day "
                f"{postop_day}: "
                f"{rag_docs[0]['content']} "
                "Remember: if you missed a dose, follow the "
                "instructions supplied with your prescription and "
                "do not double-dose. Contact your surgical team "
                "or pharmacist for dosage changes."
            )

        return (
            f"On Day {postop_day}, follow your discharge medication "
            "schedule exactly as prescribed by your surgical team. "
            "If you missed a dose, follow the medication's prescribed "
            "missed-dose instructions rather than taking an extra dose. "
            "Please consult your surgeon or pharmacist for specific "
            "prescription changes."
        )

    # ============================================================
    # NUTRITION FALLBACK
    # ============================================================

    @classmethod
    def _nutrition_fallback_reply(
        cls,
        postop_day: int,
        rag_docs: List[Dict[str, Any]],
    ) -> str:

        if rag_docs:

            return (
                f"Recovery nutrition guidance for Day "
                f"{postop_day}: "
                f"{rag_docs[0]['content']}"
            )

        return (
            f"I don't have a specific retrieved nutrition protocol "
            f"for Day {postop_day} right now. Follow any dietary "
            "instructions from your care team and aim for a balanced "
            "diet with adequate protein and fluids unless your "
            "clinician has given you different instructions."
        )

    # ============================================================
    # MENTAL WELLBEING FALLBACK
    # ============================================================

    @classmethod
    def _mental_wellbeing_fallback_reply(
        cls,
        postop_day: int,
        rag_docs: List[Dict[str, Any]],
    ) -> str:

        if rag_docs:

            return (
                f"Recovery wellbeing guidance for Day "
                f"{postop_day}: "
                f"{rag_docs[0]['content']}"
            )

        return (
            f"Recovery can feel emotionally challenging on Day "
            f"{postop_day}. It may help to take recovery one step "
            "at a time and follow the movement plan prescribed by "
            "your care team. If you experience severe distress or "
            "feelings of hopelessness, contact your care team or "
            "an appropriate mental-health professional."
        )
