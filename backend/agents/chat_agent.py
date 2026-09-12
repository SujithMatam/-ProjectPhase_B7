"""
LLM Chatbot Agent for Orthopedic Post-Op Recovery.

Supports:
- OFFLINE: Qwen 2.5 3B GGUF through llama-cpp-python
- ONLINE: Ollama / Llama 3.2
- Clinical RAG
- Deterministic Safety Guardrails
- Intake/context-aware responses
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional

from triage.safety_triage import SafetyTriageEngine
from rag.knowledge_base import ClinicalKnowledgeBase
from lam.schemas import resolve_procedure_code


# ============================================================
# LLM CONFIGURATION
# ============================================================

LLM_MODE = "offline"

OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

BACKEND_DIR = Path(__file__).resolve().parent.parent

LOCAL_MODEL_PATH = (
    BACKEND_DIR
    / "models"
    / "qwen2.5-3b-instruct-q4_k_m.gguf"
)

LOCAL_MODEL_NAME = "Qwen2.5-3B-Instruct-Q4_K_M"


# ============================================================
# LOCAL LLM
# ============================================================

_local_llm = None
_local_llm_load_error = None


def _get_local_llm():

    global _local_llm
    global _local_llm_load_error

    if _local_llm is not None:
        return _local_llm

    if _local_llm_load_error is not None:
        return None

    try:

        if not LOCAL_MODEL_PATH.exists():

            _local_llm_load_error = (
                f"GGUF model not found at: {LOCAL_MODEL_PATH}"
            )

            print(
                f"[OFFLINE LLM] {_local_llm_load_error}"
            )

            return None

        from llama_cpp import Llama

        print("[OFFLINE LLM] Loading Qwen GGUF model...")
        print(f"[OFFLINE LLM] Model: {LOCAL_MODEL_PATH}")

        _local_llm = Llama(
            model_path=str(LOCAL_MODEL_PATH),
            n_ctx=4096,
            n_threads=6,
            n_gpu_layers=0,
            verbose=False,
        )

        print(
            "[OFFLINE LLM] Qwen GGUF model loaded successfully."
        )

        return _local_llm

    except Exception as exc:

        _local_llm_load_error = str(exc)

        print(
            f"[OFFLINE LLM] Failed to load model: {exc}"
        )

        return None


# ============================================================
# CHAT AGENT
# ============================================================

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
                symbols=user_message,
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
        # LLM
        # ====================================================

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
        )

        # ====================================================
        # STEP 4
        # VALID LLM RESPONSE
        # ====================================================

        if llm_response and not any(
            phrase in llm_response.lower()
            for phrase in [
                "can't provide medical advice",
                "cannot provide medical advice",
                "cannot give medical advice",
            ]
        ):

            if LLM_MODE.lower() == "offline":

                engine_name = (
                    f"Local GGUF LLM ({LOCAL_MODEL_NAME})"
                )

            else:

                engine_name = (
                    f"Local Ollama LLM ({OLLAMA_MODEL})"
                )

            return {
                "reply": llm_response,
                "triage_level": triage["triage_level"],
                "is_escalated": triage["is_escalated"],
                "engine": engine_name,
                "sources": [
                    d["topic"]
                    for d in rag_docs
                ]
            }

        # ====================================================
        # STEP 5
        # DETERMINISTIC FALLBACK
        # ====================================================

        fallback_reply = cls._generate_smart_reply(
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
            "reply": fallback_reply,
            "triage_level": triage["triage_level"],
            "is_escalated": triage["is_escalated"],
            "engine": "Clinical Synthesis Engine",
            "sources": [
                d["topic"]
                for d in rag_docs
            ]
        }

    # ============================================================
    # LLM ROUTER
    # ============================================================

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
    ) -> Optional[str]:

        # ----------------------------------------------------
        # Conversation history
        # ----------------------------------------------------

        history_lines = []

        for turn in chat_history[-10:]:

            role = turn.get(
                "role",
                "user"
            )

            content = turn.get(
                "content",
                ""
            ).strip()

            if content and role in (
                "user",
                "assistant"
            ):

                history_lines.append(
                    f"{role}: {content}"
                )

        history_text = (
            "\n".join(history_lines)
            if history_lines
            else "No previous conversation turns."
        )

        surgery_date_text = (
            surgery_date
            or "Not provided"
        )

        # ----------------------------------------------------
        # Specialist instruction
        # ----------------------------------------------------

        specialist_text = ""

        if domain_instruction:

            specialist_text = f"""
Specialist focus:
{domain_instruction}
"""

        # ----------------------------------------------------
        # Detect intake mode
        # ----------------------------------------------------

        is_intake = False

        if domain_instruction:

            if "Intake & Context Agent" in domain_instruction:
                is_intake = True

        # ----------------------------------------------------
        # Intake-specific rules
        # ----------------------------------------------------

        intake_rules = ""

        if is_intake:

            intake_rules = """
