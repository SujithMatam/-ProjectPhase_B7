"""
LAM Orchestrator.

Controls the complete LAM pipeline for /api/chat.

Execution order:

1. Deterministic safety triage (RED short-circuits everything below)
2. Wound context determination (explicit wound message OR an active
   Wound Care follow-up -- a bare short answer alone never counts)
3. Scope validation (genuine Wound context bypasses standalone
   rejection of terse in-conversation answers; OUT_OF_SCOPE still
   short-circuits everything below)
4. Continuation / intent ownership:
     - genuine Wound context owns this turn -> WOUND_CARE
     - otherwise, narrow Recovery continuation check
       (check_recovery_continuation) -> RECOVERY_PROGRESS on match
     - otherwise, fresh IntentClassifier
5. Agent/action routing
6. Specialized agent execution

Important Wound Care behaviour:

- Explicit wound messages are routed to WoundCareAgent.
- Answers to an ACTIVE Wound Care question stay in WoundCareAgent.
- Short answers such as "yesterday", "better", "less red",
  "less warm", "yes", "no", etc. are not treated as standalone
  out-of-scope queries when they are genuinely part of an active
  Wound Care conversation -- but a bare short answer by itself, with
  no active Wound follow-up and no explicit wound term, does NOT
  establish Wound context on its own.
- Safety triage still runs FIRST on every turn.

Important Recovery behaviour:

- Recovery continuation uses check_recovery_continuation(), which reads
  existing Recovery state via peek_state() ONLY (never creates state)
  and matches ONLY when a real pending_field exists and the message
  plausibly answers that specific field (e.g. "80 degrees",
  "I don't know.", "Same as yesterday." while flexion is pending).
- Recovery continuation never overrides RED safety, OUT_OF_SCOPE, an
  explicit/active Wound Care conversation, or a genuine topic switch.
"""

from __future__ import annotations

import re
from typing import Optional, List, Dict

from triage.safety_triage import SafetyTriageEngine
from agents.agent_router import AgentRouter
from agents.recovery_integration import check_recovery_continuation
from agents import pain_logic
from agents import pain_state
from doctor_alert import doctor_alert_notifier
from agents.report_agent import ReportGenerationAgent

from lam.schemas import (
    IntentLabel,
    ScopeStatus,
    TargetAgent,
    ActionType,
    LAMContext,
    LAMResult,
    WeightBearingStatus,
    resolve_procedure_code,
)

from lam.scope_validator import ScopeValidator
from lam.intent_classifier import IntentClassifier


# ============================================================================
# ROUTING TABLE
# ============================================================================

_ROUTING_TABLE: dict[
    IntentLabel,
    tuple[TargetAgent, ActionType]
] = {

    IntentLabel.RECOVERY_PROGRESS: (
        TargetAgent.RECOVERY_AGENT,
        ActionType.INFORM,
    ),

    IntentLabel.PAIN_SYMPTOMS: (
        TargetAgent.PAIN_AGENT,
        ActionType.ASSESS,
    ),

    IntentLabel.REHABILITATION: (
        TargetAgent.REHAB_AGENT,
        ActionType.ADVISE,
    ),

    IntentLabel.MEDICATION: (
        TargetAgent.MEDICATION_AGENT,
        ActionType.INFORM,
    ),

    IntentLabel.WOUND_CARE: (
        TargetAgent.WOUND_CARE_AGENT,
        ActionType.ADVISE,
    ),

    IntentLabel.DAILY_ACTIVITY: (
        TargetAgent.DAILY_ACTIVITY_AGENT,
        ActionType.INFORM,
    ),

    IntentLabel.NUTRITION: (
        TargetAgent.NUTRITION_AGENT,
        ActionType.INFORM,
    ),

    IntentLabel.MENTAL_WELLBEING: (
        TargetAgent.MENTAL_HEALTH_AGENT,
        ActionType.ADVISE,
    ),

    IntentLabel.EMERGENCY: (
        TargetAgent.SAFETY_TRIAGE_AGENT,
        ActionType.ESCALATE,
    ),

    IntentLabel.OUT_OF_SCOPE: (
        TargetAgent.DEFLECTION_AGENT,
        ActionType.DEFLECT,
    ),

    IntentLabel.INTAKE_CONTEXT: (
        TargetAgent.INTAKE_CONTEXT_AGENT,
        ActionType.INFORM,
    ),
}


# ============================================================================
# OUT-OF-SCOPE RESPONSE
# ============================================================================

_OUT_OF_SCOPE_REPLY = (
    "I'm OrthoSync, a specialised assistant for orthopedic "
    "post-operative recovery. Your question doesn't appear to "
    "be related to your surgical recovery or orthopedic care. "
    "For general health questions, please consult your GP or a "
    "relevant healthcare professional. If you have a question "
    "about your recovery, wound, pain, medication, or "
    "rehabilitation, I'm here to help!"
)


# ============================================================================
# TEXT HELPERS
# ============================================================================

