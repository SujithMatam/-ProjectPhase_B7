"""
download_scan_images.py
Downloads real public orthopedic X-ray/MRI images from Kaggle and HuggingFace
into backend/scans/, then seeds the patient_scans table in patients.sqlite3.

PUBLIC DATASETS USED (all open-license):
  1. Kaggle: orvile/digital-knee-xray-images         (CC BY 4.0)  — knee X-rays + KL grade
  2. Kaggle: moamedgobara/multi-class-knee-osteoporosis-x-ray-dataset (Apache 2.0)
  3. HuggingFace: Veronika25/knee-X-ray-images                     — knee X-rays multi-class
  4. HuggingFace: Falah/Alzheimer_MRI  (MRI format reference)
  5. Kaggle: tawsifurrahman/tuberculosis-chest-xray (for spine context)

PREREQUISITES:
  pip install kaggle huggingface_hub Pillow tqdm

  For Kaggle: Place kaggle.json at ~/.kaggle/kaggle.json  OR
              set env vars KAGGLE_USERNAME and KAGGLE_KEY

Run:
  python backend/download_scan_images.py
  python backend/download_scan_images.py --skip-download   # seed DB from already-downloaded files
  python backend/download_scan_images.py --dry-run         # show what would be done
"""

from __future__ import annotations

import argparse
import os
import random
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

# Resolve backend dir
BACKEND_DIR = Path(__file__).resolve().parent
SCANS_DIR   = BACKEND_DIR / "scans"
sys.path.insert(0, str(BACKEND_DIR))

import patient_database as db

# ============================================================================
# SCAN DIRECTORY LAYOUT
# backend/scans/
#   knee_xray/       <- Kaggle digital knee X-ray (CC BY 4.0)
#   knee_oa_xray/    <- knee osteoporosis X-ray (Apache 2.0)
#   knee_mri/        <- HuggingFace knee MRI samples
#   hip_xray/        <- hip X-ray samples
#   spine_xray/      <- spinal X-ray samples
# ============================================================================

SCAN_SUBDIRS = ["knee_xray", "knee_oa_xray", "knee_mri", "hip_xray", "spine_xray"]

# ============================================================================
# DATASET REGISTRY
# ============================================================================

KAGGLE_DATASETS = [
    {
        "slug":    "orvile/digital-knee-xray-images",
        "subdir":  "knee_xray",
        "license": "CC BY 4.0",
        "source":  "Kaggle:orvile/digital-knee-xray-images",
        "scan_type": "XRAY",
        "body_part": "Knee",
    },
    {
        "slug":    "moamedgobara/multi-class-knee-osteoporosis-x-ray-dataset",
        "subdir":  "knee_oa_xray",
        "license": "Apache 2.0",
        "source":  "Kaggle:moamedgobara/multi-class-knee-osteoporosis-x-ray-dataset",
        "scan_type": "XRAY",
        "body_part": "Knee",
    },
]

HF_DATASETS = [
    {
        "repo_id": "Veronika25/knee-X-ray-images",
        "subdir":  "knee_xray_hf",
        "source":  "HuggingFace:Veronika25/knee-X-ray-images",
        "scan_type": "XRAY",
        "body_part": "Knee",
    },
]

# ============================================================================
# KL GRADE + FINDINGS REFERENCE (from Kellgren-Lawrence classification)
# ============================================================================

KL_FINDINGS = {
    0: "No radiographic features of osteoarthritis. Normal joint space.",
    1: "Doubtful narrowing of joint space with possible osteophytic lipping. Grade 1 OA.",
    2: "Definite osteophytes with possible narrowing of joint space. Grade 2 OA (mild).",
    3: "Multiple osteophytes, definite narrowing of joint space, some sclerosis. Grade 3 OA (moderate).",
    4: "Large osteophytes, marked narrowing of joint space, severe sclerosis, definite deformity. Grade 4 OA (severe).",
}

HIP_FINDINGS = [
    "Satisfactory position of hip prosthesis. No evidence of periprosthetic loosening or osteolysis.",
    "Total hip arthroplasty in situ. Well-fixed cemented femoral stem and acetabular cup. Normal alignment.",
    "Hip resurfacing prosthesis correctly positioned. Adequate bone stock. No fracture lines.",
    "Mild heterotopic ossification adjacent to femoral component. Cup anteversion within acceptable range.",
    "Post-operative THA — cup abduction angle 42 degrees. Femoral offset maintained. No dislocation.",
]

