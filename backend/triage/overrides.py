"""Deterministic, high-precision triage overrides that run in front of the classifier.

Two overrides, both pure functions of the message text (plus the request's own
``temperature_c`` field). They only ever RAISE the level; the hybrid engine takes
max(overrides, classifier), so an override can never lower a classifier RED.

1. **Temperature** (``temperature_override``). REPORT.md Finding 8: on unseen scenarios the
   classifier misses 12 of 50 RED HIGH_FEVER messages, every one of which states a temperature
   >= 38.5 °C ("39.6 is ths an emergency", "38.7, 38.8, 38.6 over the last three checks").
   A sentence embedding does not compare 38.6 with 38.5, so the number is read here.
   Thresholds are the guideline's (LABELLING_GUIDELINE.md rule 5, the same as
   SafetyTriageEngine's ``temperature_c`` branch): >= 38.5 °C RED, 37.8-38.4 °C YELLOW floor.

2. **Self-harm / suicidal ideation** (``self_harm_override``). RED with reason ``self_harm`` and
   ``category="mental_health_crisis"`` so the orchestrator answers with crisis guidance
   (MENTAL_HEALTH_CRISIS_TEMPLATE), not orthopaedic advice. Negation-aware ("not suicidal",
   "no thoughts of harming myself") and skips general questions ("people sometimes feel suicidal
   after big operations - is that true?").

Neither override uses an LLM or the classifier.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

RED_TEMP_C = 38.5
YELLOW_TEMP_C = 37.8

LEVEL_RANK = {"GREEN": 1, "YELLOW": 2, "RED": 3}


@dataclass
class Override:
    level: str                       # "RED" | "YELLOW"
    reason: str                      # machine name: "high_fever" | "moderate_fever" | "self_harm"
    detail: str = ""                 # human-readable evidence
    category: Optional[str] = None   # "mental_health_crisis" for self-harm
    evidence: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Temperature
# ---------------------------------------------------------------------------

# Words that make an otherwise bare number a temperature reading.
_FEVER_CONTEXT = re.compile(
    r"\b(?:fever\w*|febrile|pyrexi\w*|temp|temps|temperature\w*|temprature\w*|tempreture\w*|tmp|"
    r"thermometer\w*|reading|readings)\b|°",
    re.IGNORECASE,
)
# Antipyretics: enough context for a Fahrenheit-range integer ("its 102 again after the tylenol").
_ANTIPYRETIC = re.compile(
    r"\b(?:tylenol|paracetamol|panadol|crocin|dolo|calpol|acetaminophen|ibuprofen|advil|nurofen)\b",
    re.IGNORECASE,
)

# A number, optionally followed by a temperature unit.
_NUMBER = re.compile(
    r"(?<![\w./])(?P<num>\d{2,3}(?:\.\d{1,2})?)"
    r"(?P<unit>\s*(?:°|º|�)\s*[cf]?\b|\s*(?:deg(?:ree)?s?\.?)\s*(?:[cf]\b|celsius|centigrade|fahrenheit)?"
    r"|\s*(?:celsius|centigrade|fahrenheit)\b|\s*[cf]\b)?",
    re.IGNORECASE,
)

# A number followed by one of these is not a temperature (doses, ages, durations, angles...).
_NON_TEMP_UNIT_AFTER = re.compile(
    r"^\s*(?:mg|mcg|µg|g|gm|kg|kgs|lb|lbs|ml|cc|mm|cm|m|km|%|percent|years?|yrs?|yo|y/o|"
    r"days?|hrs?|hours?|mins?|minutes?|secs?|seconds?|weeks?|wks?|months?|steps|bpm|beats|"
    r"times|tablets?|tabs?|pills?|mmhg|units?|iu|/|:|-?(?:st|nd|rd|th)\b)",
    re.IGNORECASE,
)
# A number preceded by one of these is not a temperature reading.
_NON_TEMP_WORD_BEFORE = re.compile(
    r"\b(?:day|days|week|weeks|wk|month|room|bed|ward|page|aged|age|pan|dolo|crocin|pulse|hr|"
    r"heart\s*rate|bp|sats?|spo2|o2|oxygen|saturation|bend|flexion|extension|angle|no\.?|number)"
    r"\s*(?:of|at|is|was|to|:|=)?\s*$",
    re.IGNORECASE,
)
# "above 38.5", "if it goes over 38" - a threshold, not a reading.
_COMPARATOR_BEFORE = re.compile(
    r"\b(?:above|over|exceeds?|exceeding|more\s+than|higher\s+than|greater\s+than|below|under|"
    r"less\s+than|lower\s+than|cut-?off\s+(?:is|of))\s*$",
    re.IGNORECASE,
)
# "not 38.5", "isn't 39" - a denied reading.
_NEGATED_BEFORE = re.compile(
    r"\b(?:not|isn'?t|wasn'?t|never|no\s+longer|nowhere\s+near)\s*(?:a|at|even)?\s*$",
    re.IGNORECASE,
)
# Clinician has already assessed the fever (guideline rule 3): only readings AFTER this count.
_CLINICIAN_CLEARED = re.compile(
    r"\b(?:gp|doctor|dr\.?|a\s*&\s*e|a\s+and\s+e|ed|er|nurse|hospital|clinic|surgeon|consultant)\b"
    r"[^.?!]{0,25}?\b(?:saw|seen|checked|examined|sent\s+(?:me|him|her)\s+home|assessed|reviewed|"
    r"cleared)\b",
    re.IGNORECASE,
)
# "if my temperature goes above ..." style hypothetical with a number but no reading.
_HYPOTHETICAL_BEFORE = re.compile(r"\b(?:if|when|should)\b[^.?!,]{0,30}$", re.IGNORECASE)


def _to_celsius(value: float, unit: str) -> Optional[float]:
    """Convert a parsed number to °C (rounded to 0.1, which matches the guideline's
    100.0-101.2 °F YELLOW / >= 101.3 °F RED bands). None if it is not a body temperature."""
    unit = (unit or "").strip().lower()
    fahrenheit = unit.endswith("f") or "fahrenheit" in unit
    celsius = unit.endswith("c") or "celsius" in unit or "centigrade" in unit
    if not fahrenheit and not celsius:
        if 34.0 <= value <= 43.0:
            celsius = True
        elif 93.0 <= value <= 108.0:
            fahrenheit = True
        else:
            return None
    if fahrenheit:
        if not 93.0 <= value <= 108.0:
            return None
        return round((value - 32.0) * 5.0 / 9.0 + 1e-9, 1)
    if not 34.0 <= value <= 43.0:
        return None
    return round(value, 1)


def parse_temperatures(text: str) -> List[float]:
    """Every body-temperature reading stated in `text`, in °C, in order of appearance.

    A number counts when it is a plausible body temperature AND
      - it carries a temperature unit (°C, °F, 101F, 38.6C, "39 degree" with fever context), or
      - the message has fever context (fever / temp / thermometer / reading ...), or
      - it has a decimal point (38.6, 101.5: almost never anything else in this domain), or
      - it is a Fahrenheit-range integer and an antipyretic is mentioned.
    Numbers are skipped when they are doses / durations / ages / angles, thresholds
    ("above 38.5", "if it goes over 38"), denied ("not 38.5"), or were reported before a
    clinician assessed the fever ("had 39 last night but ED checked me ... today 38.1" -> [38.1]).
    """
    if not text:
        return []
    cleared = None
    for m in _CLINICIAN_CLEARED.finditer(text):
        cleared = m.end()
    has_context = bool(_FEVER_CONTEXT.search(text))
    has_antipyretic = bool(_ANTIPYRETIC.search(text))

    temps: List[float] = []
    for m in _NUMBER.finditer(text):
        if cleared is not None and m.start() < cleared:
            continue
        raw, unit = m.group("num"), (m.group("unit") or "")
        before, after = text[:m.start()], text[m.end():]
        if _NON_TEMP_UNIT_AFTER.match(after) and not unit.strip():
            continue
        if _NON_TEMP_WORD_BEFORE.search(before[-25:]):
            continue
        if _COMPARATOR_BEFORE.search(before[-20:]):
            continue
        if _NEGATED_BEFORE.search(before[-20:]):
            continue
        clause_before = re.split(r"[.?!;]", before)[-1]
        if (_HYPOTHETICAL_BEFORE.search(clause_before)
                and re.search(r"\b(?:goes|go|gets|get|reach\w*|hits?|rises?|climbs?)\b",
                              clause_before, re.IGNORECASE)):
            continue
        unit_s = unit.strip().lower()
        is_degree_word = unit_s.startswith("deg")
        explicit_unit = bool(unit_s) and not (is_degree_word and not has_context)
        if is_degree_word and not has_context:
            continue  # "bend my knee to 95 degrees"
        value = float(raw)
        has_decimal = "." in raw
        if not (explicit_unit or has_context or has_decimal):
            if not (has_antipyretic and 99 <= value <= 107):
                continue
        c = _to_celsius(value, unit_s if explicit_unit and not is_degree_word else
                        (unit_s[-1:] if is_degree_word and unit_s[-1:] in ("c", "f") else ""))
        if c is not None:
            temps.append(c)
    return temps


def temperature_override(text: str, temperature_c: Optional[float] = None) -> Optional[Override]:
    """RED for >= 38.5 °C, YELLOW for 37.8-38.4 °C, from the text and/or the request field.
    Uses the HIGHEST reading ("38.7, 38.8, 38.6 over three checks" -> 38.8)."""
    readings = parse_temperatures(text)
    sources = [f"text:{t}" for t in readings]
    if temperature_c is not None:
        try:
            readings.append(round(float(temperature_c), 1))
            sources.append(f"temperature_c:{float(temperature_c)}")
        except (TypeError, ValueError):
            pass
    if not readings:
        return None
    peak = max(readings)
    if peak >= RED_TEMP_C:
        return Override("RED", "high_fever", f"Temperature {peak} °C >= {RED_TEMP_C} °C",
                        evidence=sources)
    if peak >= YELLOW_TEMP_C:
        return Override("YELLOW", "moderate_fever",
                        f"Temperature {peak} °C (>= {YELLOW_TEMP_C} °C, < {RED_TEMP_C} °C)",
                        evidence=sources)
    return None


# ---------------------------------------------------------------------------
# Self-harm / suicidal ideation
# ---------------------------------------------------------------------------

_SELF = r"(?:my|him|her|them|your)sel(?:f|ves)"
_INTENT = (r"(?:thoughts?\s+(?:of|about)|thinking\s+(?:of|about)|thought\s+(?:of|about)|"
           r"want(?:s|ed)?\s+to|wanna|going\s+to|gonna|urges?\s+to|tempted\s+to|feel\s+like|"
           r"plan(?:s|ning)?\s+to|might|could\s+just|keep\s+(?:wanting|thinking))")

# (pattern, negation_check). Patterns whose wording already contains the negation that makes
# them a crisis signal ("don't want to live") are not negation-checked.
_SELF_HARM_PATTERNS = [
    (r"\bsuicid\w*", True),
    (r"\bself[- ]?harm\w*", True),
    (rf"\bkill(?:ing)?\s+{_SELF}\b", True),
    (rf"\bharm(?:ing)?\s+{_SELF}\b", True),
    (rf"\b{_INTENT}\s+(?:\w+\s+){{0,2}}(?:hurt|hurting|cut|cutting|injure|injuring)\s+{_SELF}\b", True),
    (r"\b(?:end|ending|take|taking)\s+(?:my|his|her|their)\s+(?:own\s+)?life\b", True),
    (r"\bend\s+it\s+all\b", True),
    (r"\b(?:think|thinking|thought|thoughts|want|wanted|wanna|going|gonna|plan|planning|ready|"
     r"just)\b(?:\s+\w+){0,2}\s+end\s+it\b(?!\s+(?:early|sooner|now|today|after|before|when|once|"
     r"with|for\b))", True),
    (r"\bbetter\s+off\s+(?:dead|without\s+(?:me|him|her|us)|if\s+(?:i|he|she)\s+(?:was|were)"
     r"(?:n'?t|\s+not)\s+(?:here|around|alive))\b", True),
    (r"\b(?:want|wanted|wanting|wants|wish|wishing)\s+to\s+die\b", True),
    (r"\bwish\s+(?:i|he|she)\s+(?:was|were|had\s+been)\s+dead\b", True),
    (r"\bwish\s+(?:i|he|she)\s+(?:was|were)(?:n'?t|\s+not)\s+(?:here|around|alive)\b", True),
    (r"\b(?:rather|prefer\s+to)\s+be\s+dead\b", True),
    (r"\b(?:don'?t|do\s+not|doesn'?t|does\s+not|didn'?t|did\s+not)\s+want\s+to\s+"
     r"(?:live|be\s+alive|exist|go\s+on|carry\s+on|wake\s+up|be\s+here\s+any\s*more)\b", False),
    (r"\b(?:no|not\s+any|nothing)\s+(?:point|reason)\s+(?:in\s+|to\s+|for\s+)?"
     r"(?:living|live|life|go(?:ing)?\s+on|carry(?:ing)?\s+on|being\s+(?:here|alive))\b", False),
    (r"\b(?:hope|hoping|wish|wishing)\b[^.?!]{0,25}\b(?:don'?t|not|never)\s+wake\s+up\b", False),
    (r"\b(?:sleep|asleep)\s+and\s+(?:not|never)\s+wake\s+up\b", False),
    (r"\bcan'?t\s+go\s+on\s+living\b", False),
    (r"\b(?:looking\s+at|staring\s+at|counting|saving\s+up|stockpiling|hoarding)\s+"
     r"(?:all\s+)?(?:my|the|his|her)\s+(?:tablets|pills|meds|medicines?|medication|painkillers)\b"
     r"[^.?!]{0,40}\b(?:thinking|think|thought|about\s+it|all\s+at\s+once|take\s+them\s+all)\b", True),
    (r"\b(?:deliberately|intentionally|on\s+purpose)\s+(?:overdos\w*|took\s+too\s+many)\b"
     r"|\boverdos\w*\s+on\s+purpose\b", True),
]
_SELF_HARM_RE = [(re.compile(p, re.IGNORECASE), neg) for p, neg in _SELF_HARM_PATTERNS]

_NEGATION_CUE = re.compile(
    r"\b(?:not|never|no|nor|without|don'?t|do\s+not|doesn'?t|didn'?t|isn'?t|am\s+not|i'?m\s+not|"
    r"wasn'?t|haven'?t|hasn'?t|nothing\s+like)\b|n't\b",
    re.IGNORECASE,
)
# General / informational framing: not a disclosure about this patient.
_GENERAL_CUE = re.compile(
    r"\b(?:people|patients|is\s+it\s+(?:normal|common)|"
    r"what\s+are\s+the\s+signs|if\s+(?:i|it|they)\s+ever)\b",
    re.IGNORECASE,
)
_CLAUSE_SPLIT = re.compile(r"[.?!;,]|\b(?:but|however|though|although|yet)\b", re.IGNORECASE)


def _clause_before(text: str, start: int) -> str:
    return _CLAUSE_SPLIT.split(text[:start])[-1]


def self_harm_matches(text: str) -> List[str]:
    """The self-harm phrases found in `text` that are neither negated nor general questions."""
    found: List[str] = []
    if not text:
        return found
    norm = text.replace("’", "'").replace("‘", "'")
    for rx, negation_check in _SELF_HARM_RE:
        for m in rx.finditer(norm):
            clause = _clause_before(norm, m.start())
            if _GENERAL_CUE.search(clause):
                continue
            if negation_check:
                tokens = clause.split()
                window = " ".join(tokens[-6:])
                if _NEGATION_CUE.search(window):
                    continue
            found.append(m.group(0))
    return found


def self_harm_override(text: str) -> Optional[Override]:
    hits = self_harm_matches(text)
    if not hits:
        return None
    return Override("RED", "self_harm", "Possible self-harm or suicide risk disclosed",
                    category="mental_health_crisis", evidence=hits)


# ---------------------------------------------------------------------------

def evaluate_overrides(text: str, temperature_c: Optional[float] = None) -> List[Override]:
    """All overrides that fire for this message (self-harm first)."""
    out: List[Override] = []
    for o in (self_harm_override(text), temperature_override(text, temperature_c)):
        if o is not None:
            out.append(o)
    return out
