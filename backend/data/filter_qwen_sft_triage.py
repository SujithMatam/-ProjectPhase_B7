"""Filter triage and emergency-escalation responses from Qwen SFT JSONL exports."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


SPLITS = ("train", "val", "test")
FILTER_VERSION = 2
TEXT_RULES = (
    (
        "assistant_emergency_escalation",
        re.compile(
            r"\b(?:call|dial|contact)\s+(?:911|999|112|emergency services|"
            r"an ambulance|your local emergency number)\b"
            r"|\b(?:go|proceed|head|attend|visit|report)\s+to\s+(?:the\s+)?"
            r"(?:nearest\s+)?(?:emergency department|emergency room|ER|hospital)\b"
            r"|\b(?:seek|get|obtain)\s+(?:(?:immediate|urgent|emergency)\s+)?"
            r"(?:medical\s+)?(?:care|attention|evaluation|help)\b"
            r"(?:\s+(?:immediately|right away|now|urgently|as soon as possible))?"
            r"|\b(?:immediate|urgent|emergency|emergent)\s+(?:medical\s+)?"
            r"(?:care|attention|evaluation|assessment|advice|review)\b"
            r"|\b(?:call|contact|notify)\s+(?:the\s+|your\s+)?"
            r"(?:emergency line|emergency department|emergency room|ER|"
            r"emergency medical services)\b"
            r"|\b(?:contact|call|notify)\s+(?:your\s+)?"
            r"(?:doctor|surgeon|provider|healthcare professional|"
            r"on-call surgical team)\b.{0,70}\b(?:immediately|right away|now|"
            r"urgently|emergency)\b"
            r"|\b(?:immediately|right away|urgently)\b.{0,70}\b"
            r"(?:contact|call|notify)\s+(?:your\s+)?"
            r"(?:doctor|surgeon|provider|healthcare professional|"
            r"on-call surgical team)\b"
            r"|\b(?:life-threatening|medical emergency|emergency situation|"
            r"critical emergency alert|emergent surgical)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "assistant_triage_decision",
        re.compile(
            r"\b(?:red[- ]flag|triage\s+(?:level|category|result))\b"
            r"|\b(?:symptoms?|signs?)\s+(?:may|could|can|are|indicate|"
            r"suggest|point to|are consistent with)\b.{0,100}\b"
            r"(?:blood clot|DVT|pulmonary embolism|PE|compartment syndrome|"
            r"sepsis|hemorrhag\w*|internal bleeding|dislocation)\b"
            r"|\b(?:possible|suspected|suspect)\s+"
            r"(?:DVT|pulmonary embolism|PE|compartment syndrome|sepsis|"
            r"hemorrhag\w*|dislocation)\b",
            re.IGNORECASE,
        ),
    ),
)


def _validate_record(record: Any, source: Path, line_number: int) -> Dict[str, Any]:
    location = f"{source}:{line_number}"
    if not isinstance(record, dict):
        raise ValueError(f"{location}: expected a JSON object")
    if not isinstance(record.get("id"), str) or not record["id"].strip():
        raise ValueError(f"{location}: missing or invalid id")

    conversations = record.get("conversations")
    if not isinstance(conversations, list) or len(conversations) != 3:
        raise ValueError(f"{location}: conversations must contain system, user, assistant")
    roles: List[str] = []
    for turn in conversations:
        if not isinstance(turn, dict):
            raise ValueError(f"{location}: each conversation turn must be an object")
        role = turn.get("from")
        value = turn.get("value")
        if not isinstance(role, str) or not isinstance(value, str) or not value.strip():
            raise ValueError(f"{location}: each turn must have non-empty string from/value")
        roles.append(role)
    if roles != ["system", "user", "assistant"]:
        raise ValueError(f"{location}: expected system, user, assistant turn order")

    metadata = record.get("metadata")
    expected_agent = metadata.get("expected_agent") if isinstance(metadata, dict) else None
    if not isinstance(expected_agent, str) or not expected_agent.strip():
        raise ValueError(f"{location}: metadata.expected_agent must be a non-empty string")
    return record


def exclusion_reasons(record: Dict[str, Any]) -> List[str]:
    expected_agent = record["metadata"]["expected_agent"].strip().casefold()
    assistant_response = record["conversations"][2]["value"]
    reasons = []
    if expected_agent == "emergencyagent":
        reasons.append("expected_agent:EmergencyAgent")
    reasons.extend(
        reason for reason, pattern in TEXT_RULES if pattern.search(assistant_response)
    )
    return reasons


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def filter_splits(data_dir: Path) -> Dict[str, Any]:
    prepared: Dict[str, Tuple[Path, Path, bytes, List[Dict[str, Any]], List[Dict[str, Any]]]] = {}
    report: Dict[str, Any] = {
        "filter_version": FILTER_VERSION,
        "splits": {},
    }

    for split in SPLITS:
        source = data_dir / f"qwen_sft_{split}.jsonl"
        destination = data_dir / f"qwen_sft_{split}_filtered.jsonl"
        try:
            source_bytes = source.read_bytes()
        except OSError as error:
            raise RuntimeError(f"Unable to read required SFT split {source}: {error}") from error
        if not source_bytes:
            raise ValueError(f"{source}: split is empty")

        retained: List[bytes] = []
        excluded: List[Dict[str, Any]] = []
        seen_ids = set()
        for line_number, raw_line in enumerate(source_bytes.splitlines(keepends=True), start=1):
            if not raw_line.strip():
                raise ValueError(f"{source}:{line_number}: blank JSONL records are not allowed")
            try:
                record = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError(f"{source}:{line_number}: invalid UTF-8 JSONL record") from error

            record = _validate_record(record, source, line_number)
            if record["id"] in seen_ids:
                raise ValueError(f"{source}:{line_number}: duplicate id")
            seen_ids.add(record["id"])
            reasons = exclusion_reasons(record)
            if reasons:
                excluded.append(
                    {
                        "id": record["id"],
                        "line": line_number,
                        "reasons": reasons,
                    }
                )
            else:
                retained.append(raw_line)

        output_bytes = b"".join(retained)
        reason_counts: Dict[str, int] = {}
        for item in excluded:
            for reason in item["reasons"]:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        report["splits"][split] = {
            "source": source.name,
            "source_sha256": _sha256(source_bytes),
            "output": destination.name,
            "output_sha256": _sha256(output_bytes),
            "total": len(retained) + len(excluded),
            "retained": len(retained),
            "excluded": len(excluded),
            "exclusion_counts_by_reason": reason_counts,
            "excluded_records": excluded,
        }
        prepared[split] = (source, destination, output_bytes, excluded, retained)

    for _, destination, output_bytes, _, _ in prepared.values():
        destination.write_bytes(output_bytes)
    report_path = data_dir / "qwen_sft_filter_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "exports",
        help="Directory containing qwen_sft_{train,val,test}.jsonl",
    )
    args = parser.parse_args()
    report = filter_splits(args.data_dir)
    for split in SPLITS:
        result = report["splits"][split]
        print(
            f"{split}: retained {result['retained']}/{result['total']}; "
            f"excluded {result['excluded']} -> {result['output']}"
        )
    print(f"Audit report: {args.data_dir / 'qwen_sft_filter_report.json'}")


if __name__ == "__main__":
    main()