def _normalise(text: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        (text or "").strip().lower(),
    )


# ============================================================================
# WOUND TERMS
#
# UNAMBIGUOUS WOUND ANCHORS ONLY. These are words that only ever mean
# something at/about a surgical wound/incision -- they never describe a
# generic bodily symptom that could equally be Pain & Symptoms' territory.
#
# Deliberately EXCLUDED (and must stay excluded -- see investigation report):
#   swelling, swollen, redness, red, warm, warmer, warmth, hot, fluid
#
# These are AMBIGUOUS, generic symptom words -- "My knee is swollen." or
# "My leg is swollen and painful." describe ordinary limb/joint swelling with
# no wound/incision mention at all, and the project's Symptom Assessment role
# explicitly owns localized swelling. Treating these words alone as wound
# terms previously forced EVERY such message to WoundCareAgent regardless of
# content, which PainSymptomsAgent could never see. They remain fully
# supported as Pain's own vocabulary (see lam/intent_classifier.py's
# _PAIN_KEYWORDS, which already includes "swelling"/"swollen") -- removing
# them here does not remove them from the system, only from being an
# automatic WOUND override.
#
# An ambiguous word is still correctly understood as wound-related whenever
# an unambiguous anchor is ALSO present in the same message (e.g. "My
# incision is swollen." still matches via "incision" below) or whenever
# there is a genuinely ACTIVE Wound follow-up in progress (see
# _has_active_wound_followup, which is a structurally separate check against
# the assistant's own prior question -- entirely unaffected by this list).
# ============================================================================

_WOUND_TERMS = (
    "wound",
    "incision",
    "surgical site",
    "surgical cut",
    "scar",
    "stitch",
    "stitches",
    "suture",
    "sutures",
    "staple",
    "staples",
    "dressing",
    "bandage",
    "drainage",
    "draining",
    "discharge",
    "leaking",
    "leak",
    "pus",
    "separation",
    "opening",
    "opened",
    "gap",
    "gaping",
)


_WOUND_TERM_PATTERNS = tuple(
    re.compile(r"\b" + re.escape(term) + r"\b")
    for term in _WOUND_TERMS
)


def _contains_wound_term(
    text: str,
) -> bool:

    text = _normalise(text)

    return any(
        pattern.search(text)
        for pattern in _WOUND_TERM_PATTERNS
    )


# ============================================================================
# EXPLICIT DIFFERENT DOMAIN
#
# This allows the patient to intentionally switch topics.
#
# Example:
#
# Wound conversation
# "yesterday"
# "worse"
# "Can I climb stairs?"
#
# The last message should go to DailyActivityAgent.
# ============================================================================

_DIFFERENT_DOMAIN_TERMS = (
    # Medication
    "medication",
    "medicine",
    "tablet",
    "pill",
    "dose",
    "dosage",
    "antibiotic",
    "blood thinner",
    "anticoagulant",

    # Rehabilitation
    "exercise",
    "exercises",
    "physio",
    "physiotherapy",
    "rehab",
    "rehabilitation",
    "range of motion",
    "rom",
    "heel slide",
    "quad set",
    "leg raise",
    "weight bearing",
    "crutches",
    "walker",

    # Daily activity
    "stairs",
    "stair",
    "drive",
    "driving",
    "shower",
    "showering",
    "bath",
    "bathing",
    "sleeping position",
    "sleep position",
    "getting out of bed",

    # Nutrition
    "food",
    "foods",
    "diet",
    "nutrition",
    "protein",
    "hydration",
    "water intake",
    "supplement",

    # Mental wellbeing
    "anxious",
    "anxiety",
    "worried",
    "worry",
    "scared",
    "stress",
    "stressed",
    "mood",
    "depressed",

    # Recovery progress
    "recovery timeline",
    "recovery progress",
    "milestone",
    "milestones",
    "return to work",
)


def _has_explicit_different_domain(
    user_message: str,
) -> bool:

    text = _normalise(
        user_message
    )

    return any(
        term in text
        for term in _DIFFERENT_DOMAIN_TERMS
    )


# ============================================================================
# ACTIVE WOUND FOLLOW-UP
# ============================================================================

_WOUND_FOLLOWUP_MARKERS = (
    "when did you first notice",
    "has it been getting better",
    "getting better, worse",
    "getting worse",
    "staying about the same",
    "does it look more red",
    "does the redness seem to be spreading",
    "feel warmer than",
    "you mentioned some fluid",
    "any fluid coming",
    "what does it look like",
    "does the incision still look closed",
    "opening or separating",
    "how does the area feel",
    "pain or tenderness",
    "checked your temperature",
    "felt feverish",
    "unusually unwell",
)