SPINE_FINDINGS = [
    "L4-L5 interbody fusion cage in situ. Pedicle screws bilaterally. Satisfactory alignment.",
    "Spinal fusion hardware intact. No subsidence or loosening of instrumentation noted.",
    "Post-operative lumbar spine: solid fusion mass forming. Maintained lumbar lordosis.",
    "Mild adjacent segment disc height reduction at L3-L4. Fusion levels appear solid.",
]

SHOULDER_FINDINGS = [
    "Total shoulder arthroplasty in satisfactory position. Glenoid component without loosening.",
    "Reverse shoulder arthroplasty in situ. Adequate fixation. No signs of component migration.",
    "Post-operative rotator cuff repair: suture anchors in situ at greater tuberosity. No hardware failure.",
]

ACL_FINDINGS = [
    "Post-operative ACL reconstruction. Tibial and femoral tunnels visualised. Graft in anatomical position.",
    "Knee: ACL reconstruction graft in situ. No tunnel widening. Hardware artifact present.",
    "Status post ACL repair. Joint space preserved. No effusion or bony injury detected.",
]

ANKLE_FINDINGS = [
    "Post-arthroscopic ankle: no residual loose bodies. Ankle mortise intact.",
    "Ankle: no fracture or dislocation. Ankle arthroscopy portals noted on soft tissue. Normal alignment.",
]

TIBIA_FINDINGS = [
    "Tibial plateau ORIF: plate and screws in satisfactory position. Fracture lines consolidating.",
    "Periarticular tibial plate in situ. Cortical bridging callus forming. No hardware failure.",
]


def _findings_for(surgery_type: str, body_part: str, kl_grade: Optional[int]) -> str:
    if kl_grade is not None and body_part == "Knee":
        return KL_FINDINGS.get(kl_grade, KL_FINDINGS[0])
    if "Hip" in surgery_type:
        return random.choice(HIP_FINDINGS)
    if "Spine" in surgery_type or "Spinal" in surgery_type:
        return random.choice(SPINE_FINDINGS)
    if "Shoulder" in surgery_type or "Rotator" in surgery_type:
        return random.choice(SHOULDER_FINDINGS)
    if "ACL" in surgery_type or "Cruciate" in surgery_type:
        return random.choice(ACL_FINDINGS)
    if "Ankle" in surgery_type:
        return random.choice(ANKLE_FINDINGS)
    if "Tibia" in surgery_type or "ORIF" in surgery_type:
        return random.choice(TIBIA_FINDINGS)
    return KL_FINDINGS.get(kl_grade or 0, KL_FINDINGS[0])


# ============================================================================
# DOWNLOAD HELPERS
# ============================================================================

def _try_kaggle_download(slug: str, dest_dir: Path, dry_run: bool) -> bool:
    """Attempt to download a Kaggle dataset using the kaggle CLI / API."""
    if dry_run:
        print(f"  [DRY-RUN] Would download Kaggle dataset: {slug} -> {dest_dir}")
        return True
    try:
        import kaggle  # noqa: F401 — triggers credential check
        dest_dir.mkdir(parents=True, exist_ok=True)
        import subprocess
        result = subprocess.run(
            ["kaggle", "datasets", "download", "-d", slug, "-p", str(dest_dir), "--unzip"],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            print(f"  [OK] Kaggle download complete: {slug}")
            return True
        else:
            print(f"  [WARN] Kaggle download failed: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  [WARN] Kaggle not available: {e}")
        print(f"         Manual download: kaggle datasets download -d {slug} -p backend/scans/ --unzip")
        return False


def _try_hf_download(repo_id: str, dest_dir: Path, dry_run: bool) -> bool:
    """Attempt to snapshot-download a HuggingFace image dataset."""
    if dry_run:
        print(f"  [DRY-RUN] Would download HF dataset: {repo_id} -> {dest_dir}")
        return True
    try:
        from huggingface_hub import snapshot_download
        dest_dir.mkdir(parents=True, exist_ok=True)
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            local_dir=str(dest_dir),
            ignore_patterns=["*.git*", "*.md", "*.txt"],
        )
        print(f"  [OK] HuggingFace download complete: {repo_id}")
        return True
    except Exception as e:
        print(f"  [WARN] HuggingFace download failed: {e}")
        print(f"         Manual: from huggingface_hub import snapshot_download; snapshot_download('{repo_id}', repo_type='dataset', local_dir='backend/scans/')")
        return False


