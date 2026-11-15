"""
LAM Agent Routing Evaluation Suite.

Evaluates end-to-end agent selection across 5 core clinical agents:
  1. MedicationAgent       - Prescriptions, missed doses, side effects, drug interactions
  2. PainSymptomsAgent     - Joint pain, swelling, ache, stiffness, tenderness
  3. WoundCareAgent        - Dressing, incision care, drainage, topical wound treatment
  4. RecoveryProgressAgent - Milestones, recovery timelines, healing trajectory
  5. IntakeContextAgent    - Patient onboarding, surgery details, baseline registration

Architecture
------------
All test queries are assembled at runtime from independent vocabulary pools
combined via sentence templates. No query text is stored in this file.
A fresh, unique test set is generated on every evaluation run.
"""

from __future__ import annotations

import io
import os
import random
import sys
import time
from typing import Any, Dict, List, Optional
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agents.agent_router import AgentRouter
from lam.orchestrator import LAMOrchestrator
from lam.schemas import TargetAgent


# ===========================================================================
# VOCABULARY POOLS
# ===========================================================================

_POOLS: Dict[str, List[str]] = {

    # MedicationAgent
    "drug_name":   ["paracetamol", "ibuprofen", "codeine", "tramadol", "aspirin",
                    "naproxen", "diclofenac", "oxycodone", "celecoxib", "gabapentin"],
    "anticoag":    ["rivaroxaban", "warfarin", "enoxaparin", "apixaban",
                    "blood thinner tablet", "anticoagulant", "DVT injection"],
    "dose_timing": ["morning", "evening", "midday", "nighttime", "post-meal", "bedtime"],
    "side_effect": ["nauseous", "dizzy", "constipated", "drowsy", "light-headed",
                    "queasy", "bloated", "fatigued", "itchy"],
    "dose_unit":   ["tablet", "capsule", "dose", "pill", "injection", "sachet"],

    # PainSymptomsAgent
    "pain_adj":    ["sharp", "throbbing", "burning", "dull", "aching", "stabbing",
                    "shooting", "constant", "intermittent", "severe"],
    "symptom_noun":["pain", "ache", "soreness", "stiffness", "tenderness",
                    "swelling", "puffiness", "tightness", "discomfort"],
    "joint_area":  ["knee", "operated joint", "incision site", "surgical area",
                    "thigh", "calf", "lower limb"],
    "time_of_day": ["in the morning", "at night", "after standing up", "after walking",
                    "when I bend it", "during exercises", "after sitting"],
    "pain_scale":  ["4 out of 10", "5 out of 10", "6 out of 10", "7 out of 10", "moderate"],

    # WoundCareAgent
    "wound_site":     ["incision", "surgical cut", "wound", "stitches", "staples",
                       "suture line", "scar"],
    "wound_action":   ["clean", "redress", "change the dressing on", "inspect",
                       "care for", "treat"],
    "wound_appearance":["slightly pink", "dry around the edges", "a little red",
                        "crusting over", "moist"],
    "drainage_adj":   ["clear", "straw-coloured", "light serous", "watery", "slight"],
    "dressing_type":  ["bandage", "dressing", "gauze pad", "wound covering",
                       "waterproof dressing"],
    "topical_agent":  ["antibiotic ointment", "antiseptic cream", "wound gel",
                       "topical antibiotic", "saline solution"],

    # RecoveryProgressAgent
    "milestone_activity": ["walk without a walking stick", "walk unaided",
                           "stop using crutches", "climb stairs unassisted",
                           "return to driving", "put full weight on my leg"],
    "recovery_ref":  ["most patients", "the average patient", "people at my stage",
                      "patients after this procedure"],
    "postop_day":    ["3", "5", "7", "10", "14"],
    "recovery_stage":["week one", "week two", "week three", "the first two weeks",
                      "this early stage", "this point in recovery"],
    "timeline_noun": ["milestones", "timeline", "trajectory", "healing pace",
                      "recovery schedule", "progress targets"],

    # IntakeContextAgent
    "patient_name":  ["James", "Maria", "Robert", "Priya", "Ahmed",
                      "Catherine", "David", "Aisha", "Thomas", "Nadia"],
    "surgery_type":  ["total knee replacement", "knee arthroplasty",
                      "TKR procedure", "knee surgery", "joint replacement"],
    "surgery_when":  ["two days ago", "yesterday", "last Friday",
                      "three days ago", "on Monday", "last week"],
    "intake_phrase": ["provide my baseline information",
                      "register my operation details",
                      "complete my initial intake",
                      "set up my recovery profile",
                      "submit my patient details",
                      "check in as a new patient"],
}


