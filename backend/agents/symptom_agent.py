"""
Symptom Assessment Agent
Orchestrates:
1. Deterministic Safety Triage (Hard clinical constraints)
2. RAG Guideline Retrieval
3. Clinical Reasoning & Structured Action Recommendations
"""

from typing import Dict, Any, List
from triage.safety_triage import SafetyTriageEngine
from rag.knowledge_base import ClinicalKnowledgeBase

class SymptomAssessmentAgent:
    @classmethod
    def assess(
        cls,
        patient_id: str,
        surgery_type: str,
        affected_limb: str,
        postop_day: int,
        symptoms: str,
        pain_score: int = 5,
        temperature_c: float = None
    ) -> Dict[str, Any]:
        # Step 1: Execute Deterministic Safety Triage
        triage_result = SafetyTriageEngine.evaluate(
            symptoms=symptoms,
            temperature_c=temperature_c,
            post_op_day=postop_day
        )

        # Step 2: Retrieve relevant clinical protocols via RAG
        procedure_code = "THA" if "hip" in surgery_type.lower() else "TKA"
        rag_guidelines = ClinicalKnowledgeBase.query(
            query_text=symptoms,
            procedure=procedure_code,
            limit=2
        )

        # Step 3: Synthesize Clinical Assessment
        triage_level = triage_result["triage_level"]
        
        if triage_level == "RED":
            clinical_summary = (
                f"CRITICAL CLINICAL ALERT for Patient {patient_id} (Post-Op Day {postop_day}, {surgery_type} {affected_limb}). "
                f"Symptom input indicates immediate red flags: {', '.join(triage_result['reasons'])}. "
                "Immediate medical escalation is mandatory."
            )
            recommendations = [
                "Immediately contact the orthopedic on-call registrar or visit the nearest emergency department.",
                "Do not attempt strenuous walking or deep massage on the affected limb.",
                "Keep limb rested and awaiting immediate physician evaluation."
            ]
        elif triage_level == "YELLOW":
            clinical_summary = (
                f"Moderate Risk Advisory for Patient {patient_id} (Post-Op Day {postop_day}, {surgery_type} {affected_limb}). "
                f"Identified potential complications: {', '.join(triage_result['reasons'])}. "
                "Requires clinical check-in within 12-24 hours."
            )
            recommendations = [
                "Notify your surgical coordinator or hospital hotline today.",
                "Take a well-lit photo of the incision/area if swelling or redness is increasing.",
                "Maintain limb elevation above heart level for 45 minutes; apply ice pack wrapped in towel.",
                "Monitor temperature every 4 hours."
            ]
        else:
            clinical_summary = (
                f"Routine Recovery Progress for Patient {patient_id} (Post-Op Day {postop_day}, {surgery_type} {affected_limb}). "
                f"Reported symptoms ('{symptoms}') and pain level ({pain_score}/10) are consistent with expected "
                f"healing trajectory for Day {postop_day}."
            )
            recommendations = [
                "Proceed with prescribed Day-specific physical therapy exercises.",
                "Continue cryotherapy (ice 20 mins, 3 times daily) after exercise sessions.",
                "Take prescribed analgesics 30-45 minutes before rehabilitation sessions if pain exceeds 4/10.",
                "Maintain hydration and log your daily walking distance."
            ]

        return {
            "patient_id": patient_id,
            "surgery_type": surgery_type,
            "affected_limb": affected_limb,
            "postop_day": postop_day,
            "triage": triage_result,
            "clinical_summary": clinical_summary,
            "recommendations": recommendations,
            "retrieved_protocols": [
                {"topic": doc["topic"], "summary": doc["content"][:160] + "..."}
                for doc in rag_guidelines
            ]
        }