def _collect_images(scan_dir: Path, extensions: tuple = (".jpg", ".jpeg", ".png")) -> list[Path]:
    """Recursively collect image files from a directory."""
    images = []
    if not scan_dir.exists():
        return images
    for ext in extensions:
        images.extend(scan_dir.rglob(f"*{ext}"))
        images.extend(scan_dir.rglob(f"*{ext.upper()}"))
    return images


# ============================================================================
# SCAN SEEDER
# ============================================================================

SURGERY_TO_SCAN = {
    "Total Knee Arthroplasty":                 [("XRAY", "Knee"), ("XRAY", "Knee")],
    "Total Hip Arthroplasty":                  [("XRAY", "Hip"), ("XRAY", "Hip")],
    "Anterior Cruciate Ligament Reconstruction":[("XRAY", "Knee"), ("MRI", "Knee")],
    "Rotator Cuff Repair":                     [("XRAY", "Shoulder"), ("MRI", "Shoulder")],
    "Partial Knee Replacement (Unicompartmental)": [("XRAY", "Knee")],
    "Hip Resurfacing":                         [("XRAY", "Hip"), ("XRAY", "Hip")],
    "Spinal Fusion (L4-L5)":                   [("XRAY", "Spine"), ("CT", "Spine")],
    "Tibial Plateau Fracture ORIF":            [("XRAY", "Knee"), ("CT", "Knee")],
    "Shoulder Arthroplasty":                   [("XRAY", "Shoulder")],
    "Ankle Arthroscopy":                       [("XRAY", "Ankle")],
}

# Source attribution by body part (fallback when no downloaded image available)
SOURCE_FALLBACK = {
    "Knee":     "Kaggle:orvile/digital-knee-xray-images (CC BY 4.0)",
    "Hip":      "Kaggle:unifesp/the-unifesp-x-ray-body-part-classification-dataset",
    "Shoulder": "Kaggle:unifesp/the-unifesp-x-ray-body-part-classification-dataset",
    "Spine":    "Kaggle:unifesp/the-unifesp-x-ray-body-part-classification-dataset",
    "Ankle":    "Kaggle:unifesp/the-unifesp-x-ray-body-part-classification-dataset",
}


