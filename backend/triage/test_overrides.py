"""Unit tests for triage/overrides.py (temperature + self-harm).

    cd backend && .venv/Scripts/python -m pytest triage/test_overrides.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from triage.overrides import (  # noqa: E402
    LEVEL_RANK, evaluate_overrides, parse_temperatures, self_harm_matches, self_harm_override,
    temperature_override,
)

DATA = Path(__file__).resolve().parent / "data"


def _level(text, temperature_c=None):
    o = temperature_override(text, temperature_c)
    return o.level if o else None


def _rows(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


CHALLENGE = {r["id"]: r for r in _rows(DATA / "challenge.jsonl")}
UNSEEN_TEST = {r["id"]: r for r in _rows(DATA / "splits_unseen_scenario" / "test.jsonl")}

# ---------------------------------------------------------------------------
# Temperature parser
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text, expected", [
    ("temp 38.6", [38.6]),
    ("101F", [38.3]),
    ("fever of 39", [39.0]),
    ("39.6 is this an emergency", [39.6]),
    ("38.7, 38.8, 38.6 over three checks", [38.7, 38.8, 38.6]),
    ("Tympanic reading 38.6°C, oral reading 38.4°C", [38.6, 38.4]),
    ("I checked my temperature and it is 37.9°C (100.2°F).", [37.9, 37.9]),
    ("Doctor sir, my temperature is 39 degree and body is shivering.", [39.0]),
    ("its 102 again after the tylenol wore off", [38.9]),
    ("Thermometer says 100.4 F", [38.0]),
    ("temp 101.3F what shud i do", [38.5]),           # guideline: >= 101.3 F is RED
    ("100 F on the dot", [37.8]),                     # guideline: 100.0 F is YELLOW
    ("101.2 F, just under what the leaflet says is urgent", [38.4]),
])
def test_parse_temperatures(text, expected):
    assert parse_temperatures(text) == expected


@pytest.mark.parametrize("text", [
    "I can bend my knee to 95 degrees at week 3. Is that good?",
    "knee bend stuck at 100 for 2 wks, wat else can i try",
    "Heart rate 125 sitting still and I'm short of breath",
    "BP also low 100/60. What to do now?",
    "nosebleed wont stop, been 40 mins, on xarelto",
    "Doctor told 35 days injection but hospital pharmacy gave only 28.",
    "Should I take Pan 40 before breakfast?",
    "Pain is 10/10, leg rock hard, the 50mg tramadol did nothing",
    "If my temperature goes above 38.5 who do I call?",
    "What temperature counts as a fever after a hip replacement?",
])
def test_non_temperature_numbers_ignored(text):
    assert temperature_override(text) is None


@pytest.mark.parametrize("text, expected", [
    ("temp 38.6", "RED"),
    ("101F", "YELLOW"),
    ("fever of 39", "RED"),
    ("39.6 is this an emergency", "RED"),
    ("38.7, 38.8, 38.6 over three checks", "RED"),   # max
    ("Fever went from 37.9 at noon to 38.6 now", "RED"),
    ("Temp came down from 38.6 to 38.2 with paracetamol", "RED"),  # labelled RED (max)
    ("Is 38.5 the cut-off? Because that's what I've got right now.", "RED"),
    ("temp 37.8 this evening", "YELLOW"),
    ("Temperature 38.4, feel okay otherwise", "YELLOW"),
    ("37.7 tonight, feeling okay", None),
])
def test_temperature_levels(text, expected):
    assert _level(text) == expected


@pytest.mark.parametrize("text", [
    "no fever",
    "No fever at all, just tired after physio",
    "temp 37.2 so no fever",
    "Temp 37.2 so no fever, but my foot is ice cold and numb",
    "No fever, 36.9, but my hip popped an hour ago",
    "I don't have a temperature and the wound isn't red.",
    "it's not 38.5, it's lower",
])
def test_negated_or_normal_temperature_is_not_an_override(text):
    assert temperature_override(text) is None


@pytest.mark.parametrize("text, expected", [
    # guideline rule 3: a clinician-assessed fever is labelled by what remains
    ("Was 38.9 two days ago, GP saw me and gave antibiotics, today 36.8 and I feel normal", None),
    ("had 39 last night but ED checked me, bloods fine, today it's 38.1", "YELLOW"),
    ("Was 38.7 last night but A&E checked me and sent me home, this morning it's 38.0", "YELLOW"),
    ("had a slight temp of 37.9 two days back, doctor saw me, now it's 36.8", None),
])
def test_clinician_cleared_readings(text, expected):
    assert _level(text) == expected


@pytest.mark.parametrize("temperature_c, expected", [
    (38.5, "RED"), (39.2, "RED"), (38.4, "YELLOW"), (37.8, "YELLOW"), (37.7, None), (36.9, None),
])
def test_request_temperature_field(temperature_c, expected):
    assert _level("when can I shower?", temperature_c) == expected


def test_request_field_and_text_take_the_max():
    assert _level("temp 37.9", 38.6) == "RED"
    assert _level("temp 38.7", 37.0) == "RED"


# The 12 unseen-scenario HIGH_FEVER RED rows the classifier (unseen M2 seed 0, thresholded) misses
# (REPORT.md Finding 8).
HIGH_FEVER_MISSES = [
    "HIGH_FEVER-005", "HIGH_FEVER-008", "HIGH_FEVER-015", "HIGH_FEVER-018", "HIGH_FEVER-022",
    "HIGH_FEVER-031", "HIGH_FEVER-033", "HIGH_FEVER-035", "HIGH_FEVER-040", "HIGH_FEVER-043",
    "HIGH_FEVER-046", "HIGH_FEVER-048",
]


@pytest.mark.parametrize("row_id", HIGH_FEVER_MISSES)
def test_report_high_fever_misses_are_red(row_id):
    row = UNSEEN_TEST[row_id]
    assert row["label"] == "RED"
    o = temperature_override(row["text"])
    assert o is not None and o.level == "RED" and o.reason == "high_fever", row["text"]


# Every challenge row that states a temperature, with the level the override must give.
CHALLENGE_TEMPERATURE = {
    "CH-006": "YELLOW", "CH-042": "YELLOW", "CH-063": "YELLOW", "CH-083": "RED",
    "CH-084": "YELLOW", "CH-085": None, "CH-086": "RED", "CH-087": "YELLOW", "CH-088": None,
    "CH-089": "RED", "CH-090": "YELLOW", "CH-091": None, "CH-092": "RED", "CH-093": "YELLOW",
    "CH-101": "RED", "CH-104": "YELLOW", "CH-106": "RED", "CH-148": "RED",
    # numbers that are not temperatures
    "CH-094": None, "CH-095": None, "CH-096": None, "CH-097": None, "CH-098": None,
    "CH-099": None, "CH-100": None, "CH-102": None, "CH-103": None,
    # negated fever wording, no number
    "CH-001": None, "CH-007": None, "CH-018": None, "CH-020": None,
}


@pytest.mark.parametrize("row_id, expected", sorted(CHALLENGE_TEMPERATURE.items()))
def test_challenge_temperature_rows(row_id, expected):
    assert _level(CHALLENGE[row_id]["text"]) == expected


def _all_labelled_rows():
    rows = {}
    for part in ("splits", "splits_unseen_scenario"):
        for name in ("train", "val", "test"):
            for r in _rows(DATA / part / f"{name}.jsonl"):
                rows.setdefault(r["id"], r)
    for r in CHALLENGE.values():
        rows.setdefault(r["id"], r)
    return list(rows.values())


def test_overrides_never_exceed_the_label_on_any_labelled_row():
    """High precision: across all 1,945 labelled messages (every split + challenge) no override
    is above the adjudicated label."""
    over = []
    for r in _all_labelled_rows():
        for o in evaluate_overrides(r["text"]):
            if LEVEL_RANK[o.level] > LEVEL_RANK[r["label"]]:
                over.append((r["id"], r["label"], o.level, o.reason, r["text"]))
    assert over == []


def test_every_challenge_row_override_at_or_below_label():
    for r in CHALLENGE.values():
        for o in evaluate_overrides(r["text"]):
            assert LEVEL_RANK[o.level] <= LEVEL_RANK[r["label"]], (r["id"], r["text"])


# ---------------------------------------------------------------------------
# Self-harm
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Some nights I think everyone would be better off without me. I've been looking at my "
    "tablets and thinking about it.",
    "I am feeling there is no point to live now. I am only burden on my children. Sometimes I "
    "think to end it.",
    "My husband told me tonight he doesn't want to wake up any more.",
    "I keep having thoughts about hurting myself. I don't want to feel like this.",
    "everyone would be better off without me",
    "I just want to end it",
    "I want to end it all",
    "looking at my tablets and thinking",
    "I've been feeling suicidal since the operation",
    "I want to kill myself",
    "I don't want to live like this any more",
    "I wish I was dead",
    "I want to die",
    "thinking about taking my own life",
    "Not suicidal but sometimes I think everyone would be better off without me",
    "I’m going to hurt myself",                     # curly apostrophe
])
def test_self_harm_positive(text):
    o = self_harm_override(text)
    assert o is not None and o.level == "RED" and o.reason == "self_harm"
    assert o.category == "mental_health_crisis"


@pytest.mark.parametrize("text", [
    "Not suicidal or anything like that, just really fed up and grumpy today. Normal at week 3?",
    "A friend said people sometimes feel suicidal after big operations. Is that true, and who "
    "would I call if it ever happened?",
    "I have no thoughts of harming myself",
    "I'm not going to hurt myself, I'm just low",
    "I never want to kill myself, I'm just tired",
    "If I cut myself while on blood thinners, how long should I press on it?",
    "cut myself shaving n it bled for ages b4 stopping, im on the thinner tabs",
    "I fell and hurt myself on the stairs",
    "Nearly fell when the walker caught on the rug, but I caught myself and didn't land",
    "When can I end it early, the injections I mean?",
    "fell off the step, cant stand on my leg now, its killin me",
    "Killer workout at physio today, my legs are dead tired but in a good way",
    "honestly not coping, havent slept properly in 4 nights",
    "Can I take all my tablets together in the morning?",
])
def test_self_harm_negative(text):
    assert self_harm_matches(text) == [], text


def test_self_harm_mood_rows_in_data():
    """Every RED MOOD_SLEEP row fires; no GREEN/YELLOW row anywhere fires self-harm."""
    for r in _all_labelled_rows():
        fired = self_harm_override(r["text"]) is not None
        if r.get("scenario_id") == "MOOD_SLEEP" and r["label"] == "RED":
            assert fired, r["text"]
        if r["label"] != "RED":
            assert not fired, r["text"]
