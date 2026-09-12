"""
LAM Scope Validator -- Algorithm 1 implementation (revised).

Determines whether a patient query belongs to the orthopedic post-op care
domain AND whether the anatomical region is within the supported set.

DESIGN CHANGE FROM ORIGINAL:
The original implementation used a whitelist-only approach: a query was
rejected unless it matched a keyword in a fixed domain/intent list. This
caused false rejections for any natural phrasing the list didn't happen to
cover (e.g. "Can I climb stairs yet?", "When can I bend down to tie my
shoes?") -- since every user of this app is a known post-op patient talking
to a dedicated recovery assistant, treating unmatched queries as suspicious
by default is the wrong prior.

This version flips the default: a query is IN_SCOPE unless it is either
(a) explicitly about an unsupported anatomical region, or
(b) clearly about a topic unrelated to health/recovery at all (weather,
    sports scores, general trivia, coding help, etc.), detected via a
    small set of distinctly non-clinical topic signals.

This is intentionally permissive at the boundary -- false negatives here
(deflecting a real recovery question) are worse for patient trust and
safety than the rare false positive (answering a mildly off-topic question
that isn't actually harmful).

Supported regions (hip and below-hip lower-extremity):
  hip, knee, lower leg, tibia, fibula, ankle, foot

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

# Explicitly unsupported anatomical regions -- these always reject,
# regardless of other content in the query.
# NOTE: "back" is deliberately NOT a bare trigger word here. Common phrasing
# like "2 days back" (meaning "ago", especially in Indian English) or "I'm
# back at work" would falsely match a bare "back" and reject an unrelated,
# perfectly in-scope message. Instead, back/spine mentions require a
# co-occurring body/pain-context word (see _is_back_pain_context below).
_UNSUPPORTED_REGION_LIST: list[str] = [
    "shoulder", "elbow", "wrist", "hand", "finger", "thumb",
    "spine", "neck", "cervical", "lumbar", "thoracic", "rotator cuff",
]

# "back" only counts as the unsupported spine/back region when it
# co-occurs with a symptom/body word -- e.g. "back pain", "my back hurts",
# "lower back" -- not on its own.
_BACK_CONTEXT_WORDS: list[str] = [
    "pain", "hurt", "hurts", "hurting", "ache", "aching", "sore", "stiff",
    "stiffness", "injury", "injured", "lower", "upper", "spasm", "strain",
]

# Supported anatomical regions (hip and below-hip lower-extremity only).
_SUPPORTED_REGION_LIST: list[str] = [
    "lower leg", "tibia", "fibula",
    "hip", "knee", "ankle", "foot", "calf",
]

# Surgery-type keyword -> inferred supported region (for context display only).
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

# Distinct non-clinical topic signals -- if a query is DOMINATED by these
# and shows no health/recovery framing at all, it's treated as off-topic.
# Kept intentionally small and high-precision to avoid false rejections.
_OFF_TOPIC_SIGNAL_LIST: list[str] = [
    "weather", "forecast", "temperature outside", "rain", "snow forecast",
    "stock price", "cryptocurrency", "bitcoin", "share market",
    "football score", "cricket score", "match result", "world cup",
    "movie", "netflix", "tv show", "celebrity",
    "recipe for", "cook a", "bake a",
    "write code", "python script", "programming", "debug my",
    "homework", "math problem", "essay about",
    "joke", "tell me a story", "poem about",
    "capital of", "president of", "prime minister",
]

# ---------------------------------------------------------------------------
# Pre-compiled regex helpers
# ---------------------------------------------------------------------------

def _build_pattern(terms: list[str]) -> re.Pattern:
    """Build a single OR regex with word boundaries for a list of terms."""
    escaped = sorted((re.escape(t) for t in terms), key=len, reverse=True)
    return re.compile(r'\b(?:' + '|'.join(escaped) + r')\b', re.IGNORECASE)

@lru_cache(maxsize=None)
def _supported_re()  -> re.Pattern: return _build_pattern(_SUPPORTED_REGION_LIST)
@lru_cache(maxsize=None)
def _unsupported_re()-> re.Pattern: return _build_pattern(_UNSUPPORTED_REGION_LIST)
@lru_cache(maxsize=None)
def _back_word_re()  -> re.Pattern: return _build_pattern(["back"])
@lru_cache(maxsize=None)
def _back_context_re() -> re.Pattern: return _build_pattern(_BACK_CONTEXT_WORDS)
@lru_cache(maxsize=None)
def _off_topic_re()  -> re.Pattern: return _build_pattern(_OFF_TOPIC_SIGNAL_LIST)

SUPPORTED_REGIONS: list[str] = _SUPPORTED_REGION_LIST
UNSUPPORTED_REGIONS: list[str] = _UNSUPPORTED_REGION_LIST
OFF_TOPIC_SIGNALS: frozenset[str] = frozenset(_OFF_TOPIC_SIGNAL_LIST)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class ScopeValidator:
    """
    Implements Algorithm 1 (revised): default-accept scope check.

    Usage:
        status, reason = ScopeValidator.validate(query, surgery_type)

    Algorithm:
      1. Reject queries that explicitly mention an unsupported body region.
      2. Reject queries that match a distinct off-topic signal (weather,
         sports scores, coding help, etc.) with no health/recovery framing.
      3. Otherwise -> IN_SCOPE. The patient is a known post-op user of a
         recovery app; ambiguous or naturally-phrased questions default to
         being handled, with the anatomical region inferred from their
         surgery context when not explicitly stated.
    """

    @classmethod
    def validate(
        cls,
        query: str,
        surgery_type: str,
    ) -> Tuple[ScopeStatus, str]:
        # Step 1 -- explicit unsupported region always rejects
        m = _unsupported_re().search(query)
        if m:
            return (
                ScopeStatus.OUT_OF_SCOPE,
                f"Query mentions '{m.group()}', which is outside the supported "
                "hip-and-below-hip orthopedic post-op scope.",
            )

        # "back" only rejects when paired with pain/injury context -
        # otherwise phrases like "2 days back" (= "ago") would falsely reject.
        if _back_word_re().search(query) and _back_context_re().search(query):
            return (
                ScopeStatus.OUT_OF_SCOPE,
                "Query mentions back pain/injury, which is outside the supported "
                "hip-and-below-hip orthopedic post-op scope.",
            )

        # Step 2 -- distinct off-topic signal with no clinical framing
        off_topic_match = _off_topic_re().search(query)
        if off_topic_match:
            return (
                ScopeStatus.OUT_OF_SCOPE,
                f"Query appears unrelated to orthopedic recovery "
                f"(matched off-topic signal: '{off_topic_match.group()}').",
            )

        # Step 3 -- default accept, region inferred from surgery context
        region_match = _supported_re().search(query)
        lower_surgery = surgery_type.lower()
        inferred_region = next(
            (region for kw, region in SURGERY_TYPE_REGION_MAP.items() if kw in lower_surgery),
            surgery_type,
        )
        return (
            ScopeStatus.IN_SCOPE,
            "Query treated as in-scope for a known post-op patient"
            + (f"; mentions supported region '{region_match.group()}'."
               if region_match
               else f"; region inferred from surgery context ('{inferred_region}')."),
        )
