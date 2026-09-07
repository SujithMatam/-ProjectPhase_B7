# OrthoSync Agentic AI Backend

FastAPI service powering the multi-agent clinical recovery engine for orthopedic post-operative patients.

## Features
- **Deterministic Safety Triage**: Strict rule-based RED/YELLOW/GREEN filter preventing hallucinations on critical conditions (DVT, Pulmonary Embolism, Infection/Sepsis).
- **RAG Knowledge Base**: Domain-specific recovery guidelines for Total Knee Arthroplasty (TKA) and Total Hip Arthroplasty (THA).
- **Symptom Assessment Agent**: Generates structured, clinically validated recommendations.
- **REST Endpoints & Swagger UI**: Available at `http://127.0.0.1:8000/docs`.

## Setup & Running Locally
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
