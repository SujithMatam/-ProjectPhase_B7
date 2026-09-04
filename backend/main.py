"""
FastAPI Agentic AI Backend for Orthopedic Post-Op Recovery
Exposes endpoints for the Flutter mobile/web client.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from agents.symptom_agent import SymptomAssessmentAgent
from agents.chat_agent import ChatAgent
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
    message: str = Field(..., example="Is it normal for my knee to swell after walking?")

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
        "agents": ["SafetyTriageEngine", "SymptomAssessmentAgent", "ClinicalKnowledgeBase", "ChatAgent"]
    }

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
        result = ChatAgent.answer_question(
            patient_id=payload.patient_id,
            surgery_type=payload.surgery_type,
            affected_limb=payload.affected_limb,
            postop_day=payload.postop_day,
            user_message=payload.message
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
