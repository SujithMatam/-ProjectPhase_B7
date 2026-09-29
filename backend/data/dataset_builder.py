"""
Dataset Management Database & Synthetic Generator for Orthopedic Multi-Agent Chatbot.

Provides:
1. SQLite relational database storage for all training, validation, and benchmark datasets.
2. Synthetic generation engine covering:
   - Clinical Safety Triage (RED, YELLOW, GREEN)
   - Multi-Agent Intent Routing (PAIN, REHAB, MEDS, WOUND, RECOVERY, etc.)
   - Qwen/ChatML instruction-tuning dialogues (ShareGPT format for QLoRA training)
3. Export utilities to train/test JSONL splits ready for Unsloth / Hugging Face / SetFit.
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATABASE_FILE = Path(__file__).resolve().parent / "datasets.sqlite3"
EXPORT_DIR = Path(__file__).resolve().parent / "exports"


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class TriageIntentRecord:
    case_id: str
    patient_id: str
    surgery_type: str
    affected_limb: str
    postop_day: int
    user_message: str
    expected_triage: str          # RED, YELLOW, GREEN
    expected_intent: str          # PAIN_SYMPTOMS, MEDICATION, etc.
    escalation_required: bool
    temperature_c: Optional[float]
    clinical_rationale: str
    split: str                    # train, val, test
    created_at: str = ""


@dataclass
class ChatDialogueRecord:
    conversation_id: str
    case_id: str
    system_prompt: str
    user_prompt: str
    assistant_response: str
    expected_agent: str           # ChatAgent, WoundCareAgent, PainAgent, etc.
    split: str                    # train, val, test
    created_at: str = ""


# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatasetDatabase:
    """Manages SQLite tables storing all synthetic and benchmark datasets."""

    def __init__(self, db_path: Path = DATABASE_FILE):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Table 1: Triage & Multi-Agent Routing Dataset
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS triage_intent_cases (
                    case_id TEXT PRIMARY KEY,
                    patient_id TEXT,
                    surgery_type TEXT,
                    affected_limb TEXT,
                    postop_day INTEGER,
                    user_message TEXT,
                    expected_triage TEXT,
                    expected_intent TEXT,
                    escalation_required INTEGER,
                    temperature_c REAL,
                    clinical_rationale TEXT,
                    split TEXT,
                    created_at TEXT
                )
            """)

            # Table 2: Qwen SFT Generative Chatbot Dialogues
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chatbot_sft_dialogues (
                    conversation_id TEXT PRIMARY KEY,
                    case_id TEXT,
                    system_prompt TEXT,
                    user_prompt TEXT,
                    assistant_response TEXT,
                    expected_agent TEXT,
                    split TEXT,
                    created_at TEXT,
                    FOREIGN KEY(case_id) REFERENCES triage_intent_cases(case_id)
                )
            """)

            # Indexes for quick retrieval by split and intent
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_triage_split ON triage_intent_cases(split)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_triage_intent ON triage_intent_cases(expected_intent)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sft_split ON chatbot_sft_dialogues(split)")
            conn.commit()

    def insert_triage_cases(self, cases: List[TriageIntentRecord]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for c in cases:
                cursor.execute("""
                    INSERT OR REPLACE INTO triage_intent_cases 
                    (case_id, patient_id, surgery_type, affected_limb, postop_day, 
                     user_message, expected_triage, expected_intent, escalation_required, 
                     temperature_c, clinical_rationale, split, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c.case_id, c.patient_id, c.surgery_type, c.affected_limb, c.postop_day,
                    c.user_message, c.expected_triage, c.expected_intent, 1 if c.escalation_required else 0,
                    c.temperature_c, c.clinical_rationale, c.split, c.created_at or datetime.utcnow().isoformat()
                ))
            conn.commit()

    def insert_sft_dialogues(self, dialogues: List[ChatDialogueRecord]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for d in dialogues:
                cursor.execute("""
                    INSERT OR REPLACE INTO chatbot_sft_dialogues
                    (conversation_id, case_id, system_prompt, user_prompt, assistant_response, expected_agent, split, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    d.conversation_id, d.case_id, d.system_prompt, d.user_prompt,
                    d.assistant_response, d.expected_agent, d.split, d.created_at or datetime.utcnow().isoformat()
                ))
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM triage_intent_cases")
            total_triage = cursor.fetchone()[0]

            cursor.execute("SELECT split, COUNT(*) FROM triage_intent_cases GROUP BY split")
            triage_splits = dict(cursor.fetchall())

            cursor.execute("SELECT expected_triage, COUNT(*) FROM triage_intent_cases GROUP BY expected_triage")
            triage_levels = dict(cursor.fetchall())

            cursor.execute("SELECT COUNT(*) FROM chatbot_sft_dialogues")
            total_sft = cursor.fetchone()[0]

            cursor.execute("SELECT split, COUNT(*) FROM chatbot_sft_dialogues GROUP BY split")
            sft_splits = dict(cursor.fetchall())

            return {
                "triage_cases_count": total_triage,
                "triage_splits": triage_splits,
                "triage_levels": triage_levels,
                "sft_dialogues_count": total_sft,
                "sft_splits": sft_splits,
            }

    def export_qwen_jsonl(self, output_dir: Path = EXPORT_DIR):
        """Exports data into ShareGPT/Qwen ChatML JSONL format ready for QLoRA fine-tuning."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for split in ["train", "val", "test"]:
                cursor.execute("SELECT * FROM chatbot_sft_dialogues WHERE split = ?", (split,))
                rows = cursor.fetchall()
                if not rows:
                    continue

                split_file = output_dir / f"qwen_sft_{split}.jsonl"
                with open(split_file, "w", encoding="utf-8") as f:
                    for row in rows:
                        item = {
                            "id": row["conversation_id"],
                            "conversations": [
                                {"from": "system", "value": row["system_prompt"]},
                                {"from": "user", "value": row["user_prompt"]},
                                {"from": "assistant", "value": row["assistant_response"]},
                            ],
                            "metadata": {
                                "case_id": row["case_id"],
                                "expected_agent": row["expected_agent"]
                            }
                        }
                        f.write(json.dumps(item) + "\n")

            # Also export Triage/Intent test benchmark
            for split in ["train", "test"]:
                cursor.execute("SELECT * FROM triage_intent_cases WHERE split = ?", (split,))
                rows = cursor.fetchall()
                triage_file = output_dir / f"triage_intent_{split}.jsonl"
                with open(triage_file, "w", encoding="utf-8") as f:
                    for r in rows:
                        f.write(json.dumps(dict(r)) + "\n")


# ============================================================================
# SYNTHETIC DATASET GENERATOR
# ============================================================================

class SyntheticDatasetGenerator:
    """Generates clinically accurate synthetic queries and agent responses."""

    SURGERIES = [
        ("Total Knee Arthroplasty", "TKA"),
        ("Total Hip Arthroplasty", "THA"),
        ("Anterior Cruciate Ligament Reconstruction", "ACLR"),
        ("Rotator Cuff Repair", "RCR")
    ]
    LIMBS = ["Right", "Left"]

    # Clinical scenarios across AAOS/NHS recovery protocols
    SCENARIOS = [
        # --- RED ALERTS (Critical Emergencies) ---
        {
            "domain": "DVT",
            "triage": "RED",
            "intent": "PAIN_SYMPTOMS",
            "escalate": True,
            "agent": "EmergencyAgent",
            "templates": [
                "My {limb} calf is noticeably swollen, throbbing and very warm to touch.",
                "I have a deep ache in my {limb} calf and the back of my lower leg is hard and red.",
                "My {limb} calf hurts terribly whenever I stand and it won't go down with elevation."
            ],
            "response": "⚠️ **CRITICAL EMERGENCY ALERT**: Your symptoms indicate possible Deep Vein Thrombosis (DVT). Stop all activity, do not massage or put pressure on your calf, keep your leg supported, and immediately contact your hospital emergency line or attend the nearest Emergency Department.",
            "rationale": "Unilateral calf pain, localized warmth, and persistent induration are classic indicators of DVT."
        },
        {
            "domain": "Pulmonary Embolism",
            "triage": "RED",
            "intent": "PAIN_SYMPTOMS",
            "escalate": True,
            "agent": "EmergencyAgent",
            "templates": [
                "I am suddenly having severe shortness of breath and a sharp pain in my chest when inhaling.",
                "Feeling very faint and can't catch my breath at all today.",
                "I just coughed up a small amount of blood and my heart is racing."
            ],
            "response": "⚠️ **CRITICAL EMERGENCY ALERT**: Sudden shortness of breath, chest pain, and hemoptysis indicate a suspected Pulmonary Embolism (PE), a life-threatening medical emergency. Dial 911 / 999 or go immediately to the nearest Emergency Department.",
            "rationale": "Acute dyspnea and chest pain following orthopedic surgery are high-risk indicators of Pulmonary Embolism."
        },
        {
            "domain": "Neurovascular Impairment",
            "triage": "RED",
            "intent": "PAIN_SYMPTOMS",
            "escalate": True,
            "agent": "EmergencyAgent",
            "templates": [
                "My {limb} toes have turned pale and cold, and I can't move them at all.",
                "Total numbness in my entire {limb} foot and I cannot feel any sensation.",
                "My foot feels completely dead and freezing, with severe pins and needles."
            ],
            "response": "⚠️ **CRITICAL EMERGENCY ALERT**: Loss of sensation, cold/pale extremities, or inability to move your toes indicate acute neurovascular compromise or compartment syndrome. Seek immediate emergency medical care.",
            "rationale": "Acute sensory and motor loss with circulatory deficits requires emergent orthopedic evaluation."
        },
        {
            "domain": "Severe Joint Sepsis",
            "triage": "RED",
            "intent": "WOUND_CARE",
            "escalate": True,
            "agent": "EmergencyAgent",
            "templates": [
                "Thick yellow and foul-smelling pus is gushing out from my incision.",
                "My wound has gaped open and there is heavy green drainage with shaking chills.",
                "The redness around the surgical cut has spread 4 inches with burning pain and fever."
            ],
            "response": "⚠️ **CRITICAL EMERGENCY ALERT**: Foul-smelling purulent discharge, wound dehiscence, or rapidly spreading erythema are severe signs of acute Surgical Site Infection (SSI) or joint sepsis. Please contact the on-call surgical team or visit emergency immediately.",
            "rationale": "Purulent foul discharge with systemic fever/chills indicates deep surgical site infection."
        },

        # --- YELLOW CASES (Moderate Attention / Nurse Review) ---
        {
            "domain": "Persistent Wound Drainage",
            "triage": "YELLOW",
            "intent": "WOUND_CARE",
            "escalate": False,
            "agent": "WoundCareAgent",
            "templates": [
                "I noticed some clear pinkish fluid leaking through my dressing today.",
                "My bandage is damp with pale watery discharge. Is this expected on day {day}?",
                "There is a small amount of serosanguinous fluid staining the gauze pad."
            ],
            "response": "Serosanguinous (clear to pale pink) drainage can be expected in the first 3 to 5 days post-surgery. Keep the dressing clean and dry, avoid peeling the edges, and monitor for changes in color, odor, or expansion. If fluid continues to soak through past Day 5 or turns cloudy/yellow, notify your surgical team.",
            "rationale": "Minor serosanguinous exudate is common early post-op but requires hygiene precautions and monitoring."
        },
        {
            "domain": "Low-Grade Temperature",
            "triage": "YELLOW",
            "intent": "PAIN_SYMPTOMS",
            "escalate": False,
            "agent": "PainSymptomsAgent",
            "templates": [
                "I checked my temperature and it is 37.9°C (100.2°F). Should I be worried?",
                "Feeling a little flushed and feverish this evening, thermometer says 38.0°C.",
                "Is a low fever normal a few days after joint replacement?"
            ],
            "response": "A low-grade temperature (under 38.3°C / 101°F) is a known physiological response to tissue inflammation and surgical stress in the first 48–72 hours. Stay well hydrated, practice deep breathing exercises, and retake your temperature in 2 hours. If it rises above 38.3°C or is accompanied by chills or wound redness, contact your team.",
            "rationale": "Transient post-operative pyrexia without systemic symptoms is usually inflammatory atelectasis or post-op response."
        },

        # --- GREEN CASES (Routine Recovery / Guidance) ---
        {
            "domain": "Medication Timing & Safety",
            "triage": "GREEN",
            "intent": "MEDICATION",
            "escalate": False,
            "agent": "MedicationAgent",
            "templates": [
                "When should I take my pain medicine before starting my physical therapy exercises?",
                "Can I take paracetamol and ibuprofen together for my knee pain?",
                "I forgot my blood thinner dose 2 hours ago. Should I take it now?"
            ],
            "response": "For physical therapy, taking prescribed breakthrough analgesia roughly 30 to 45 minutes prior allows optimal pain relief during exercises. For missed blood thinners, take the missed dose as soon as remembered unless it is nearly time for your next scheduled dose—never take a double dose. Always consult your discharge medication sheet for specific anticoagulation guidelines.",
            "rationale": "Medication timing guidance and adhering strictly to prescribed anticoagulation/multimodal analgesia."
        },
        {
            "domain": "Physical Therapy & Milestones",
            "triage": "GREEN",
            "intent": "REHABILITATION",
            "escalate": False,
            "agent": "RehabilitationAgent",
            "templates": [
                "How many degrees should I be able to bend my {limb} knee by the end of week 1?",
                "My physical therapist gave me heel slide exercises. How often should I perform them?",
                "Is it okay to put all my weight on my operated leg when using crutches?"
            ],
            "response": "For Total Knee Arthroplasty, target milestones by Post-Op Day 7 are approximately 70°–90° of flexion and near-full extension (0°–5°). Perform your prescribed heel slides and quad sets in short, controlled sets 2 to 3 times daily. Do not place pillows directly under the knee joint, as keeping the leg straight is vital for terminal extension.",
            "rationale": "Standard AAOS rehabilitation milestones and joint extension protocols."
        },
        {
            "domain": "Hip Dislocation Precautions",
            "triage": "GREEN",
            "intent": "REHABILITATION",
            "escalate": False,
            "agent": "RehabilitationAgent",
            "templates": [
                "Can I bend forward to pick up my dropped phone after my hip replacement?",
                "What is the correct way to sleep so I don't dislocate my new hip?",
                "Can I cross my ankles while sitting down on the couch?"
            ],
            "response": "To protect your new hip and prevent dislocation during the first 6 weeks: 1) Do not bend your hip past 90 degrees (use a reacher tool for dropped items). 2) Do not cross your legs or ankles. 3) Avoid pointing your toes inward. Sleep on your back or on the non-operated side with a pillow between your knees to maintain abduction.",
            "rationale": "Posterior approach total hip arthroplasty dislocation precautions."
        },
        {
            "domain": "Normal Edema & Elevation",
            "triage": "GREEN",
            "intent": "RECOVERY_PROGRESS",
            "escalate": False,
            "agent": "RecoveryProgressAgent",
            "templates": [
                "My ankle and foot get swollen towards the afternoon, is this normal?",
                "How long should I keep ice packs on my knee during the day?",
                "What is the best way to elevate my operated leg to reduce swelling?"
            ],
            "response": "Mild to moderate edema of the operative leg and ankle is very normal for up to 3 months post-op due to gravity. Elevate your leg so your foot is propped above the level of your heart using pillows under the calf and ankle. Apply cold therapy for 20 minutes at a time with a protective cloth barrier, allowing at least 40 minutes between icing sessions.",
            "rationale": "Orthopedic recovery education on normal edema vs pathological swelling and RICE protocol."
        },
        {
            "domain": "Daily Activities & Showering",
            "triage": "GREEN",
            "intent": "DAILY_ACTIVITY",
            "escalate": False,
            "agent": "DailyActivityAgent",
            "templates": [
                "When is it safe for me to take a regular shower after surgery?",
                "Can I sleep on my stomach or side tonight?",
                "When am I allowed to drive my car again?"
            ],
            "response": "Most waterproof surgical dressings allow brief showers after 48 to 72 hours, but you must avoid soaking in a bathtub, pool, or hot tub until your surgeon verifies complete wound closure. Pat the dressing dry gently after showering. Driving is strictly prohibited while taking narcotic pain medications and typically requires 4–6 weeks until emergency braking reflexes return.",
            "rationale": "Activities of daily living, incision water safety, and driving restrictions post-arthroplasty."
        },

        # --- EXPANDED RED CASES (Emergency Complications) ---
        {
            "domain": "Severe Anticoagulation Bleeding",
            "triage": "RED",
            "intent": "MEDICATION",
            "escalate": True,
            "agent": "EmergencyAgent",
            "templates": [
                "I noticed black tarry stools and vomit that looks like coffee grounds.",
                "I have bleeding from my gums that won't stop and sudden large unexplained bruises all over.",
                "There is bright red blood in my urine and I feel lightheaded."
            ],
            "response": "⚠️ **CRITICAL EMERGENCY ALERT**: Black tarry stools, coffee-ground emesis, active unprovoked bleeding, or gross hematuria indicate acute internal hemorrhaging, a critical complication of blood thinners (anticoagulation). Immediately contact emergency services or go to the nearest Emergency Department.",
            "rationale": "Acute gastrointestinal or systemic bleeding associated with post-operative thromboprophylaxis."
        },
        {
            "domain": "Compartment Syndrome / Severe Acute Pain",
            "triage": "RED",
            "intent": "PAIN_SYMPTOMS",
            "escalate": True,
            "agent": "EmergencyAgent",
            "templates": [
                "The pain in my {limb} lower leg is unbearable, tight as a drum, and painkillers do not touch it at all.",
                "Extreme unrelenting pain in my operated leg with severe shin tightness that is rapidly worsening.",
                "My shin feels rock hard and burning with pain that feels out of proportion to the surgery."
            ],
            "response": "⚠️ **CRITICAL EMERGENCY ALERT**: Severe, unrelenting pain that is out of proportion and unresponsive to opioids, especially combined with tense, firm compartment swelling, indicates suspected Acute Compartment Syndrome. This requires emergent surgical decompression. Seek emergency medical attention immediately.",
            "rationale": "Tense swelling and refractory pain are cardinal signs of acute compartment syndrome."
        },
        {
            "domain": "Suspected Hip Dislocation",
            "triage": "RED",
            "intent": "PAIN_SYMPTOMS",
            "escalate": True,
            "agent": "EmergencyAgent",
            "templates": [
                "I felt a loud pop in my {limb} hip, my leg looks shorter, and I cannot bear any weight at all.",
                "Sudden violent popping sensation in my replaced hip and my foot is twisted inward painfully.",
                "Heard a click and sudden inability to move my operated hip with excruciating pain."
            ],
            "response": "⚠️ **CRITICAL EMERGENCY ALERT**: A sudden popping sensation accompanied by limb shortening, abnormal rotation, and inability to bear weight is highly indicative of acute prosthetic hip dislocation. Do not attempt to walk or manipulate the leg. Keep the limb still and call an ambulance immediately.",
            "rationale": "Audible pop with limb deformity and acute functional loss indicates prosthetic dislocation."
        },

        # --- EXPANDED YELLOW CASES (Subacute Follow-ups) ---
        {
            "domain": "Opioid-Induced Constipation & Nausea",
            "triage": "YELLOW",
            "intent": "MEDICATION",
            "escalate": False,
            "agent": "MedicationAgent",
            "templates": [
                "I have not had a bowel movement in 4 days since starting my pain pills and feel very bloated.",
                "The pain medication is making me extremely nauseous and constipated.",
                "Is it normal to go several days without passing stool after joint surgery?"
            ],
            "response": "Post-operative constipation is a very common side effect of prescription opioid analgesics, anesthesia, and reduced mobility. Ensure generous fluid intake, increase dietary fiber, and take prescribed stool softeners (like docusate or senna). If nausea is severe or if you experience abdominal cramping and vomiting, notify your care team so an antiemetic or alternative analgesic can be prescribed.",
            "rationale": "Opioid-induced bowel dysfunction requires proactive bowel regimens and multimodal review."
        },
        {
            "domain": "Incision Staples / Suture Irritation",
            "triage": "YELLOW",
            "intent": "WOUND_CARE",
            "escalate": False,
            "agent": "WoundCareAgent",
            "templates": [
                "A couple of my staples are pulling tight and feel itchy and irritated.",
                "When will my surgical clips or stitches be removed by the clinic?",
                "One corner of the incision looks slightly puckered but there is no pus."
            ],
            "response": "Mild itching and a pulling sensation around surgical staples or sutures are common as the wound edges contract and heal. Do not scratch or pick at the clips. Staples are typically removed in the clinic between Post-Op Days 10 and 14 once epithelialization is verified. Keep the incision clean, dry, and notify the clinic if you observe expanding redness or fluid leakage.",
            "rationale": "Routine staple care, suture line maturation, and scheduled removal timeline."
        },
        {
            "domain": "Joint Clicking & Internal Sensations",
            "triage": "YELLOW",
            "intent": "RECOVERY_PROGRESS",
            "escalate": False,
            "agent": "RecoveryProgressAgent",
            "templates": [
                "I hear a clicking or tapping noise inside my new knee when I bend it.",
                "My artificial joint makes a knocking sound when I walk. Is my implant loose?",
                "Feels like metal hitting plastic when I straighten my leg out."
            ],
            "response": "Clicking or clicking sounds in a prosthetic knee or hip are very common and benign in the first year. It occurs as the metal and high-density polyethylene components glide against each other, particularly as post-operative swelling resolves. As long as the clicking is painless and the joint remains stable without giving way, it is completely normal.",
            "rationale": "Benign prosthetic joint acoustics vs mechanical failure or loosening."
        },

        # --- EXPANDED GREEN CASES (Nutrition, Mental Health, Recovery Milestones) ---
        {
            "domain": "Post-Op Wound Healing Nutrition",
            "triage": "GREEN",
            "intent": "NUTRITION",
            "escalate": False,
            "agent": "NutritionAgent",
            "templates": [
                "What foods should I eat to help my bone and surgical incision heal faster?",
                "Should I take protein shakes or vitamin C supplements during my joint recovery?",
                "How much water should I drink each day to prevent blood clots?"
            ],
            "response": "Adequate post-operative nutrition accelerates tissue repair and immune function. Prioritize lean protein (chicken, fish, eggs, legumes, or whey protein) with a target of 1.2–1.5 grams per kilogram daily, alongside vitamin C, zinc, and calcium for collagen synthesis. Drink at least 2 to 2.5 liters of water daily to maintain circulatory volume and aid in DVT prevention.",
            "rationale": "Evidence-based clinical nutrition for collagen synthesis, immune competence, and hydration."
        },
        {
            "domain": "Post-Op Sleep & Emotional Wellbeing",
            "triage": "GREEN",
            "intent": "MENTAL_WELLBEING",
            "escalate": False,
            "agent": "MentalWellbeingAgent",
            "templates": [
                "I feel really frustrated and tearful because my recovery feels slower than expected.",
                "Having trouble sleeping through the night because of restlessness and joint discomfort.",
                "Is it normal to feel down and anxious in the first few weeks after major surgery?"
            ],
            "response": "Post-operative emotional fatigue, sleep disruption, and mood fluctuations ('post-op blues') are very common due to anesthesia recovery, sleep architecture disruption, and temporary loss of independence. Recovery is a non-linear journey. Establish a calming bedtime routine, practice daytime elevation and breathing relaxation, and celebrate daily functional milestones. Share your feelings with loved ones and your surgical team.",
            "rationale": "Psychological recovery, sleep hygiene education, and validation of post-surgical emotional adjustments."
        },
        {
            "domain": "Weight Bearing & Walking Aids",
            "triage": "GREEN",
            "intent": "REHABILITATION",
            "escalate": False,
            "agent": "RehabilitationAgent",
            "templates": [
                "When can I transition from a walker to a single cane or crutch?",
                "How do I use a walking stick on the stairs after knee surgery?",
                "My discharge says WBAT (Weight Bearing As Tolerated). What does that actually mean?"
            ],
            "response": "'Weight Bearing As Tolerated' (WBAT) means you may place as much body weight on your operated leg as comfort allows, using crutches or a walker primarily for stability and balance. Transitioning to a single cane occurs when you can walk without an antalgic limp and maintain good quadriceps control. When navigating stairs, remember: 'Up with the good leg, down with the operated leg.'",
            "rationale": "Assistive device progression, WBAT clinical definition, and stair ambulation safety rule."
        },
        {
            "domain": "Long-Term Extension & Knee Stiffness",
            "triage": "GREEN",
            "intent": "RECOVERY_PROGRESS",
            "escalate": False,
            "agent": "RecoveryProgressAgent",
            "templates": [
                "My knee feels tight like a rubber band wrapped around it when I get up.",
                "How long does the morning stiffness usually last after knee replacement?",
                "Is knee tightness normal on Post-Op Day {day}?"
            ],
            "response": "A sensation of an internal 'tight band' around the knee is one of the most frequent normal recovery sensations, often persisting for 6 to 12 months. It is caused by internal scar tissue remodeling and localized soft-tissue healing. Gentle warm-up stretches, regular heel slides, and short walks throughout the day will gradually loosen the stiffness.",
            "rationale": "Internal scar tissue remodeling, arthrofibrosis prevention, and subjective tight-band reassurance."
        },
    ]

    @classmethod
    def generate_dataset(cls, target_total: int = 120, seed: int = 42) -> Tuple[List[TriageIntentRecord], List[ChatDialogueRecord]]:
        random.seed(seed)
        triage_records: List[TriageIntentRecord] = []
        dialogue_records: List[ChatDialogueRecord] = []

        system_prompt = (
            "You are an AI Clinical Assistant specializing in orthopedic post-operative recovery (AAOS/NHS guidelines). "
            "Provide empathetic, clinically sound, evidence-based guidance. "
            "Never offer unapproved prescriptions, never dismiss red-flag symptoms, and escalate medical emergencies immediately."
        )

        case_idx = 1
        splits_pool = ["train"] * 70 + ["val"] * 15 + ["test"] * 15

        while len(triage_records) < target_total:
            for sc in cls.SCENARIOS:
                surgery_name, surgery_code = random.choice(cls.SURGERIES)
                limb = random.choice(cls.LIMBS)
                postop_day = random.randint(1, 28)
                patient_num = random.randint(100, 999)
                patient_id = f"PT-{patient_num}"

                template = random.choice(sc["templates"])
                user_msg = template.format(limb=limb, day=postop_day, surgery=surgery_name)

                # Assign split deterministically
                split = splits_pool[case_idx % len(splits_pool)]

                temp_c = None
                if sc["triage"] == "RED" and "Sepsis" in sc["domain"]:
                    temp_c = round(random.uniform(38.5, 39.4), 1)
                elif sc["triage"] == "YELLOW" and "Fever" in sc["domain"]:
                    temp_c = round(random.uniform(37.8, 38.2), 1)
                else:
                    temp_c = round(random.uniform(36.5, 37.2), 1)

                case_id = f"CASE_{case_idx:04d}"
                conv_id = f"QWEN_CHAT_{case_idx:04d}"

                t_rec = TriageIntentRecord(
                    case_id=case_id,
                    patient_id=patient_id,
                    surgery_type=surgery_name,
                    affected_limb=limb,
                    postop_day=postop_day,
                    user_message=user_msg,
                    expected_triage=sc["triage"],
                    expected_intent=sc["intent"],
                    escalation_required=sc["escalate"],
                    temperature_c=temp_c,
                    clinical_rationale=sc["rationale"],
                    split=split,
                    created_at=datetime.utcnow().isoformat()
                )
                triage_records.append(t_rec)

                # Context-infused prompt for Qwen SFT
                user_prompt = (
                    f"Patient Context: {patient_id} | Post-Op Day {postop_day} | {surgery_name} ({limb} limb)\n"
                    f"Message: {user_msg}"
                )

                d_rec = ChatDialogueRecord(
                    conversation_id=conv_id,
                    case_id=case_id,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    assistant_response=sc["response"],
                    expected_agent=sc["agent"],
                    split=split,
                    created_at=datetime.utcnow().isoformat()
                )
                dialogue_records.append(d_rec)

                case_idx += 1
                if len(triage_records) >= target_total:
                    break

        return triage_records, dialogue_records


# ============================================================================
# CLI GENERATOR & INITIALIZER
# ============================================================================

def populate_database_and_export(total_records: int = 150):
    print("=" * 70)
    print("INITIALIZING DATASET DATABASE & GENERATING SYNTHETIC DATASETS")
    print("=" * 70)

    db = DatasetDatabase()
    print(f"[*] SQLite Database ready at: {db.db_path}")

    generator = SyntheticDatasetGenerator()
    triage_records, dialogue_records = generator.generate_dataset(target_total=total_records)

    print(f"[*] Generated {len(triage_records)} clinical triage/routing cases.")
    print(f"[*] Generated {len(dialogue_records)} Qwen instruction dialogue pairs.")

    db.insert_triage_cases(triage_records)
    db.insert_sft_dialogues(dialogue_records)

    stats = db.get_stats()
    print("\nDatabase Statistics:")
    print(json.dumps(stats, indent=2))

    print("\n[*] Exporting JSONL dataset files for training and testing...")
    db.export_qwen_jsonl()

    print(f"[OK] Completed! Exported files saved in: {EXPORT_DIR}")
    for item in EXPORT_DIR.glob("*.jsonl"):
        print(f"    - {item.name} ({item.stat().st_size} bytes)")


if __name__ == "__main__":
    populate_database_and_export(600)
