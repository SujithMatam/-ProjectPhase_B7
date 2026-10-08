"""
Read-only LLM trace for the --live conversation eval.

Wraps (never replaces) the points where a final-turn reply is decided, so a
live run records, per turn:
  * every Ollama /api/generate call: the full prompt, the raw response,
    done_reason ("length" = stopped at num_predict), eval_count, wall time,
    or the exception (timeout / other) that made ChatAgent fall back;
  * what ChatAgent.answer_question returned (engine + reply);
  * each agent-side acceptance check and its result (Pain: unhelpful /
    invents-symptom / consistency with sub-reason; Recovery: unhelpful /
    llm_body_is_acceptable with sub-reason; Rehab: unhelpful / the
    weight-bearing status guard);
  * the deterministic reply the agent would have sent instead of (or did
    send in place of) the LLM text.

Every wrapper calls the original function with the original arguments and
returns its result unchanged; agent behaviour is identical to an untraced
run. Nothing here is imported unless run_conversations.py is given --live.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import socket
import sys
import time
import urllib.request
from typing import Any, Dict, List
from unittest.mock import patch

OLLAMA_GENERATE = "/api/generate"


class _Response(io.BytesIO):
    """Stands in for the urlopen response after its body was read once."""

    def __init__(self, body: bytes, status: int):
        super().__init__(body)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class LLMTrace:
    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def take(self) -> List[Dict[str, Any]]:
        events, self.events = self.events, []
        return events

    # ------------------------------------------------------------------
    @contextlib.contextmanager
    def install(self, backend):
        from agents import pain_integration, recovery_integration, rehab_agent

        stack = contextlib.ExitStack()
        trace = self

        # 1. Ollama HTTP calls ------------------------------------------------
        original_urlopen = urllib.request.urlopen

        def urlopen(req, *args, **kwargs):
            url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
            if OLLAMA_GENERATE not in url:
                return original_urlopen(req, *args, **kwargs)
            payload = json.loads(req.data.decode("utf-8")) if getattr(req, "data", None) else {}
            event: Dict[str, Any] = {
                "kind": "ollama", "model": payload.get("model"),
                "num_predict": (payload.get("options") or {}).get("num_predict"),
                "timeout": kwargs.get("timeout", args[1] if len(args) > 1 else None),
                "prompt": payload.get("prompt", ""),
            }
            started = time.time()
            try:
                with original_urlopen(req, *args, **kwargs) as resp:
                    body = resp.read()
                    status = resp.status
            except Exception as exc:
                event["seconds"] = round(time.time() - started, 2)
                timed_out = isinstance(exc, (socket.timeout, TimeoutError)) or "timed out" in str(exc).lower()
                event["outcome"] = "timeout" if timed_out else "error"
                event["error"] = f"{type(exc).__name__}: {exc}"
                trace.events.append(event)
                raise
            event["seconds"] = round(time.time() - started, 2)
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                data = {}
            event.update({
                "outcome": "ok",
                "response": data.get("response", ""),
                "done_reason": data.get("done_reason"),
                "eval_count": data.get("eval_count"),
                "load_duration_s": round((data.get("load_duration") or 0) / 1e9, 2),
                "total_duration_s": round((data.get("total_duration") or 0) / 1e9, 2),
            })
            trace.events.append(event)
            return _Response(body, status)

        stack.enter_context(patch.object(urllib.request, "urlopen", urlopen))

        # 2. ChatAgent.answer_question ---------------------------------------
        original_answer = backend.ChatAgent.answer_question

        def answer_question(*args, **kwargs):
            result = original_answer(*args, **kwargs)
            trace.events.append({
                "kind": "chat_agent", "engine": (result or {}).get("engine"),
                "reply": (result or {}).get("reply"), "triage_level": (result or {}).get("triage_level"),
                "caller": sys._getframe(1).f_code.co_name,
            })
            return result

        stack.enter_context(patch.object(backend.ChatAgent, "answer_question", staticmethod(answer_question)))

        # 3. Acceptance checks -----------------------------------------------
        def wrap_check(module, name, agent, detail=None):
            original = getattr(module, name)

            def wrapper(*args, **kwargs):
                result = original(*args, **kwargs)
                event = {"kind": "check", "agent": agent, "check": name, "result": result}
                if detail is not None:
                    try:
                        event["detail"] = detail(result, *args, **kwargs)
                    except Exception as exc:  # detail is diagnostic only
                        event["detail"] = f"(detail failed: {exc})"
                trace.events.append(event)
                return result

            stack.enter_context(patch.object(module, name, wrapper))

        def pain_consistency_detail(result, reply, assessment, triage):
            if result:
                return None
            lowered = (reply or "").strip().lower()
            if not pain_integration._reflects_pain_score(lowered, assessment):
                return "does not reflect the pain score"
            if not pain_integration._reflects_location(lowered, assessment):
                return "does not reflect the location"
            if not pain_integration._reflects_worsening_trend(lowered, assessment):
                return "does not reflect the worsening trend"
            if pain_integration._contains_blanket_reassurance(lowered):
                return f"blanket reassurance at {(triage or {}).get('triage_level')}"
            return f"action protocol not reflected at {(triage or {}).get('triage_level')}"

        def recovery_detail(result, body, *, allowed_numbers):
            if result:
                return None
            text = (body or "").strip()
            if len(text) < 20:
                return "shorter than 20 characters"
            phrases = [p for p in recovery_integration._FORBIDDEN_LLM_PHRASES if p in text.lower()]
            if phrases:
                return f"trajectory language: {phrases}"
            allowed = {recovery_integration._fmt_num(n) for n in allowed_numbers}
            extra = [m for m in recovery_integration._NUMBER_RE.findall(text)
                     if recovery_integration._fmt_num(m) not in allowed]
            return f"number(s) not in the deterministic data: {extra}"

        def wb_detail(result, reply, weight_bearing):
            if not result:
                return None
            lower = (reply or "").lower().replace("’", "'")
            hits = [p for p in rehab_agent._LOADING_BREACH_PHRASES.get(weight_bearing or "", ())
                    if any(not rehab_agent._loading_phrase_negated(lower, m.start())
                           for m in re.finditer(re.escape(p), lower))]
            return f"status {weight_bearing}: {hits}"

        wrap_check(pain_integration, "is_unhelpful_llm_reply", "pain/recovery")
        wrap_check(pain_integration, "reply_invents_unreported_symptom", "pain")
        wrap_check(pain_integration, "reply_consistent_with_assessment_and_triage", "pain", pain_consistency_detail)
        wrap_check(recovery_integration, "llm_body_is_acceptable", "recovery", recovery_detail)
        wrap_check(rehab_agent, "is_unhelpful_llm_reply", "rehab")
        wrap_check(rehab_agent, "reply_breaches_weight_bearing", "rehab", wb_detail)
        wrap_check(rehab_agent, "reply_unsourced_numbers", "rehab")

        # 4. Deterministic counterparts --------------------------------------
        original_pain_compose = pain_integration.compose_final_reply
        original_pain_det = pain_integration.deterministic_summary

        def pain_compose(body, assessment, triage, trend_note):
            trace.events.append({"kind": "deterministic", "agent": "pain", "used": False,
                                 "reply": original_pain_det(assessment, triage, trend_note)})
            return original_pain_compose(body, assessment, triage, trend_note)

        def pain_det(assessment, triage, trend_note):
            reply = original_pain_det(assessment, triage, trend_note)
            trace.events.append({"kind": "deterministic", "agent": "pain", "used": True, "reply": reply})
            return reply

        stack.enter_context(patch.object(pain_integration, "compose_final_reply", pain_compose))
        stack.enter_context(patch.object(pain_integration, "deterministic_summary", pain_det))

        original_rec_compose = recovery_integration.compose_final_reply

        def recovery_compose(llm_body, block):
            trace.events.append({"kind": "deterministic", "agent": "recovery", "used": not llm_body,
                                 "reply": original_rec_compose(None, block)})
            return original_rec_compose(llm_body, block)

        stack.enter_context(patch.object(recovery_integration, "compose_final_reply", recovery_compose))

        original_collapse = rehab_agent.collapse_blank_lines

        def rehab_collapse(text):
            frame = sys._getframe(1)
            if frame.f_code.co_name == "_answer":
                loc = frame.f_locals
                if {"procedure", "topic", "day", "entry", "closing", "engine"} <= set(loc):
                    det_body = rehab_agent.fallback_text(loc["procedure"], loc["topic"], loc["day"], loc["entry"])
                    used = loc["engine"] != rehab_agent.RehabilitationAgent.ENGINE_LLM
                    trace.events.append({"kind": "deterministic", "agent": "rehab", "used": used,
                                         "reply": original_collapse("\n\n".join([det_body] + list(loc["closing"])))})
            return original_collapse(text)

        stack.enter_context(patch.object(rehab_agent, "collapse_blank_lines", rehab_collapse))

        with stack:
            yield self
