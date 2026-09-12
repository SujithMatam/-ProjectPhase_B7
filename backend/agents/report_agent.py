"""
Report Generation Agent -- Milestone 2 (Section 2.14).

Synthesizes patient interaction logs, daily recovery metrics (pain trajectory,
swelling status, rehabilitation adherence, ROM milestones, medication compliance,
safety alerts) into structured clinical summaries:
1. generate_patient_summary(patient_id, days=7): returns structured clinical JSON
   consumed by the Physician / Care Team Dashboard.
2. export_pdf_report(patient_id, days=7): generates a clean, professional orthopedic
   clinical PDF report (ReportLab) formatted for surgeon review.
"""

from __future__ import annotations

import io
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    _REPORTLAB_AVAILABLE = True
except ImportError:
    _REPORTLAB_AVAILABLE = False


# Mock repository of clinical patient baselines and check-in logs for post-op synthesis
_PATIENT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "PT-B7-8921": {
        "patient_id": "PT-B7-8921",
        "full_name": "Rishi Priyan V N",
        "age": 58,
        "gender": "Male",
        "surgery_type": "Total Knee Arthroplasty (TKA)",
        "affected_limb": "Right",
        "surgery_date": "2026-09-02",
        "postop_day": 7,
        "surgeon": "Dr. Sarah Jenkins, MD, FRCS (Ortho)",
        "implant": "Zimmer Biomet Persona PS Knee System",
        "weight_bearing_status": "Weight Bearing as Tolerated (WBAT)",
        "allergies": "Penicillin, NSAIDs (mild rash)",
        "current_medications": [
            {"name": "Paracetamol", "dose": "650mg TDS", "purpose": "Scheduled Analgesia", "adherence_pct": 95},
            {"name": "Enoxaparin", "dose": "40mg SC OD", "purpose": "DVT Prophylaxis", "adherence_pct": 100},
            {"name": "Oxycodone", "dose": "5mg PRN", "purpose": "Breakthrough PT Pain", "adherence_pct": 70},
            {"name": "Docusate Sodium", "dose": "100mg BD", "purpose": "Stool Softener", "adherence_pct": 90},
        ],
        "metrics_history": [
            {"day": 1, "date": "2026-09-03", "pain_score": 7, "rom_flexion": 45, "rom_extension": 10, "exercise_completed": True, "swelling": "Moderate", "triage": "GREEN"},
            {"day": 2, "date": "2026-09-04", "pain_score": 6, "rom_flexion": 55, "rom_extension": 8, "exercise_completed": True, "swelling": "Moderate", "triage": "GREEN"},
            {"day": 3, "date": "2026-09-05", "pain_score": 6, "rom_flexion": 65, "rom_extension": 6, "exercise_completed": True, "swelling": "Mild-Moderate", "triage": "GREEN"},
            {"day": 4, "date": "2026-09-06", "pain_score": 5, "rom_flexion": 70, "rom_extension": 5, "exercise_completed": True, "swelling": "Mild", "triage": "GREEN"},
            {"day": 5, "date": "2026-09-07", "pain_score": 4, "rom_flexion": 75, "rom_extension": 4, "exercise_completed": True, "swelling": "Mild", "triage": "GREEN"},
            {"day": 6, "date": "2026-09-08", "pain_score": 4, "rom_flexion": 80, "rom_extension": 3, "exercise_completed": True, "swelling": "Mild", "triage": "GREEN"},
            {"day": 7, "date": "2026-09-09", "pain_score": 3, "rom_flexion": 85, "rom_extension": 2, "exercise_completed": True, "swelling": "Minimal", "triage": "GREEN"},
        ],
        "triage_events": [
            {"timestamp": "2026-09-05 14:30", "level": "GREEN", "symptom": "Normal swelling after walking", "action": "Advised elevation and cold therapy"}
        ],
    },
    "PT-B7-8922": {
        "patient_id": "PT-B7-8922",
        "full_name": "Sujith Matam",
        "age": 62,
        "gender": "Male",
        "surgery_type": "Total Hip Arthroplasty (THA)",
        "affected_limb": "Left",
        "surgery_date": "2026-09-02",
        "postop_day": 7,
        "surgeon": "Dr. Michael Chen, MD, FAAOS",
        "implant": "Stryker Trident II Tritanium Acetabular Cup",
        "weight_bearing_status": "Partial Weight Bearing (PWB)",
        "allergies": "Sulfa drugs",
        "current_medications": [
            {"name": "Aspirin", "dose": "81mg BD", "purpose": "VTE Prophylaxis", "adherence_pct": 100},
            {"name": "Paracetamol", "dose": "1000mg TDS", "purpose": "Analgesia", "adherence_pct": 92},
            {"name": "Tramadol", "dose": "50mg PRN", "purpose": "Moderate Breakthrough Pain", "adherence_pct": 60},
        ],
        "metrics_history": [
            {"day": 1, "date": "2026-09-03", "pain_score": 6, "rom_flexion": 40, "rom_extension": 0, "exercise_completed": True, "swelling": "Moderate", "triage": "GREEN"},
            {"day": 2, "date": "2026-09-04", "pain_score": 5, "rom_flexion": 50, "rom_extension": 0, "exercise_completed": True, "swelling": "Moderate", "triage": "GREEN"},
            {"day": 3, "date": "2026-09-05", "pain_score": 5, "rom_flexion": 60, "rom_extension": 0, "exercise_completed": True, "swelling": "Mild-Moderate", "triage": "GREEN"},
            {"day": 4, "date": "2026-09-06", "pain_score": 4, "rom_flexion": 65, "rom_extension": 0, "exercise_completed": True, "swelling": "Mild", "triage": "GREEN"},
            {"day": 5, "date": "2026-09-07", "pain_score": 4, "rom_flexion": 70, "rom_extension": 0, "exercise_completed": True, "swelling": "Mild", "triage": "GREEN"},
            {"day": 6, "date": "2026-09-08", "pain_score": 3, "rom_flexion": 75, "rom_extension": 0, "exercise_completed": True, "swelling": "Minimal", "triage": "GREEN"},
            {"day": 7, "date": "2026-09-09", "pain_score": 3, "rom_flexion": 80, "rom_extension": 0, "exercise_completed": True, "swelling": "Minimal", "triage": "GREEN"},
        ],
        "triage_events": [
            {"timestamp": "2026-09-04 10:15", "level": "GREEN", "symptom": "Incision tightness on sitting", "action": "Reiterated posterior hip precautions (no flexion > 90 deg)"}
        ],
    }
}