def _last_assistant_message(
    chat_history: Optional[List[Dict[str, str]]],
) -> str:

    for item in reversed(
        chat_history or []
    ):

        if not isinstance(item, dict):
            continue

        role = str(item.get("role", "")).lower().strip()

        content = str(
            item.get("content")
            or item.get("reply")
            or item.get("message")
            or item.get("text")
            or ""
        ).strip()

        if role in {
            "assistant",
            "bot",
            "ai",
            "model",
            "assistant_message",
        } and content:

            return content

    return ""


def _has_active_wound_followup(
    chat_history: Optional[List[Dict[str, str]]],
) -> bool:

    last_message = _normalise(
        _last_assistant_message(
            chat_history
        )
    )

    if not last_message:
        return False

    return any(
        marker in last_message
        for marker in _WOUND_FOLLOWUP_MARKERS
    )


# ============================================================================
# ACTIVE PAIN & SYMPTOMS FOLLOW-UP
#
# Narrow, two-signal check -- both must agree before a short reply ("8",
# "suddenly", "my calf") stays with PainSymptomsAgent instead of falling
# through to fresh intent classification:
#
#   1. The LAST assistant message actually asked one of Pain's own
#      questions (chat-history-derived, robust to a server restart --
#      mirrors _has_active_wound_followup above and
#      wound_care_agent.py::_previous_question_field).
#   2. The server-side PainSessionState for this patient (pain_state.py)
#      genuinely agrees a field is pending, for the SAME field.
#
# Requiring BOTH prevents a STALE Pain session (e.g. from much earlier in a
# long conversation, now abandoned) from hijacking a short reply that is
# really answering a DIFFERENT agent's most recent question: if the last
# assistant message was asked by Wound/Recovery/anything else, signal (1)
# is already False regardless of what pain_state still remembers.
#
# This is checked ONLY when wound_context (above) does not already own the
# turn, and the caller additionally excludes an explicit topic switch (see
# _has_explicit_different_domain) -- an unfinished Pain assessment must
# never hijack "Can I climb stairs?", "When should I take my antibiotic?",
# or an explicit wound/RED message.
#
# NOTE ON "LAST assistant message": signal (1) here (via
# pain_logic.previous_pending_field) deliberately BRIDGES past an
# intervening assistant reply that did NOT ask a Pain question (e.g. a
# Daily Activity answer after a brief detour), so a short reply resuming an
# old pending Pain question can still be routed correctly. This is a
# ROUTING decision (should a short/ambiguous reply stay with Pain), and is
# intentionally more lenient than the STRICTER check
# pain_logic.is_active_assessment_continuation() applies (the literal most
# recent assistant message, no bridging) when deciding whether to REUSE an
# active assessment's own bookkeeping (pending_field/ask_counts/cached
# facts/active-history boundary) vs. start a fresh one -- see
# PainSymptomsAgent.handle() and Step 2's cumulative-safety block below,
# both of which use that stricter check for that different purpose.
# ============================================================================

def _has_active_pain_followup(
    patient_id: str,
    chat_history: Optional[List[Dict[str, str]]],
    user_message: str,
) -> bool:

    if not (user_message or "").strip():
        return False

    last_asked_field = pain_logic.previous_pending_field(
        chat_history
    )

    if last_asked_field is None:
        return False

    state = pain_state.peek_state(patient_id)

    if state is None or state.pending_field != last_asked_field:
        return False

    return True


# ============================================================================
# SHORT ANSWER DETECTION
#
# These are common answers to Wound Care questions. They are used ONLY for
# diagnostic logging and to justify skipping standalone scope rejection
# while genuine Wound context (see _has_active_wound_followup /
# _contains_wound_term) already applies. A short answer by itself must
# NEVER establish Wound context on its own -- see the wound_context
# expression below -- otherwise generic short replies such as "same" or
# "yesterday" would be misrouted to Wound Care even with no active wound
# conversation (e.g. stealing a pending Recovery flexion answer like
# "Same as yesterday.").
# ============================================================================

_SHORT_WOUND_ANSWERS = (
    "yes",
    "yeah",
    "yep",
    "no",
    "nope",
    "yesterday",
    "today",
    "this morning",
    "this afternoon",
    "this evening",
    "last night",
    "better",
    "worse",
    "same",
    "about the same",
    "unchanged",
    "slightly better",
    "slightly worse",
    "a little better",
    "a little worse",
    "less red",
    "more red",
    "less warm",
    "more warm",
    "warmer",
    "cooler",
    "not really",
    "a little",
    "a little bit",
    "small amount",
    "small amount of fluid",
    "no fluid",
    "no drainage",
    "none",
)


def _looks_like_short_wound_answer(
    user_message: str,
) -> bool:

    text = _normalise(
        user_message
    )

    if not text:
        return False

    if text in _SHORT_WOUND_ANSWERS:
        return True

    words = text.split()

    if len(words) <= 5:

        answer_words = (
            "better",
            "worse",
            "same",
            "less",
            "more",
            "yes",
            "no",
            "slightly",
            "little",
            "yesterday",
            "today",
            "closed",
            "open",
            "clear",
            "warm",
            "warmer",
            "cooler",
        )

        return any(
            word in answer_words
            for word in words
        )

    return False


