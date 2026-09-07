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
    ) -> Dict[str, Any]:
        # Safety triage is always based on the CURRENT message.
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

        procedure = procedure or resolve_procedure_code(surgery_type)
        rag_docs = ClinicalKnowledgeBase.query(
            user_message, procedure=procedure, limit=2
        )
        rag_context = "\n".join(
            [f"- {d['topic']}: {d['content']}" for d in rag_docs]
        )

        # Grounding gate: the local LLM has no reliable way to refuse to
        # answer just because we ASK it to in the prompt -- a live test
        # against llama3.2 showed it will confidently invent a recovery
        # assessment ("you're doing great", "typically by Day 10...") and
        # unsupported treatment advice even when rag_context is empty and it
        # was told to answer "based on the discharge notes". So this is not
        # a prompting problem to work around with stronger wording: when
        # nothing relevant was retrieved, the free-generation LLM call must
        # not run at all, and we go straight to the deterministic,
        # never-invents-a-claim fallback below. This is also what keeps
        # `sources` truthful -- an empty sources list will now always pair
        # with a reply that only cites what was (not) retrieved, never with
        # LLM-invented content attributed to no source.
        llm_response = None
        if rag_docs:
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
                "sources": [d["topic"] for d in rag_docs]
            }

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
    ) -> str:
        history_lines = []
        for turn in chat_history[-10:]:
            role = turn.get("role", "user")
            content = turn.get("content", "").strip()
            if content:
                history_lines.append(f"{role}: {content}")

        history_text = "\n".join(history_lines) if history_lines else "No previous conversation turns."
        surgery_date_text = surgery_date or "Not provided"

        if domain_instruction:
            prompt = f"""Read the provided physical therapy discharge reference for Day {postop_day} after {surgery_type} ({affected_limb}):
{rag_context}

Patient surgery date: {surgery_date_text}

Previous conversation:
{history_text}

Specialist focus for this answer: {domain_instruction}

User's Question: "{user_message}"

Write a friendly, 2-3 sentence answer directly answering the user's question based on the discharge notes and relevant conversation context. Mention Day {postop_day} goals, icing, and limb elevation only when relevant:"""
        else:
            prompt = f"""Read the provided physical therapy discharge reference for Day {postop_day} after {surgery_type} ({affected_limb}):
{rag_context}

Patient surgery date: {surgery_date_text}

Previous conversation:
{history_text}

User's Question: "{user_message}"

Write a friendly, 2-3 sentence answer directly answering the user's question based on the discharge notes and relevant conversation context. Mention Day {postop_day} goals, icing, and limb elevation only when relevant:"""

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

        if rag_docs:
            return f"Based on your Day {postop_day} protocol for {surgery_type}: {rag_docs[0]['content']}"

        # No retrieved protocol content matched this question -- do not
        # assert a recovery assessment ("on track", "doing great"), a
        # timeline ("typically by Day X..."), or unrequested clinical advice
        # (icing, elevation, hydration) with no retrieved support behind it.
        # This is the conservative reply Milestone Sec 2.5 requires when
        # nothing relevant was retrieved for a recovery-progress-style
        # question (see agents/specialized_agents.py::RecoveryProgressAgent).
        return (
            f"I don't have enough retrieved protocol information for Day {postop_day} "
            f"of your {surgery_type} recovery to judge whether you're on track or give "
            "a specific timeline for this question. Please continue following your "
            "surgical and physical therapy team's existing guidance, and check with "
            "them for a personalized assessment of your progress."
        )

    @classmethod
    def _rehab_fallback_reply(
        cls,
        postop_day: int,
        rag_docs: List[Dict[str, Any]],
        domain_instruction: Optional[str] = None,
    ) -> str:
        """
        Deterministic (Ollama-unavailable) fallback for exercise/workout/
        physio queries. `rag_docs` was already retrieved by
        answer_question() via ClinicalKnowledgeBase.query(..., procedure=
        procedure) -- i.e. already procedure-filtered (TKA/THA/GEN never
        cross-contaminate, see rag/knowledge_base.py). This method must
        NEVER hardcode procedure-specific exercise content itself (that was
        the root cause of TKA-flavored ROM/rep numbers leaking to THA/GEN
        patients) -- it only ever cites the already-filtered rag_docs, or
        falls back to conservative, non-specific wording. No exercise name,
        repetition count, or ROM value is invented here.
        """
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
        """
        Deterministic (Ollama-unavailable) fallback for swelling/pain
        symptom queries. `rag_docs` was already retrieved by
        answer_question() via ClinicalKnowledgeBase.query(..., procedure=
        procedure) -- i.e. already procedure-filtered (TKA/THA/GEN never
        cross-contaminate, see rag/knowledge_base.py).

        This method must NEVER hardcode a clinical judgment ("is normal",
        "is typical"), a numeric treatment instruction (icing duration,
        medication timing), or any threshold of its own -- that was the
        root cause of unfounded claims like "normal due to increased
        circulation" and "ice pack for 20 minutes" being asserted with no
        grounding in the retrieved protocol. It only ever cites the
        already-filtered rag_docs verbatim, or acknowledges the reported
        symptom and defers to the patient's existing care-team/discharge
        instructions when nothing relevant was retrieved -- never
        classifying the symptom as normal or abnormal itself.
        """
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
