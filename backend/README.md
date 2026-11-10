# OrthoSync Agentic AI Backend

FastAPI service powering the multi-agent clinical recovery engine for orthopedic post-operative patients.

## Features
- **Deterministic Safety Triage**: Rule-based RED/YELLOW/GREEN escalation for critical postoperative red flags and self-harm/crisis disclosures.
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
