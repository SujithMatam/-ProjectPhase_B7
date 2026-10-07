"""
Build the data sections of eval/agents/LIVE_REPORT.md from the two --live
runs (results/live_direct.json, results/live_orchestrator.json).

    .venv/Scripts/python.exe eval/agents/build_live_report.py > draft.md

A "final turn" is a turn on which the conversation's own agent closed the
interview with a synthesized answer, i.e. the trace holds a deterministic
counterpart for it (Pain deterministic_summary, Recovery block without an
LLM body, Rehab sourced fallback). Each is classified from its llm_trace.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RUNS = [("direct", "live_direct.json"), ("orchestrator", "live_orchestrator.json")]
AGENTS = ["pain", "recovery", "rehab"]
SIDE_BY_SIDE = {f"c0{i}" for i in range(1, 8)}
NUMBER = re.compile(r"\d+(?:\.\d+)?")
RAG_SECTION = re.compile(r"\):\s*\n(.*?)\n\s*Patient surgery date:", re.S)


def first(events, kind, **match) -> Optional[Dict[str, Any]]:
    for e in events:
        if e.get("kind") == kind and all(e.get(k) == v for k, v in match.items()):
            return e
    return None


def classify(turn: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    events = turn.get("llm_trace") or []
    det = [e for e in events if e["kind"] == "deterministic"]
    if not det:
        return None
    det = det[-1]
    ollama = [e for e in events if e["kind"] == "ollama"]
    ollama = ollama[-1] if ollama else None
    chat = [e for e in events if e["kind"] == "chat_agent"]
    chat = chat[-1] if chat else None
    chat_engine = (chat or {}).get("engine") or ""
    checks = [e for e in events if e["kind"] == "check"]

    reasons: List[str] = []
    category = None
    if ollama is None:
        if chat_engine == "Deterministic Safety Triage":
            category = "RED triage (no LLM call)"
        else:
            category = "no LLM call"
        reasons.append(f"ChatAgent engine: {chat_engine or 'not called'}")
    elif ollama["outcome"] == "timeout":
        category = "timeout"
        reasons.append(f"Ollama call timed out after {ollama['seconds']} s (timeout={ollama['timeout']} s)")
    elif ollama["outcome"] == "error":
        category = "Ollama error"
        reasons.append(ollama.get("error", ""))
    truncated = bool(ollama and ollama.get("done_reason") == "length")
    for c in checks:
        failed = (c["check"] in ("is_unhelpful_llm_reply", "reply_breaches_weight_bearing") and c["result"]) \
            or (c["check"] == "reply_invents_unreported_symptom" and c["result"]) \
            or (c["check"] in ("reply_consistent_with_assessment_and_triage", "llm_body_is_acceptable") and not c["result"])
        if failed:
            label = {"reply_breaches_weight_bearing": "status guard"}.get(c["check"], "consistency check")
            category = category or label
            detail = c.get("detail") or (c["result"] if c["check"] == "reply_invents_unreported_symptom" else "")
            reasons.append(f"{c['check']} -> {c['result']}" + (f" ({detail})" if detail else ""))
    if not det["used"]:
        if chat_engine.startswith("Local LLM"):
            category = "LLM"
        else:
            category = "accepted non-LLM ChatAgent text"
            reasons.append(f"ChatAgent engine {chat_engine} text passed the agent's checks")
    elif category is None:
        if ollama and ollama["outcome"] == "ok" and not chat_engine.startswith("Local LLM"):
            category = "ChatAgent fallback (empty or refusal)"
            reasons.append(f"Ollama returned {len(ollama.get('response') or '')} chars; ChatAgent engine {chat_engine}")
        else:
            category = "other"
    if truncated:
        reasons.append(f"Ollama stopped at num_predict={ollama['num_predict']} (done_reason=length, {ollama['eval_count']} tokens)")
        if category in ("consistency check", "status guard"):
            category = f"150-token cutoff -> {category}"
    return {"category": category, "reasons": reasons, "ollama": ollama, "chat_engine": chat_engine,
            "deterministic": det["reply"], "used_deterministic": det["used"], "truncated": truncated}


def number_flags(ollama: Dict[str, Any]) -> Dict[str, List[str]]:
    prompt = ollama.get("prompt") or ""
    m = RAG_SECTION.search(prompt)
    rag = m.group(1) if m else ""
    rag_nums = set(NUMBER.findall(rag))
    prompt_nums = set(NUMBER.findall(prompt))
    out = {"not_in_prompt": [], "patient_data_only": []}
    for n in NUMBER.findall(ollama.get("response") or ""):
        if n in rag_nums:
            continue
        key = "patient_data_only" if n in prompt_nums else "not_in_prompt"
        if n not in out[key]:
            out[key].append(n)
    return out


def fence(text: str) -> str:
    return "```text\n" + (text or "").strip() + "\n```"


def main() -> int:
    data = {name: json.loads((RESULTS / fn).read_text(encoding="utf-8")) for name, fn in RUNS}
    lines: List[str] = []
    w = lines.append

    w("## Final-turn engine per agent\n")
    w("| run | agent | final turns | Local LLM | deterministic fallback | fallback rate | fallback causes |")
    w("|---|---|---|---|---|---|---|")
    finals: Dict[str, List[Dict[str, Any]]] = {}
    for run_name, d in data.items():
        for agent in AGENTS:
            rows = []
            for run in d["runs"]:
                if run["agent"] != agent:
                    continue
                for t in run["turns"]:
                    c = classify(t)
                    if c:
                        rows.append(dict(c, conv=run["id"], turn=t["index"], run=run_name,
                                         sent=t["reply"], triage=t["triage_level"]))
            finals[f"{run_name}/{agent}"] = rows
            llm = sum(r["category"] == "LLM" for r in rows)
            fb = len(rows) - llm
            causes: Dict[str, int] = {}
            for r in rows:
                if r["category"] != "LLM":
                    causes[r["category"]] = causes.get(r["category"], 0) + 1
            rate = f"{fb / len(rows):.0%}" if rows else "-"
            w(f"| {run_name} | {agent} | {len(rows)} | {llm} | {fb} | {rate} | "
              + ("; ".join(f"{k} x{v}" for k, v in sorted(causes.items())) or "-") + " |")
    w("")

    w("## Every final turn\n")
    for key, rows in finals.items():
        w(f"### {key}\n")
        w("| conversation | turn | triage | outcome | why | Ollama s | tokens / done_reason |")
        w("|---|---|---|---|---|---|---|")
        for r in rows:
            o = r["ollama"] or {}
            w(f"| {r['conv']} | {r['turn']} | {r['triage']} | {r['category']} | "
              + ("; ".join(r["reasons"]).replace("|", "/") or "accepted") + f" | {o.get('seconds', '-')} | "
              + (f"{o.get('eval_count')} / {o.get('done_reason')}" if o.get("outcome") == "ok" else "-") + " |")
        w("")

    w("## Latency\n")
    w("Wall time of the whole turn (agent + retrieval + LLM) as recorded by run_conversations.py, "
      "and the Ollama call alone. The warm-up request (results/live_warmup.json) ran in a separate "
      "process before both runs and is in none of these figures.\n")
    w("| run | agent | turns | median s/turn | median s/final turn | median Ollama s/call | max s/turn |")
    w("|---|---|---|---|---|---|---|")
    for run_name, d in data.items():
        for agent in AGENTS:
            secs = [t["seconds"] for run in d["runs"] if run["agent"] == agent for t in run["turns"]]
            final_keys = {(r["conv"], r["turn"]) for r in finals[f"{run_name}/{agent}"]}
            fsecs = [t["seconds"] for run in d["runs"] if run["agent"] == agent for t in run["turns"]
                     if (run["id"], t["index"]) in final_keys]
            osecs = [e["seconds"] for run in d["runs"] if run["agent"] == agent for t in run["turns"]
                     for e in t.get("llm_trace") or [] if e["kind"] == "ollama"]
            med = lambda xs: f"{statistics.median(xs):.2f}" if xs else "-"
            w(f"| {run_name} | {agent} | {len(secs)} | {med(secs)} | {med(fsecs)} | {med(osecs)} | "
              f"{max(secs) if secs else '-'} |")
    w("")

    w("## LLM-generated final replies, c01-c07, side by side\n")
    for key, rows in finals.items():
        for r in rows:
            if r["conv"][:3] not in SIDE_BY_SIDE or not r["ollama"] or r["ollama"].get("outcome") != "ok":
                continue
            nums = number_flags(r["ollama"])
            w(f"### {r['conv']} turn {r['turn']} ({r['run']}) - {r['category']}\n")
            w(f"Triage {r['triage']}; Ollama {r['ollama']['seconds']} s, {r['ollama']['eval_count']} tokens, "
              f"done_reason {r['ollama']['done_reason']}. Numbers in the LLM text not in the retrieved context: "
              f"absent from the whole prompt {nums['not_in_prompt'] or 'none'}; "
              f"only in the patient data / instruction {nums['patient_data_only'] or 'none'}.\n")
            w("**Raw LLM text**\n")
            w(fence(r["ollama"]["response"]))
            w("\n**Reply sent to the patient**" + (" (deterministic - LLM text rejected)" if r["used_deterministic"] else " (built around the LLM text)") + "\n")
            w(fence(r["sent"]))
            if not r["used_deterministic"]:
                w("\n**Deterministic reply it replaced**\n")
                w(fence(r["deterministic"]))
            w("")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
