"""
Held-out routing set v3: 12 fresh hip-precaution / movement-restriction
messages, written and committed BEFORE the classifier change they are meant
to judge (hip-precaution example sentences for the "What movements should I
avoid after my hip replacement?" gap).  Nothing in lam/intent_classifier.py
may be tuned against these sentences; they are scored, not trained on.

Same fields and scoring as eval/routing/cases.py (see its docstring); ids are
V001.. so the three sets never collide.  Run with

    .venv/Scripts/python.exe eval/routing/run_routing_benchmark.py --cases heldout_v3 --label <name>

Every case is a movement restriction / precaution question: 11 after a hip
replacement (THA), 1 after a knee replacement (TKA).  Indian-English
phrasing: low sofa, crossing legs, tying shoe laces, sleeping on the side,
Indian-style toilet, sitting cross-legged for meals.  Acceptable agents are
Daily Activity and Rehabilitation for every case (`expected` is the more
natural owner of the two).

Near-duplicate guard: every sentence has cosine <= 0.85 (all-MiniLM-L6-v2,
the classifier's own model) to every case in cases.py and heldout_v2.py
(max 0.709); checked by
    .venv/Scripts/python.exe eval/routing/check_near_duplicates.py heldout --set heldout_v3
"""

from __future__ import annotations

from typing import Any, Dict, List

RP, PS, RH, MD, WC, DA, NU, MW, IC = (
    "recovery_progress", "pain_symptoms", "rehabilitation", "medication",
    "wound_care", "daily_activity", "nutrition", "mental_wellbeing", "intake_context",
)

CASES: List[Dict[str, Any]] = []


def C(text: str, expected: str, acceptable=None, *, confidence: str = "clear",
      source: str, kind: str = "opening", note: str = "", surgery: str = "THA") -> None:
    acc = list(acceptable) if acceptable else [expected]
    if expected not in acc:
        acc.insert(0, expected)
    if confidence == "debatable" and len(acc) < 2:
        raise ValueError(f"debatable case needs two acceptable labels: {text!r}")
    case = {
        "id": f"V{len(CASES) + 1:03d}",
        "text": text,
        "expected": expected,
        "acceptable": acc,
        "confidence": confidence,
        "kind": kind,
        "source": source,
        "surgery": surgery,
    }
    if note:
        case["note"] = note
    CASES.append(case)


DEB = dict(confidence="debatable")

# ---------------------------------------------------------------------------
# Hip precautions after THA
# ---------------------------------------------------------------------------
S = "heldout_v3:hip_precautions"
C("Which hip movements are banned for the first few weeks after my hip replacement?", RH, [RH, DA], source=S, **DEB)
C("Is it safe to sit on the low sofa in our hall or is it too low for my new hip?", DA, [DA, RH], source=S, **DEB)
C("Doctor said don't cross the legs, till when I have to follow that?", DA, [DA, RH], source=S, **DEB)
C("How do I tie my shoe laces without bending too much at the hip?", DA, [DA, RH], source=S, **DEB)
C("Can I lie on my side at night, and should I keep a pillow between the knees?", DA, [DA, RH], source=S, **DEB)
C("My in-laws' house has only an Indian-style toilet, can I squat on it with the new hip?", DA, [DA, RH],
  source=S, **DEB)
C("Sitting cross-legged on the floor for meals, is that allowed after hip surgery?", DA, [DA, RH], source=S, **DEB)
C("What positions should my hip not go into while it heals?", RH, [RH, DA], source=S, **DEB)
C("Is twisting my body while standing at the kitchen counter risky for the new hip?", DA, [DA, RH], source=S, **DEB)
C("How low can a chair be before it is unsafe for my operated hip?", DA, [DA, RH], source=S, **DEB)
C("Can I put on my socks myself or should I use a sock aid?", DA, [DA, RH], source=S, **DEB)

# ---------------------------------------------------------------------------
# Movement restrictions after TKA
# ---------------------------------------------------------------------------
S = "heldout_v3:knee_precautions"
C("After my knee replacement, are there positions I must avoid, like kneeling or keeping a pillow under the knee?",
  RH, [RH, DA], source=S, surgery="TKA", **DEB)


def by_id() -> Dict[str, Dict[str, Any]]:
    return {case["id"]: case for case in CASES}


if __name__ == "__main__":
    from collections import Counter
    print(len(CASES), "cases")
    print(Counter(c["expected"] for c in CASES))
    print(Counter(c["source"] for c in CASES))
    print(Counter(c["surgery"] for c in CASES))
