"""
Dynamic Orthopedic Patient Report Extractor.

Extracts structured fields (name, age, sex, diagnosis, surgery date,
surgery type, prescriptions, current plan) from an arbitrary PDF patient
report -- WITHOUT being hardcoded to any single layout or terminology.

Design:

    PDF file
        v
    Raw text extraction (pdfplumber)
        v
    LLM-based field extraction (local Ollama model)
        v
    Robust JSON parsing (handles markdown fences, stray text)
        v
    Structured dict, every field independently nullable

Why an LLM and not regex/rules:
    The requirement is explicit -- the tool must handle a NEWLY uploaded
    report with a "completely different layout" or "different fields"
    than any seen before. A fixed set of regexes/labels is exactly the
    kind of hardcoding that breaks the first time terminology changes
    ("Rx" vs "Medications Prescribed" vs "Discharge Meds" vs a narrative
    paragraph with no label at all -- see synthetic_report_generator.py's
    5 deliberately different formats). An LLM reading the raw text and
    reasoning about what the diagnosis/surgery/medications ARE, rather
    than where a specific label sits, generalizes to formats it has
    never seen. Regex is used only as a very small, best-effort SAFETY
    NET if the LLM is completely unavailable -- see _regex_fallback().

This mirrors the exact same "local Ollama over HTTP" pattern already
used in agents/chat_agent.py -- same endpoint, same failure handling
style -- rather than introducing a second way of talking to the LLM.
"""

from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

import pdfplumber

OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = "llama3.2"

REQUIRED_FIELDS = (
    "full_name",
    "age",
    "sex",
    "diagnosis",
    "surgery_date",
    "surgery_type",
    "prescriptions",
    "current_medical_plan",
)


@dataclass
class ExtractionResult:
    full_name: Optional[str] = None
    age: Optional[str] = None
    sex: Optional[str] = None
    diagnosis: Optional[str] = None
    surgery_date: Optional[str] = None
    surgery_type: Optional[str] = None
    prescriptions: List[str] = None
    current_medical_plan: Optional[str] = None

    # Not a patient field -- diagnostic info for the admin dashboard so
    # a reviewer can see HOW the value was obtained.
    extraction_method: str = "unknown"
    raw_text_preview: str = ""
    warnings: List[str] = None

    def __post_init__(self):
        if self.prescriptions is None:
            self.prescriptions = []
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# STEP 1 -- RAW TEXT EXTRACTION
# ============================================================================


def extract_pdf_text(pdf_path: str) -> str:
    """
    Extracts all text from every page of the PDF, preserving reading
    order. Works regardless of layout (paragraphs, tables, forms) --
    pdfplumber's extract_text() reads a table's cells as plain text too,
    which is enough for the LLM step to work with.
    """
    text_parts: List[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text)

            # Tables sometimes extract poorly as plain text (e.g. the
            # label/value columns run together) -- explicitly walking
            # table cells too gives the LLM a cleaner second view of the
            # same content rather than relying on extract_text() alone.
            for table in page.extract_tables():
                for row in table:
                    cells = [str(cell).strip() for cell in row if cell]
                    if cells:
                        text_parts.append(" | ".join(cells))

    return "\n".join(text_parts).strip()


# ============================================================================
# STEP 2 -- LLM-BASED FIELD EXTRACTION
# ============================================================================


_EXTRACTION_PROMPT_TEMPLATE = """You are a medical records extraction assistant. You will be given the raw text of an orthopedic patient report. The report's LAYOUT AND TERMINOLOGY MAY VARY -- it could be a labeled form, a table, or a narrative paragraph, and different reports use different words for the same thing (e.g. "Rx", "Medications Prescribed", and "Discharge Meds" all mean the same field).

Your job is to read the text and extract the following fields, understanding their MEANING rather than looking for exact label matches:

- full_name: the patient's full name
- age: the patient's age as stated or directly computable from a stated date of birth (do not guess if not present)
- sex: the patient's sex/gender (Male/Female/M/F as stated)
- diagnosis: the medical diagnosis or presenting condition
- surgery_date: the date the surgery/operation/procedure was performed (return it in the format it appears in the source text; do not reformat or guess a date)
- surgery_type: the name of the surgical procedure performed
- prescriptions: a list of medications prescribed, each as a separate string (include dose/frequency if stated)
- current_medical_plan: the current treatment/follow-up/recovery plan

CRITICAL RULES:
1. If a field is genuinely not present in the text, return null for it (or an empty list for prescriptions). DO NOT invent, guess, or infer a value that isn't actually stated or directly computable.
2. Extract information based on MEANING, not exact label text -- the report will not always use the exact field names above.
3. Return ONLY a single JSON object with exactly these keys: full_name, age, sex, diagnosis, surgery_date, surgery_type, prescriptions, current_medical_plan. No markdown code fences, no explanation, no extra text before or after the JSON.

REPORT TEXT:
---
{report_text}
---

JSON:"""


