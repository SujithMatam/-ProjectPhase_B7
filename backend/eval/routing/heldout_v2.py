"""
Held-out routing set v2: 30 fresh patient messages, written and committed
BEFORE the classifier changes they are meant to judge (medication symptom
keywords gated on a medication cue, Recovery prototype margin fix).  Nothing
in lam/intent_classifier.py may be tuned against these sentences; they are
scored, not trained on.

Same fields and scoring as eval/routing/cases.py (see its docstring); ids are
H001.. so the two sets never collide.  Run with

    .venv/Scripts/python.exe eval/routing/run_routing_benchmark.py --cases heldout_v2 --label <name>

Groups:
    med_symptom      a symptom word (itching, dizzy, nausea, bloated, drowsy,
                     constipated, light-headed, queasy, fatigued) next to a
                     medication cue -> Medication
    nonmed_symptom   the same symptom words with NO medication cue (incision
                     itching, bloated after meals, dizzy standing up after
                     physio) -> Wound / Nutrition / Pain / Daily Activity /
                     Recovery
    rehab, daily, recovery
                     rehabilitation, daily-activity and recovery-progress
                     questions in patient language

Near-duplicate guard: every sentence has cosine <= 0.85 (all-MiniLM-L6-v2,
the classifier's own model) to every case in cases.py; checked by
eval/routing/check_near_duplicates.py and recorded in
eval/reports/2026-11-12_heldout-v2.md.
"""

from __future__ import annotations

from typing import Any, Dict, List

RP, PS, RH, MD, WC, DA, NU, MW, IC = (
    "recovery_progress", "pain_symptoms", "rehabilitation", "medication",
    "wound_care", "daily_activity", "nutrition", "mental_wellbeing", "intake_context",
)

CASES: List[Dict[str, Any]] = []


def C(text: str, expected: str, acceptable=None, *, confidence: str = "clear",
      source: str, kind: str = "opening", note: str = "", surgery: str = "TKA") -> None:
    acc = list(acceptable) if acceptable else [expected]
    if expected not in acc:
        acc.insert(0, expected)
    if confidence == "debatable" and len(acc) < 2:
        raise ValueError(f"debatable case needs two acceptable labels: {text!r}")
    case = {
        "id": f"H{len(CASES) + 1:03d}",
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


# ---------------------------------------------------------------------------
# Symptom word WITH a medication cue -> Medication
# ---------------------------------------------------------------------------
S = "heldout_v2:med_symptom"
C("Itching all over my arms since the new tablets started", MD, source=S)
C("I feel dizzy about an hour after my painkiller", MD, source=S)
C("Since I started the tramadol I am badly constipated", MD, [MD, NU], confidence="debatable", source=S)
C("Is feeling drowsy all day a side effect of gabapentin?", MD, source=S)
C("The blood thinner injection makes me light headed, is that expected?", MD, source=S)
C("Tummy feels bloated ever since I began these pills", MD, [MD, NU], confidence="debatable", source=S)
C("Nausea comes after every dose, should I eat something first?", MD, [MD, NU], confidence="debatable", source=S)
C("Queasy in the mornings after my medicine, what can I do?", MD, source=S)

# ---------------------------------------------------------------------------
# The same symptom words WITHOUT a medication cue
# ---------------------------------------------------------------------------
S = "heldout_v2:nonmed_symptom"
C("The skin along my incision line is very itchy", WC, source=S)
C("Itching near the stitches at night, does that mean it is healing?", WC, source=S)
C("Feeling bloated and gassy after eating rice, what should I avoid?", NU, source=S)
C("Bloated after meals, which foods are lighter on the stomach?", NU, source=S)
C("I get dizzy when I stand up after physio", PS, [PS, RH, DA], confidence="debatable", source=S)
C("Feeling light-headed when I get out of bed in the morning", PS, [PS, DA], confidence="debatable", source=S)
C("Constipated since the operation, which foods will help?", NU, source=S)
C("I feel nauseous when I smell cooking these days, what can I eat?", NU, [NU, PS], confidence="debatable", source=S)
C("Very fatigued after walking to the gate and back, is that normal at this stage?", RP, [RP, RH, DA],
  confidence="debatable", source=S)

# ---------------------------------------------------------------------------
# Rehabilitation
# ---------------------------------------------------------------------------
S = "heldout_v2:rehab"
C("My physio wants a 90 degree bend by next week, how do I get there?", RH, source=S)
C("Should I do the quad exercises before or after icing?", RH, source=S)
C("How many times a day should I practise straightening the leg?", RH, source=S)
C("Can I start pedalling on the home exercise bike?", RH, [RH, DA], confidence="debatable", source=S)
C("The knee will not fully bend yet, what can I practise at home?", RH, source=S)

# ---------------------------------------------------------------------------
# Daily activity
# ---------------------------------------------------------------------------
S = "heldout_v2:daily"
C("Can I sit cross-legged on the floor for puja?", DA, source=S)
C("When is it ok to travel by train for a family wedding?", DA, [DA, RP], confidence="debatable", source=S)
C("Is a slow evening stroll in the colony park fine for me?", DA, [DA, RH], confidence="debatable", source=S)
C("Is it fine to use an Indian-style toilet yet?", DA, source=S)

# ---------------------------------------------------------------------------
# Recovery progress
# ---------------------------------------------------------------------------
S = "heldout_v2:recovery"
C("Is it normal to still need the stick at three weeks?", RP, source=S)
C("How far along should I be by the end of the first month?", RP, source=S)
C("My neighbour was walking freely by now, am I slow?", RP, source=S)
C("What should I be able to do by my six week check-up?", RP, source=S)


def by_id() -> Dict[str, Dict[str, Any]]:
    return {case["id"]: case for case in CASES}


if __name__ == "__main__":
    from collections import Counter
    print(len(CASES), "cases")
    print(Counter(c["expected"] for c in CASES))
    print(Counter(c["source"] for c in CASES))
    print(Counter(c["confidence"] for c in CASES))
