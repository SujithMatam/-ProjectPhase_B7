"""
Synthetic Orthopedic Patient Report Generator.

Generates a small set of FAKE patient report PDFs for testing the
extraction pipeline. No real patient data is used anywhere.

Deliberately varies:
    - field labels / terminology ("Patient Name" vs "Name" vs "Pt.")
    - layout (label: value on one line vs label above value vs table)
    - field order
    - which fields are present at all
    - date formats
    - how medications/plan are listed (comma list vs bullet vs paragraph)

This is what makes it a real test of "the extractor must not be
hardcoded to one template" -- if the extractor only works on report_1,
that's a bug we want caught here, before a real admin ever uses it.
"""

from __future__ import annotations

import os

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "synthetic_reports")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontSize=16,
        )
    )
    return styles


# ============================================================================
# REPORT 1 -- clean "label: value" clinic letterhead style
# ============================================================================

def generate_report_1(path: str) -> None:
    styles = _styles()
    doc = SimpleDocTemplate(path, pagesize=letter)
    story = []

    story.append(Paragraph("Amrita Orthopedic Clinic", styles["ReportTitle"]))
    story.append(Paragraph("Postoperative Discharge Summary", styles["Heading2"]))
    story.append(Spacer(1, 16))

    fields = [
        ("Patient Name", "Rajesh Kumar Nair"),
        ("Age", "58 years"),
        ("Sex", "Male"),
        ("Diagnosis", "Osteoarthritis, right knee, end-stage"),
        ("Date of Surgery", "12/06/2026"),
        ("Procedure Performed", "Total Knee Arthroplasty (TKA), Right"),
        ("Medications Prescribed", "Tab. Paracetamol 650mg TDS, Tab. Rivaroxaban 10mg OD, Cap. Pantoprazole 40mg OD"),
        ("Current Treatment Plan", "Continue physiotherapy 3x/week, follow-up in OPD after 2 weeks, wound review at 10 days."),
    ]

    for label, value in fields:
        story.append(Paragraph(f"<b>{label}:</b> {value}", styles["Normal"]))
        story.append(Spacer(1, 8))

    doc.build(story)


# ============================================================================
# REPORT 2 -- table-based EHR export style, different terminology
# ============================================================================

def generate_report_2(path: str) -> None:
    styles = _styles()
    doc = SimpleDocTemplate(path, pagesize=letter)
    story = []

    story.append(Paragraph("MediCare Hospital - EHR Export", styles["ReportTitle"]))
    story.append(Spacer(1, 12))

    data = [
        ["Field", "Value"],
        ["Pt. Name", "Anjali S. Menon"],
        ["DOB / Age", "34F (DOB: 03-Aug-1991)"],
        ["Gender", "Female"],
        ["Primary Dx", "Displaced fracture, left ankle (bimalleolar)"],
        ["Surgery Date", "2026-06-20"],
        ["Operation", "Open Reduction Internal Fixation (ORIF), Left Ankle"],
        ["Rx", "Ibuprofen 400mg PRN; Enoxaparin 40mg SC OD x14 days"],
        ["Plan", "Non-weight-bearing 6 weeks; recheck X-ray at 6-week visit; ortho follow-up scheduled."],
    ]

    table = Table(data, colWidths=[1.8 * inch, 4.2 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8B1E3F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
            ]
        )
    )
    story.append(table)

    doc.build(story)


# ============================================================================
# REPORT 3 -- narrative/paragraph style, minimal labeling, missing some fields
# ============================================================================