INTAKE MODE:

The current user message is being handled by the
Intake & Context Agent.

If the user is simply greeting or introducing themselves:

- respond naturally and warmly;
- if they provide their name, use it naturally;
- do not repeat their entire message back to them;
- do not say phrases such as "I have received your message";
- do not give generic postoperative recovery advice;
- do not give exercise, medication, diet, wound-care,
  or recovery-timeline advice unless explicitly requested;
- simply acknowledge them and ask how you can help.

If the user provides patient or surgery information:

- acknowledge the information naturally;
- use only information explicitly supplied by the user;
- do not invent missing information;
- do not assume a specific procedure from a general statement
  such as "knee surgery";
- do not assume the affected limb unless supplied;
- do not invent a surgery date;
- ask for missing information only when it is useful.

The response should sound like a natural healthcare assistant,
not like a system confirmation message.
"""

        # ----------------------------------------------------
        # System prompt
        # ----------------------------------------------------

        system_prompt = f"""
You are an orthopedic postoperative recovery assistant.

You are helping a patient recover after orthopedic surgery.

Patient information:
- Patient ID: {patient_id}
- Surgery type: {surgery_type}
- Affected limb: {affected_limb}
- Post-operative day: {postop_day}
- Surgery date: {surgery_date_text}

Clinical reference material retrieved from the approved
knowledge base:

{rag_context}

Safety status from the deterministic safety system:
{triage["triage_level"]}

Important rules:

1. Answer the CURRENT user message directly.
2. Use retrieved clinical reference material when relevant.
3. Do not invent medical protocols, exercises, medication
   instructions, restrictions, or recovery timelines.
4. Do not diagnose the patient.
5. Do not contradict the surgeon's or clinician's instructions.
6. If the retrieved reference does not contain enough information,
   clearly say that the available information is insufficient.
7. The deterministic safety system has already checked the
   current message.
8. Never claim that you performed a physical examination.
9. Keep the answer short and patient-friendly.
10. Do not mention internal implementation details such as
    RAG, ChromaDB, agents, prompts, or model names.
11. Do not answer an intake message with generic postoperative
    instructions unless the patient actually asks for those
    instructions.
12. Do not mechanically repeat the user's message back to them.
13. For greetings and introductions, respond conversationally
    rather than giving medical information.
{specialist_text}

{intake_rules}
"""

        # ----------------------------------------------------
        # User prompt
        # ----------------------------------------------------

        user_prompt = f"""
Previous conversation:
{history_text}

Current user message:
{user_message}

Respond directly to the current user message.

If this is a simple greeting or introduction:
respond naturally and briefly.

If this is an intake/context message:
acknowledge the information provided and respond specifically
to what the patient said.

If this is a clinical question:
answer the clinical question using the available retrieved
reference material.
"""

        # ====================================================
        # OFFLINE
        # ====================================================

        if LLM_MODE.lower() == "offline":

            return cls._query_local_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                chat_history=chat_history
            )

        # ====================================================
        # ONLINE
        # ====================================================

        if LLM_MODE.lower() == "online":

            return cls._query_ollama(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )

        print(
            f"[LLM] Invalid LLM_MODE='{LLM_MODE}'. "
            "Use 'offline' or 'online'."
        )

        return None

    # ============================================================
    # OFFLINE
    # ============================================================

    @classmethod
    def _query_local_llm(
        cls,
        system_prompt: str,
        user_prompt: str,
        chat_history: List[Dict[str, str]]
    ) -> Optional[str]:

        llm = _get_local_llm()

        if llm is None:

            print(
                "[OFFLINE LLM] Model unavailable."
            )

            return None

        messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]

        for turn in chat_history[-10:]:

            role = turn.get("role")
            content = turn.get(
                "content",
                ""
            ).strip()

            if role in (
                "user",
                "assistant"
            ) and content:

                messages.append(
                    {
                        "role": role,
                        "content": content
                    }
                )

        messages.append(
            {
                "role": "user",
                "content": user_prompt
            }
        )

        try:

            result = llm.create_chat_completion(
                messages=messages,
                temperature=0.2,
                max_tokens=150,
            )

            response = (
                result["choices"][0]["message"]["content"]
                .strip()
            )

            return response

        except Exception as exc:

            print(
                f"[OFFLINE LLM] Generation failed: {exc}"
            )

            return None

    # ============================================================
    # ONLINE
    # ============================================================

    @classmethod
    def _query_ollama(
        cls,
        system_prompt: str,
        user_prompt: str,
    ) -> Optional[str]:

        prompt = f"""
{system_prompt}

{user_prompt}
"""

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 150
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

        except Exception as exc:

            print(
                f"[OLLAMA] Request failed: {exc}"
            )

            return None

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
