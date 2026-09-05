"""
Base Clinical Agent -- Phase 4 specialized-agent execution layer.

Defines the common interface every specialized clinical agent implements.
Each subclass carries exactly two pieces of domain identity:

    TARGET_AGENT    -- the lam.schemas.TargetAgent enum value this agent
                       corresponds to (must match the orchestrator's
                       existing intent -> TargetAgent routing table).
    DOMAIN_FOCUS    -- a concise, human-written instruction describing what
                       this agent should focus on (and avoid) when framing
                       its answer. This is a domain INSTRUCTION, not new
                       clinical knowledge -- it steers how the existing
                       RAG + local-LLM pipeline phrases its answer; it does
                       not introduce facts that aren't already in the
                       retrieved clinical context.

No agent reimplements RAG, LLM calling, or fallback synthesis -- handle()
delegates straight to the existing ChatAgent.answer_question(), passing its
DOMAIN_FOCUS through the (new, optional, backward-compatible)
`domain_instruction` parameter. This is what makes each agent functionally
specialized without duplicating the response-generation pipeline eight
times.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.chat_agent import ChatAgent
from lam.schemas import TargetAgent


class BaseClinicalAgent:
    """
    Common interface for all specialized clinical agents. Not instantiated --
    subclasses set the two class attributes below and inherit handle()
    unchanged, unless a specific agent genuinely needs different behavior.
    """

    TARGET_AGENT: TargetAgent
    DOMAIN_FOCUS: str

    @classmethod
    def handle(
        cls,
        *,
        patient_id: str,
        surgery_type: str,
        affected_limb: str,
        postop_day: int,
        user_message: str,
        procedure: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        precomputed_triage: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute this specialized agent against the shared response-generation
        pipeline (Phase 3 RAG + local LLM + deterministic fallback), steered
        by this agent's DOMAIN_FOCUS. Returns the same dict shape ChatAgent
        has always returned (reply, triage_level, is_escalated, engine,
        sources) -- the orchestrator merges this with LAM routing metadata
        exactly as before.

        `precomputed_triage`: the LAM already ran SafetyTriageEngine once,
        upstream, before this agent was ever dispatched (a RED result never
        reaches here). Passed straight through to ChatAgent so it is not
        evaluated a second time for the same request.
        """
        return ChatAgent.answer_question(
            patient_id=patient_id,
            surgery_type=surgery_type,
            affected_limb=affected_limb,
            postop_day=postop_day,
            user_message=user_message,
            chat_history=chat_history,
            procedure=procedure,
            domain_instruction=cls.DOMAIN_FOCUS,
            precomputed_triage=precomputed_triage,
        )
