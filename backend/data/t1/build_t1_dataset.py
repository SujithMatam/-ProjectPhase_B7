"""Build an auditable, review-pending T1 triage dataset from the source exports."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


VERSION = "t1-seed-v1"
LABELS = {"RED", "YELLOW", "GREEN"}
SPLITS = ("train", "test")
REQUIRED_FIELDS = {
    "case_id",
    "patient_id",
    "surgery_type",
    "affected_limb",
    "postop_day",
    "user_message",
    "expected_triage",
    "expected_intent",
    "escalation_required",
    "temperature_c",
    "clinical_rationale",
    "split",
}
NORMALIZATION_METHOD = (
    "casefold; replace whole-word left/right with {side}; replace "
    "post-op day/postoperative day/day followed by an integer with {day}; "
    "collapse whitespace; preserve all other wording and punctuation"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_message(message: str) -> str:
    normalized = message.casefold()
    normalized = re.sub(r"\b(?:left|right)\b", "{side}", normalized)
    normalized = re.sub(
        r"\b(?:post[- ]?op(?:erative)?\s+day|postop\s+day|day)\s*\d+\b",
        "{day}",
        normalized,
    )
    return re.sub(r"\s+", " ", normalized).strip()


def _normalize_rationale(rationale: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", rationale.casefold())
    return re.sub(r"\s+", " ", normalized).strip()


def _read_sources(source_dir: Path) -> dict[str, list[dict[str, Any]]]:
    datasets: dict[str, list[dict[str, Any]]] = {}
    seen_case_ids: set[str] = set()
    for split in SPLITS:
        path = source_dir / f"triage_intent_{split}.jsonl"
        rows: list[dict[str, Any]] = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {error}") from error
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: each row must be a JSON object")
            missing = REQUIRED_FIELDS - row.keys()
            if missing:
                raise ValueError(f"{path}:{line_number}: missing fields {sorted(missing)}")
            if row["split"] != split:
                raise ValueError(f"{path}:{line_number}: split must be {split!r}")
            if row["expected_triage"] not in LABELS:
                raise ValueError(f"{path}:{line_number}: invalid expected_triage")
            if not isinstance(row["user_message"], str) or not row["user_message"].strip():
                raise ValueError(f"{path}:{line_number}: user_message must be nonempty text")
            if not isinstance(row["clinical_rationale"], str) or not row["clinical_rationale"].strip():
                raise ValueError(f"{path}:{line_number}: clinical_rationale must be nonempty text")
            case_id = row["case_id"]
            if case_id in seen_case_ids:
                raise ValueError(f"{path}:{line_number}: duplicate case_id {case_id!r}")
            seen_case_ids.add(case_id)
            rows.append(row)
        datasets[split] = rows
    return datasets


def _jsonl_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _stable_groups(
    rows: list[dict[str, Any]], key_for: Any, prefix: str
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[key_for(row)].append(row)
    return {
        f"{prefix}-{_sha256(key.encode('utf-8'))[:16]}": group
        for key, group in sorted(groups.items())
    }


def _partition_groups(
    groups: dict[str, list[dict[str, Any]]], eval_fraction: float = 0.2
) -> dict[str, str]:
    strata: dict[str, list[str]] = defaultdict(list)
    for group_id, rows in groups.items():
        labels = sorted({row["expected_triage"] for row in rows})
        stratum = labels[0] if len(labels) == 1 else "LABEL_CONFLICT"
        strata[stratum].append(group_id)

    assignment: dict[str, str] = {}
    for group_ids in strata.values():
        ordered = sorted(group_ids, key=lambda group_id: _sha256(group_id.encode("utf-8")))
        held_out_count = max(1, round(len(ordered) * eval_fraction)) if len(ordered) > 1 else 0
        held_out = set(ordered[:held_out_count])
        assignment.update(
            {group_id: "evaluation" if group_id in held_out else "train" for group_id in ordered}
        )
    return assignment


def _rows_with_provenance(
    datasets: dict[str, list[dict[str, Any]]],
    group_ids: dict[str, str],
    assignment: dict[str, str],
    grouping_method: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    output: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    for source_split in SPLITS:
        for source in datasets[source_split]:
            group_id = group_ids[source["case_id"]]
            row = dict(source)
            row.update(
                {
                    "source_seed_id": source["case_id"],
                    "source_split": source_split,
                    "split": assignment[group_id],
                    "scenario_id": group_id,
                    "scenario_grouping_method": grouping_method,
                    "scenario_review_status": "needs_manual_scenario_review",
                    "label_source": "source_seed_expected_triage",
                    "label_review_status": "needs_clinical_review",
                    "generation_method": "source_seed",
                }
            )
            output.append(row)
            review_queue.append(
                {
                    "source_seed_id": source["case_id"],
                    "source_split": source_split,
                    "scenario_id": group_id,
                    "user_message": source["user_message"],
                    "expected_triage": source["expected_triage"],
                    "expected_intent": source["expected_intent"],
                    "clinical_rationale": source["clinical_rationale"],
                    "review_status": "needs_clinical_review",
                    "review_reasons": [
                        "No standalone written clinical triage guideline was located.",
                        "Source label has not been clinician-validated for T1.",
                        "Provisional scenario grouping requires manual review.",
                    ],
                }
            )
    return output, review_queue


def _split_rows(
    rows: list[dict[str, Any]], group_id_by_case: dict[str, str], assignments: dict[str, str]
) -> dict[str, list[dict[str, Any]]]:
    partitions: dict[str, list[dict[str, Any]]] = {"train": [], "evaluation": []}
    for row in rows:
        group_id = group_id_by_case[row["source_seed_id"]]
        partitions[assignments[group_id]].append(row)
    return partitions


def _audit(
    datasets: dict[str, list[dict[str, Any]]],
    scenario_groups: dict[str, list[dict[str, Any]]],
    word_groups: dict[str, list[dict[str, Any]]],
    scenario_assignment: dict[str, str],
    word_assignment: dict[str, str],
) -> dict[str, Any]:
    train_messages = {row["user_message"] for row in datasets["train"]}
    test_messages = {row["user_message"] for row in datasets["test"]}
    train_normalized = {_normalize_message(message) for message in train_messages}
    test_normalized = {_normalize_message(message) for message in test_messages}
    train_scenarios = {
        _normalize_rationale(row["clinical_rationale"]) for row in datasets["train"]
    }
    test_scenarios = {
        _normalize_rationale(row["clinical_rationale"]) for row in datasets["test"]
    }

    def label_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
        counts = Counter(row["expected_triage"] for row in rows)
        return {label: counts.get(label, 0) for label in ("RED", "YELLOW", "GREEN")}

    def unique_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "exact_user_messages": len({row["user_message"] for row in rows}),
            "normalized_user_messages": len({_normalize_message(row["user_message"]) for row in rows}),
        }

    def partition_counts(
        groups: dict[str, list[dict[str, Any]]], assignments: dict[str, str]
    ) -> dict[str, Any]:
        partition_rows: dict[str, list[dict[str, Any]]] = {"train": [], "evaluation": []}
        for group_id, rows in groups.items():
            partition_rows[assignments[group_id]].extend(rows)
        return {
            partition: {
                "rows": len(rows),
                "groups": sum(value == partition for value in assignments.values()),
                "triage_labels": label_counts(rows),
            }
            for partition, rows in partition_rows.items()
        }

    normalized_groups = _stable_groups(
        [row for split in SPLITS for row in datasets[split]],
        lambda row: _normalize_message(row["user_message"]),
        "wording",
    )
    rationale_to_labels: dict[str, set[str]] = defaultdict(set)
    for row in (row for split in SPLITS for row in datasets[split]):
        rationale_to_labels[_normalize_rationale(row["clinical_rationale"])].add(
            row["expected_triage"]
        )

    return {
        "version": VERSION,
        "clinical_status": (
            "All source triage labels are pending clinician review. The repository contains "
            "implementation code but no standalone written clinical triage guideline; no "
            "clinical label corrections or synthetic examples were created."
        ),
        "source_row_counts": {split: len(datasets[split]) for split in SPLITS},
        "source_total_rows": sum(len(rows) for rows in datasets.values()),
        "source_label_counts": {split: label_counts(datasets[split]) for split in SPLITS},
        "source_unique_user_messages": {
            split: unique_counts(datasets[split]) for split in SPLITS
        },
        "original_train_test_overlap": {
            "exact_unique_message_intersection": len(train_messages & test_messages),
            "exact_unique_test_messages": len(test_messages),
            "normalized_unique_message_intersection": len(train_normalized & test_normalized),
            "normalized_unique_test_messages": len(test_normalized),
            "scenario_group_intersection": len(train_scenarios & test_scenarios),
            "train_scenario_groups": len(train_scenarios),
            "test_scenario_groups": len(test_scenarios),
            "scenario_grouping_basis": "casefolded, punctuation/whitespace-normalized clinical_rationale",
        },
        "normalization": NORMALIZATION_METHOD,
        "provisional_grouping": {
            "grouping_basis": "normalized clinical_rationale",
            "scenario_group_count": len(scenario_groups),
            "wording_group_count": len(normalized_groups),
            "scenario_groups_with_triage_label_conflicts": sum(
                len(labels) > 1 for labels in rationale_to_labels.values()
            ),
            "review_status": "needs_manual_scenario_review",
        },
        "scenario_held_out_partition": partition_counts(
            scenario_groups, scenario_assignment
        ),
        "wording_held_out_partition": partition_counts(word_groups, word_assignment),
        "synthetic_candidate_count": 0,
        "label_correction_count": 0,
        "qwen_sft_rows_included": 0,
        "note": (
            "This is a triage-seed audit/build, not model training, clinical validation, or a "
            "replacement for deterministic SafetyTriageEngine decisions. Qwen SFT exports are "
            "a separate dataset and are not included."
        ),
    }


def build_dataset(
    source_dir: Path,
    seed_dir: Path,
    output_dir: Path,
    source_commit: str,
) -> dict[str, Any]:
    source_dir = Path(source_dir)
    seed_dir = Path(seed_dir)
    output_dir = Path(output_dir)
    datasets = _read_sources(source_dir)

    source_bytes: dict[str, bytes] = {}
    seed_hashes: dict[str, str] = {}
    for split in SPLITS:
        name = f"triage_intent_{split}.jsonl"
        source_data = (source_dir / name).read_bytes()
        source_bytes[name] = source_data
        seed_path = seed_dir / name
        if seed_path.exists():
            if seed_path.read_bytes() != source_data:
                raise ValueError(
                    f"{seed_path} differs from the current source export; create a new "
                    "versioned seed directory instead of replacing this immutable seed."
                )
        else:
            _write_bytes(seed_path, source_data)
        seed_hashes[name] = _sha256(seed_path.read_bytes())

    all_rows = [row for split in SPLITS for row in datasets[split]]
    scenario_groups = _stable_groups(
        all_rows, lambda row: _normalize_rationale(row["clinical_rationale"]), "scenario"
    )
    word_groups = _stable_groups(
        all_rows, lambda row: _normalize_message(row["user_message"]), "wording"
    )

    # A wording group must never be split across provisional scenarios. If a
    # future export violates that assumption, fail rather than silently leak it.
    word_to_scenarios: dict[str, set[str]] = defaultdict(set)
    for scenario_id, rows in scenario_groups.items():
        for row in rows:
            word_to_scenarios[_normalize_message(row["user_message"])].add(scenario_id)
    conflicting_words = [word for word, ids in word_to_scenarios.items() if len(ids) > 1]
    if conflicting_words:
        raise ValueError(
            "A normalized user message appears in multiple rationale-based scenario groups; "
            "review scenario grouping before building splits."
        )

    scenario_id_by_case: dict[str, str] = {}
    rationale_by_scenario: dict[str, str] = {}
    for scenario_id, rows in scenario_groups.items():
        for row in rows:
            scenario_id_by_case[row["case_id"]] = scenario_id
        rationale_by_scenario[scenario_id] = _normalize_rationale(rows[0]["clinical_rationale"])

    word_id_by_case: dict[str, str] = {}
    for word_id, rows in word_groups.items():
        for row in rows:
            word_id_by_case[row["case_id"]] = word_id

    scenario_assignment = _partition_groups(scenario_groups)
    word_assignment = _partition_groups(word_groups)
    scenario_rows, review_queue = _rows_with_provenance(
        datasets,
        scenario_id_by_case,
        scenario_assignment,
        "normalized_clinical_rationale_provisional",
    )
    wording_rows, _ = _rows_with_provenance(
        datasets,
        word_id_by_case,
        word_assignment,
        "normalized_user_message",
    )

    scenario_partitions = _split_rows(
        scenario_rows, scenario_id_by_case, scenario_assignment
    )
    wording_partitions = _split_rows(wording_rows, word_id_by_case, word_assignment)
    output_payloads = {
        "audit_report.json": (
            json.dumps(
                _audit(
                    datasets,
                    scenario_groups,
                    word_groups,
                    scenario_assignment,
                    word_assignment,
                ),
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8"),
        "clinical_review_queue.jsonl": _jsonl_bytes(review_queue),
        "scenario_held_out_train.jsonl": _jsonl_bytes(scenario_partitions["train"]),
        "scenario_held_out_eval.jsonl": _jsonl_bytes(scenario_partitions["evaluation"]),
        "wording_held_out_train.jsonl": _jsonl_bytes(wording_partitions["train"]),
        "wording_held_out_eval.jsonl": _jsonl_bytes(wording_partitions["evaluation"]),
    }

    group_map_rows = []
    for scenario_id, rows in sorted(scenario_groups.items()):
        group_map_rows.append(
            {
                "scenario_id": scenario_id,
                "normalized_clinical_rationale": rationale_by_scenario[scenario_id],
                "source_seed_ids": sorted(row["case_id"] for row in rows),
                "source_splits": sorted({row["split"] for row in rows}),
                "source_triage_labels": sorted({row["expected_triage"] for row in rows}),
                "grouping_method": "normalized_clinical_rationale_provisional",
                "review_status": "needs_manual_scenario_review",
            }
        )
    output_payloads["scenario_group_map.jsonl"] = _jsonl_bytes(group_map_rows)
    correction_header = (
        "case_id,source_split,source_label,proposed_label,reason,review_status,reviewer,reviewed_at\n"
    ).encode("utf-8")
    output_payloads["label_corrections.csv"] = correction_header

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in output_payloads.items():
        _write_bytes(output_dir / filename, payload)

    source_hashes = {name: _sha256(data) for name, data in source_bytes.items()}
    manifest = {
        "version": VERSION,
        "source_commit": source_commit,
        "source_directory": source_dir.name,
        "seed_directory": seed_dir.name,
        "source_files": {
            name: {
                "sha256": source_hashes[name],
                "seed_copy_sha256": seed_hashes[name],
                "byte_identical": source_hashes[name] == seed_hashes[name],
                "row_count": len(datasets[name.removeprefix("triage_intent_").removesuffix(".jsonl")]),
            }
            for name in sorted(source_bytes)
        },
        "output_files": {
            name: {"sha256": _sha256(payload), "bytes": len(payload)}
            for name, payload in sorted(output_payloads.items())
        },
        "split_protocols": {
            "scenario_held_out": {
                "grouping": "normalized clinical_rationale, provisional and manual-review-needed",
                "eval_fraction": 0.2,
                "assignment": "stable SHA-256 order within expected_triage strata; at least one held out when a stratum has multiple groups",
            },
            "wording_held_out": {
                "grouping": "casefolded user_message with only laterality and day-number normalization",
                "eval_fraction": 0.2,
                "assignment": "stable SHA-256 order within expected_triage strata; at least one held out when a stratum has multiple groups",
            },
        },
        "label_status": "needs_clinical_review",
        "synthetic_examples_generated": 0,
        "corrections_applied": 0,
        "clinical_guideline": None,
    }
    _write_bytes(
        output_dir / "manifest.json",
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return manifest


def _git_commit(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    repo_root = Path(__file__).resolve().parents[3]
    parser.add_argument("--source-dir", type=Path, default=repo_root / "backend" / "data" / "exports")
    parser.add_argument("--seed-dir", type=Path, default=Path(__file__).resolve().parent / "seed_v1")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "build_v1")
    parser.add_argument("--source-commit", default=None)
    args = parser.parse_args()
    source_commit = args.source_commit or _git_commit(repo_root)
    build_dataset(args.source_dir, args.seed_dir, args.output_dir, source_commit)


if __name__ == "__main__":
    main()
