"""
Prompt variants for the local-LLM RAG comparison harness.

  project  Mirrors agents/chat_agent.py ChatAgent._query_llama()'s
           domain-instruction template -- the branch Recovery (THA/GEN),
           Pain and Rehabilitation answers go through -- with the per-domain
           DOMAIN_FOCUS text from agents/specialized_agents.py. Both are COPIED
           here as text; nothing from the backend is imported. Run
           `python prompts.py --check-drift` to confirm the copies still match
           the source files (read as text / parsed with ast, never executed).

  project_abstain
           Identical to "project" plus ONE added sentence (ABSTAIN_SENTENCE)
           telling the model to say it doesn't have the information and to
           refer the patient to their surgeon or physiotherapist when the
           notes don't cover the question. The drift check verifies both the
           shared portion against chat_agent.py and that removing the
           sentence gives back the project rendering exactly.

  minimal  A short grounded-QA system prompt with numbered context.

Structural difference from production (project variant): the backend sends
the whole template as ONE prompt to /api/generate. /api/chat has roles, so the
default "system_user" layout sends the template's wording, in the same order,
as the system message and moves only the `User's Question:` block into the
user message. Use --project-layout single_user in run_models.py to send the
verbatim single-prompt layout (whole template as one user message) instead.

postop_day comes from each query row and is required (no fallback). The other
template values use the backend's own defaults (main.py ChatRequest):
affected_limb="Right" unless the row gives one, surgery date not provided,
no chat history.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from typing import Any, Dict, List

from common import BACKEND_DIR

VARIANTS = ("project", "project_abstain", "minimal")
PROJECT_LAYOUTS = ("system_user", "single_user")
DEFAULT_PROJECT_LAYOUT = "system_user"

# Copied verbatim from agents/specialized_agents.py (DOMAIN_FOCUS class attributes).
# Note: in production, TKA Recovery answers are fully deterministic (no LLM), and
# Pain reaches the LLM only after its multi-turn interview with an extended
# instruction; this harness evaluates the single-turn grounded-answer step.
DOMAIN_FOCUS: Dict[str, str] = {
    "recovery": (
        "Focus on recovery milestones, expected postoperative progression, and "
        "realistic healing timelines. Do not present an exact recovery date as "
        "guaranteed -- frame timelines as typical ranges, not promises."
    ),
    "pain": (
        "Focus on interpreting postoperative pain, swelling, stiffness, numbness, "
        "and tingling in the context of expected healing, giving non-pharmacological "
        "guidance grounded in the retrieved clinical context. You may note risk-related "
        "observations that the retrieved clinical context itself raises (e.g. what "
        "distinguishes normal swelling from a concerning sign), but never restate, "
        "second-guess, or soften the upstream safety triage result, and never perform "
        "emergency triage or red-flag screening yourself -- that has already been "
        "handled upstream."
    ),
    "rehab": (
        "Focus on physiotherapy, exercises, range of motion, and mobility "
        "progression. Do not invent a specific exercise prescription beyond what "
        "the retrieved clinical context supports."
    ),
}
_DOMAIN_FOCUS_SOURCE_CLASSES = {
    "RecoveryProgressAgent": "recovery",
    "PainSymptomsAgent": "pain",
    "RehabilitationAgent": "rehab",
}

SURGERY_TYPE_BY_PROCEDURE = {
    "TKA": "Total Knee Arthroplasty (TKA)",
    "THA": "Total Hip Arthroplasty (THA)",
}
DEFAULT_AFFECTED_LIMB = "Right"   # main.py ChatRequest default; postop_day has NO default
SURGERY_DATE_TEXT = "Not provided"   # chat_agent.py: surgery_date or "Not provided"
HISTORY_TEXT = "No previous conversation turns."   # chat_agent.py, empty history

# Copied verbatim from agents/chat_agent.py (domain_instruction branch), split
# only so the question block can be moved into the user message.
_PROJECT_HEAD = """
Read the provided physical therapy discharge reference for Day
{postop_day} after {surgery_type} ({affected_limb}):

{rag_context}

Patient surgery date:
{surgery_date_text}

Previous conversation:
{history_text}

Specialist focus for this answer:
{domain_instruction}

