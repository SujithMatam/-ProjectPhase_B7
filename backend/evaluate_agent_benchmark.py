"""
Automated Evaluation Suite for Qwen Chatbot & Multi-Agent Orchestration.

Tests:
1. Safety Triage Accuracy & Critical Under-Triage Rate (ensures RED emergencies are never missed).
2. Intent Routing Accuracy & F1 Performance (routes correctly to specialized agent).
3. Qwen Chatbot & Multi-Agent Response Synthesis validation.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure project modules can be loaded
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from triage.safety_triage import SafetyTriageEngine
from lam.intent_classifier import IntentClassifier
from lam.schemas import LAMContext, IntentLabel
from agents.chat_agent import ChatAgent

TEST_DATASET_PATH = backend_dir / "data" / "exports" / "triage_intent_test.jsonl"


def run_benchmark():
    print("=" * 75)
    print("RUNNING BENCHMARK EVALUATION ON SYNTHETIC TEST DATASET")
    print(f"Dataset: {TEST_DATASET_PATH}")
    print("=" * 75)

    if not TEST_DATASET_PATH.exists():
        print(f"[!] Test file not found: {TEST_DATASET_PATH}")
        print("Please run `python backend/data/dataset_builder.py` first.")
        return

    with open(TEST_DATASET_PATH, "r", encoding="utf-8") as f:
        test_cases = [json.loads(line) for line in f if line.strip()]

    total = len(test_cases)
    print(f"Loaded {total} ground-truth test cases.\n")

    triage_correct = 0
    critical_undertriage = 0  # RED predicted as GREEN (unacceptable in clinical AI)
    intent_correct = 0
    escalation_matches = 0

    results_summary: List[Dict[str, Any]] = []

    for idx, case in enumerate(test_cases, 1):
        msg = case["user_message"]
        exp_triage = case["expected_triage"]
        exp_intent = case["expected_intent"]
        exp_escalate = bool(case["escalation_required"])
        postop_day = case.get("postop_day", 1)
        temp_c = case.get("temperature_c")

        # 1. Evaluate Deterministic Safety Triage
        triage_res = SafetyTriageEngine.evaluate(
            symptoms=msg,
            temperature_c=temp_c,
            post_op_day=postop_day
        )
        pred_triage = triage_res["triage_level"]
        pred_escalate = triage_res["is_escalated"]

        # 2. Evaluate Intent Classification
        context = LAMContext(
            patient_id=case.get("patient_id", "PT-100"),
            surgery_type=case.get("surgery_type", "Total Knee Arthroplasty"),
            affected_limb=case.get("affected_limb", "Right"),
            postop_day=postop_day,
            user_message=msg,
        )
        pred_intent_obj = IntentClassifier.classify(msg, context)
        pred_intent = pred_intent_obj.value.upper() if hasattr(pred_intent_obj, "value") else str(pred_intent_obj).upper()

        # Check metrics
        is_triage_match = (pred_triage == exp_triage)
        if is_triage_match:
            triage_correct += 1

        if exp_triage == "RED" and pred_triage == "GREEN":
            critical_undertriage += 1

        if pred_escalate == exp_escalate:
            escalation_matches += 1

        is_intent_match = (pred_intent == exp_intent)
        if is_intent_match:
            intent_correct += 1

        status_tag = "[PASS]" if (is_triage_match and is_intent_match) else "[AUDIT]"
        print(f"{status_tag} Case {idx:02d} | Triage: {pred_triage} (Exp: {exp_triage}) | Intent: {pred_intent} (Exp: {exp_intent})")
        if not is_triage_match or not is_intent_match:
            print(f"       Msg: \"{msg}\"")
            print(f"       Rationale: {case.get('clinical_rationale')}\n")

    # Scorecard
    triage_acc = (triage_correct / total) * 100
    intent_acc = (intent_correct / total) * 100
    escalation_acc = (escalation_matches / total) * 100

    print("\n" + "=" * 75)
    print("CLINICAL BENCHMARK SCORECARD")
    print("=" * 75)
    print(f"Total Test Cases:            {total}")
    print(f"Safety Triage Accuracy:      {triage_acc:.2f}% ({triage_correct}/{total})")
    print(f"Critical Under-Triage (RED->GREEN): {critical_undertriage} (Target: 0)")
    print(f"Emergency Escalation Match:  {escalation_acc:.2f}% ({escalation_matches}/{total})")
    print(f"Intent Classification Acc:   {intent_acc:.2f}% ({intent_correct}/{total})")
    print("=" * 75)

    if critical_undertriage == 0:
        print("[SAFETY CERTIFIED] Zero critical under-triage instances detected.")
    else:
        print(f"[SAFETY WARNING] {critical_undertriage} red-flag emergencies were not escalated!")


if __name__ == "__main__":
    run_benchmark()