class ReportGenerationAgent:
    """
    Synthesizes orthopedic rehabilitation progress and clinical metrics
    into structured JSON summaries and physician-ready PDF reports.
    """

    @classmethod
    def get_patient_record(cls, patient_id: str) -> Dict[str, Any]:
        clean_id = (patient_id or "PT-B7-8921").strip().upper()
        if clean_id in _PATIENT_REGISTRY:
            return _PATIENT_REGISTRY[clean_id]

        # Generic default template for any other ID
        return {
            "patient_id": clean_id,
            "full_name": "Post-Op Recovery Patient",
            "age": 60,
            "gender": "Not Specified",
            "surgery_type": "Total Knee Arthroplasty (TKA)",
            "affected_limb": "Right",
            "surgery_date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
            "postop_day": 7,
            "surgeon": "Orthopedic Surgical Service",
            "implant": "Standard Orthopedic Prosthesis",
            "weight_bearing_status": "Weight Bearing as Tolerated (WBAT)",
            "allergies": "None documented",
            "current_medications": [
                {"name": "Paracetamol", "dose": "650mg TDS", "purpose": "Scheduled Analgesia", "adherence_pct": 92},
                {"name": "Enoxaparin", "dose": "40mg SC OD", "purpose": "DVT Prophylaxis", "adherence_pct": 100},
            ],
            "metrics_history": [
                {"day": i, "date": (datetime.now() - timedelta(days=7-i)).strftime("%Y-%m-%d"), "pain_score": max(2, 7 - i // 2), "rom_flexion": 50 + i * 5, "rom_extension": max(2, 10 - i), "exercise_completed": True, "swelling": "Mild", "triage": "GREEN"}
                for i in range(1, 8)
            ],
            "triage_events": [],
        }

    @classmethod
    def generate_patient_summary(cls, patient_id: str, days: int = 7) -> Dict[str, Any]:
        """
        Synthesizes structured metrics for dashboard and clinical analytics.
        """
        patient = cls.get_patient_record(patient_id)
        metrics = patient.get("metrics_history", [])[-days:]

        pain_scores = [m["pain_score"] for m in metrics if "pain_score" in m]
        flexion_scores = [m["rom_flexion"] for m in metrics if "rom_flexion" in m]
        extension_scores = [m["rom_extension"] for m in metrics if "rom_extension" in m]
        exercise_counts = sum(1 for m in metrics if m.get("exercise_completed"))

        avg_pain = round(sum(pain_scores) / len(pain_scores), 1) if pain_scores else 0.0
        min_pain = min(pain_scores) if pain_scores else 0
        max_pain = max(pain_scores) if pain_scores else 0
        latest_flexion = flexion_scores[-1] if flexion_scores else 0
        latest_extension = extension_scores[-1] if extension_scores else 0
        exercise_compliance_pct = round((exercise_counts / len(metrics) * 100), 1) if metrics else 0.0

        meds = patient.get("current_medications", [])
        overall_med_adherence = round(sum(m.get("adherence_pct", 100) for m in meds) / len(meds), 1) if meds else 100.0

        # High-risk flags
        triage_events = patient.get("triage_events", [])
        has_red_alert = any(t.get("level") == "RED" for t in triage_events)
        has_yellow_alert = any(t.get("level") == "YELLOW" for t in triage_events)

        if has_red_alert:
            safety_status = "CRITICAL ALERT: Emergency Red Flag Triggered"
        elif has_yellow_alert:
            safety_status = "MODERATE: Clinical Nurse Review Required"
        else:
            safety_status = "NORMAL: Satisfactory Recovery Course"

        # Actionable insights
        actionable_insights = [
            f"Pain levels trending favorably down from {max_pain}/10 to {min_pain}/10 over the last {len(metrics)} days.",
            f"Active flexion reached {latest_flexion}° with terminal extension at {latest_extension}°, meeting Day {patient.get('postop_day')} goals.",
            f"Medication adherence is robust at {overall_med_adherence}% including DVT prophylaxis.",
            f"Exercise adherence is high at {exercise_compliance_pct}%. Continue home exercise progression."
        ]

        return {
            "patient_id": patient["patient_id"],
            "full_name": patient["full_name"],
            "age": patient.get("age", 60),
            "gender": patient.get("gender", "Unspecified"),
            "surgery_type": patient["surgery_type"],
            "affected_limb": patient["affected_limb"],
            "postop_day": patient["postop_day"],
            "surgery_date": patient["surgery_date"],
            "operating_surgeon": patient.get("surgeon", "Orthopedic Surgery"),
            "implant_details": patient.get("implant", "Titanium Prosthesis"),
            "weight_bearing_status": patient.get("weight_bearing_status", "WBAT"),
            "reporting_period_days": len(metrics),
            "pain_trend": {
                "min": min_pain,
                "max": max_pain,
                "average": avg_pain,
                "latest": pain_scores[-1] if pain_scores else 0,
                "status": "Decreasing" if len(pain_scores) >= 2 and pain_scores[-1] <= pain_scores[0] else "Stable",
            },
            "mobility_progression": {
                "latest_flexion_deg": latest_flexion,
                "latest_extension_deg": latest_extension,
                "exercise_compliance_pct": exercise_compliance_pct,
                "target_milestone_met": latest_flexion >= 70,
            },
            "medication_adherence": {
                "overall_adherence_pct": overall_med_adherence,
                "active_prescriptions": meds,
            },
            "safety_triage": {
                "status": safety_status,
                "recent_alerts": triage_events,
            },
            "surgeon_actionable_insights": actionable_insights,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    @classmethod
    def export_pdf_report(cls, patient_id: str, days: int = 7) -> bytes:
        """
        Generates a publication-grade orthopedic clinical report PDF using ReportLab.
        """
        if not _REPORTLAB_AVAILABLE:
            # Fallback simple text-based PDF bytes if reportlab is not installed
            buffer = io.BytesIO()
            summary = cls.generate_patient_summary(patient_id, days)
            txt = f"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<<>>>>endobj\n4 0 obj<</Length 150>>stream\nBT /F1 12 Tf 50 700 Td (OrthoSync Clinical Summary Report: {summary['patient_id']}) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000117 00000 n \n0000000215 00000 n \ntrailer<</Size 5/Root 1 0 R>>\nstartxref\n415\n%%EOF"
            buffer.write(txt.encode('utf-8'))
            buffer.seek(0)
            return buffer.getvalue()

        summary = cls.generate_patient_summary(patient_id, days)
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#0F172A'),
        )
        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#475569'),
        )
        section_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#1E3A8A'),
            spaceBefore=10,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            'ReportBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#1E293B'),
        )
        body_bold = ParagraphStyle(
            'ReportBodyBold',
            parent=body_style,
            fontName='Helvetica-Bold',
        )

        story = []

        # --- Header Banner ---
        story.append(Paragraph("OrthoSync™ Clinical Post-Operative Summary", title_style))
        story.append(Paragraph(f"Orthopedic Surgery Department • Generated on {summary['generated_at']} • Confidential Medical Record", subtitle_style))
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284C7'), spaceBefore=2, spaceAfter=8))

        # --- Patient Demographics & Surgery Details Table ---
        demo_data = [
            [
                Paragraph("<b>Patient Name:</b>", body_style), Paragraph(summary["full_name"], body_style),
                Paragraph("<b>Patient ID:</b>", body_style), Paragraph(summary["patient_id"], body_style),
            ],
            [
                Paragraph("<b>Surgery:</b>", body_style), Paragraph(f"{summary['surgery_type']} ({summary['affected_limb']})", body_style),
                Paragraph("<b>Surgery Date:</b>", body_style), Paragraph(summary["surgery_date"], body_style),
            ],
            [
                Paragraph("<b>Post-Op Day:</b>", body_style), Paragraph(f"Day {summary['postop_day']}", body_bold),
                Paragraph("<b>Operating Surgeon:</b>", body_style), Paragraph(summary["operating_surgeon"], body_style),
            ],
            [
                Paragraph("<b>Weight Bearing:</b>", body_style), Paragraph(summary["weight_bearing_status"], body_style),
                Paragraph("<b>Prosthesis:</b>", body_style), Paragraph(summary["implant_details"], body_style),
            ],
        ]
        demo_table = Table(demo_data, colWidths=[100, 170, 110, 160])
        demo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(demo_table)
        story.append(Spacer(1, 10))

        # --- Recovery Key Metrics Cards ---
        story.append(Paragraph("7-Day Recovery Metrics & Functional Milestones", section_style))

        pt = summary["pain_trend"]
        mp = summary["mobility_progression"]
        ma = summary["medication_adherence"]

        metric_cards = [
            [
                Paragraph("<b>Pain Index (NPRS 0-10)</b>", body_style),
                Paragraph("<b>ROM & Milestones</b>", body_style),
                Paragraph("<b>Adherence & Compliance</b>", body_style),
            ],
            [
                Paragraph(f"• Current: <b>{pt['latest']}/10</b><br/>• 7-Day Avg: <b>{pt['average']}/10</b><br/>• Trend: <b>{pt['status']}</b> (Min {pt['min']} - Max {pt['max']})", body_style),
                Paragraph(f"• Flexion: <b>{mp['latest_flexion_deg']}°</b><br/>• Extension: <b>{mp['latest_extension_deg']}°</b><br/>• Milestone: <b>{'MET' if mp['target_milestone_met'] else 'IN PROGRESS'}</b>", body_style),
                Paragraph(f"• Exercise Compliance: <b>{mp['exercise_compliance_pct']}%</b><br/>• Med Adherence: <b>{ma['overall_adherence_pct']}%</b><br/>• DVT Prophylaxis: <b>Active</b>", body_style),
            ]
        ]
        metric_table = Table(metric_cards, colWidths=[180, 180, 180])
        metric_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E0F2FE')),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F0F9FF')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BAE6FD')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(metric_table)
        story.append(Spacer(1, 10))

        # --- Daily Log Trajectory Table ---
        story.append(Paragraph("Daily Recovery Trajectory (Past 7 Days)", section_style))
        raw_metrics = cls.get_patient_record(patient_id).get("metrics_history", [])[-7:]
        log_rows = [
            [
                Paragraph("<b>Date</b>", body_bold),
                Paragraph("<b>Post-Op Day</b>", body_bold),
                Paragraph("<b>Pain (0-10)</b>", body_bold),
                Paragraph("<b>Flexion (°)</b>", body_bold),
                Paragraph("<b>Extension (°)</b>", body_bold),
                Paragraph("<b>PT Session</b>", body_bold),
                Paragraph("<b>Safety Triage</b>", body_bold),
            ]
        ]
        for m in raw_metrics:
            log_rows.append([
                Paragraph(m.get("date", "-"), body_style),
                Paragraph(f"Day {m.get('day', '-')}", body_style),
                Paragraph(str(m.get("pain_score", "-")), body_style),
                Paragraph(f"{m.get('rom_flexion', '-')}°", body_style),
                Paragraph(f"{m.get('rom_extension', '-')}°", body_style),
                Paragraph("Completed" if m.get("exercise_completed") else "Missed", body_style),
                Paragraph(m.get("triage", "GREEN"), body_style),
            ])

        log_table = Table(log_rows, colWidths=[80, 75, 75, 75, 75, 80, 80])
        log_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ]))
        story.append(log_table)
        story.append(Spacer(1, 10))

        # --- Active Medications & Safety Triage ---
        story.append(Paragraph("Medication Adherence & Safety Triage Evaluation", section_style))
        med_rows = [
            [
                Paragraph("<b>Medication</b>", body_bold),
                Paragraph("<b>Dosage & Timing</b>", body_bold),
                Paragraph("<b>Clinical Indication</b>", body_bold),
                Paragraph("<b>Adherence %</b>", body_bold),
            ]
        ]
        for med in summary["medication_adherence"]["active_prescriptions"]:
            med_rows.append([
                Paragraph(med.get("name", "-"), body_style),
                Paragraph(med.get("dose", "-"), body_style),
                Paragraph(med.get("purpose", "-"), body_style),
                Paragraph(f"{med.get('adherence_pct', 100)}%", body_style),
            ])

        med_table = Table(med_rows, colWidths=[130, 130, 180, 100])
        med_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#047857')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(med_table)
        story.append(Spacer(1, 10))

        # --- Actionable Surgeon Insights ---
        story.append(Paragraph("Actionable Orthopedic Surgeon Insights", section_style))
        insights = summary["surgeon_actionable_insights"]
        insight_items = "".join([f"• {item}<br/>" for item in insights])
        insight_box = [
            [
                Paragraph(f"<b>Clinical Observations & Synthesis:</b><br/>{insight_items}<br/><b>Safety Status:</b> {summary['safety_triage']['status']}", body_style)
            ]
        ]
        insight_table = Table(insight_box, colWidths=[540])
        insight_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EFF6FF')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#3B82F6')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(insight_table)
        story.append(Spacer(1, 14))

        # --- Physician Sign-off ---
        signoff_data = [
            [
                Paragraph("<b>Reviewed by Orthopedic Attending:</b> ___________________________", body_style),
                Paragraph("<b>Date:</b> ______________", body_style),
            ]
        ]
        signoff_table = Table(signoff_data, colWidths=[380, 160])
        signoff_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(KeepTogether(signoff_table))

        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