"""
_PROJECT_QUESTION = """User's Question:
"{user_message}"

"""
_PROJECT_TAIL_ANSWER = """Write a friendly, 2-3 sentence answer directly answering the
user's question based on the discharge notes and relevant
conversation context.

"""
_PROJECT_TAIL_REST = """Write in plain, everyday language a patient without a medical
background would understand.

Mention Day {postop_day} goals, icing, and limb elevation
only when relevant:
"""
_PROJECT_TAIL = _PROJECT_TAIL_ANSWER + _PROJECT_TAIL_REST

# The single sentence project_abstain adds (as its own paragraph, right after
# the "Write a friendly, 2-3 sentence answer..." instruction).
ABSTAIN_SENTENCE = (
    "Whenever the discharge notes above do not cover the user's question, say that "
    "you do not have that information and ask the patient to check with their "
    "surgeon or physiotherapist."
)
_ABSTAIN_PARAGRAPH = ABSTAIN_SENTENCE + "\n\n"

MINIMAL_SYSTEM = (
    "You are a patient-education assistant for orthopedic post-operative recovery. "
    "Answer the patient's question using only the information in the provided context. "
    "If the context does not contain the information needed, say so plainly instead of guessing. "
    "Answer in 2-3 sentences of plain, everyday language."
)

# What followed_format is judged against (see score.py).
FORMAT_EXPECTATIONS = {
    "project": "A friendly 2-3 sentence answer in plain, everyday language that directly answers the question.",
    "project_abstain": (
        "A friendly 2-3 sentence answer in plain, everyday language that directly answers the question, "
        "or, when the notes don't cover it, says it doesn't have that information and refers the patient "
        "to their surgeon or physiotherapist."
    ),
    "minimal": (
        "A 2-3 sentence answer in plain, everyday language that uses only the provided context "
        "and says so when the context lacks the answer."
    ),
}


def _patient_fields(query: Dict[str, Any]) -> Dict[str, Any]:
    if query.get("postop_day") is None:
        raise ValueError(f"query {query.get('id')!r} has no postop_day; it is required (no default)")
    return {
        "postop_day": query["postop_day"],
        "surgery_type": SURGERY_TYPE_BY_PROCEDURE[query["procedure"]],
        "affected_limb": query.get("affected_limb", DEFAULT_AFFECTED_LIMB),
    }


def format_rag_context(chunks: List[Dict[str, Any]]) -> str:
    """Same shape chat_agent.py builds: one '- topic: content' line per chunk."""
    return "\n".join(f"- {chunk['topic']}: {chunk['content']}" for chunk in chunks)


def build_project_messages(
    query: Dict[str, Any],
    context: Dict[str, Any],
    layout: str = DEFAULT_PROJECT_LAYOUT,
    abstain: bool = False,
) -> List[Dict[str, str]]:
    values = {
        **_patient_fields(query),
        "rag_context": format_rag_context(context.get("chunks") or []),
        "surgery_date_text": SURGERY_DATE_TEXT,
        "history_text": HISTORY_TEXT,
        "domain_instruction": DOMAIN_FOCUS[query["domain"]],
        "user_message": query["query"],
    }
    head = _PROJECT_HEAD.format(**values)
    question = _PROJECT_QUESTION.format(**values)
    tail = (
        _PROJECT_TAIL_ANSWER.format(**values)
        + (_ABSTAIN_PARAGRAPH if abstain else "")
        + _PROJECT_TAIL_REST.format(**values)
    )
    if layout == "single_user":
        return [{"role": "user", "content": head + question + tail}]
    if layout == "system_user":
        return [
            {"role": "system", "content": head + tail},
            {"role": "user", "content": question.strip()},
        ]
    raise ValueError(f"unknown project layout {layout!r}")


def _numbered_context(chunks: List[Dict[str, Any]]) -> str:
    if not chunks:
        return "(no relevant context was retrieved)"
    return "\n".join(
        f"[{index}] {chunk['topic']}: {chunk['content']}"
        for index, chunk in enumerate(chunks, start=1)
    )


def build_minimal_messages(query: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, str]]:
    user = (
        f"Procedure: {SURGERY_TYPE_BY_PROCEDURE[query['procedure']]}\n\n"
        f"Context:\n{_numbered_context(context.get('chunks') or [])}\n\n"
        f"Question: {query['query']}"
    )
    return [
        {"role": "system", "content": MINIMAL_SYSTEM},
        {"role": "user", "content": user},
    ]


def build_messages(
    variant: str,
    query: Dict[str, Any],
    context: Dict[str, Any],
    project_layout: str = DEFAULT_PROJECT_LAYOUT,
) -> List[Dict[str, str]]:
    if variant == "project":
        return build_project_messages(query, context, layout=project_layout)
    if variant == "project_abstain":
        return build_project_messages(query, context, layout=project_layout, abstain=True)
    if variant == "minimal":
        return build_minimal_messages(query, context)
    raise ValueError(f"unknown prompt variant {variant!r}")


def check_drift() -> List[str]:
    """Compare the copied text with the backend source files (read-only; never imported)."""
    problems = []
    chat_source = (BACKEND_DIR / "agents" / "chat_agent.py").read_text(encoding="utf-8")
    template = (_PROJECT_HEAD + _PROJECT_QUESTION + _PROJECT_TAIL).lstrip("\n")
    if template not in chat_source:
        problems.append(
            "agents/chat_agent.py: the domain-instruction template no longer matches "
            "prompts.py's project variant"
        )

    tree = ast.parse((BACKEND_DIR / "agents" / "specialized_agents.py").read_text(encoding="utf-8"))
    found = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in _DOMAIN_FOCUS_SOURCE_CLASSES:
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "DOMAIN_FOCUS" for t in stmt.targets)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                ):
                    found[_DOMAIN_FOCUS_SOURCE_CLASSES[node.name]] = stmt.value.value
    for class_name, domain in _DOMAIN_FOCUS_SOURCE_CLASSES.items():
        if domain not in found:
            problems.append(f"agents/specialized_agents.py: {class_name}.DOMAIN_FOCUS not found")
        elif found[domain] != DOMAIN_FOCUS[domain]:
            problems.append(f"agents/specialized_agents.py: {class_name}.DOMAIN_FOCUS differs from prompts.py")

    # project_abstain must be the project prompt plus exactly ABSTAIN_SENTENCE, in every layout.
    for layout in PROJECT_LAYOUTS:
        for domain in DOMAIN_FOCUS:
            query, context = _example_inputs(domain)
            base = build_messages("project", query, context, project_layout=layout)
            abstain = build_messages("project_abstain", query, context, project_layout=layout)
            restored = [
                {**message, "content": message["content"].replace(_ABSTAIN_PARAGRAPH, "", 1)}
                for message in abstain
            ]
            added = sum(message["content"].count(ABSTAIN_SENTENCE) for message in abstain)
            if restored != base or added != 1:
                problems.append(f"project_abstain is not 'project + one sentence' (layout={layout}, domain={domain})")
    return problems


def _example_inputs(domain: str = "rehab"):
    query = {"id": "example", "domain": domain, "procedure": "TKA", "postop_day": 7, "answerability": "full",
             "query": "How far should I be able to bend my knee by now?", "reference_answer": ""}
    context = {"chunks": [{"topic": "Example Topic", "content": "Example retrieved chunk text."}]}
    return query, context


def _example_render(variant: str, layout: str) -> List[Dict[str, str]]:
    query, context = _example_inputs()
    return build_messages(variant, query, context, project_layout=layout)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inspect or verify the harness prompt variants.")
    parser.add_argument("--check-drift", action="store_true", help="verify copied text still matches the backend source")
    parser.add_argument("--show", choices=VARIANTS, help="print an example rendering of a variant")
    parser.add_argument("--layout", choices=PROJECT_LAYOUTS, default=DEFAULT_PROJECT_LAYOUT)
    args = parser.parse_args(argv)
    if not (args.check_drift or args.show):
        parser.print_help()
        return 0
    if args.show:
        print(json.dumps(_example_render(args.show, args.layout), indent=2, ensure_ascii=False))
    if args.check_drift:
        problems = check_drift()
        for problem in problems:
            print(f"DRIFT: {problem}")
        if problems:
            return 1
        print("OK: project prompt and DOMAIN_FOCUS copies match the backend source; "
              "project_abstain = project + one sentence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
