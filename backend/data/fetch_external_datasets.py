"""
fetch_external_datasets.py
Downloads, filters, reformats, and merges external Hugging Face medical datasets
with the existing synthetic orthopedic chatbot data.

Run from project root:
    pip install datasets huggingface_hub tqdm
    python backend/data/fetch_external_datasets.py

Output:
    backend/data/exports/merged_sft_train.jsonl  (merged training set)
    backend/data/exports/merged_sft_val.jsonl    (merged validation set)
"""

from __future__ import annotations

import json
import hashlib
import random
from pathlib import Path
from typing import Any

try:
    from datasets import load_dataset
    from tqdm import tqdm
except ImportError:
    raise SystemExit("Run: pip install datasets huggingface_hub tqdm")

# ============================================================================
# CONFIG
# ============================================================================

EXPORT_DIR = Path(__file__).resolve().parent / "exports"
EXPORT_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = (
    "You are an AI Clinical Assistant specializing in orthopedic post-operative "
    "recovery (AAOS/NHS guidelines). Provide empathetic, clinically sound, "
    "evidence-based guidance. Never offer unapproved prescriptions, never dismiss "
    "red-flag symptoms, and escalate medical emergencies immediately."
)

# Keywords to keep a row — must appear in question or answer
ORTHO_KEYWORDS = [
    "knee", "hip", "joint", "surgery", "post-op", "post op", "orthopedic",
    "orthopaedic", "wound", "swelling", "physiotherapy", "physical therapy",
    "fracture", "calf", "infection", "arthroplasty", "ligament", "tendon",
    "dislocation", "dvt", "clot", "thrombosis", "rehab", "rehabilitation",
    "incision", "suture", "staple", "immobilization", "weight bearing",
    "range of motion", "rom", "acl", "tka", "tha", "rotator cuff",
    "anterior cruciate", "meniscus", "cartilage", "bone", "implant",
    "prosthesis", "cast", "splint", "brace", "physiotherapist",
]

VAL_FRACTION = 0.1   # 10% of external data -> validation
MAX_RESPONSE_TOKENS = 800   # Approximate — filter out very long responses

# ============================================================================
# HELPERS
# ============================================================================

def _is_ortho_relevant(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in ORTHO_KEYWORDS)


def _msg_hash(user_msg: str) -> str:
    return hashlib.md5(user_msg.strip().lower().encode()).hexdigest()


def _approx_tokens(text: str) -> int:
    return len(text.split())


def _make_record(user: str, assistant: str, source: str, idx: int) -> dict[str, Any]:
    return {
        "id": f"EXT_{source.upper()}_{idx:05d}",
        "conversations": [
            {"from": "system",    "value": SYSTEM_PROMPT},
            {"from": "user",      "value": user.strip()},
            {"from": "assistant", "value": assistant.strip()},
        ],
        "metadata": {"source": source, "expected_agent": "ChatAgent"},
    }


# ============================================================================
# DATASET FETCHERS
# ============================================================================

def fetch_ruslanmv(max_rows: int = 20_000) -> list[dict]:
    """ruslanmv/ai-medical-chatbot - patient/doctor Q&A pairs."""
    print("\n[1/3] Downloading ruslanmv/ai-medical-chatbot ...")
    try:
        ds = load_dataset("ruslanmv/ai-medical-chatbot", split="train", streaming=True)
    except Exception as e:
        print(f"  WARNING: Could not load ruslanmv dataset: {e}")
        return []

    records, seen, count = [], set(), 0
    for row in tqdm(ds, total=max_rows, desc="  Filtering"):
        if count >= max_rows:
            break
        patient_msg = row.get("Patient", "") or ""
        doctor_msg  = row.get("Doctor",  "") or ""
        if not patient_msg or not doctor_msg:
            continue
        combined = patient_msg + " " + doctor_msg
        if not _is_ortho_relevant(combined):
            continue
        if _approx_tokens(doctor_msg) > MAX_RESPONSE_TOKENS:
            continue
        h = _msg_hash(patient_msg)
        if h in seen:
            continue
        seen.add(h)
        records.append(_make_record(patient_msg, doctor_msg, "ruslanmv", len(records)))
        count += 1

    print(f"  OK: {len(records)} ortho-relevant rows collected from ruslanmv")
    return records


