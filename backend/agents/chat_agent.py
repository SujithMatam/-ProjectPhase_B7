"""
LLM Chatbot Agent for Orthopedic Post-Op Recovery
Powered by Local Offline LLM (Ollama / Llama 3.2) + Clinical RAG + Safety Guardrails.
Generates unique, context-aware, medically grounded answers for every question.
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
        precomputed_triage: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Phase 4 notes (both optional, backward-compatible additions --
        existing callers that omit them get byte-identical behavior to
        before):

        `domain_instruction` -- when a specialized agent (agents/agent_
        router.py) supplies it, it steers the LLM prompt's framing (see
        _query_llama) without adding a second RAG implementation or a
        second LLM call.

        `precomputed_triage` -- the LAM orchestrator already runs
        SafetyTriageEngine.evaluate() once, upstream, before a specialized
        agent is ever dispatched (RED short-circuits there and never
        reaches this method at all). Passing that already-computed result
        through here avoids evaluating safety triage a second time for the
        same request. If omitted (direct/legacy ChatAgent callers not going
        through the LAM), this method still runs its own triage exactly as
        before -- callers outside the LAM have no other safety net.
        """

        # Step 1: Emergency Safety Triage Check (Hard rule filter).
        # Reuse the LAM's already-computed result when supplied instead of
        # evaluating it again -- see precomputed_triage note above.
        triage = precomputed_triage if precomputed_triage is not None else SafetyTriageEngine.evaluate(
            symptoms=user_message,
            post_op_day=postop_day
        )

        if triage["triage_level"] == "RED":
            reply_text = (
                f"⚠️ **CRITICAL EMERGENCY ALERT**\n\n"
                f"Your symptoms require urgent medical evaluation: "
                f"**{', '.join(triage['reasons'])}**.\n\n"
                f"{triage['action_protocol']}\n\n"
                f"Please contact your hospital emergency line or visit the nearest emergency department right away."
            )
            return {
                "reply": reply_text,
                "triage_level": "RED",
                "is_escalated": True,
                "engine": "Deterministic Safety Triage",
                "sources": []
            }

        # Step 2: Retrieve Relevant Orthopedic RAG Protocols
        procedure = procedure or resolve_procedure_code(surgery_type)
        rag_docs = ClinicalKnowledgeBase.query(user_message, procedure=procedure, limit=2)
        rag_context = "\n".join([f"- {d['topic']}: {d['content']}" for d in rag_docs])

        # Step 3: Local LLM Inference via Ollama (Llama 3.2)
        llm_response = cls._query_llama(
            user_message=user_message,
            patient_id=patient_id,
            surgery_type=surgery_type,
            affected_limb=affected_limb,
            postop_day=postop_day,
            rag_context=rag_context,
            triage=triage,
            domain_instruction=domain_instruction
        )

        # Ensure we filter out Meta's generic refusal if it triggers
        if llm_response and not any(r in llm_response.lower() for r in ["can't provide medical advice", "cannot provide medical advice", "cannot give medical advice"]):
            return {
                "reply": llm_response,
                "triage_level": triage["triage_level"],
                "is_escalated": triage["is_escalated"],
                "engine": f"Local LLM ({DEFAULT_MODEL})",
                "sources": [d["topic"] for d in rag_docs]
            }

        # Smart generative fallback tailored to the user's specific text & day
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
            "sources": [d["topic"] for d in rag_docs]
        }

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
        domain_instruction: Optional[str] = None
    ) -> str:
        # Byte-identical to the original prompt when no domain_instruction is
        # supplied, so existing callers (direct ChatAgent use without the
        # Phase 4 specialized-agent layer) see no behavior change.
        if domain_instruction:
            prompt = f"""Read the provided physical therapy discharge reference for Day {postop_day} after {surgery_type} ({affected_limb}):
{rag_context}

Specialist focus for this answer: {domain_instruction}

User's Question: "{user_message}"

Write a friendly, 2-3 sentence answer directly answering the user's question based on the discharge notes. Mention Day {postop_day} goals, icing, and limb elevation:"""
        else:
            prompt = f"""Read the provided physical therapy discharge reference for Day {postop_day} after {surgery_type} ({affected_limb}):
{rag_context}

User's Question: "{user_message}"

Write a friendly, 2-3 sentence answer directly answering the user's question based on the discharge notes. Mention Day {postop_day} goals, icing, and limb elevation:"""

        payload = {
            "model": DEFAULT_MODEL,
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
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data.get("response", "").strip()
        except Exception:
            return None

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

        # Day specific exercise guidance
        if "exercise" in lower or "workout" in lower or "physio" in lower:
            if postop_day <= 2:
                return f"For Post-Op Day {postop_day}, your focus is gentle in-bed mobility: ankle pumps (10 every hour) to prevent blood clots, gentle quad sets pushing your knee flat into the bed, and short assisted transfers with your walker."
            elif postop_day <= 7:
                return f"On Day {postop_day}, your targets are active-assisted heel slides aiming for 70°–90° flexion, straight leg raises to rebuild quadriceps strength, and walking 5–10 minutes with your walker every 2 hours."
            else:
                return f"At Day {postop_day}, work on progressing your passive flexion past 90°, standing calf raises, seated knee extension, and increasing your independent walking endurance as tolerated."

        if "swell" in lower or "puff" in lower:
            return f"Swelling in your {affected_limb} {('knee' if 'knee' in surgery_type.lower() else 'hip')} on Day {postop_day} is normal due to increased circulation during healing. Lie down with your foot elevated above heart level and apply an ice pack for 20 minutes."

        if "pain" in lower or "hurt" in lower:
            return f"Mild to moderate soreness is typical on Day {postop_day}. Take your prescribed pain medication 30-45 minutes before starting physical therapy to keep your discomfort manageable."

        if rag_docs:
            return f"Based on your Day {postop_day} protocol for {surgery_type}: {rag_docs[0]['content']}"

        return f"Hello! On Day {postop_day} of your recovery from {surgery_type} ({affected_limb}), make sure to keep up with your daily physical therapy routine, elevate your leg when resting, and stay hydrated."
