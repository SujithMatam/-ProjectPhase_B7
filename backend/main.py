"""
FastAPI Agentic AI Backend for Orthopedic Post-Op Recovery
Exposes endpoints for the Flutter mobile/web client.
"""

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from agents.symptom_agent import SymptomAssessmentAgent
from agents.chat_agent import ChatAgent
from agents.report_agent import ReportGenerationAgent
from lam.orchestrator import LAMOrchestrator
from lam.schemas import WeightBearingStatus
from triage.safety_triage import SafetyTriageEngine

app = FastAPI(
    title="OrthoSync Agentic AI Backend",
    description="Multi-agent orthopedic post-operative recovery monitoring service with deterministic safety triage.",
    version="1.0.0"
)

# Enable CORS for Flutter Web / Mobile
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SymptomAssessmentRequest(BaseModel):
    patient_id: str = Field(..., example="PT-B7-8921")
    surgery_type: str = Field(default="Total Knee Arthroplasty (TKA)", example="Total Knee Arthroplasty (TKA)")
    affected_limb: str = Field(default="Right", example="Right")
    postop_day: int = Field(default=3, example=3)
    symptoms: str = Field(..., example="I have sharp calf pain and swelling in my right leg since this morning")
    pain_score: int = Field(default=5, ge=0, le=10, example=6)
    temperature_c: Optional[float] = Field(default=None, example=37.2)


class ChatRequest(BaseModel):
    patient_id: str = Field(default="PT-B7-8921", example="PT-B7-8921")
    surgery_type: str = Field(default="Total Knee Arthroplasty (TKA)", example="Total Knee Arthroplasty (TKA)")
    affected_limb: str = Field(default="Right", example="Right")
    postop_day: int = Field(default=3, example=3)
    surgery_date: Optional[str] = Field(default=None, example="2026-08-15T00:00:00.000Z")
    message: str = Field(..., example="Is it normal for my knee to swell after walking?")
    chat_history: Optional[List[Dict[str, str]]] = Field(default=None)
    # Optional structured symptom fields (Milestone Sec 2.6 -- Symptom
    # Assessment). All additive/optional: omitting them reproduces prior
    # /api/chat behavior exactly. When supplied, temperature_c also feeds
    # the deterministic SafetyTriageEngine at Step 1 (see
    # lam/orchestrator.py), not just PainSymptomsAgent.
    pain_score: Optional[int] = Field(default=None, ge=0, le=10, example=6)
    pain_characteristics: Optional[str] = Field(default=None, example="throbbing, worse at night")
    swelling_description: Optional[str] = Field(default=None, example="mild swelling around the incision")
    temperature_c: Optional[float] = Field(default=None, example=37.2)
    # Optional structured rehabilitation fields (Milestone Sec 2.7 --
    # Rehabilitation & Exercise Agent). All additive/optional: omitting them
    # reproduces prior /api/chat behavior exactly. weight_bearing_status is
    # validated against the controlled NWB/PWB/WBAT/FWB vocabulary by
    # Pydantic -- an invalid value is rejected at the API boundary rather
    # than silently guessed.
    weight_bearing_status: Optional[WeightBearingStatus] = Field(default=None, example="WBAT")
    current_rom: Optional[str] = Field(default=None, example="Flexion to about 80 degrees")
    exercise_history: Optional[str] = Field(default=None, example="Completed heel slides and quad sets today; missed yesterday's session")


@app.get("/")
def read_root():
    return {
        "service": "OrthoSync Clinical AI Agent Service",
        "status": "online",
        "version": "1.0.0",
        "docs_url": "/docs"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "agents": [
            "SafetyTriageEngine",
            "SymptomAssessmentAgent",
            "ClinicalKnowledgeBase",
            "ChatAgent",
            "ReportGenerationAgent",
        ]
    }


@app.get("/api/reports/summary/{patient_id}")
def get_report_summary(patient_id: str, days: int = 7):
    """
    Synthesizes recovery metrics, pain trajectory, exercise milestones,
    medication adherence, and safety triage alerts into a structured JSON summary.
    """
    try:
        summary = ReportGenerationAgent.generate_patient_summary(patient_id=patient_id, days=days)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/pdf/{patient_id}")
def get_pdf_report(patient_id: str, days: int = 7):
    """
    Exports a publication-quality orthopedic clinical report PDF (ReportLab)
    suitable for physician review and patient discharge records.
    """
    try:
        pdf_bytes = ReportGenerationAgent.export_pdf_report(patient_id=patient_id, days=days)
        filename = f"OrthoSync_Report_{patient_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename={filename}",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/assess-symptoms")
def assess_symptoms(payload: SymptomAssessmentRequest):
    try:
        result = SymptomAssessmentAgent.assess(
            patient_id=payload.patient_id,
            surgery_type=payload.surgery_type,
            affected_limb=payload.affected_limb,
            postop_day=payload.postop_day,
            symptoms=payload.symptoms,
            pain_score=payload.pain_score,
            temperature_c=payload.temperature_c
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
def chat(payload: ChatRequest):
    try:
        result = LAMOrchestrator.process(
            patient_id=payload.patient_id,
            surgery_type=payload.surgery_type,
            affected_limb=payload.affected_limb,
            postop_day=payload.postop_day,
            surgery_date=payload.surgery_date,
            user_message=payload.message,
            chat_history=payload.chat_history or [],
            pain_score=payload.pain_score,
            pain_characteristics=payload.pain_characteristics,
            swelling_description=payload.swelling_description,
            temperature_c=payload.temperature_c,
            weight_bearing_status=payload.weight_bearing_status,
            current_rom=payload.current_rom,
            exercise_history=payload.exercise_history,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
