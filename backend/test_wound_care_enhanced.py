"""
Comprehensive test suite for enhanced Wound Care Agent (OrthoSync Milestone Phase II).

Tests the 5 core improvements:
1. Multimodal Photo-Chat Fusion (wound CV analysis ingestion, appearance auto-seeding, acknowledgment)
2. Dressing vs. Bare Incision Awareness (Day <= 3 dressing status priority vs exposed incision)
3. Drainage Characteristic Classification (serous vs purulent/SSI vs sanguineous vs none)
4. Longitudinal Trend Tracking & SQLite Persistence (wound_assessments table, prior visit comparison)
5. Physician Alert & Report Linkage (doctor_alert_notifier, triage_events, ReportGenerationAgent summary)
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from agents.wound_care_agent import (
    WoundCareAgent,
    classify_drainage_type,
    _get_question_order,
    _extract_photo_analysis,
    _should_conclude,
)
from patient_database import (
    initialize_database,
    save_wound_assessment,
    get_recent_wound_assessments,
    get_patient,
    record_triage_event,
)
from agents.report_agent import ReportGenerationAgent
from lam.orchestrator import LAMOrchestrator


def test_drainage_classification():
    print("Testing Drainage Characteristic Classification...")
    
    # None / Dry
    cat, desc = classify_drainage_type("No fluid at all, completely dry")
    assert cat == "none", f"Expected none, got {cat}"

    # Serous
    cat, desc = classify_drainage_type("A small amount of clear pale straw colored fluid")
    assert cat == "serous", f"Expected serous, got {cat}"
    assert "clear or straw" in desc.lower()

    # Serosanguineous
    cat, desc = classify_drainage_type("Thin pink blood-tinged watery liquid")
    assert cat == "serosanguineous", f"Expected serosanguineous, got {cat}"

    # Sanguineous
    cat, desc = classify_drainage_type("There is active red blood leaking out")
    assert cat == "sanguineous", f"Expected sanguineous, got {cat}"

    # Purulent (Critical SSI Indicator)
    cat, desc = classify_drainage_type("It has thick yellow pus with a bad foul odor")
    assert cat == "purulent", f"Expected purulent, got {cat}"
    assert "suspected surgical site infection" in desc.lower()

    print("  [PASS] Drainage classification passed for all clinical categories.")


def test_dressing_status_awareness():
    print("Testing Dressing vs Bare Incision Awareness (Post-op Day <= 3)...")

    # Day 2: Early post-op -> dressing status must be first
    order_day2 = _get_question_order(postop_day=2)
    assert order_day2[0] == "dressing_status", f"Expected dressing_status first on Day 2, got {order_day2[0]}"

    # Day 7: Later post-op -> onset first
    order_day7 = _get_question_order(postop_day=7)
    assert order_day7[0] == "onset", f"Expected onset first on Day 7, got {order_day7[0]}"

    # Should conclude checks
    partial_assessment = {
        "onset": "yesterday",
        "progression": "same",
        "appearance": "normal",
        "warmth": "not warm",
        "drainage": "none",
        "separation": "closed",
    }
    # On Day 7, 6 core fields conclude:
    assert _should_conclude(partial_assessment, postop_day=7) is True

    # On Day 2, dressing_status is also required:
    assert _should_conclude(partial_assessment, postop_day=2) is False
    partial_assessment["dressing_status"] = "Bandage is clean, dry and intact"
    assert _should_conclude(partial_assessment, postop_day=2) is True

    # Check interaction on Day 2 asks dressing_status first
    resp = WoundCareAgent.handle(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=2,
        user_message="My knee wound feels tight today",
        procedure="TKA",
    )
    assert "dressing" in resp["reply"].lower() or "bandage" in resp["reply"].lower()
    print("  [PASS] Dressing status priority verified for Day <= 3.")


def test_multimodal_photo_fusion():
    print("Testing Multimodal Photo-Chat Fusion...")

    photo_analysis = {
        "visual_flag": "elevated_redness_detected",
        "redness_score": 0.09,
        "redness_intensity": 0.55,
        "color_variability": 0.32,
    }

    # Pass photo_analysis directly
    resp = WoundCareAgent.handle(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=5,
        user_message="I took a picture of my wound, what do you think?",
        procedure="TKA",
        photo_analysis=photo_analysis,
    )
    
    # Should acknowledge the photo
    assert "photo" in resp["reply"].lower() or "redness" in resp["reply"].lower()
    # Next question should be onset (not appearance/redness question because redness was already extracted from photo!)
    assert "when did you first notice" in resp["reply"].lower()

    # Test extraction from chat history
    history = [
        {"role": "user", "content": "Here is the photo"},
        {"role": "assistant", "content": "Looking at the photo, I can see some noticeable redness in the area."},
    ]
    extracted = _extract_photo_analysis(None, history, "Is this redness bad?")
    assert extracted is not None
    assert extracted["visual_flag"] == "elevated_redness_detected"

    print("  [PASS] Multimodal photo fusion and redundant question skipping verified.")


def test_sqlite_persistence_and_longitudinal_tracking():
    print("Testing SQLite Persistence and Longitudinal Trend Comparison...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db = os.path.join(tmp_dir, "test_patients.sqlite3")
        initialize_database(test_db)

        # Patch PATIENT_DATABASE_PATH to use our temp test_db
        with patch.dict(os.environ, {"PATIENT_DATABASE_PATH": test_db}):
            # Patient record
            patient_id = "PT-TEST-001"
            from patient_database import create_patient
            create_patient({
                "patient_id": patient_id,
                "full_name": "Test Patient",
                "surgery_type": "Total Knee Arthroplasty (TKA)",
                "affected_limb": "Right",
                "postop_day": 3,
            }, path=test_db)

            # 1. Record Visit 1 on Day 3: Moderate redness, serous drainage
            record_day3 = {
                "postop_day": 3,
                "onset": "2 days ago",
                "progression": "same",
                "appearance": "moderately red around stitches",
                "warmth": "slightly warm",
                "drainage": "clear watery fluid leaking slightly",
                "drainage_type": "serous",
                "separation": "closed",
                "pain": "5/10",
                "fever": "no",
                "dressing_status": "dressing had minor stain",
                "redness_score": 0.06,
                "visual_flag": "elevated_redness_detected",
                "triage_level": "GREEN",
                "summary": "Mild redness and serous drainage on Day 3",
            }
            row_id = save_wound_assessment(patient_id, record_day3, path=test_db)
            assert row_id > 0

            # Verify saved
            recent = get_recent_wound_assessments(patient_id, limit=3, path=test_db)
            assert len(recent) == 1
            assert recent[0]["drainage_type"] == "serous"
            assert recent[0]["postop_day"] == 3

            # 2. Record Visit 2 on Day 6: Patient reports improvement
            # We run complete dialogue or conclude directly
            history_day6 = [
                {"role": "user", "content": "Checking on my incision"},
                {"role": "assistant", "content": "When did you notice it?"},
                {"role": "user", "content": "Started 3 days ago"},
                {"role": "assistant", "content": "Is it getting better or worse?"},
                {"role": "user", "content": "Getting much better and less red"},
                {"role": "assistant", "content": "Please check appearance"},
                {"role": "user", "content": "Much less red and normal skin"},
                {"role": "assistant", "content": "How warm does it feel?"},
                {"role": "user", "content": "Cooler and not warm"},
                {"role": "assistant", "content": "Any fluid?"},
                {"role": "user", "content": "No fluid at all, completely dry now"},
                {"role": "assistant", "content": "Any separation?"},
                {"role": "user", "content": "Edges are completely closed"},
            ]

            resp_day6 = WoundCareAgent.handle(
                patient_id=patient_id,
                surgery_type="Total Knee Arthroplasty (TKA)",
                affected_limb="Right",
                postop_day=6,
                user_message="Edges are completely closed",
                chat_history=history_day6[:-1],
                procedure="TKA",
            )

            # Verify longitudinal comparison appears in conclusion
            reply = resp_day6["reply"]
            assert "Recovery Trend" in reply or "improved" in reply.lower()
            assert "resolved" in reply.lower() or "previous" in reply.lower() or "prior" in reply.lower()

            # Verify Day 6 assessment was automatically saved to SQLite
            recent_after = get_recent_wound_assessments(patient_id, limit=3, path=test_db)
            assert len(recent_after) == 2
            assert recent_after[0]["postop_day"] == 6

    print("  [PASS] SQLite persistence and longitudinal comparison verified.")


def test_doctor_alert_and_report_linkage():
    print("Testing Physician Alert and Report Linkage on Purulent / SSI findings...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db = os.path.join(tmp_dir, "test_patients_ssi.sqlite3")
        initialize_database(test_db)

        with patch.dict(os.environ, {"PATIENT_DATABASE_PATH": test_db}):
            patient_id = "PT-B7-8921"
            from patient_database import create_patient
            create_patient({
                "patient_id": patient_id,
                "full_name": "Rishi Priyan V N",
                "surgery_type": "Total Knee Arthroplasty (TKA)",
                "affected_limb": "Right",
                "postop_day": 7,
                "surgeon": "Dr. Sarah Jenkins",
            }, path=test_db)

            # Purulent drainage conversation + fever
            history_ssi = [
                {"role": "user", "content": "My knee incision is leaking bad smelling fluid"},
                {"role": "assistant", "content": "When did you notice it?"},
                {"role": "user", "content": "Started this morning"},
                {"role": "assistant", "content": "Is it getting better or worse?"},
                {"role": "user", "content": "Getting worse quickly"},
                {"role": "assistant", "content": "How does it look?"},
                {"role": "user", "content": "Skin is bright red and spreading"},
                {"role": "assistant", "content": "How warm is it?"},
                {"role": "user", "content": "It feels very hot to touch"},
                {"role": "assistant", "content": "What does the drainage look like?"},
                {"role": "user", "content": "Thick yellow pus with a foul smelly odor"},
                {"role": "assistant", "content": "Is it separating?"},
                {"role": "user", "content": "Yes, part of the wound is gaping open and I have a high fever"},
            ]

            with patch("agents.wound_care_agent.doctor_alert_notifier.notify_red_triage_background") as mock_notify:
                resp = WoundCareAgent.handle(
                    patient_id=patient_id,
                    surgery_type="Total Knee Arthroplasty (TKA)",
                    affected_limb="Right",
                    postop_day=7,
                    user_message="Yes, part of the wound is gaping open and I have a high fever",
                    chat_history=history_ssi[:-1],
                    procedure="TKA",
                )

                # Must escalate to RED
                assert resp["triage_level"] == "RED", f"Expected RED triage, got {resp['triage_level']}"
                assert resp["is_escalated"] is True
                assert "infection" in resp["reply"].lower() or "purulent" in resp["reply"].lower()
                assert mock_notify.called, "doctor_alert_notifier.notify_red_triage_background should have been called for RED triage"

            # Check ReportGenerationAgent includes wound care status
            summary = ReportGenerationAgent.generate_patient_summary(patient_id)
            assert "wound_care" in summary
            assert len(summary["wound_care"]["recent_assessments"]) > 0
            assert summary["wound_care"]["recent_assessments"][0]["drainage_type"] == "purulent"
            # Actionable insights should flag the critical finding
            assert any("purulent" in insight.lower() or "wound" in insight.lower() for insight in summary["surgeon_actionable_insights"])

    print("  [PASS] Physician Alert and Report Linkage verified.")


def test_orchestrator_integration():
    print("Testing End-to-End LAM Orchestrator with photo_analysis payload...")
    
    photo_payload = {
        "visual_flag": "elevated_redness_detected",
        "redness_score": 0.08,
        "redness_intensity": 0.48,
    }

    result = LAMOrchestrator.process(
        patient_id="PT-B7-8921",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=4,
        user_message="I took a picture of my incision, is it normal?",
        photo_analysis=photo_payload,
    )

    assert result is not None
    assert "reply" in result
    assert result["intent"] == "wound_care"
    assert "photo" in result["reply"].lower() or "redness" in result["reply"].lower()
    print("  [PASS] End-to-end LAM Orchestrator with photo_analysis passed.")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("RUNNING ORTHOSYNC WOUND CARE AGENT ENHANCED TEST SUITE")
    print("=" * 70)
    
    test_drainage_classification()
    test_dressing_status_awareness()
    test_multimodal_photo_fusion()
    test_sqlite_persistence_and_longitudinal_tracking()
    test_doctor_alert_and_report_linkage()
    test_orchestrator_integration()

    print("\n" + "=" * 70)
    print("ALL 5 WOUND CARE AGENT ENHANCEMENT TESTS PASSED PERFECTLY!")
    print("=" * 70)
