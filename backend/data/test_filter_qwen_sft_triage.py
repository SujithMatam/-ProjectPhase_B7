"""Tests for filtering triage-style content from Qwen SFT exports."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from filter_qwen_sft_triage import exclusion_reasons, filter_splits


def make_record(record_id: str, response: str, expected_agent: str = "ChatAgent") -> dict:
    return {
        "id": record_id,
        "conversations": [
            {"from": "system", "value": "Answer recovery questions."},
            {"from": "user", "value": "A generic question."},
            {"from": "assistant", "value": response},
        ],
        "metadata": {"expected_agent": expected_agent},
    }


class FilterQwenSftTriageTests(unittest.TestCase):
    def test_metadata_emergency_agent_is_excluded(self) -> None:
        record = make_record("emergency", "Emergency response.", "emergencyagent")
        self.assertEqual(exclusion_reasons(record), ["expected_agent:EmergencyAgent"])

    def test_emergency_escalation_is_excluded(self) -> None:
        record = make_record("escalation", "Call 911 or go to the nearest emergency department.")
        self.assertEqual(exclusion_reasons(record), ["assistant_emergency_escalation"])
        after_hours = make_record("after-hours", "Seek medical attention immediately.")
        self.assertEqual(exclusion_reasons(after_hours), ["assistant_emergency_escalation"])

    def test_case_specific_triage_diagnosis_is_excluded(self) -> None:
        record = make_record(
            "diagnosis",
            "Your symptoms may indicate a pulmonary embolism.",
        )
        self.assertEqual(exclusion_reasons(record), ["assistant_triage_decision"])

    def test_triage_text_is_excluded_for_non_emergency_agent(self) -> None:
        record = make_record(
            "non-emergency-triage",
            "Your symptoms may indicate a pulmonary embolism.",
            "PainSymptomsAgent",
        )
        self.assertEqual(exclusion_reasons(record), ["assistant_triage_decision"])

    def test_metadata_and_text_reasons_are_both_counted_once_per_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            emergency = make_record(
                "emergency-with-triage-text",
                "Your symptoms may indicate a pulmonary embolism. Seek immediate medical attention now.",
                "EmergencyAgent",
            )
            for split in ("train", "val", "test"):
                safe = make_record(f"{split}-safe", "Follow your written exercise plan.")
                rows = (safe, emergency)
                (data_dir / f"qwen_sft_{split}.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in rows),
                    encoding="utf-8",
                )

            report = filter_splits(data_dir)
            for split in ("train", "val", "test"):
                result = report["splits"][split]
                self.assertEqual(result["excluded"], 1)
                self.assertEqual(len(result["excluded_records"]), 1)
                self.assertEqual(
                    result["excluded_records"][0]["reasons"],
                    [
                        "expected_agent:EmergencyAgent",
                        "assistant_emergency_escalation",
                        "assistant_triage_decision",
                    ],
                )
                self.assertEqual(
                    result["exclusion_counts_by_reason"],
                    {
                        "expected_agent:EmergencyAgent": 1,
                        "assistant_emergency_escalation": 1,
                        "assistant_triage_decision": 1,
                    },
                )

    def test_ordinary_clinical_education_is_retained(self) -> None:
        responses = (
            "Contact your surgeon if you have questions about your recovery.",
            "Avoid emergency braking while taking opioid pain medication.",
            "Some patients are told to call their doctor during routine office hours.",
        )
        for response in responses:
            with self.subTest(response=response):
                self.assertEqual(exclusion_reasons(make_record("safe", response)), [])

    def test_outputs_are_deterministic_and_preserve_split_membership(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            original_records = {}
            for split in ("train", "val", "test"):
                safe = make_record(f"{split}-safe", "Follow your written exercise plan.")
                urgent = make_record(f"{split}-urgent", "Seek immediate medical attention.")
                original_records[split] = (safe, urgent)
                source = data_dir / f"qwen_sft_{split}.jsonl"
                source.write_text(
                    "".join(json.dumps(row) + "\n" for row in (safe, urgent)),
                    encoding="utf-8",
                )

            first_report = filter_splits(data_dir)
            first_outputs = {
                split: (data_dir / f"qwen_sft_{split}_filtered.jsonl").read_bytes()
                for split in ("train", "val", "test")
            }
            first_manifest = (data_dir / "qwen_sft_filter_report.json").read_bytes()
            second_report = filter_splits(data_dir)

            self.assertEqual(first_report, second_report)
            self.assertEqual(first_manifest, (data_dir / "qwen_sft_filter_report.json").read_bytes())
            for split in ("train", "val", "test"):
                output = data_dir / f"qwen_sft_{split}_filtered.jsonl"
                self.assertEqual(first_outputs[split], output.read_bytes())
                rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
                self.assertEqual([row["id"] for row in rows], [f"{split}-safe"])
                self.assertEqual(exclusion_reasons(rows[0]), [])
                result = first_report["splits"][split]
                self.assertEqual(result["excluded_records"][0]["id"], f"{split}-urgent")
                self.assertEqual(result["excluded_records"][0]["reasons"], ["assistant_emergency_escalation"])
                self.assertEqual([row["id"] for row in original_records[split]], [f"{split}-safe", f"{split}-urgent"])

    def test_invalid_schema_fails_without_writing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            for split in ("train", "val", "test"):
                record = make_record(f"{split}-safe", "Routine information.")
                if split == "val":
                    record["conversations"].pop()
                (data_dir / f"qwen_sft_{split}.jsonl").write_text(
                    json.dumps(record) + "\n",
                    encoding="utf-8",
                )

            with self.assertRaisesRegex(ValueError, "conversations must contain"):
                filter_splits(data_dir)
            self.assertFalse((data_dir / "qwen_sft_train_filtered.jsonl").exists())
            self.assertFalse((data_dir / "qwen_sft_filter_report.json").exists())


if __name__ == "__main__":
    unittest.main()