# ============================================================================
# TRIAGE INPUT NORMALISATION
#
# Important:
#
# "less red"
# "less redness"
# "redness is improving"
# "redness has decreased"
#
# should NOT be interpreted as the patient currently having increasing
# redness.
#
# We do NOT remove genuine new symptoms.
#
# Example:
#
# "less red but there is pus"
#
# becomes effectively:
#
# "but there is pus"
#
# so the pus can still be detected by the deterministic triage engine.
# ============================================================================

_NEGATED_OR_IMPROVING_SYMPTOMS = (
    r"\bless\s+red\b",
    r"\bless\s+redness\b",
    r"\bredness\s+is\s+less\b",
    r"\bredness\s+has\s+decreased\b",
    r"\bredness\s+has\s+reduced\b",
    r"\bredness\s+is\s+improving\b",
    r"\bredness\s+is\s+getting\s+better\b",
    r"\bnot\s+red\b",
    r"\bno\s+redness\b",

    r"\bless\s+warm\b",
    r"\bless\s+warmth\b",
    r"\bnot\s+warm\b",
    r"\bno\s+warmth\b",

    r"\bless\s+swelling\b",
    r"\bswelling\s+has\s+decreased\b",
    r"\bswelling\s+is\s+improving\b",
    r"\bno\s+swelling\b",

    r"\bno\s+pus\b",
    r"\bno\s+drainage\b",
    r"\bno\s+discharge\b",
    r"\bno\s+fluid\b",

    r"\bno\s+fever\b",
    r"\bnot\s+feverish\b",
)


def _prepare_triage_text(
    user_message: str,
) -> str:

    text = user_message or ""

    for pattern in _NEGATED_OR_IMPROVING_SYMPTOMS:

        text = re.sub(
            pattern,
            " ",
            text,
            flags=re.IGNORECASE,
        )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# ============================================================================
# TRIAGE SEVERITY COMPARISON
#
# Used ONLY to pick which of two ALREADY-COMPUTED SafetyTriageEngine results
# (raw-turn vs. cumulative-Pain-text) is more severe -- this performs no
# triage classification of its own and adds no new clinical rule. Ranks
# directly off SafetyTriageEngine's own `status_code` (RED=3, YELLOW=2,
# GREEN=1 -- see triage/safety_triage.py), so it can never disagree with the
# engine's own notion of severity ordering.
# ============================================================================

def _more_severe_triage(
    a: dict,
    b: dict,
) -> dict:

    a_rank = a.get("status_code", 0)
    b_rank = b.get("status_code", 0)

    return b if b_rank > a_rank else a


# ============================================================================
# ORCHESTRATOR
# ============================================================================