def generate_report_3(path: str) -> None:
    styles = _styles()
    doc = SimpleDocTemplate(path, pagesize=letter)
    story = []

    story.append(Paragraph("Sunrise Bone & Joint Center", styles["ReportTitle"]))
    story.append(Paragraph("Clinical Note", styles["Heading2"]))
    story.append(Spacer(1, 16))

    narrative = (
        "This is a summary note for Mr. David Thomas Fernandez, a 45-year-old male, "
        "who presented following a fall resulting in a comminuted fracture of the "
        "right tibial plateau. He underwent surgical fixation on the 5th of June, "
        "2026. Postoperatively he has been started on Tramadol 50mg as needed for "
        "pain and Aspirin 75mg once daily. He is to remain partially weight-bearing "
        "with crutches for the next four weeks and will be reviewed in clinic in "
        "three weeks' time, with repeat imaging prior to that visit."
    )

    story.append(Paragraph(narrative, styles["Normal"]))
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            "Note: this record does not include a formally coded diagnosis field "
            "or a separate 'surgery type' line -- both are embedded in the "
            "narrative above, as is common in dictated clinical notes.",
            styles["Italic"],
        )
    )

    doc.build(story)


# ============================================================================
# REPORT 4 -- abbreviated intake-form style, very different field set/order
# ============================================================================

def generate_report_4(path: str) -> None:
    styles = _styles()
    doc = SimpleDocTemplate(path, pagesize=letter)
    story = []

    story.append(Paragraph("PostOp Intake Form", styles["ReportTitle"]))
    story.append(Spacer(1, 12))

    fields = [
        ("Full Name", "Priya Ramachandran"),
        ("Sex/Age", "F / 61"),
        ("Operative Procedure", "Total Hip Arthroplasty (THA) - Left"),
        ("Indication", "Avascular necrosis of left femoral head"),
        ("Date of Operation", "18-06-2026"),
        ("Discharge Meds", "1) Acetaminophen 500mg q6h prn  2) Apixaban 2.5mg BID x 30 days  3) Docusate 100mg BID"),
        ("Follow-up Plan", "Hip precautions x6 weeks (no bending past 90deg, no crossing legs); staple removal day 14; PT starts week 2."),
    ]

    for label, value in fields:
        story.append(Paragraph(f"<b>{label}</b>", styles["Heading4"]))
        story.append(Paragraph(value, styles["Normal"]))
        story.append(Spacer(1, 10))

    doc.build(story)


# ============================================================================
# REPORT 5 -- different terminology entirely (UK-style spelling/terms),
# unusual date format, age not stated directly (must be inferred / absent)
# ============================================================================

def generate_report_5(path: str) -> None:
    styles = _styles()
    doc = SimpleDocTemplate(path, pagesize=letter)
    story = []

    story.append(Paragraph("St. Margaret's Orthopaedic Unit", styles["ReportTitle"]))
    story.append(Paragraph("Theatre & Discharge Summary", styles["Heading2"]))
    story.append(Spacer(1, 16))

    fields = [
        ("Patient", "Mohammed Iqbal Sheikh (Mr.)"),
        ("Gender", "M"),
        ("Presenting Complaint / Diagnosis", "Degenerative meniscal tear, right knee"),
        ("Date of Theatre", "3rd July 2026"),
        ("Operation Undertaken", "Arthroscopic Partial Meniscectomy, Right Knee"),
        ("Medicines on Discharge", "Naproxen 250mg twice daily with food; Omeprazole 20mg once daily"),
        ("Ongoing Management", "Weight-bear as tolerated; physiotherapy referral sent; review in fracture clinic in 4 weeks if not settling."),
    ]

    for label, value in fields:
        story.append(Paragraph(f"<b>{label}:</b> {value}", styles["Normal"]))
        story.append(Spacer(1, 8))

    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "Note: this record deliberately omits an explicit 'age' field -- "
            "a correct extractor should return null/not found for age here, "
            "not guess a number.",
            styles["Italic"],
        )
    )

    doc.build(story)


def generate_all() -> list[str]:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    generators = [
        ("report_1_clinic_letterhead.pdf", generate_report_1),
        ("report_2_ehr_table.pdf", generate_report_2),
        ("report_3_narrative.pdf", generate_report_3),
        ("report_4_intake_form.pdf", generate_report_4),
        ("report_5_uk_style.pdf", generate_report_5),
    ]

    paths = []
    for filename, generator_fn in generators:
        path = os.path.join(OUTPUT_DIR, filename)
        generator_fn(path)
        paths.append(path)
        print(f"Generated: {path}")

    return paths


if __name__ == "__main__":
    generate_all()