"""
LLM Chatbot Agent for Orthopedic Post-Op Recovery
Supports:
- OFFLINE: Qwen 2.5 3B GGUF through llama-cpp-python
- ONLINE: Ollama / Llama 3.2
- Clinical RAG
- Deterministic Safety Guardrails
"""

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

# Change this to "online" if you want to use Ollama.
# "offline" = Qwen GGUF + llama.cpp
# "online"  = Ollama + llama3.2
LLM_MODE = "offline"

# Ollama configuration
OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

# Local GGUF configuration
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
    """
    Load the local GGUF model only when offline mode is used.

    The model is loaded once and then reused for subsequent
    requests.
    """
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
            print(f"[OFFLINE LLM] {_local_llm_load_error}")
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

        print("[OFFLINE LLM] Qwen GGUF model loaded successfully.")

        return _local_llm

    except Exception as exc:
        _local_llm_load_error = str(exc)
        print(f"[OFFLINE LLM] Failed to load model: {exc}")
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
        # STEP 1: DETERMINISTIC SAFETY TRIAGE
        # ====================================================

        # Safety triage is ALWAYS based on the CURRENT message.
        # Chat history must NEVER override this.
        triage = (
            precomputed_triage
            if precomputed_triage is not None
            else SafetyTriageEngine.evaluate(
                symbols=user_message,
                post_op_day=postop_day
            )
        )

        # RED emergency immediately bypasses the LLM.
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

        # ====================================================
        # STEP 2: RAG
        # ====================================================

        procedure = procedure or resolve_procedure_code(surgery_type)

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

        # If RAG returned nothing, explicitly tell the model.
        if not rag_context:
            rag_context = "No relevant clinical reference was retrieved."

        # ====================================================
        # STEP 3: LLM
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
        # STEP 4: RETURN LLM RESPONSE
        # ====================================================

        if llm_response and not any(
            r in llm_response.lower()
            for r in [
                "can't provide medical advice",
                "cannot provide medical advice",
                "cannot give medical advice",
            ]
        ):

            if LLM_MODE.lower() == "offline":
                engine_name = f"Local GGUF LLM ({LOCAL_MODEL_NAME})"
            else:
                engine_name = f"Local Ollama LLM ({OLLAMA_MODEL})"

            return {
                "reply": llm_response,
                "triage_level": triage["triage_level"],
                "is_escalated": triage["is_escalated"],
                "engine": engine_name,
                "sources": [d["topic"] for d in rag_docs]
            }

        # ====================================================
        # STEP 5: FALLBACK
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
        )

        return {
            "reply": fallback_reply,
            "triage_level": triage["triage_level"],
            "is_escalated": triage["is_escalated"],
            "engine": "Clinical Synthesis Engine",
            "sources": [d["topic"] for d in rag_docs]
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
        # Build conversation history
        # ----------------------------------------------------

        history_lines = []

        for turn in chat_history[-10:]:
            role = turn.get("role", "user")
            content = turn.get("content", "").strip()

            if content and role in ("user", "assistant"):
                history_lines.append(
                    f"{role}: {content}"
                )

        history_text = (
            "\n".join(history_lines)
            if history_lines
            else "No previous conversation turns."
        )

        surgery_date_text = surgery_date or "Not provided"

        # ----------------------------------------------------
        # Specialist instruction
        # ----------------------------------------------------

        specialist_text = ""

        if domain_instruction:
            specialist_text = f"""
Specialist focus for this answer:
{domain_instruction}
"""

        # ----------------------------------------------------
        # System instructions
        # ----------------------------------------------------

        system_prompt = f"""
You are an orthopedic postoperative recovery assistant.

You are helping a patient recover after orthopedic surgery.

Patient information:
- Surgery type: {surgery_type}
- Affected limb: {affected_limb}
- Post-operative day: {postop_day}
- Surgery date: {surgery_date_text}

Clinical reference material retrieved from the approved knowledge base:
{rag_context}

Safety status from the deterministic safety system:
{triage["triage_level"]}

Important rules:
1. Answer using the retrieved clinical reference when relevant.
2. Do not invent medical protocols, exercises, medication instructions,
    restrictions, or recovery timelines.
3. Do not diagnose the patient.
4. Do not contradict the surgeon's or clinician's instructions.
5. If the retrieved reference does not contain enough information,
    clearly say that the available information is insufficient.
6. The deterministic safety system has already checked the current message.
7. Never claim that you performed a physical examination.
8. Keep the answer short and patient-friendly.
9. Do not mention internal implementation details such as RAG,
    ChromaDB, agents, prompts, or model names.
{specialist_text}
"""

        # ----------------------------------------------------
        # User prompt
        # ----------------------------------------------------

        user_prompt = f"""
Previous conversation:
{history_text}

Current user question:
{user_message}

Write a friendly 2-3 sentence answer directly addressing the
current question.

Mention postoperative-day goals, icing, limb elevation, exercises,
or other recovery instructions only when they are relevant to the
question AND supported by the clinical reference material.
"""

        # ====================================================
        # OFFLINE MODE
        # ====================================================

        if LLM_MODE.lower() == "offline":

            return cls._query_local_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                chat_history=chat_history
            )

        # ====================================================
        # ONLINE/OLLAMA MODE
        # ====================================================

        if LLM_MODE.lower() == "online":

            return cls._query_ollama(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )

        # ====================================================
        # INVALID MODE
        # ====================================================

        print(
            f"[LLM] Invalid LLM_MODE='{LLM_MODE}'. "
            f"Use 'offline' or 'online'."
        )

        return None

    # ============================================================
    # OFFLINE: QWEN GGUF + LLAMA.CPP
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
            print("[OFFLINE LLM] Model unavailable.")
            return None

        messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]

        # Add previous conversation turns.
        for turn in chat_history[-10:]:
            role = turn.get("role")
            content = turn.get("content", "").strip()

            if role in ("user", "assistant") and content:
                messages.append(
                    {
                        "role": role,
                        "content": content
                    }
                )

        # Current question comes last.
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
            print(f"[OFFLINE LLM] Generation failed: {exc}")
            return None

    # ============================================================
    # ONLINE: OLLAMA
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

            print(f"[OLLAMA] Request failed: {exc}")

            return None

    # NOTE: this exact phrase is generated verbatim by
    # agents/specialized_agents.py::_rehab_context_note() whenever a
    # weight_bearing_status was supplied to RehabilitationAgent. It is
    # checked here (via domain_instruction) as a deliberately minimal,
    # no-new-parameter signal that a restriction is on record -- see
    # _rehab_fallback_reply(). If that wording ever changes, update both.
    _WEIGHT_BEARING_RESTRICTION_MARKER = "Prescribed weight-bearing status:"

    # Anatomical body-region wording per RESOLVED procedure code, for
    # fallback text only -- mirrors the same TKA->knee / THA->hip
    # convention already used for RAG chunk metadata (see
    # rag/ingest.py::_BODY_REGION_BY_PROCEDURE). Deliberately has NO entry
    # for "GEN" (ankle/foot/lower-leg/unresolved): that code covers multiple
    # distinct anatomical regions, so guessing a specific one would be an
    # invented clinical assumption, not a lookup. Any procedure code with no
    # entry here (including GEN) falls back to neutral wording instead.
    _SWELLING_BODY_REGION_BY_PROCEDURE: Dict[str, str] = {
        "TKA": "knee",
        "THA": "hip",
    }
    _NEUTRAL_BODY_REGION = "operative area"

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
    ) -> str:

        lower = user_message.lower()

        if "update" in lower or "profile" in lower or "background" in lower or "history" in lower or "surgical" in lower:
            return (
                f"I can help you review and update your recovery profile and medical history for Day {postop_day}. "
                "Please provide the specific details, past surgeries, or background modifications you would like to change."
            )

        if "exercise" in lower or "workout" in lower or "physio" in lower:
            return cls._rehab_fallback_reply(
                postop_day=postop_day,
                rag_docs=rag_docs,
                domain_instruction=domain_instruction,
            )

        if "swell" in lower or "puff" in lower:
            body_region = cls._SWELLING_BODY_REGION_BY_PROCEDURE.get(
                procedure, cls._NEUTRAL_BODY_REGION
            )
            return cls._symptom_fallback_reply(
                symptom_label=f"swelling in your {affected_limb} {body_region}",
                postop_day=postop_day,
                rag_docs=rag_docs,
            )

        if "pain" in lower or "hurt" in lower:
            return cls._symptom_fallback_reply(
                symptom_label="pain",
                postop_day=postop_day,
                rag_docs=rag_docs,
            )

        if "drain" in lower or "incision" in lower or "bandage" in lower or "wound" in lower or "discharge" in lower:
            return cls._symptom_fallback_reply(
                symptom_label="drainage on your incision bandage",
                postop_day=postop_day,
                rag_docs=rag_docs,
            )

        if rag_docs:
            return f"Based on your Day {postop_day} recovery guidelines for {surgery_type}: {rag_docs[0]['content']}"

        return f"Hello! On Day {postop_day} of your recovery from {surgery_type} ({affected_limb}), make sure to keep up with your daily physical therapy routine, elevate your leg when resting, and stay hydrated."

    @classmethod
    def _rehab_fallback_reply(
        cls,
        postop_day: int,
        rag_docs: List[Dict[str, Any]],
        domain_instruction: Optional[str] = None,
    ) -> str:
        has_weight_bearing_restriction = (
            domain_instruction is not None
            and cls._WEIGHT_BEARING_RESTRICTION_MARKER in domain_instruction
        )
        restriction_note = (
            " A weight-bearing restriction is on record for you -- please follow it exactly "
            "and do not exceed what your care team has prescribed."
            if has_weight_bearing_restriction else ""
        )

        if rag_docs:
            return (
                f"Based on your Day {postop_day} retrieved rehabilitation guidance: "
                f"{rag_docs[0]['content']}{restriction_note}"
            )

        if has_weight_bearing_restriction:
            return (
                f"On Day {postop_day}, a weight-bearing restriction is on record for you, and "
                "I don't have a matching retrieved exercise protocol for this question right "
                "now. Please follow your prescribed restriction exactly and check with your "
                "surgical or physical therapy team before starting or progressing any exercise."
            )

        return (
            f"On Day {postop_day}, I don't have a specific retrieved exercise protocol for "
            "this question right now. Please follow your surgical team's prescribed "
            "rehabilitation plan, and check with your physical therapist before starting or "
            "progressing any exercise."
        )

    @classmethod
    def _symptom_fallback_reply(
        cls,
        symptom_label: str,
        postop_day: int,
        rag_docs: List[Dict[str, Any]],
    ) -> str:
        if rag_docs:
            return (
                f"You reported {symptom_label} on Day {postop_day}. Based on your retrieved "
                f"clinical guidance: {rag_docs[0]['content']}"
            )

        return (
            f"You reported {symptom_label} on Day {postop_day}. I don't have a matching "
            "retrieved protocol for this right now, so please follow your existing "
            "care-team or discharge instructions, and contact your surgical or physical "
            "therapy team if you're unsure or if it changes."
        )