class LAMOrchestrator:

    @classmethod
    def process(
        cls,
        patient_id: str,
        surgery_type: str,
        affected_limb: str,
        postop_day: int,
        user_message: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        surgery_date: Optional[str] = None,
        pain_score: Optional[int] = None,
        pain_characteristics: Optional[str] = None,
        swelling_description: Optional[str] = None,
        temperature_c: Optional[float] = None,
        weight_bearing_status: Optional[WeightBearingStatus] = None,
        current_rom: Optional[str] = None,
        exercise_history: Optional[str] = None,
    ) -> dict:

        history = chat_history or []

        context = LAMContext(
            patient_id=patient_id,
            surgery_type=surgery_type,
            affected_limb=affected_limb,
            postop_day=postop_day,
            user_message=user_message,
            surgery_date=surgery_date,
            chat_history=history,
            medication_names=[
                str(medication.get("name", "")).strip()
                for medication in ReportGenerationAgent.get_patient_record(patient_id).get(
                    "current_medications", []
                )
                if medication.get("name")
            ],
        )


        # ============================================================
        # STEP 1
        # DETERMINE GENUINE WOUND / PAIN CONTEXT
        #
        # Computed BEFORE safety triage (moved up from its previous
        # position after Step 1) SOLELY so that Step 2's cumulative Pain
        # safety check below can reuse the exact same, already-proven,
        # narrow "is this turn genuinely part of an active Pain
        # conversation" signal used for routing -- rather than
        # re-implementing a second, possibly-divergent copy of that
        # signal just for safety purposes. Nothing about WHAT these
        # booleans mean changes -- only WHEN they are computed. They are
        # pure functions of `history` / `user_message` / `patient_id`
        # (peek-only, never create state), so moving them earlier has no
        # ordering dependency on safety triage having already run.
        #
        # IMPORTANT: this is still computed BEFORE ScopeValidator and
        # BEFORE the Recovery continuation check (Step 4).
        #
        # Otherwise:
        #
        # "less warm"
        #
        # could be rejected as an isolated out-of-scope sentence.
        #
        # CRITICAL: a bare short answer ("yes", "same", "yesterday", ...)
        # by itself must NOT establish Wound context. Only an explicit
        # wound-related message, or a reply to an ACTUALLY active Wound
        # Care follow-up question, does. This is what keeps a pending
        # Recovery flexion answer such as "Same as yesterday." eligible
        # for Recovery continuation (Step 4 below) when there is no
        # active Wound conversation -- see _looks_like_short_wound_answer's
        # docstring for why short_wound_answer is excluded here.
        # ============================================================

        active_wound_followup = _has_active_wound_followup(history)
        explicit_wound_message = _contains_wound_term(user_message)
        short_wound_answer = _looks_like_short_wound_answer(user_message)
        explicit_different_domain = _has_explicit_different_domain(user_message)

        wound_context = (
            (active_wound_followup or explicit_wound_message)
            and not explicit_different_domain
        )

        print(
            "[LAM][WOUND CONTEXT] "
            f"active_followup={active_wound_followup} "
            f"explicit_wound={explicit_wound_message} "
            f"short_answer={short_wound_answer} "
            f"different_domain={explicit_different_domain} "
            f"wound_context={wound_context}"
        )

        # ============================================================
        # ACTIVE PAIN & SYMPTOMS FOLLOW-UP
        #
        # Checked here so a short reply such as "8" or "my calf" also
        # bypasses standalone scope rejection (Step 3) -- same rationale
        # as wound_context above. Wound always owns the turn first: a
        # Pain follow-up never overrides an explicit/active Wound
        # conversation, and an explicit topic switch (medication, rehab,
        # daily activity, ...) never gets hijacked by a stale, unfinished
        # Pain assessment.
        #
        # `pain_context` is ALSO the exact gate used below (Step 2) to
        # decide whether cumulative Pain safety re-evaluation runs --
        # this is what keeps a stale Pain session from having its old
        # facts re-triaged just because some unrelated later message
        # happens to arrive while that session technically still exists
        # (see Step 2's docstring for the full explanation).
        # ============================================================

        active_pain_followup = (
            not wound_context
            and _has_active_pain_followup(patient_id, history, user_message)
        )

        pain_context = (
            active_pain_followup
            and not explicit_different_domain
            and not explicit_wound_message
        )

        print(
            "[LAM][PAIN CONTEXT] "
            f"active_followup={active_pain_followup} "
            f"different_domain={explicit_different_domain} "
            f"pain_context={pain_context}"
        )


        # ============================================================
        # STEP 2
        # DETERMINISTIC SAFETY TRIAGE
        #
        # This ALWAYS runs before any agent dispatch or intent handling.
        #
        # MULTI-TURN CUMULATIVE SAFETY:
        #
        # SafetyTriageEngine's co-occurrence / compound-escalation rules
        # (e.g. "calf" + "swollen"/"pain" -> RED) are matched against ONE
        # string. When an agentic conversation collects the same facts
        # across several turns ("suddenly" -> "8" -> "my calf" -> "yes,
        # it's swollen"), each turn's raw text alone never contains the
        # full combination, so the SAME clinical picture that would be
        # RED as one message could otherwise only ever reach YELLOW here
        # -- a genuine safety gap, not a hypothetical one (confirmed by
        # investigation).
        #
        # Fix: when this turn is genuinely part of an ACTIVE Pain
        # conversation (`pain_context`, computed in Step 1 above -- the
        # same narrow pending-question/recent-assistant-question
        # ownership signal already used for routing), ALSO evaluate
        # SafetyTriageEngine on a synthesized text built from the
        # accumulated Pain facts (pain_logic.build_cumulative_triage_text
        # -- pure text synthesis, no triage logic of its own), and take
        # the MORE SEVERE of the raw-turn result and the cumulative
        # result.
        #
        # SafetyTriageEngine.evaluate() remains the ONLY authority that
        # decides GREEN/YELLOW/RED -- this adds a second INPUT for it to
        # evaluate, never a second decision-maker, never a duplicated or
        # approximated rule. If the cumulative result is RED, it flows
        # through the exact same RED branch (and therefore the exact
        # same doctor-alert path) immediately below -- there is no
        # second RED response path.
        #
        # `pain_context` requiring "not explicit_different_domain" and
        # "not wound_context" (see Step 1) is exactly what keeps a stale
        # Pain session from being cumulative-triaged against an unrelated
        # later message: e.g. a stale pending Pain field followed by
        # "Can I climb stairs?" has explicit_different_domain=True, so
        # pain_context is False and this block does not run at all --
        # only the raw "Can I climb stairs?" text is evaluated, exactly
        # as today.
        #
        # pain_score / swelling_description (the existing structured API
        # fields) are also genuine patient-reported facts, so they are
        # passed into build_cumulative_triage_text() too, straight from
        # THIS request's own arguments. A turn that does NOT resupply them
        # does not lose them either: pain_state.py intentionally caches the
        # last value of each (see PainSessionState.cache_structured_facts /
        # cached_structured_facts) for as long as the active Pain
        # assessment lasts, and `cached_pain_facts` below reads that
        # BOUNDED cache as a fallback baseline -- so a structured fact
        # reported once genuinely IS reasserted on a later turn that omits
        # it, deliberately, closing the exact gap described in
        # pain_state.py's module docstring ("My pain suddenly got much
        # worse today" + pain_score=8, then "my calf" with pain_score
        # omitted -- cumulative safety must still see the 8). This is
        # bounded, not unbounded reassertion: the cache -- and therefore
        # this reassertion -- is scoped to the SAME active-assessment
        # history boundary as `history` below (see
        # pain_state.PainSessionState.active_history_start /
        # start_new_assessment()), so it is always cleared on assessment
        # conclusion/TTL and can never carry a value forward from a
        # COMPLETED or ABANDONED earlier assessment into a later, unrelated
        # one. A free-text correction from the conversation itself still
        # always overrides a cached value (see build_assessment()'s
        # precedence contract) -- a stale cached value is never blindly
        # repeated over a genuine later correction.
        # temperature_c is deliberately NOT passed here: it already has
        # its own direct, per-turn path straight into
        # SafetyTriageEngine.evaluate() below, so it can never "arrive in
        # pieces" across turns the way free-text facts can -- adding it
        # here too would only risk double-applying the same threshold,
        # not add any real coverage.
        # ============================================================

        triage_input = _prepare_triage_text(
            user_message
        )

        triage = SafetyTriageEngine.evaluate(
            symptoms=triage_input,
            post_op_day=postop_day,
            temperature_c=temperature_c,
        )

        print(
            "[LAM][TRIAGE] "
            f"query={user_message!r} "
            f"triage_input={triage_input!r} "
            f"level={triage.get('triage_level')} "
            f"escalated={triage.get('is_escalated')}"
        )

        if pain_context:

            # Read-only peek at this patient's session. peek_state() never
            # creates state and already returns None for a stale/expired
            # session, so a long-abandoned session can never contribute a
            # stale cached fact here.
            pain_session = pain_state.peek_state(patient_id)

            # STRICT CONTINUATION CHECK -- `pain_context` above already
            # guarantees `_has_active_pain_followup`'s (bridging) routing
            # signal agrees this turn stays with Pain, but that bridging
            # signal alone is not enough to trust the PEEKED session's
            # active-history boundary/cached facts here: it can still be
            # True after an ABANDONED interview followed by an off-topic
            # detour and a genuinely NEW Pain complaint (the old
            # pending_field was never formally resolved, so bridging still
            # finds it) -- exactly the case
            # PainSymptomsAgent.handle()/pain_logic.is_active_assessment_
            # continuation() itself will independently treat as FRESH once
            # this turn is dispatched (Step 6, below). Recomputing that
            # SAME stricter check here -- literally the most recent
            # assistant message, not one found by bridging past an
            # intervening non-Pain reply -- keeps this cumulative
            # reconstruction in sync with what the agent will actually do
            # with this turn, so a stale/abandoned session's facts are
            # never combined with THIS turn's own message here either.
            is_continuation = pain_session is not None and pain_logic.is_active_assessment_continuation(
                history, pain_session.pending_field,
            )

            if is_continuation:
                # ACTIVE-ASSESSMENT HISTORY BOUNDARY -- reconstruct against
                # the SAME boundary PainSymptomsAgent.handle() itself uses
                # for pain_logic.build_assessment() (see pain_state.py's
                # active_history_start / start_new_assessment()), never the
                # full, potentially cross-assessment `history`. This is
                # what stops a COMPLETED or ABANDONED older Pain
                # assessment's facts from being re-triaged as though they
                # were part of THIS active assessment. Falls back to the
                # full `history` only if no boundary was ever recorded
                # (should not happen once is_continuation is True, since
                # start_new_assessment() always runs on/before the turn
                # that first makes pending_field non-None).
                active_history_start = pain_session.active_history_start
                scoped_history_for_pain = (
                    history[active_history_start:] if active_history_start is not None else history
                )
                cached_pain_facts = pain_session.cached_structured_facts()
            else:
                # This turn will itself be treated as the START of a FRESH
                # Pain assessment once dispatched -- no prior history and
                # no supplemental structured-fact cache belongs to it yet;
                # only THIS turn's own message (plus this request's own
                # pain_score/swelling_description, passed below) is used.
                scoped_history_for_pain = []
                cached_pain_facts = {}

            cumulative_triage_text = pain_logic.build_cumulative_triage_text(
                scoped_history_for_pain, user_message,
                pain_score=pain_score,
                swelling_description=swelling_description,
                cached_facts=cached_pain_facts,
            )

            if cumulative_triage_text:

                cumulative_triage = SafetyTriageEngine.evaluate(
                    symptoms=cumulative_triage_text,
                    post_op_day=postop_day,
                    temperature_c=None,
                )

                print(
                    "[LAM][CUMULATIVE TRIAGE] "
                    f"text={cumulative_triage_text!r} "
                    f"level={cumulative_triage.get('triage_level')} "
                    f"escalated={cumulative_triage.get('is_escalated')}"
                )

                triage = _more_severe_triage(
                    triage, cumulative_triage,
                )


        # ============================================================
        # RED
        # ============================================================

        if triage.get(
            "triage_level"
        ) == "RED":

            reasons = triage.get(
                "reasons",
                [],
            )

            reason_text = ", ".join(
                reasons
            ) if reasons else "your reported symptoms"

            # ========================================================
            # DOCTOR ALERT NOTIFICATION
            #
            # This is the single point where the deterministic
            # SafetyTriageEngine can produce RED for /api/chat -- this
            # branch always returns before any downstream agent runs,
            # so at most one alert is scheduled per request. Notification
            # is strictly secondary to patient safety and must never
            # delay the patient-facing RED response: the background
            # entry point hands the SMTP send off to a bounded thread
            # pool and returns immediately (see doctor_alert.py). Any
            # failure to even schedule it is caught and logged here too.
            #
            # This is also the SAME path a cumulative-Pain-triage RED
            # (see Step 2 above) flows through -- `triage` at this point
            # may be either the raw-turn result or the cumulative result,
            # whichever was more severe, but there is only ever this one
            # RED branch and only ever this one notification call site.
            # ========================================================

            try:
                doctor_alert_notifier.notify_red_triage_background(
                    patient_id=patient_id,
                    user_message=user_message,
                    triage=triage,
                    surgery_type=surgery_type,
                    surgery_date=surgery_date,
                    postop_day=postop_day,
                )
            except Exception as exc:
                print(f"[DOCTOR ALERT] notification scheduling failed: {exc}")

            reply_text = (
                "🚨 **CRITICAL EMERGENCY ALERT**\n\n"
                "Your reported symptoms require urgent medical "
                f"evaluation: **{reason_text}**.\n\n"
                f"{triage.get('action_protocol', '')}\n\n"
                "Please contact your hospital emergency line or "
                "visit the nearest emergency department right away."
            )

            return LAMResult(
                reply=reply_text,
                triage_level="RED",
                is_escalated=True,
                engine="Deterministic Safety Triage",
                sources=[],
                intent=IntentLabel.EMERGENCY.value,
                target_agent=TargetAgent.SAFETY_TRIAGE_AGENT.value,
                action=ActionType.ESCALATE.value,
                scope_status=ScopeStatus.NOT_EVALUATED.value,
            ).to_dict()


        # ============================================================
        # STEP 3
        # SCOPE VALIDATION
        #
        # Active/explicit Wound Care conversations are already known to
        # be inside the orthopedic postoperative conversation. We
        # therefore do NOT run standalone scope rejection on:
        #
        #   yesterday
        #   better
        #   less red
        #   less warm
        #   yes
        #   no
        #
        # when they are genuinely part of one. Otherwise the normal
        # ScopeValidator still runs, and OUT_OF_SCOPE still short-
        # circuits everything below (including Recovery continuation).
        #
        # Safety triage has already run.
        # ============================================================

        if wound_context or pain_context:

            scope_status = ScopeStatus.IN_SCOPE
            scope_reason = (
                "Active or explicit Wound Care conversation"
                if wound_context
                else "Active Pain & Symptoms follow-up"
            )

            print(
                "[LAM][SCOPE] "
                f"status={scope_status.value} "
                f"reason={scope_reason}"
            )

        else:

            scope_status, scope_reason = (
                ScopeValidator.validate(
                    query=user_message,
                    surgery_type=surgery_type,
                )
            )

            print(
                "[LAM][SCOPE] "
                f"status={scope_status.value} "
                f"reason={scope_reason}"
            )

            if (
                scope_status
                == ScopeStatus.OUT_OF_SCOPE
            ):

                return LAMResult(
                    reply=_OUT_OF_SCOPE_REPLY,
                    triage_level=triage.get(
                        "triage_level",
                        "GREEN",
                    ),
                    is_escalated=bool(
                        triage.get(
                            "is_escalated",
                            False,
                        )
                    ),
                    engine="Scope Validator",
                    sources=[],
                    intent=IntentLabel.OUT_OF_SCOPE.value,
                    target_agent=TargetAgent.DEFLECTION_AGENT.value,
                    action=ActionType.DEFLECT.value,
                    scope_status=ScopeStatus.OUT_OF_SCOPE.value,
                ).to_dict()


        # Computed once here and reused for STEP 6 below -- resolve_procedure_code
        # is a pure function of surgery_type, so this is a single computation,
        # not a duplicated one.
        resolved_procedure = resolve_procedure_code(surgery_type)


        # ============================================================
        # STEP 4
        # CONTINUATION / INTENT OWNERSHIP
        #
        # Ownership order:
        #
        #   1. Genuine Wound context (explicit wound message, or an
        #      ACTIVE Wound Care follow-up) owns this turn -> WOUND_CARE
        #      directly, without running Recovery continuation or fresh
        #      classification.
        #   2. Otherwise, the narrow Recovery continuation check --
        #      matches ONLY when an existing Recovery episode (found via
        #      peek_state(), never created here) has a real pending_field
        #      that this message plausibly answers. See
        #      recovery_integration.check_recovery_continuation() for the
        #      full contract. Never uses "Recovery was the last active
        #      agent" as a signal, and never bypasses fresh classification
        #      for an unrelated topic (wound, medication, etc.) even while
        #      a Recovery field is pending.
        #   3. Otherwise, fresh IntentClassifier.
        #
        # This ordering is what keeps both directions safe:
        #   - "My wound is red and leaking." while a Recovery flexion
        #     field is pending -> wound_context is True -> WOUND_CARE.
        #   - "Same as yesterday." while a Recovery flexion field is
        #     pending and there is NO active Wound conversation ->
        #     wound_context is False -> Recovery continuation runs and
        #     matches -> RECOVERY_PROGRESS.
        # ============================================================

        if wound_context:

            intent_label = (
                IntentLabel.WOUND_CARE
            )

            print(
                "[LAM][INTENT] "
                f"query={user_message!r} "
                "intent=wound_care "
                "path=wound_context_priority"
            )

        elif pain_context:

            intent_label = (
                IntentLabel.PAIN_SYMPTOMS
            )

            print(
                "[LAM][INTENT] "
                f"query={user_message!r} "
                "intent=pain_symptoms "
                "path=pain_context_followup"
            )

        else:

            is_recovery_continuation = check_recovery_continuation(
                patient_id=patient_id,
                surgery_date_raw=surgery_date,
                procedure=resolved_procedure,
                user_message=user_message,
            )

            if is_recovery_continuation:

                intent_label = IntentLabel.RECOVERY_PROGRESS

                print(
                    "[LAM][CONTINUATION] "
                    f"query={user_message!r} "
                    "matched a pending Recovery field -- routing directly to "
                    "RecoveryProgressAgent without fresh intent classification."
                )

            else:

                classification = (
                    IntentClassifier.classify_detailed(
                        query=user_message,
                        context=context,
                    )
                )

                intent_label = classification.intent

                # IMPORTANT DEBUG OUTPUT.
                #
                # This lets you immediately see whether the problem is:
                # classifier -> router -> agent -> response.
                print(
                    "[LAM][INTENT] "
                    f"query={user_message!r} "
                    f"intent={intent_label.value} "
                    f"path={classification.decision_path} "
                    f"top1={getattr(classification.top1_intent, 'value', None)} "
                    f"score={classification.top1_score:.3f} "
                    f"top2={getattr(classification.top2_intent, 'value', None)} "
                    f"margin={classification.margin:.3f}"
                )


        # ============================================================
        # STEP 5
        # ROUTING
        # ============================================================

        target_agent, action_type = _ROUTING_TABLE.get(
            intent_label,
            (
                TargetAgent.DEFLECTION_AGENT,
                ActionType.INFORM,
            ),
        )

        print(
            "[LAM][ROUTE] "
            f"intent={intent_label.value} "
            f"agent={target_agent.value} "
            f"action={action_type.value}"
        )


        # ============================================================
        # STEP 6
        # SPECIALIZED AGENT
        # ============================================================
        # resolved_procedure was already computed above (Step 3) for the
        # Recovery continuation check -- reused here rather than recomputed.

        chat_result = AgentRouter.dispatch(
            intent_label=intent_label,
            patient_id=patient_id,
            surgery_type=surgery_type,
            affected_limb=affected_limb,
            postop_day=postop_day,
            user_message=user_message,
            procedure=resolved_procedure,
            chat_history=history,
            surgery_date=surgery_date,
            precomputed_triage=triage,
            pain_score=pain_score,
            pain_characteristics=pain_characteristics,
            swelling_description=swelling_description,
            temperature_c=temperature_c,
            weight_bearing_status=weight_bearing_status,
            current_rom=current_rom,
            exercise_history=exercise_history,
        )


        # ============================================================
        # STEP 7
        # FINAL RESULT
        # ============================================================

        return LAMResult(
            reply=chat_result.get(
                "reply",
                "",
            ),
            triage_level=chat_result.get(
                "triage_level",
                triage.get(
                    "triage_level",
                    "GREEN",
                ),
            ),
            is_escalated=chat_result.get(
                "is_escalated",
                bool(
                    triage.get(
                        "is_escalated",
                        False,
                    )
                ),
            ),
            engine=chat_result.get(
                "engine",
                "LAM",
            ),
            sources=chat_result.get(
                "sources",
                [],
            ),
            intent=intent_label.value,
            target_agent=target_agent.value,
            action=action_type.value,
            scope_status=ScopeStatus.IN_SCOPE.value,
        ).to_dict()
