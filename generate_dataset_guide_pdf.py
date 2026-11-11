"""
generate_dataset_guide_pdf.py
Generates a clean, professional, publication-quality reference PDF guide
covering all datasets, patient records, scan images, commands, and architecture.
"""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 755, "Orthopedic AI System — Datasets, Patient Records & Imaging Guide")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, 748, 558, 748)
            
        # Footer
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(558, 36, page_str)
        self.drawString(54, 36, "Confidential — Ortho AI Assistant & Agentic Pipeline Reference")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 48, 558, 48)
        self.restoreState()


def build_pdf(filename="docs/DATASETS_AND_PATIENT_RECORDS_GUIDE.pdf"):
    out_path = Path(filename)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom palette
    NAVY = colors.HexColor("#1E3A8A")
    SLATE = colors.HexColor("#0F172A")
    ACCENT_BLUE = colors.HexColor("#2563EB")
    BG_LIGHT = colors.HexColor("#F8FAFC")
    BORDER_COLOR = colors.HexColor("#CBD5E1")
    TEXT_MUTED = colors.HexColor("#475569")
    CODE_BG = colors.HexColor("#F1F5F9")
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=NAVY,
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=TEXT_MUTED,
        spaceAfter=14
    )
    
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=NAVY,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=ACCENT_BLUE,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=SLATE,
        spaceAfter=5
    )
    
    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=SLATE,
        leftIndent=14,
        spaceAfter=3
    )
    
    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=0
    )
    
    story = []
    
    # Title Section
    story.append(Paragraph("Orthopedic AI & Agentic System", title_style))
    story.append(Paragraph("Complete Technical Guide: Datasets, Patient Records, Medical Imaging & Model Commands", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceBefore=2, spaceAfter=12))
    
    # Executive Summary Card
    summary_html = """<b>System Overview:</b> This document provides an exhaustive operational reference for the Orthopedic AI Chatbot, Multi-Agent Clinical Triage System, Fine-Tuning pipelines, synthetic and real-world orthopedic patient records, and medical scan datasets (X-Ray / MRI) with Kellgren-Lawrence (KL) grading."""
    summary_table = Table([[Paragraph(summary_html, body_style)]], colWidths=[504])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))
    
    # Section 1: Chatbot & Qwen LLM Fine-Tuning Datasets
    story.append(Paragraph("1. Chatbot & LLM Fine-Tuning Datasets", h1_style))
    story.append(Paragraph("The system combines high-grade orthopedic and clinical dialogue datasets into unified JSONL files formatted for instruction tuning (Qwen-2.5 / LoRA).", body_style))
    
    dataset_summary = [
        [Paragraph("<b>Dataset Source</b>", body_style), Paragraph("<b>Type & Scope</b>", body_style), Paragraph("<b>Records Filtered</b>", body_style), Paragraph("<b>License / Access</b>", body_style)],
        [Paragraph("ruslanmv/ai-medical-chatbot", code_style), Paragraph("Multi-specialty patient-doctor dialogues", body_style), Paragraph("20,000 QA pairs", body_style), Paragraph("Open / HuggingFace", body_style)],
        [Paragraph("jtatman/medical-sci-instruct-1m", code_style), Paragraph("Complex scientific clinical reasoning", body_style), Paragraph("15,000 instruct pairs", body_style), Paragraph("Open / HuggingFace", body_style)],
        [Paragraph("lavita/chatdoctor-*", code_style), Paragraph("Real doctor-patient conversations (HealthCareMagic, iCliniq)", body_style), Paragraph("Orthopedic keywords filtered", body_style), Paragraph("Research Open", body_style)],
        [Paragraph("Synthetic Ortho SFT", code_style), Paragraph("Targeted TKA, THA, ACL, spine recovery & rehab protocols", body_style), Paragraph("510 QA pairs", body_style), Paragraph("Internal (Project)", body_style)],
        [Paragraph("<b>TOTAL MERGED</b>", body_style), Paragraph("<b>Consolidated Train + Val Splits</b>", body_style), Paragraph("<b>35,510 total records</b>", body_style), Paragraph("<b>Ready in backend/data/exports/</b>", body_style)]
    ]
    t1 = Table(dataset_summary, colWidths=[140, 150, 110, 104])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#EFF6FF")),
    ]))
    story.append(t1)
    story.append(Spacer(1, 8))
    
    # Commands for Datasets
    story.append(Paragraph("Commands to Fetch and Fine-Tune Datasets:", h2_style))
    cmds_1 = [
        [Paragraph("<b>Task</b>", body_style), Paragraph("<b>Execution Command</b>", body_style)],
        [Paragraph("Fetch external datasets & merge into JSONL", body_style), Paragraph("python backend/data/fetch_external_datasets.py", code_style)],
        [Paragraph("Export synthetic Qwen SFT train/val splits", body_style), Paragraph("python backend/data/export_sft_splits.py", code_style)],
        [Paragraph("Run Qwen-2.5 1.5B/7B QLoRA Fine-Tuning", body_style), Paragraph("python backend/data/train_qwen_lora.py", code_style)],
        [Paragraph("Test fine-tuned model inference checkpoint", body_style), Paragraph("python backend/data/test_lora_inference.py", code_style)],
    ]
    t_cmd1 = Table(cmds_1, colWidths=[170, 334])
    t_cmd1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_cmd1)
    story.append(Spacer(1, 10))
    
    # Section 2: Patient Records Database
    story.append(Paragraph("2. Orthopedic Patient Records Database", h1_style))
    story.append(Paragraph("The local SQLite database (<code>backend/patients.sqlite3</code>) contains 50 comprehensive orthopedic patient records structured for clinical multi-agent workflows.", body_style))
    
    story.append(Paragraph("Database Schema Architecture:", h2_style))
    story.append(Paragraph("&bull; <b>patients</b>: Demographics, surgery type (TKA, THA, ACL Reconstruction, Lumbar Discectomy, Rotator Cuff Repair, Ankle Fusion), surgery date, surgeon name, implant details.", bullet_style))
    story.append(Paragraph("&bull; <b>patient_medications</b>: Prescriptions, dosages, schedules, indication, risk notes (e.g., Enoxaparin, Tramadol, Celecoxib).", bullet_style))
    story.append(Paragraph("&bull; <b>patient_rehab_exercises</b>: Prescribed rehab protocols, sets, reps, frequency, restrictions.", bullet_style))
    story.append(Paragraph("&bull; <b>patient_documents</b>: Clinical notes, discharge summaries, op notes, extraction status.", bullet_style))
    story.append(Paragraph("&bull; <b>patient_scans</b>: Medical imaging metadata (scan type, body part, laterality, KL grade, radiologist impression, local scan file path).", bullet_style))
    story.append(Spacer(1, 6))
    
    cmds_2 = [
        [Paragraph("<b>Database Action</b>", body_style), Paragraph("<b>Command / API Call</b>", body_style)],
        [Paragraph("Seed 50 Orthopedic Patients with Full Records", body_style), Paragraph("python backend/seed_ortho_patients.py", code_style)],
        [Paragraph("Inspect DB Tables & Schema", body_style), Paragraph("python backend/inspect_db.py", code_style)],
        [Paragraph("Query Patient via Python API", body_style), Paragraph("from patient_database import get_patient; pt = get_patient('PT-1005')", code_style)],
        [Paragraph("Retrieve Patient List & Filters", body_style), Paragraph("from patient_database import list_patients; pts = list_patients()", code_style)],
    ]
    t_cmd2 = Table(cmds_2, colWidths=[170, 334])
    t_cmd2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_cmd2)
    story.append(Spacer(1, 12))
    
    # Page Break for clean layout
    story.append(PageBreak())
    
    # Section 3: Medical Imaging & Scan Datasets
    story.append(Paragraph("3. Medical Imaging & Scan Datasets (X-Ray / MRI)", h1_style))
    story.append(Paragraph("To support upcoming Computer Vision & Vision-Language Agents (VLM) for orthopedic assessments, the pipeline includes scan integration and automated linkage to patient records.", body_style))
    
    imaging_sources = [
        [Paragraph("<b>Dataset Name</b>", body_style), Paragraph("<b>Modality & Anatomy</b>", body_style), Paragraph("<b>Clinical Labels / Features</b>", body_style), Paragraph("<b>Access Method</b>", body_style)],
        [Paragraph("Kaggle: Knee Osteoarthritis", code_style), Paragraph("X-Ray (AP views) Knee", body_style), Paragraph("Kellgren-Lawrence (KL) Grade 0 to 4 (9,700+ images)", body_style), Paragraph("Free / Kaggle API", body_style)],
        [Paragraph("HuggingFace: medical-imaging", code_style), Paragraph("Multimodal X-Ray / CT", body_style), Paragraph("Pathology classifications, fractures", body_style), Paragraph("Free / HuggingFace API", body_style)],
        [Paragraph("Stanford MURA (Bone X-rays)", code_style), Paragraph("X-Ray (Upper / Lower Extremities)", body_style), Paragraph("Musculoskeletal abnormalities, 40,000+ scans", body_style), Paragraph("Free Stanford Research DUA", body_style)],
        [Paragraph("fastMRI (NYU / Meta)", code_style), Paragraph("Knee & Spine MRI", body_style), Paragraph("Raw k-space & DICOM clinical knee MRI", body_style), Paragraph("fastmri.med.nyu.edu", body_style)],
        [Paragraph("OAI (Osteoarthritis Initiative)", code_style), Paragraph("Serial Knee Radiographs & 3T MRI", body_style), Paragraph("Gold standard longitudinal joint health study", body_style), Paragraph("NDA / NIMH Data Archive", body_style)],
    ]
    t_img = Table(imaging_sources, colWidths=[130, 110, 160, 104])
    t_img.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_img)
    story.append(Spacer(1, 8))
    
    story.append(Paragraph("Imaging Pipeline Commands:", h2_style))
    cmds_3 = [
        [Paragraph("<b>Imaging Task</b>", body_style), Paragraph("<b>Execution Command</b>", body_style)],
        [Paragraph("Link scan records to 50 patients (metadata + paths)", body_style), Paragraph("python backend/download_scan_images.py --skip-download", code_style)],
        [Paragraph("Download full Kaggle Knee X-Ray dataset", body_style), Paragraph("python backend/download_scan_images.py --source kaggle", code_style)],
        [Paragraph("Download HuggingFace medical images", body_style), Paragraph("python backend/download_scan_images.py --source huggingface", code_style)],
        [Paragraph("Download sample preview images directly", body_style), Paragraph("python backend/download_scan_images.py --samples 50", code_style)],
    ]
    t_cmd3 = Table(cmds_3, colWidths=[170, 334])
    t_cmd3.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_cmd3)
    story.append(Spacer(1, 10))
    
    # Section 4: External Real-World Clinical Repositories
    story.append(Paragraph("4. Real-World Hospital Clinical Data Repositories", h1_style))
    story.append(Paragraph("For formal validation where simulated hospital data is insufficient, the following authenticated repositories provide real patient records:", body_style))
    story.append(Paragraph("&bull; <b>ACORN Joint Replacement Registry</b>: Real de-identified Australian arthroplasty outcomes (TKA/THA) with PROMs (Oxford Knee Score). Creative Commons 4.0 license at <i>doi.org/10.26190/5ee17b8708b7e</i>.", bullet_style))
    story.append(Paragraph("&bull; <b>PhysioNet MIMIC-IV</b>: 300,000+ hospital admissions including orthopedic surgical cases, real lab telemetry, medications, and discharge summaries. Access requires completing free CITI 'Data or Specimens Only Research' training at <i>physionet.org</i>.", bullet_style))
    story.append(Paragraph("&bull; <b>Cancer Imaging Archive (TCIA)</b>: De-identified sarcoma and musculoskeletal CT/MRI scans in standard DICOM format.", bullet_style))
    story.append(Spacer(1, 10))
    
    # Section 5: Architecture & Git Branching Summary
    story.append(Paragraph("5. Architecture & Git Collaboration Workflow", h1_style))
    story.append(Paragraph("To ensure safe integration with your teammate's code before merging to <code>main</code>:", body_style))
    
    git_flow = [
        [Paragraph("<b>Step</b>", body_style), Paragraph("<b>Branch & Git Action</b>", body_style), Paragraph("<b>Description</b>", body_style)],
        [Paragraph("1. Feature Branch", body_style), Paragraph("git checkout rishp118-complete-medication-agent", code_style), Paragraph("All datasets, DB scripts, scan loaders, and PDF docs committed here.", body_style)],
        [Paragraph("2. Push to Remote", body_style), Paragraph("git push origin rishp118-complete-medication-agent", code_style), Paragraph("Pushes branch cleanly to GitHub remote.", body_style)],
        [Paragraph("3. Merge with Teammate", body_style), Paragraph("git fetch origin main<br/>git merge origin/main", code_style), Paragraph("Pull your teammate's latest changes from main, resolve conflicts if any.", body_style)],
        [Paragraph("4. Pull Request to Main", body_style), Paragraph("Create PR via GitHub / merge branch into main", code_style), Paragraph("Safely merges medication agent, datasets, and patient DB into main project.", body_style)],
    ]
    t_git = Table(git_flow, colWidths=[80, 210, 214])
    t_git.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_git)
    story.append(Spacer(1, 14))
    
    # Footer Notice
    footer_note = "<i>Generated for Orthopedic AI Assistant Project &bull; All scripts and schemas reside under the <code>backend/</code> directory.</i>"
    story.append(Paragraph(footer_note, ParagraphStyle('Foot', parent=body_style, textColor=TEXT_MUTED, fontSize=8)))
    
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[+] Successfully generated PDF at: {out_path.resolve()}")

if __name__ == "__main__":
    build_pdf()
