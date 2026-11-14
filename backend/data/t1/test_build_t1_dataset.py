"""Tests for the deterministic T1 seed audit and split builder."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from build_t1_dataset import (
    _normalize_message,
    build_dataset,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = REPO_ROOT / "backend" / "data" / "exports"


class T1DatasetBuilderTests(unittest.TestCase):
    def build_in(self, root: Path) -> tuple[Path, Path, dict]:
        seed_dir = root / "seed_v1"
        output_dir = root / "build_v1"
        manifest = build_dataset(SOURCE_DIR, seed_dir, output_dir, "test-source-commit")
        return seed_dir, output_dir, manifest

    @staticmethod
    def read_jsonl(path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_seed_copies_are_byte_identical_and_manifested(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            seed_dir, _, manifest = self.build_in(Path(temporary_directory))
            for split in ("train", "test"):
                name = f"triage_intent_{split}.jsonl"
                source_bytes = (SOURCE_DIR / name).read_bytes()
                self.assertEqual((seed_dir / name).read_bytes(), source_bytes)
                self.assertTrue(manifest["source_files"][name]["byte_identical"])
                self.assertEqual(manifest["source_files"][name]["row_count"], 420 if split == "train" else 90)

    def test_audit_records_exact_and_normalized_original_split_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            _, output_dir, _ = self.build_in(Path(temporary_directory))
            audit = json.loads((output_dir / "audit_report.json").read_text(encoding="utf-8"))
            self.assertEqual(audit["source_total_rows"], 510)
            self.assertEqual(audit["source_row_counts"], {"train": 420, "test": 90})
            self.assertEqual(
                audit["source_label_counts"],
                {
                    "train": {"RED": 142, "YELLOW": 101, "GREEN": 177},
                    "test": {"RED": 31, "YELLOW": 19, "GREEN": 40},
                },
            )
            self.assertEqual(
                audit["source_unique_user_messages"],
                {
                    "train": {"exact_user_messages": 82, "normalized_user_messages": 63},
                    "test": {"exact_user_messages": 55, "normalized_user_messages": 51},
                },
            )
            self.assertEqual(
                audit["original_train_test_overlap"]["exact_unique_message_intersection"], 52
            )
            self.assertEqual(audit["original_train_test_overlap"]["exact_unique_test_messages"], 55)
            self.assertEqual(
                audit["original_train_test_overlap"]["normalized_unique_message_intersection"], 51
            )
            self.assertEqual(
                audit["original_train_test_overlap"]["normalized_unique_test_messages"], 51
            )
            self.assertEqual(audit["original_train_test_overlap"]["scenario_group_intersection"], 21)

    def test_outputs_are_deterministic_and_source_exports_are_untouched(self) -> None:
        source_before = {
            path.name: path.read_bytes()
            for path in SOURCE_DIR.glob("triage_intent_*.jsonl")
        }
        with tempfile.TemporaryDirectory() as first_temp, tempfile.TemporaryDirectory() as second_temp:
            _, first_output, _ = self.build_in(Path(first_temp))
            _, second_output, _ = self.build_in(Path(second_temp))
            first_files = {path.name: path.read_bytes() for path in first_output.iterdir()}
            second_files = {path.name: path.read_bytes() for path in second_output.iterdir()}
        self.assertEqual(first_files, second_files)
        self.assertEqual(
            source_before,
            {path.name: path.read_bytes() for path in SOURCE_DIR.glob("triage_intent_*.jsonl")},
        )

    def test_scenario_split_isolates_scenarios_and_wording(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            _, output_dir, _ = self.build_in(Path(temporary_directory))
            train = self.read_jsonl(output_dir / "scenario_held_out_train.jsonl")
            evaluation = self.read_jsonl(output_dir / "scenario_held_out_eval.jsonl")
            self.assertTrue(train)
            self.assertTrue(evaluation)
            self.assertFalse({row["scenario_id"] for row in train} & {row["scenario_id"] for row in evaluation})
            self.assertFalse(
                {_normalize_message(row["user_message"]) for row in train}
                & {_normalize_message(row["user_message"]) for row in evaluation}
            )
            self.assertEqual(len(train) + len(evaluation), 510)

    def test_wording_split_isolates_normalized_wording(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            _, output_dir, _ = self.build_in(Path(temporary_directory))
            train = self.read_jsonl(output_dir / "wording_held_out_train.jsonl")
            evaluation = self.read_jsonl(output_dir / "wording_held_out_eval.jsonl")
            train_words = {_normalize_message(row["user_message"]) for row in train}
            evaluation_words = {_normalize_message(row["user_message"]) for row in evaluation}
            self.assertFalse(train_words & evaluation_words)
            self.assertEqual(len(train) + len(evaluation), 510)

    def test_all_labels_are_review_pending_and_corrections_stay_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            _, output_dir, manifest = self.build_in(Path(temporary_directory))
            for filename in (
                "scenario_held_out_train.jsonl",
                "scenario_held_out_eval.jsonl",
                "wording_held_out_train.jsonl",
                "wording_held_out_eval.jsonl",
            ):
                for row in self.read_jsonl(output_dir / filename):
                    self.assertTrue(
                        {
                            "case_id",
                            "source_seed_id",
                            "source_split",
                            "split",
                            "scenario_id",
                            "expected_triage",
                            "expected_intent",
                            "label_source",
                            "label_review_status",
                            "scenario_review_status",
                            "generation_method",
                        }.issubset(row)
                    )
                    self.assertEqual(row["label_review_status"], "needs_clinical_review")
                    self.assertEqual(row["scenario_review_status"], "needs_manual_scenario_review")
                    self.assertEqual(row["generation_method"], "source_seed")
                    self.assertEqual(row["source_seed_id"], row["case_id"])
            with (output_dir / "label_corrections.csv").open(newline="", encoding="utf-8") as file:
                self.assertEqual(
                    next(csv.reader(file)),
                    [
                        "case_id",
                        "source_split",
                        "source_label",
                        "proposed_label",
                        "reason",
                        "review_status",
                        "reviewer",
                        "reviewed_at",
                    ],
                )
                self.assertEqual(list(csv.reader(file)), [])
            review_queue = self.read_jsonl(output_dir / "clinical_review_queue.jsonl")
            self.assertEqual(len(review_queue), 510)
            self.assertEqual(manifest["synthetic_examples_generated"], 0)
            self.assertEqual(manifest["corrections_applied"], 0)
            self.assertIsNone(manifest["clinical_guideline"])

    def test_invalid_source_schema_fails_before_seed_or_output_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_dir = root / "source"
            source_dir.mkdir()
            train_lines = (SOURCE_DIR / "triage_intent_train.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            first_record = json.loads(train_lines[0])
            del first_record["expected_triage"]
            train_lines[0] = json.dumps(first_record)
            (source_dir / "triage_intent_train.jsonl").write_text(
                "\n".join(train_lines) + "\n", encoding="utf-8"
            )
            (source_dir / "triage_intent_test.jsonl").write_bytes(
                (SOURCE_DIR / "triage_intent_test.jsonl").read_bytes()
            )
            seed_dir = root / "seed"
            output_dir = root / "output"
            with self.assertRaisesRegex(ValueError, "missing fields"):
                build_dataset(source_dir, seed_dir, output_dir, "test-commit")
            self.assertFalse(seed_dir.exists())
            self.assertFalse(output_dir.exists())

    def test_message_normalization_avoids_substring_false_positives(self) -> None:
        left = "My LEFT calf is sore on postoperative day 4."
        right = "My right calf is sore on post-op day 12."
        self.assertEqual(_normalize_message(left), _normalize_message(right))
        self.assertNotEqual(
            _normalize_message("The leftover bandage is torn."),
            _normalize_message("The bandage is torn."),
        )
        self.assertNotEqual(
            _normalize_message("The rightfully approved plan is unchanged."),
            _normalize_message("The approved plan is unchanged."),
        )

    def test_changed_source_cannot_silently_replace_versioned_seed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            for split in ("train", "test"):
                (source / f"triage_intent_{split}.jsonl").write_bytes(
                    (SOURCE_DIR / f"triage_intent_{split}.jsonl").read_bytes()
                )
            seed_dir = root / "seed"
            output_dir = root / "output"
            build_dataset(source, seed_dir, output_dir, "commit-a")
            original_seed = (seed_dir / "triage_intent_train.jsonl").read_bytes()
            (source / "triage_intent_train.jsonl").write_bytes(original_seed + b"\n")
            with self.assertRaisesRegex(ValueError, "differs from the current source export"):
                build_dataset(source, seed_dir, output_dir, "commit-b")
            self.assertEqual((seed_dir / "triage_intent_train.jsonl").read_bytes(), original_seed)


if __name__ == "__main__":
    unittest.main()