def _call_ollama(prompt: str, timeout: int = 90) -> Optional[str]:
    """
    Same local-Ollama-over-HTTP pattern as agents/chat_agent.py --
    reused deliberately rather than introducing a second LLM-calling
    convention in the codebase.

    timeout=90 (not 30): the FIRST request after Ollama starts has to
    load the model into memory (can take 10-20+ seconds alone on CPU),
    and this prompt is long (full report text + detailed instructions),
    so a low timeout can fail even when Ollama is working correctly.
    """
    payload = {
        "model": DEFAULT_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,  # deterministic extraction, not creative writing
            "num_predict": 700,
        },
    }

    try:
        req = urllib.request.Request(
            OLLAMA_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            response_text = data.get("response", "").strip()
            print(f"[EXTRACTOR] Ollama responded ({len(response_text)} chars).")
            return response_text
    except urllib.error.URLError as exc:
        print(f"[EXTRACTOR] Ollama connection failed: {exc}")
        return None
    except Exception as exc:
        print(f"[EXTRACTOR] Ollama call failed unexpectedly: {type(exc).__name__}: {exc}")
        return None


def _parse_llm_json(raw_response: str) -> Optional[Dict[str, Any]]:
    """
    LLMs frequently wrap JSON in ```json fences or add a sentence before
    /after it despite instructions. This strips common wrapping before
    attempting json.loads, and falls back to extracting the first
    {...} block if the whole string isn't valid JSON on its own.
    """
    if not raw_response:
        return None

    text = raw_response.strip()

    # Strip markdown code fences if present.
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"[EXTRACTOR] Direct JSON parse failed: {exc}")

    # Fallback: find the first {...} block and try that.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            print(f"[EXTRACTOR] Fallback JSON parse also failed: {exc}")
            print(f"[EXTRACTOR] Raw LLM response was:\n{raw_response[:1000]}")
            return None

    print(f"[EXTRACTOR] No JSON object found in LLM response at all. Raw response:\n{raw_response[:1000]}")
    return None


def _normalise_llm_fields(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Coerces the parsed JSON into the exact shape ExtractionResult
    expects, defaulting anything missing/malformed to None/[] rather
    than raising -- a partially-good LLM response should still produce
    a partially-filled result, not a hard failure.
    """
    result: Dict[str, Any] = {}

    for field in REQUIRED_FIELDS:
        value = parsed.get(field)

        if field == "prescriptions":
            if isinstance(value, list):
                result[field] = [str(v).strip() for v in value if str(v).strip()]
            elif isinstance(value, str) and value.strip():
                # Some models return a single string instead of a list --
                # accept it as a one-item list rather than discarding it.
                result[field] = [value.strip()]
            else:
                result[field] = []
            continue

        if value in (None, "", "null", "N/A", "n/a"):
            result[field] = None
        else:
            result[field] = str(value).strip()

    return result


# ============================================================================
# STEP 3 -- SAFETY-NET REGEX FALLBACK (only used if the LLM is unreachable)
# ============================================================================


def _regex_fallback(report_text: str) -> Dict[str, Any]:
    """
    Best-effort ONLY. This is intentionally minimal -- it exists so the
    tool degrades gracefully (some fields, clearly marked as
    low-confidence) instead of returning nothing at all if Ollama is
    down, NOT as the primary extraction strategy. It will not handle
    the full variety of real-world report formats; that's the LLM's
    job. Every field found this way is flagged in `warnings` so the
    dashboard can visually mark it as needing manual review.
    """
    result: Dict[str, Any] = {field: None for field in REQUIRED_FIELDS}
    result["prescriptions"] = []

    patterns = {
        "full_name": r"(?:patient(?:'s)?\s*name|pt\.?\s*name|full name|patient)\s*[:\-]\s*([A-Za-z.\s]+?)(?:\n|$)",
        "age": r"age\s*[:/\-]?\s*(\d{1,3})",
        "sex": r"(?:sex|gender)\s*[:/\-]\s*(male|female|m|f)\b",
        "surgery_date": r"(?:date of (?:surgery|operation|theatre)|surgery date)\s*[:\-]\s*([\w\-/,\.\s]+?)(?:\n|$)",
    }

    for field, pattern in patterns.items():
        match = re.search(pattern, report_text, re.IGNORECASE)
        if match:
            result[field] = match.group(1).strip()

    return result


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


def extract_report(pdf_path: str) -> ExtractionResult:
    """
    Full pipeline: PDF -> text -> LLM extraction -> structured result.
    Falls back to a minimal regex safety net (clearly flagged) only if
    the LLM is completely unreachable or returns unparseable output.
    """
    report_text = extract_pdf_text(pdf_path)

    if not report_text.strip():
        return ExtractionResult(
            extraction_method="failed",
            warnings=["No extractable text found in this PDF (it may be a scanned image -- OCR is not yet wired in)."],
        )

    prompt = _EXTRACTION_PROMPT_TEMPLATE.format(report_text=report_text)
    llm_response = _call_ollama(prompt)

    parsed = _parse_llm_json(llm_response) if llm_response else None

    if parsed is not None:
        fields = _normalise_llm_fields(parsed)
        return ExtractionResult(
            **fields,
            extraction_method="llm",
            raw_text_preview=report_text[:500],
            warnings=[],
        )

    # LLM unreachable or returned unparseable output -- degrade to the
    # minimal regex safety net rather than failing outright.
    fallback_fields = _regex_fallback(report_text)
    return ExtractionResult(
        **fallback_fields,
        extraction_method="regex_fallback",
        raw_text_preview=report_text[:500],
        warnings=[
            "The local LLM was unavailable or returned an unparseable response. "
            "These fields were extracted with a limited pattern-matching fallback "
            "and should be manually verified -- diagnosis, surgery type, "
            "prescriptions, and current plan could not be extracted this way "
            "(they require language understanding, not pattern matching)."
        ],
    )