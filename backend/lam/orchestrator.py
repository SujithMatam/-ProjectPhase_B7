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
from lam.multi_agent_coordinator import MultiAgentCoordinator


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
# ============================================================================

_WOUND_TERMS = (
    "wound",
    "incision",
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
    "fluid",
    "redness",
    "red",
    "warm",
    "warmer",
    "warmth",
    "hot",
    "swelling",
    "swollen",
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

# Generic redness, warmth, swelling, and pain are symptom signals rather than
# proof that the patient is asking about wound care.  Keep wound ownership for
# an actual wound/incision reference or an active wound follow-up.
_EXPLICIT_WOUND_TERMS = (
    "wound", "incision", "surgical cut", "scar", "stitch", "stitches",
    "suture", "sutures", "staple", "staples", "dressing", "bandage",
    "drainage", "draining", "discharge", "pus", "yellow fluid",
)
_EXPLICIT_WOUND_TERM_PATTERNS = tuple(
    re.compile(r"\b" + re.escape(term) + r"\b")
    for term in _EXPLICIT_WOUND_TERMS
)

def _contains_wound_term(
    text: str,
) -> bool:

    text = _normalise(text)

    return any(pattern.search(text) for pattern in _EXPLICIT_WOUND_TERM_PATTERNS)


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
        # Computed BEFORE safety triage so Step 2's cumulative Pain
        # safety check below can reuse this same, already-proven, narrow
        # "is this turn genuinely part of an active Pain conversation"
        # signal used for routing, rather than re-implementing a second,
        # possibly-divergent copy of it just for safety purposes. These
        # booleans are pure functions of `history` / `user_message` /
        # `patient_id` (peek-only, never create state), so computing them
        # before safety triage has run has no ordering dependency.
        #
        # IMPORTANT:
        #
        # This is checked BEFORE ScopeValidator and BEFORE the Recovery
        # continuation check.
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

        detected_intents = IntentClassifier.detect_applicable_intents(
            query=user_message,
            context=context,
        )

        # An explicit different-domain topic switch (medication, rehab,
        # daily activity, nutrition, mental wellbeing, recovery) must not
        # let a STALE Wound/Pain marker in the chat history smuggle an
        # unrelated agent into applicable_intents. detect_applicable_
        # intents() retains Wound ownership for a terse in-conversation
        # reply by scanning the WHOLE chat history for wound/incision
        # wording -- but that scan cannot tell a genuine Wound follow-up
        # apart from, e.g., Pain's own location question offering "around
        # the incision" as one of its answer options. When the CURRENT
        # message itself contains no wound term (explicit_wound_message
        # is False) but an explicit different-domain term, any Wound
        # intent here can only have come from that history scan, never
        # from this turn's own wording, so it is dropped here -- the one
        # place both signals are already available -- rather than
        # weakening the shared detect_applicable_intents() heuristic
        # other callers still rely on for genuine terse Wound follow-ups.
        if (
            explicit_different_domain
            and not explicit_wound_message
            and IntentLabel.WOUND_CARE in detected_intents
        ):
            detected_intents = tuple(
                intent for intent in detected_intents
                if intent != IntentLabel.WOUND_CARE
            )

                # Stronger two-signal Pain ownership check.
        genuine_pain_followup = _has_active_pain_followup(
            patient_id,
            history,
            user_message,
        )

        # Explicit wound messages still win -- even when the same message
        # also carries pain wording (e.g. "My incision hurts and there is
        # yellow fluid coming out."), so the len(detected_intents) == 1
        # gate below must NOT apply to the explicit_wound_message signal,
        # only to the softer active_wound_followup text-overlap signal.
        # A generic Wound follow-up text match must still not steal a
        # question that the Pain agent actually owns.
        wound_context = (
            explicit_wound_message
            or (
                active_wound_followup
                and not genuine_pain_followup
                and len(detected_intents) == 1
            )
        )

        pain_context = (
            genuine_pain_followup
            and not explicit_different_domain
            and not explicit_wound_message
        )

        print(
            "[LAM][WOUND CONTEXT] "
            f"active_followup={active_wound_followup} "
            f"explicit_wound={explicit_wound_message} "
            f"short_answer={short_wound_answer} "
            f"different_domain={explicit_different_domain} "
            f"wound_context={wound_context}"
        )

        print(
            "[LAM][PAIN CONTEXT] "
            f"active_followup={genuine_pain_followup} "
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
        # string. When a conversation collects the same facts across
        # several turns ("suddenly" -> "8" -> "my calf" -> "yes, it's
        # swollen"), each turn's raw text alone never contains the full
        # combination, so the same clinical picture that would be RED as
        # one message could otherwise only ever reach YELLOW here.
        #
        # Fix: when this turn is genuinely part of an ACTIVE Pain
        # conversation (`pain_context` above -- the same narrow
        # pending-question/recent-assistant-question ownership signal
        # already used for routing), ALSO evaluate SafetyTriageEngine on
        # a synthesized text built from the accumulated Pain facts
        # (pain_logic.build_cumulative_triage_text -- pure text
        # synthesis, no triage logic of its own), and take the MORE
        # SEVERE of the raw-turn result and the cumulative result.
        #
        # SafetyTriageEngine.evaluate() remains the ONLY authority that
        # decides GREEN/YELLOW/RED -- this adds a second INPUT for it to
        # evaluate, never a second decision-maker, never a duplicated or
        # approximated rule. If the cumulative result is RED, it flows
        # through the exact same RED branch (and therefore the exact
        # same doctor-alert path) immediately below -- there is no
        # second RED response path.
        #
        # `pain_context` already requires "not explicit_different_domain"
        # and "not explicit_wound_message" -- exactly what keeps a stale
        # Pain session from being cumulative-triaged against an unrelated
        # later message: a stale pending Pain field followed by "Can I
        # climb stairs?" has explicit_different_domain=True, so
        # pain_context is False and this block does not run at all --
        # only the raw "Can I climb stairs?" text is evaluated.
        #
        # pain_score / swelling_description (the existing structured API
        # fields) are genuine patient-reported facts too, so they are
        # passed into build_cumulative_triage_text() straight from this
        # request's own arguments. A turn that omits them does not lose
        # them either: pain_state.py caches the last value of each for as
        # long as the active Pain assessment lasts (see
        # PainSessionState.cached_structured_facts), read below as a
        # fallback baseline -- bounded to the SAME active-assessment
        # history boundary as `history` (active_history_start /
        # start_new_assessment()), so it can never carry a value forward
        # from a COMPLETED or ABANDONED earlier assessment into a later,
        # unrelated one. temperature_c is deliberately NOT passed here:
        # it already has its own direct, per-turn path straight into
        # SafetyTriageEngine.evaluate() below, so folding it in here too
        # would only risk double-applying the same threshold.
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
            # guarantees the bridging routing signal agrees this turn
            # stays with Pain, but that alone is not enough to trust the
            # PEEKED session's active-history boundary/cached facts here:
            # it can still be True after an ABANDONED interview followed
            # by an off-topic detour and a genuinely NEW Pain complaint.
            # Recomputing the STRICTER check here (literally the most
            # recent assistant message, no bridging) keeps this
            # cumulative reconstruction in sync with what
            # PainSymptomsAgent.handle() will actually do with this turn
            # (Step 6, below), so a stale/abandoned session's facts are
            # never combined with THIS turn's own message here either.
            is_continuation = (
                pain_session is not None
                and pain_logic.is_active_assessment_continuation(
                    history, pain_session.pending_field,
                )
            )

            if is_continuation:
                # ACTIVE-ASSESSMENT HISTORY BOUNDARY -- reconstruct
                # against the SAME boundary PainSymptomsAgent.handle()
                # itself uses (pain_state.py's active_history_start),
                # never the full, potentially cross-assessment `history`.
                # This is what stops a COMPLETED or ABANDONED older Pain
                # assessment's facts from being re-triaged as though they
                # were part of THIS active assessment.
                active_history_start = pain_session.active_history_start
                scoped_history_for_pain = (
                    history[active_history_start:]
                    if active_history_start is not None
                    else history
                )
                cached_pain_facts = pain_session.cached_structured_facts()
            else:
                # This turn will itself be treated as the START of a
                # FRESH Pain assessment once dispatched -- no prior
                # history and no supplemental structured-fact cache
                # belongs to it yet.
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
            # (Step 2 above) flows through -- `triage` at this point may
            # be either the raw-turn result or the cumulative result,
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

        applicable_intents: tuple[IntentLabel, ...] = ()

        if wound_context and not explicit_different_domain:

            intent_label = (
                IntentLabel.WOUND_CARE
            )
            applicable_intents = (intent_label,)

            print(
                "[LAM][INTENT] "
                f"query={user_message!r} "
                "intent=wound_care "
                "path=wound_context_priority"
            )
        elif pain_context:

            intent_label = IntentLabel.PAIN_SYMPTOMS
            applicable_intents = (intent_label,)

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
                applicable_intents = (intent_label,)

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
                applicable_intents = detected_intents
                if intent_label not in applicable_intents:
                    applicable_intents = (intent_label,) + applicable_intents

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

        if not applicable_intents:
            applicable_intents = (intent_label,)
        ordered_intents = MultiAgentCoordinator.order_intents(applicable_intents)

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

        dispatch_kwargs = dict(
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
        if len(ordered_intents) > 1:
            coordinated = MultiAgentCoordinator.execute(
                intents=tuple(ordered_intents),
                dispatch_kwargs=dispatch_kwargs,
            )
            chat_result = coordinated
            target_agent = coordinated["target_agent"]
            action_type = coordinated["action"]
        else:
            chat_result = AgentRouter.dispatch(
                intent_label=ordered_intents[0],
                **dispatch_kwargs,
            )


        # ============================================================
        # STEP 7
        # FINAL RESULT
        # ============================================================

        final_result = LAMResult(
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
            intent=(
                ",".join(intent.value for intent in ordered_intents)
                if len(ordered_intents) > 1
                else intent_label.value
            ),
            target_agent=(
                target_agent
                if isinstance(target_agent, str)
                else target_agent.value
            ),
            action=(
                action_type
                if isinstance(action_type, str)
                else action_type.value
            ),
            scope_status=ScopeStatus.IN_SCOPE.value,
        ).to_dict()
        if len(ordered_intents) > 1:
            final_result["execution_plan"] = [
                {
                    "step": index,
                    "intent": intent.value,
                    "target_agent": _ROUTING_TABLE[intent][0].value,
                    "action": _ROUTING_TABLE[intent][1].value,
                }
                for index, intent in enumerate(ordered_intents, start=1)
            ]
            final_result["handoffs"] = coordinated["handoffs"]
            final_result["participating_agents"] = [
                item["target_agent"]
                for item in final_result["execution_plan"]
            ]
        return final_result