def fetch_jtatman(max_rows: int = 15_000) -> list[dict]:
    """jtatman/medical-sci-instruct-1m-sharegpt - already ShareGPT conversations format."""
    print("\n[2/3] Downloading jtatman/medical-sci-instruct-1m-sharegpt ...")
    try:
        ds = load_dataset("jtatman/medical-sci-instruct-1m-sharegpt", split="train", streaming=True)
    except Exception as e:
        print(f"  WARNING: Could not load jtatman dataset: {e}")
        return []

    records, seen, count = [], set(), 0
    for row in tqdm(ds, total=max_rows, desc="  Filtering"):
        if count >= max_rows:
            break
        convs = row.get("conversations", [])
        if not convs or len(convs) < 2:
            continue

        user_msg = ""
        asst_msg = ""
        for turn in convs:
            role = turn.get("from", "")
            val  = turn.get("value", "") or ""
            if role in ("human", "user") and not user_msg:
                user_msg = val
            elif role in ("gpt", "assistant") and not asst_msg:
                asst_msg = val

        if not user_msg or not asst_msg:
            continue
        combined = user_msg + " " + asst_msg
        if not _is_ortho_relevant(combined):
            continue
        if _approx_tokens(asst_msg) > MAX_RESPONSE_TOKENS:
            continue
        h = _msg_hash(user_msg)
        if h in seen:
            continue
        seen.add(h)
        new_convs = [{"from": "system", "value": SYSTEM_PROMPT}]
        new_convs += [c for c in convs if c.get("from") in ("human", "user", "gpt", "assistant")]
        records.append({
            "id": f"EXT_JTATMAN_{len(records):05d}",
            "conversations": new_convs,
            "metadata": {"source": "jtatman", "expected_agent": "ChatAgent"},
        })
        count += 1

    print(f"  OK: {len(records)} ortho-relevant rows collected from jtatman")
    return records


def fetch_lavita(max_rows: int = 10_000) -> list[dict]:
    """lavita/medical-qa-datasets - Alpaca-style (input/output)."""
    print("\n[3/3] Downloading lavita/medical-qa-datasets ...")
    all_records: list[dict] = []
    # Config names as of 2024 — updated from original healthcaremagic-100k / icliniq-10k
    for config in ("chatdoctor_healthcaremagic", "chatdoctor-icliniq"):
        try:
            ds = load_dataset("lavita/medical-qa-datasets", config, split="train", streaming=True)
        except Exception as e:
            print(f"  WARNING: Could not load lavita/{config}: {e}")
            continue

        seen = set()
        for row in tqdm(ds, total=max_rows, desc=f"  {config}"):
            if len(all_records) >= max_rows:
                break
            user_msg = row.get("input", "") or row.get("question", "") or ""
            asst_msg = row.get("output", "") or row.get("answer", "") or ""
            if not user_msg or not asst_msg:
                continue
            combined = user_msg + " " + asst_msg
            if not _is_ortho_relevant(combined):
                continue
            if _approx_tokens(asst_msg) > MAX_RESPONSE_TOKENS:
                continue
            h = _msg_hash(user_msg)
            if h in seen:
                continue
            seen.add(h)
            all_records.append(_make_record(user_msg, asst_msg, f"lavita_{config}", len(all_records)))

    print(f"  OK: {len(all_records)} ortho-relevant rows collected from lavita")
    return all_records


# ============================================================================
# MERGE & EXPORT
# ============================================================================

def load_existing_jsonl(path: Path) -> list[dict]:
    records = []
    if not path.exists():
        return records
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def write_jsonl(records: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  Saved {len(records):,} records -> {path}")


def main() -> None:
    print("=" * 60)
    print("  Orthopedic Chatbot -- External Dataset Fetcher")
    print("=" * 60)

    # 1. Collect from external sources
    external: list[dict] = []
    external += fetch_ruslanmv()
    external += fetch_jtatman()
    external += fetch_lavita()

    print(f"\nTotal external records (before merge): {len(external):,}")

    # 2. Deduplicate across all external sources
    seen_hashes: set[str] = set()
    deduped: list[dict] = []
    for rec in external:
        convs = rec.get("conversations", [])
        user_val = next((c["value"] for c in convs if c.get("from") in ("user", "human")), "")
        h = _msg_hash(user_val)
        if h not in seen_hashes:
            seen_hashes.add(h)
            deduped.append(rec)

    print(f"  After dedup: {len(deduped):,} unique records")

    # 3. Split external into train/val
    random.seed(42)
    random.shuffle(deduped)
    n_val = int(len(deduped) * VAL_FRACTION)
    ext_val   = deduped[:n_val]
    ext_train = deduped[n_val:]

    # 4. Load existing synthetic data
    existing_train = load_existing_jsonl(EXPORT_DIR / "qwen_sft_train.jsonl")
    existing_val   = load_existing_jsonl(EXPORT_DIR / "qwen_sft_val.jsonl")
    print(f"\nExisting synthetic data -- train: {len(existing_train)}, val: {len(existing_val)}")

    # 5. Merge
    merged_train = existing_train + ext_train
    merged_val   = existing_val   + ext_val
    random.shuffle(merged_train)
    random.shuffle(merged_val)

    # 6. Write merged files
    print(f"\nFinal dataset sizes:")
    write_jsonl(merged_train, EXPORT_DIR / "merged_sft_train.jsonl")
    write_jsonl(merged_val,   EXPORT_DIR / "merged_sft_val.jsonl")

    print("\nDone! Update train_qwen_lora.py to use:")
    print('   TRAIN_FILE = str(DATA_DIR / "merged_sft_train.jsonl")')
    print('   VAL_FILE   = str(DATA_DIR / "merged_sft_val.jsonl")')


if __name__ == "__main__":
    main()
