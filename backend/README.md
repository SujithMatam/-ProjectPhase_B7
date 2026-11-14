# OrthoSync Agentic AI Backend

FastAPI service powering the multi-agent clinical recovery engine for orthopedic post-operative patients.

## Features
- **Safety Triage**: RED/YELLOW/GREEN escalation for critical postoperative red flags and self-harm/crisis disclosures, before any LLM runs (hybrid model + deterministic checks by default; see [Triage](#triage)).
- **RAG Knowledge Base**: Domain-specific recovery guidelines for Total Knee Arthroplasty (TKA) and Total Hip Arthroplasty (THA).
- **Symptom Assessment Agent**: Generates structured, clinically validated recommendations.
- **Nutrition and Mental Wellbeing Agents**: Provide deterministic, general recovery guidance, ask for relevant patient context, avoid diagnosis or individualized prescriptions, and escalate concerning symptoms to appropriate human support.
- **REST Endpoints & Swagger UI**: Available at `http://127.0.0.1:8000/docs`.

## Setup & Running Locally
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Triage

Every patient message is triaged RED / YELLOW / GREEN before any agent or LLM answers. No LLM
decides the level. The engine is chosen by the `TRIAGE_MODE` environment variable, read on
every call.

**Hybrid (the default: `TRIAGE_MODE` unset).** Three checks run on the message and the most
serious level wins:

- **Model:** a small SetFit classifier (MiniLM sentence embeddings + logistic regression)
  trained on post-op messages. It is committed in
  `triage/model/artifacts/setfit/m2_main_v2_it3_seed0` (~88 MB), so a fresh clone needs no
  training and no download. The startup log shows
  `classifier loaded: M2:m2_main_v2_it3_seed0`.
- **Temperature check:** reads temperatures from the text or the request's `temperature_c`.
  38.5 °C or higher is RED; 37.8-38.4 °C is at least YELLOW.
- **Self-harm check:** a negation-aware match for thoughts of self-harm gives RED with crisis
  guidance.

A doctor email goes out for a RED from the temperature or self-harm check, or when the model is
confident (p(RED) >= `t_alert`). If the model folder is missing or fails to load, the server
prints one `WARNING` naming the folder and uses the M1 fallback model (frozen MiniLM + a
committed logistic-regression head; downloads all-MiniLM-L6-v2 on first use). Details,
thresholds and evaluation: `triage/REPORT.md`.

**Rules.** `TRIAGE_MODE=rules` runs only the original keyword engine
(`triage/safety_triage.py`), exactly as before hybrid became the default:

```bash
TRIAGE_MODE=rules python main.py          # bash
$env:TRIAGE_MODE="rules"; python main.py  # PowerShell
```

`TRIAGE_MODEL_VERSION=v1` keeps hybrid mode but uses the v1 model and thresholds. The v1 SetFit
weights are not committed, so on a fresh clone this prints the warning and runs v1's M1 model.

## Qwen SFT dataset

Before fine-tuning, filter the exported SFT train/validation/test splits. This
creates separate `*_filtered.jsonl` files and a deterministic
`qwen_sft_filter_report.json` audit manifest; the source exports and triage
intent datasets are not modified.

Run these commands from the repository root:

```bash
python backend/data/filter_qwen_sft_triage.py
python backend/data/test_filter_qwen_sft_triage.py
python backend/data/train_qwen_lora.py
```

## T1 triage seed audit

Build the versioned triage seed copies, leakage audit, clinician review queue,
and isolated scenario-held-out and wording-held-out partitions with:

```bash
python backend/data/t1/build_t1_dataset.py
python backend/data/t1/test_build_t1_dataset.py
```

These are review-pending dataset artifacts, not clinical validation or model
training. See `backend/data/t1/README.md` for source overlap metrics, provenance,
and the required clinical review workflow.

The Qwen trainer requires the filtered train and validation files and fails
with a setup error if they have not been generated.