def seed_scans_to_db(
    downloaded_images: dict[str, list[Path]],
    dry_run: bool = False,
) -> None:
    """Assign scan records to every patient in the DB."""
    db.initialize_database()
    patient_ids = db.list_patient_ids()
    if not patient_ids:
        print("  [WARN] No patients in DB. Run seed_ortho_patients.py first.")
        return

    # Flatten all downloaded knee X-rays for assignment
    knee_imgs  = downloaded_images.get("knee_xray", []) + downloaded_images.get("knee_oa_xray", [])
    random.shuffle(knee_imgs)
    knee_pool  = iter(knee_imgs * 10)  # cycle if fewer images than patients

    seeded_count = 0
    for pid in patient_ids:
        patient = db.get_patient(pid)
        if not patient:
            continue

        # Skip if already has scans
        if patient.get("scans"):
            continue

        surgery_type = patient.get("surgery_type", "")
        laterality   = patient.get("affected_limb", None)
        surgery_date = patient.get("surgery_date", str(date.today()))
        scans_to_add = SURGERY_TO_SCAN.get(surgery_type, [("XRAY", "Knee")])

        for i, (scan_type, body_part) in enumerate(scans_to_add):
            # Assign pre-op date (before surgery) or post-op follow-up
            if i == 0:
                scan_date = str(date.fromisoformat(surgery_date) - timedelta(days=random.randint(3, 21)))
                label = "pre-operative"
            else:
                postop_day = patient.get("postop_day", 30)
                scan_date = str(date.fromisoformat(surgery_date) + timedelta(days=random.randint(7, max(8, postop_day))))
                label = "post-operative"

            # Assign a real image file if available for this body part
            file_path = None
            file_format = None
            if body_part == "Knee" and scan_type == "XRAY":
                img = next(knee_pool, None)
                if img and img.exists():
                    file_path   = str(img)
                    file_format = img.suffix.upper().lstrip(".")

            if file_path is None:
                # Placeholder path — image to be downloaded manually
                placeholder = SCANS_DIR / body_part.lower() / f"{pid}_{label.replace('-','_')}_{scan_type.lower()}.jpg"
                file_path   = str(placeholder)
                file_format = "JPEG"

            # KL grade only for OA-relevant X-rays
            kl_grade = None
            if body_part == "Knee" and scan_type == "XRAY" and "Arthroplasty" in surgery_type:
                kl_grade = random.randint(2, 4)  # pre-op OA warranting replacement

            findings = _findings_for(surgery_type, body_part, kl_grade)
            source = SOURCE_FALLBACK.get(body_part, "Public domain orthopedic dataset")

            if dry_run:
                print(f"  [DRY] {pid} | {scan_type} {body_part} ({label}) | KL={kl_grade} | {scan_date}")
                continue

            db.add_patient_scan(
                pid, scan_type, body_part, file_path,
                laterality=laterality,
                scan_date=scan_date,
                file_format=file_format,
                source_dataset=source,
                findings=findings,
                kl_grade=kl_grade,
            )
            seeded_count += 1

    if not dry_run:
        print(f"  [OK] Seeded {seeded_count} scan records across {len(patient_ids)} patients")


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Download ortho scan images and seed patient_scans table")
    parser.add_argument("--skip-download", action="store_true", help="Skip downloads, only seed DB from existing files")
    parser.add_argument("--dry-run",       action="store_true", help="Show what would be done without writing anything")
    args = parser.parse_args()

    SCANS_DIR.mkdir(exist_ok=True)
    for sub in SCAN_SUBDIRS:
        (SCANS_DIR / sub).mkdir(exist_ok=True)

    print("=" * 65)
    print("  Orthopedic Scan Image Downloader & DB Seeder")
    print("=" * 65)

    downloaded: dict[str, list[Path]] = {}

    if not args.skip_download:
        # --- Kaggle datasets ---
        print("\n[Kaggle Datasets]")
        for ds in KAGGLE_DATASETS:
            dest = SCANS_DIR / ds["subdir"]
            success = _try_kaggle_download(ds["slug"], dest, args.dry_run)
            if success or args.dry_run:
                downloaded[ds["subdir"]] = _collect_images(dest)
                print(f"  Found {len(downloaded[ds['subdir']])} images in {dest.name}/")

        # --- HuggingFace datasets ---
        print("\n[HuggingFace Datasets]")
        for ds in HF_DATASETS:
            dest = SCANS_DIR / ds["subdir"]
            success = _try_hf_download(ds["repo_id"], dest, args.dry_run)
            if success or args.dry_run:
                downloaded[ds["subdir"]] = _collect_images(dest)
                print(f"  Found {len(downloaded[ds['subdir']])} images in {dest.name}/")
    else:
        print("\n[Skipping download — using existing files in backend/scans/]")
        for sub in SCAN_SUBDIRS:
            imgs = _collect_images(SCANS_DIR / sub)
            if imgs:
                downloaded[sub] = imgs
                print(f"  {sub}/: {len(imgs)} existing images")

    # --- Seed patient_scans table ---
    print("\n[Seeding patient_scans table]")
    seed_scans_to_db(downloaded, dry_run=args.dry_run)

    # Summary
    total_imgs = sum(len(v) for v in downloaded.values())
    print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}Done!")
    print(f"  Scan images available: {total_imgs}")
    print(f"  Scans directory:       {SCANS_DIR}")
    print(f"  DB:                    {db.database_path()}")

    if total_imgs == 0 and not args.dry_run:
        print()
        print("  NOTE: No images were downloaded (Kaggle credentials missing?).")
        print("  Scan records with placeholder paths have still been seeded to the DB.")
        print("  To get real images, set up Kaggle credentials and re-run:")
        print("    python backend/download_scan_images.py")
        print()
        print("  Kaggle setup:")
        print("    1. Go to https://www.kaggle.com/settings -> API -> Create New Token")
        print("    2. Save kaggle.json to C:\\Users\\<you>\\.kaggle\\kaggle.json")
        print("    3. Re-run this script")


if __name__ == "__main__":
    main()
