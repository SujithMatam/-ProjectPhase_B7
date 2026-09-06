"""
LAM Scope Validator -- Algorithm 1 implementation.

Determines whether a patient query belongs to the orthopedic post-op care
domain AND whether the anatomical region is within the supported set.

Supported regions (hip and below-hip lower-extremity):
  hip, knee, lower leg, tibia, fibula, ankle, foot

Key rule (avoids false rejection):
  When the query text contains NO explicit anatomical region keyword,
  the validator falls back to the patient's surgery_type context to infer
  the region -- but ONLY when the query also contains at least one clinical
  intent signal (e.g. a health/recovery-related word).  Purely off-topic
  queries that happen to share a surgery keyword are still rejected.

All keyword matching uses regex word boundaries to prevent substring false
positives (e.g. 'eat' inside 'weather', 'leg' inside 'college').

Returns:
  (ScopeStatus, reason: str)
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Tuple
from lam.schemas import ScopeStatus

# ---------------------------------------------------------------------------
# Vocabulary sets
# ---------------------------------------------------------------------------

# Primary orthopedic post-op domain keywords.
# Presence of any of these anchors the query in the clinical domain.
_DOMAIN_KEYWORD_LIST: list[str] = [
    # clinical concepts
    "surgery", "operation", "procedure", "surgical", "post-op", "postop",
    "post op", "recovery", "rehabilitation", "rehab", "physical therapy",
    "physio", "physiotherapy", "exercise", "exercises", "mobility",
    # symptoms & wound
    "pain", "swelling", "swell", "bruising", "bruise", "wound", "incision",
    "staples", "stitches", "suture", "drainage", "bandage", "dressing",
    "redness", "infection",
    # medication & clinical care
    "medication", "medicine", "painkiller", "paracetamol", "ibuprofen",
    "opioid", "anticoagulant", "blood thinner", "aspirin", "icing",
    "elevation", "elevate", "crutches", "walker", "brace",
    # activity & nutrition
    "weight bearing", "diet", "eating", "nutrition",
    "showering", "bathing", "driving", "return to work",
    # mental health in recovery context
    "anxious", "anxiety", "depressed", "depression", "mental health",
    "mood", "stressed", "stress", "worried",
    # orthopedic anatomy / procedures (also serve as region signals)
    "hip", "knee", "ankle", "foot", "tibia", "fibula", "femur",
    "lower leg", "calf", "thigh", "joint", "bone", "ligament",
    "tendon", "cartilage", "implant", "prosthesis", "arthroplasty",
    "replacement", "fracture", "fixation", "orif", "tka", "tha",
]

# Secondary clinical-intent words -- used ONLY in the surgery-type fallback.
# Words that signal health/recovery intent without naming a body part.
# Use whole-word-safe tokens only (no substring traps).
_CLINICAL_INTENT_LIST: list[str] = [
    "normal", "safe", "allowed", "should i", "when can", "how long",
    "how much", "feel", "feeling", "sleep", "sleeping", "walk", "walking",
    "sit", "standing", "ice", "heat", "numb", "nausea", "dizzy",
    "healing", "hurt", "hurts", "sore", "tired", "fatigue",
    "drink", "shower", "drive", "work",
]

# Supported anatomical regions (hip and below-hip lower-extremity only).
# Multi-word entries listed first so they are matched before their sub-words.
_SUPPORTED_REGION_LIST: list[str] = [
    "lower leg", "tibia", "fibula",
    "hip", "knee", "ankle", "foot", "calf",
]

# Explicitly unsupported regions.
_UNSUPPORTED_REGION_LIST: list[str] = [
    "shoulder", "elbow", "wrist", "hand", "finger", "thumb",
    "spine", "back", "neck", "cervical", "lumbar", "thoracic",
    "rotator cuff",
]

# Surgery-type keyword -> inferred supported region (for fallback)
SURGERY_TYPE_REGION_MAP: dict[str, str] = {
    "hip":       "hip",
    "knee":      "knee",
    "tibia":     "tibia",
    "fibula":    "fibula",
    "ankle":     "ankle",
    "foot":      "foot",
    "lower leg": "lower leg",
    "fracture":  "leg",
}


# ---------------------------------------------------------------------------
# Pre-compiled regex helpers
# ---------------------------------------------------------------------------

def _build_pattern(terms: list[str]) -> re.Pattern:
    """Build a single OR regex with word boundaries for a list of terms."""
    escaped = sorted((re.escape(t) for t in terms), key=len, reverse=True)
    return re.compile(r'\b(?:' + '|'.join(escaped) + r')\b', re.IGNORECASE)

@lru_cache(maxsize=None)
def _domain_re()     -> re.Pattern: return _build_pattern(_DOMAIN_KEYWORD_LIST)
@lru_cache(maxsize=None)
def _intent_re()     -> re.Pattern: return _build_pattern(_CLINICAL_INTENT_LIST)
@lru_cache(maxsize=None)
def _supported_re()  -> re.Pattern: return _build_pattern(_SUPPORTED_REGION_LIST)
@lru_cache(maxsize=None)
def _unsupported_re()-> re.Pattern: return _build_pattern(_UNSUPPORTED_REGION_LIST)

# Expose DOMAIN_KEYWORDS as a frozenset for external use (e.g. tests)
DOMAIN_KEYWORDS: frozenset[str] = frozenset(_DOMAIN_KEYWORD_LIST)
CLINICAL_INTENT_WORDS: frozenset[str] = frozenset(_CLINICAL_INTENT_LIST)
SUPPORTED_REGIONS: list[str] = _SUPPORTED_REGION_LIST
UNSUPPORTED_REGIONS: list[str] = _UNSUPPORTED_REGION_LIST


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class ScopeValidator:
    """
    Implements Algorithm 1: orthopedic post-op domain and region scope check.

    Usage:
        status, reason = ScopeValidator.validate(query, surgery_type)
    """

    @classmethod
    def validate(
        cls,
        query: str,
        surgery_type: str,
    ) -> Tuple[ScopeStatus, str]:
        """
        Returns (ScopeStatus.IN_SCOPE, reason) or (ScopeStatus.OUT_OF_SCOPE, reason).

        All matching uses word-boundary regex to prevent substring false positives.

        Algorithm:
          1. Reject queries that explicitly mention an unsupported body region.
          2. Check whether the query contains at least one primary domain keyword.
             If yes -> IN_SCOPE (region may be explicit or inferred from context).
          3. No primary domain keyword: check for a clinical-intent word AND a
             surgery-type-inferable region (fallback for natural phrasing like
             'Is that normal?' from a hip patient -- region inferred from context).
          4. No signal found -> OUT_OF_SCOPE.
        """
        lower_surgery = surgery_type.lower()

        # Step 1 -- explicit unsupported region
        if _unsupported_re().search(query):
            m = _unsupported_re().search(query)
            return (
                ScopeStatus.OUT_OF_SCOPE,
                f"Query mentions '{m.group()}', which is outside the supported "
                "hip-and-below-hip orthopedic post-op scope.",
            )

        # Step 2 -- primary domain keyword present
        if _domain_re().search(query):
            region_match = _supported_re().search(query)
            return (
                ScopeStatus.IN_SCOPE,
                "Query contains orthopedic domain signal"
                + (f" and mentions supported region '{region_match.group()}'."
                   if region_match
                   else f"; region inferred from surgery context ('{surgery_type}')."),
            )

        # Step 3 -- surgery-type fallback (requires clinical-intent word in query)
        if _intent_re().search(query):
            for keyword, inferred_region in SURGERY_TYPE_REGION_MAP.items():
                if keyword in lower_surgery:
                    return (
                        ScopeStatus.IN_SCOPE,
                        f"No explicit domain keyword; clinical intent detected and "
                        f"region '{inferred_region}' inferred from surgery context "
                        f"('{surgery_type}').",
                    )

        # Step 4 -- no signal
        return (
            ScopeStatus.OUT_OF_SCOPE,
            "Query does not appear to be related to orthopedic post-operative care. "
            "No domain keywords, supported anatomical regions, or clinical intent detected.",
        )