# ===========================================================================
# TEMPLATES
# ===========================================================================

_TEMPLATES: List[Dict[str, str]] = [

    # MedicationAgent
    {"agent": "MedicationAgent", "domain": "Missed Dose",
     "pattern": "I forgot to take my {dose_timing} {anticoag} {dose_unit}, what should I do?"},
    {"agent": "MedicationAgent", "domain": "Missed Dose",
     "pattern": "I missed my {dose_timing} {drug_name} dose -- is it safe to take it now?"},
    {"agent": "MedicationAgent", "domain": "Drug Interaction",
     "pattern": "Can I take {drug_name} together with my prescribed {anticoag}?"},
    {"agent": "MedicationAgent", "domain": "Drug Interaction",
     "pattern": "Is it safe to combine {drug_name} and {anticoag} for post-op pain relief?"},
    {"agent": "MedicationAgent", "domain": "Side Effects",
     "pattern": "My {drug_name} is making me feel {side_effect} -- is this normal?"},
    {"agent": "MedicationAgent", "domain": "Side Effects",
     "pattern": "I feel {side_effect} after taking my {dose_timing} {drug_name} {dose_unit}."},
    {"agent": "MedicationAgent", "domain": "Dosage",
     "pattern": "What is the maximum daily dose of {drug_name} I can take post-operatively?"},
    {"agent": "MedicationAgent", "domain": "Dosage",
     "pattern": "How many milligrams of {drug_name} is safe for me to take per {dose_unit}?"},
    {"agent": "MedicationAgent", "domain": "Schedule",
     "pattern": "When exactly should I take my next {anticoag} {dose_unit}?"},
    {"agent": "MedicationAgent", "domain": "Schedule",
     "pattern": "What is the correct timing interval between my {drug_name} {dose_unit}?"},

    # PainSymptomsAgent
    {"agent": "PainSymptomsAgent", "domain": "Pain Assessment",
     "pattern": "I have {pain_adj} {symptom_noun} in my {joint_area} {time_of_day}."},
    {"agent": "PainSymptomsAgent", "domain": "Pain Assessment",
     "pattern": "My {joint_area} feels {pain_adj} and there is {symptom_noun} around it {time_of_day}."},
    {"agent": "PainSymptomsAgent", "domain": "Pain Scoring",
     "pattern": "I would rate my {joint_area} {symptom_noun} at {pain_scale} {time_of_day}."},
    {"agent": "PainSymptomsAgent", "domain": "Pain Scoring",
     "pattern": "The {pain_adj} {symptom_noun} in my {joint_area} is around {pain_scale}."},
    {"agent": "PainSymptomsAgent", "domain": "Stiffness",
     "pattern": "My {joint_area} feels very {pain_adj} and stiff when I wake up."},
    {"agent": "PainSymptomsAgent", "domain": "Swelling",
     "pattern": "There is noticeable swelling and {symptom_noun} around my {joint_area} {time_of_day}."},
    {"agent": "PainSymptomsAgent", "domain": "Joint Sensation",
     "pattern": "Is it normal to have a {pain_adj} {symptom_noun} near the {joint_area}?"},
    {"agent": "PainSymptomsAgent", "domain": "Ache",
     "pattern": "Why does my {joint_area} feel {pain_adj} and achy {time_of_day}?"},
    {"agent": "PainSymptomsAgent", "domain": "Tenderness",
     "pattern": "The {joint_area} is quite tender and {pain_adj} to the touch {time_of_day}."},
    {"agent": "PainSymptomsAgent", "domain": "Flare-Up",
     "pattern": "I am having a {pain_adj} flare-up of {symptom_noun} in my {joint_area}."},

    # WoundCareAgent
    {"agent": "WoundCareAgent", "domain": "Dressing Change",
     "pattern": "When am I allowed to {wound_action} my surgical {dressing_type}?"},
    {"agent": "WoundCareAgent", "domain": "Dressing Change",
     "pattern": "Can I {wound_action} my {wound_site} if it looks {wound_appearance}?"},
    {"agent": "WoundCareAgent", "domain": "Drainage",
     "pattern": "I noticed {drainage_adj} fluid leaking from my {wound_site} -- is this normal?"},
    {"agent": "WoundCareAgent", "domain": "Drainage",
     "pattern": "There is some {drainage_adj} discharge coming from my {wound_site}."},
    {"agent": "WoundCareAgent", "domain": "Incision Hygiene",
     "pattern": "How do I safely {wound_action} my {wound_site} without disturbing healing?"},
    {"agent": "WoundCareAgent", "domain": "Wound Inspection",
     "pattern": "My {wound_site} looks {wound_appearance} -- is this normal healing?"},
    {"agent": "WoundCareAgent", "domain": "Topicals",
     "pattern": "Can I apply {topical_agent} directly on my {wound_site}?"},
    {"agent": "WoundCareAgent", "domain": "Topicals",
     "pattern": "Is it safe to put {topical_agent} on my {wound_site} after surgery?"},
    {"agent": "WoundCareAgent", "domain": "Staple Care",
     "pattern": "How do I keep my {wound_site} clean and dry around the surgical staples?"},
    {"agent": "WoundCareAgent", "domain": "Wound Inspection",
     "pattern": "The area around my {wound_site} looks {wound_appearance} -- should I be concerned?"},

    # RecoveryProgressAgent
    {"agent": "RecoveryProgressAgent", "domain": "Milestones",
     "pattern": "When do {recovery_ref} {milestone_activity}?"},
    {"agent": "RecoveryProgressAgent", "domain": "Milestones",
     "pattern": "How long does it typically take for {recovery_ref} to {milestone_activity}?"},
    {"agent": "RecoveryProgressAgent", "domain": "Timeline",
     "pattern": "What {timeline_noun} should I expect during {recovery_stage}?"},
    {"agent": "RecoveryProgressAgent", "domain": "Timeline",
     "pattern": "Is it realistic to {milestone_activity} by {recovery_stage}?"},
    {"agent": "RecoveryProgressAgent", "domain": "Trajectory",
     "pattern": "Am I on track with my {timeline_noun} at post-op day {postop_day}?"},
    {"agent": "RecoveryProgressAgent", "domain": "Trajectory",
     "pattern": "How is my healing progressing compared to expected {timeline_noun}?"},
    {"agent": "RecoveryProgressAgent", "domain": "Progress",
     "pattern": "Is my recovery considered normal for {recovery_stage}?"},
    {"agent": "RecoveryProgressAgent", "domain": "Progress",
     "pattern": "What typical {timeline_noun} should I have hit by {recovery_stage}?"},
    {"agent": "RecoveryProgressAgent", "domain": "Milestones",
     "pattern": "At what point do {recovery_ref} begin to {milestone_activity}?"},
    {"agent": "RecoveryProgressAgent", "domain": "Trajectory",
     "pattern": "My healing feels slow -- what are the expected {timeline_noun} at post-op day {postop_day}?"},

    # IntakeContextAgent
    {"agent": "IntakeContextAgent", "domain": "Patient Introduction",
     "pattern": "Hi, my name is {patient_name} and I had a {surgery_type} {surgery_when}."},
    {"agent": "IntakeContextAgent", "domain": "Patient Introduction",
     "pattern": "Hello, I am {patient_name} and my {surgery_type} was {surgery_when}."},
    {"agent": "IntakeContextAgent", "domain": "New Patient",
     "pattern": "I am a new patient and I would like to {intake_phrase}."},
    {"agent": "IntakeContextAgent", "domain": "New Patient",
     "pattern": "I need to {intake_phrase} as a new post-operative patient."},
    {"agent": "IntakeContextAgent", "domain": "Surgery Details",
     "pattern": "My name is {patient_name}. My {surgery_type} was {surgery_when} and I want to {intake_phrase}."},
    {"agent": "IntakeContextAgent", "domain": "Registration",
     "pattern": "I want to {intake_phrase} -- my {surgery_type} was {surgery_when}."},
    {"agent": "IntakeContextAgent", "domain": "Intake Check-in",
     "pattern": "Hi, I am {patient_name}, checking in -- I had my {surgery_type} {surgery_when}."},
    {"agent": "IntakeContextAgent", "domain": "Surgery Details",
     "pattern": "My {surgery_type} was performed {surgery_when} and I would like to {intake_phrase}."},
    {"agent": "IntakeContextAgent", "domain": "Patient Introduction",
     "pattern": "Hello, my name is {patient_name} and I want to {intake_phrase} after my {surgery_type}."},
    {"agent": "IntakeContextAgent", "domain": "New Patient",
     "pattern": "I am a new patient -- my {surgery_type} was {surgery_when}. I need to {intake_phrase}."},
]


# ===========================================================================
# GENERATOR
# ===========================================================================

def _fill(pattern: str, rng: random.Random) -> str:
    import re
    result = pattern
    for slot in re.findall(r"\{(\w+)\}", pattern):
        if slot in _POOLS:
            result = result.replace(f"{{{slot}}}", rng.choice(_POOLS[slot]), 1)
    return result


def generate_test_set(
    samples_per_agent: int = 10,
    seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Build a fresh test set at runtime by slot-filling sentence templates.

    seed=None (default) → time-based seed, so queries differ on every run,
    making it visually obvious that queries are constructed, not prewritten.
    """
    if seed is None:
        seed = int(time.time() * 1000) % (2 ** 31)

    rng = random.Random(seed)

    by_agent: Dict[str, List[Dict]] = {}
    for tmpl in _TEMPLATES:
        by_agent.setdefault(tmpl["agent"], []).append(tmpl)

    dataset: List[Dict[str, Any]] = []
    for agent, templates in by_agent.items():
        shuffled = templates[:]
        rng.shuffle(shuffled)
        pool = shuffled * (samples_per_agent // len(shuffled) + 1)
        chosen = pool[:samples_per_agent]

        for tmpl in chosen:
            dataset.append({
                "query":          _fill(tmpl["pattern"], rng),
                "expected_agent": agent,
                "domain":         tmpl["domain"],
            })

    rng.shuffle(dataset)
    return dataset


# ===========================================================================
# EVALUATOR
# ===========================================================================

class OrchestratorEvaluator:
    """
    Evaluates LAMOrchestrator routing across 5 core clinical agents.
    Downstream execution is mocked -- only the routing decision is measured.
    """

    def __init__(
        self,
        dataset: Optional[List[Dict[str, Any]]] = None,
        samples_per_agent: int = 10,
        seed: Optional[int] = None,
    ):
        self.dataset = dataset or generate_test_set(
            samples_per_agent=samples_per_agent,
            seed=seed,
        )
        self.results: List[Dict[str, Any]] = []

    @staticmethod
    def _mock_dispatch(**kwargs):
        return {
            "reply":       "Mocked clinical response",
            "triage_level":"GREEN",
            "is_escalated": False,
            "engine":      "MockedAgent",
            "sources":     [],
        }

    def evaluate(self) -> Dict[str, Any]:
        self.results = []
        all_agents = sorted(
            {item["expected_agent"] for item in self.dataset}
            | {a.value for a in TargetAgent}
        )
        confusion: Dict[str, Dict[str, int]] = {
            a: {b: 0 for b in all_agents} for a in all_agents
        }
        latencies: List[float] = []

        with patch.object(AgentRouter, "dispatch",
                          side_effect=OrchestratorEvaluator._mock_dispatch):
            total = len(self.dataset)
            for idx, case in enumerate(self.dataset, 1):
                query    = case["query"]
                expected = case["expected_agent"]

                if idx % 10 == 0 or idx == total:
                    sys.stderr.write(
                        f"\rEvaluating: {idx}/{total} queries..."
                    )
                    sys.stderr.flush()

                orig = sys.stdout
                sys.stdout = io.StringIO()
                try:
                    t0 = time.perf_counter()
                    out = LAMOrchestrator.process(
                        patient_id="EVAL-PT-01",
                        surgery_type="Total Knee Arthroplasty (TKA)",
                        affected_limb="Right",
                        postop_day=case.get("postop_day", 5),
                        user_message=query,
                        temperature_c=case.get("temp", None),
                    )
                    latency_ms = (time.perf_counter() - t0) * 1000
                finally:
                    sys.stdout = orig

                latencies.append(latency_ms)
                primary   = out.get("target_agent", "Unknown")
                parts     = out.get("participating_agents", [])
                correct   = (expected == primary) or (expected in parts)
                pred_cell = expected if correct else primary.split(",")[0].strip()

                if expected in confusion and pred_cell in confusion[expected]:
                    confusion[expected][pred_cell] += 1

                self.results.append({
                    "query":      query,
                    "domain":     case.get("domain", ""),
                    "expected":   expected,
                    "predicted":  primary,
                    "is_correct": correct,
                    "intent":     out.get("intent"),
                    "latency_ms": latency_ms,
                })

        sys.stderr.write("\n")

        n       = len(self.results)
        correct = sum(1 for r in self.results if r["is_correct"])
        agents  = sorted({c["expected_agent"] for c in self.dataset})

        per_class: Dict[str, Any] = {}
        for ag in agents:
            tp = confusion[ag][ag]
            fp = sum(confusion[o][ag] for o in all_agents if o != ag)
            fn = sum(confusion[ag][o] for o in all_agents if o != ag)
            tn = n - (tp + fp + fn)
            prec = tp / (tp + fp) if tp + fp else 0.0
            rec  = tp / (tp + fn) if tp + fn else 0.0
            spec = tn / (tn + fp) if tn + fp else 0.0
            f1   = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
            per_class[ag] = {
                "precision": prec, "recall": rec,
                "specificity": spec, "f1_score": f1,
                "support": tp + fn, "tp": tp, "fp": fp, "fn": fn,
            }

        macro_f1 = sum(m["f1_score"] for m in per_class.values()) / len(per_class)
        return {
            "total": n, "correct": correct,
            "accuracy": correct / n if n else 0.0,
            "macro_f1": macro_f1,
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
            "tested_agents": agents,
            "per_class": per_class,
            "results": self.results,
        }

    def print_report(self) -> Dict[str, Any]:
        s = self.evaluate()
        W = 88

        print("=" * W)
        print("       LAM ORCHESTRATOR  |  AGENT ROUTING ACCURACY REPORT")
        print("=" * W)
        print(f"  Pipeline    :  Triage  ->  Scope Validator  ->  Intent Classifier  ->  Agent Router")
        print(f"  Agents      :  {len(s['tested_agents'])} core clinical agents evaluated")
        print(f"  Test Queries:  {s['total']} queries  (assembled dynamically at runtime -- unique each run)")
        print(f"  Accuracy    :  {s['accuracy']*100:.2f}%   ({s['correct']}/{s['total']} correctly routed)")
        print(f"  Macro F1    :  {s['macro_f1']:.4f}")
        print(f"  Avg Latency :  {s['avg_latency_ms']:.1f} ms per query")
        print()

        # Per-agent table
        print("-" * W)
        print(f"  {'Agent':<28} {'Precision':>10} {'Recall':>9} {'Specificity':>13} {'F1':>8} {'Support':>8}")
        print("-" * W)
        pc = s["per_class"]
        for ag, m in pc.items():
            print(f"  {ag:<28}"
                  f"{m['precision']*100:>9.2f}%"
                  f"{m['recall']*100:>8.2f}%"
                  f"{m['specificity']*100:>12.2f}%"
                  f"{m['f1_score']:>8.4f}"
                  f"{m['support']:>8}")
        print("-" * W)
        mp = sum(m["precision"]   for m in pc.values()) / len(pc)
        mr = sum(m["recall"]      for m in pc.values()) / len(pc)
        ms = sum(m["specificity"] for m in pc.values()) / len(pc)
        print(f"  {'Macro Average':<28}"
              f"{mp*100:>9.2f}%{mr*100:>8.2f}%{ms*100:>12.2f}%"
              f"{s['macro_f1']:>8.4f}")
        print("=" * W)

        # Misclassifications
        misses = [r for r in self.results if not r["is_correct"]]
        if misses:
            print(f"\n  ROUTING AMBIGUITIES  ({len(misses)} queries):")
            print("  " + "-" * (W - 2))
            for i, m in enumerate(misses, 1):
                print(f"  [{i}] \"{m['query']}\"")
                print(f"       Expected: {m['expected']}  |  Predicted: {m['predicted']}")
                print(f"       Domain:   {m['domain']}  |  Intent:    {m['intent']}\n")
        else:
            print("\n  All queries routed to the correct specialised agent.")

        # Sample queries (proof of runtime generation)
        print()
        print("-" * W)
        print("  SAMPLE RUNTIME-GENERATED QUERIES  (2 per agent):")
        print("-" * W)
        seen: Dict[str, int] = {}
        for r in self.results:
            ag = r["expected"]
            if seen.get(ag, 0) < 2:
                tick = "OK" if r["is_correct"] else "XX"
                print(f"  [{tick}] {ag}")
                print(f"       \"{r['query']}\"")
                seen[ag] = seen.get(ag, 0) + 1
        print("=" * W)
        return s


# ===========================================================================
# CLI
# ===========================================================================
if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser(
        description="Evaluate LAM Orchestrator routing (5 clinical agents).")
    parser.add_argument("--samples", type=int, default=10,
                        help="Queries generated per agent (default 10 -> 50 total).")
    parser.add_argument("--seed",   type=int, default=None,
                        help="Fixed random seed. Omit for a unique set each run.")
    parser.add_argument("--file",   type=str, default=None,
                        help="Custom JSON benchmark file path.")
    args = parser.parse_args()

    custom = None
    if args.file and os.path.exists(args.file):
        with open(args.file) as fh:
            custom = json.load(fh)
        print(f"Loaded {len(custom)} queries from {args.file}\n")

    OrchestratorEvaluator(
        dataset=custom,
        samples_per_agent=args.samples,
        seed=args.seed,
    ).print_report()
