# 2026-11-12: Triage classifier wired in behind TRIAGE_MODE (default rules)

Branch feature/triage-classifier. Full write-up: `backend/triage/REPORT.md`, section "Shipped configuration" (reproduced below).

## Files changed outside backend/triage/

- `backend/doctor_alert.py`: new `alert_suppressed(triage)`; `notify_red_triage` / `notify_red_triage_background` skip the email when the triage result has `doctor_alert: false` (only hybrid mode sets it; rules results have no such key, so rules behaviour is unchanged).
- `backend/eval/reports/2026-11-12_triage_hybrid_shipped.md`: this report.
- `lam/orchestrator.py`: **not changed** (temperature_c already reaches `SafetyTriageEngine.evaluate`).

## Shipped configuration (from REPORT.md)

What is wired in (`TRIAGE_MODE=hybrid`; the default, `TRIAGE_MODE=rules` or unset, is the keyword
engine and behaves exactly as before):

- **level = max(overrides, classifier)**, never lower than any component. Classifier = M2 seed 4
  (`artifacts/setfit/m2_main_it3_seed4`, thresholded with its val t_red 0.217 / t_yel 0.237); if those
  weights are absent, M1. `classifier_triage.py` logs which one loaded and returns it as `model_used`.
  The keyword engine is **not** part of the max (Finding 4: it adds no RED catch, only false REDs).
  No LLM is on this path.
- **Overrides** (`overrides.py`, deterministic): a temperature parser over the text (°C, °F, bare
  numbers in a fever context, decimals such as "39.6 is ths an emergency", the highest of several
  readings, negation, thresholds such as "if it goes above 38.5", readings before a clinician
  assessment ignored) plus the request's `temperature_c`: >= 38.5 °C RED, 37.8-38.4 °C YELLOW floor.
  And a negation-aware self-harm matcher -> RED, reason `self_harm`, `category="mental_health_crisis"`
  (the orchestrator then answers with its crisis template, not orthopaedic advice). On all 1,945
  labelled messages (every split + challenge) no override is ever above the label: the temperature
  override fires on 140 (76 RED on RED rows, 59 YELLOW on YELLOW rows, 5 YELLOW on RED rows where
  something else makes it RED) and self-harm on the 4 RED MOOD_SLEEP rows only
  (`test_overrides.py`, 128 tests).
- **Doctor-alert gate**: email only for an override RED or p(RED) >= **t_alert = 0.637**, the lowest
  threshold on **val** with RED precision >= 0.90 (val precision 0.903, val RED recall above it
  0.816; `model/choose_alert_threshold.py`, stored in `selection.json`; M1 fallback 0.579). A RED
  below t_alert still gives the patient the RED advice; the result carries `doctor_alert: false`
  and `flags: ["alert_suppressed_low_confidence"]`, and `doctor_alert.py` does not send.
- **Multi-turn Pain check**: unchanged orchestrator code calls `SafetyTriageEngine.evaluate` on the
  single message and on the accumulated Pain text and keeps the higher `status_code`; in hybrid
  mode both calls go through the hybrid engine.

Numbers below: `model/evaluate_shipped.py` (`artifacts/shipped_results.json`). Text only, no
temperature field. Rules mode emails on every RED.

| set | mode | RED recall | 95% CI | RED prec. | macro F1 | RED->GREEN | RED->YELLOW | GREEN->RED | YELLOW->RED | RED calls / 100 | emails / 100 | RED rows emailed | non-RED emails | suppressed (of which RED) |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| main test (n=266, RED 104) | rules (default) | 0.192 | 0.128-0.278 | 0.667 | 0.357 | 74 | 10 | 5 | 5 | 11.3 | 11.3 | 20/104 | 10 |  |
| main test (n=266, RED 104) | classifier only (thresholded) | 0.923 | 0.856-0.961 | 0.706 | 0.678 | 2 | 6 | 6 | 34 | 51.1 |  |  |  |  |
| main test (n=266, RED 104) | **hybrid (shipped)** | 0.962 | 0.905-0.985 | 0.714 | 0.703 | 0 | 4 | 6 | 34 | 52.6 | 35.3 | 83/104 | 11 | 46 (17) |
| challenge (n=150, RED 58) | rules (default) | 0.241 | 0.150-0.365 | 0.438 | 0.333 | 39 | 5 | 12 | 6 | 21.3 | 21.3 | 14/58 | 18 |  |
| challenge (n=150, RED 58) | classifier only (thresholded) | 0.966 | 0.883-0.990 | 0.636 | 0.618 | 0 | 2 | 6 | 26 | 58.7 |  |  |  |  |
| challenge (n=150, RED 58) | **hybrid (shipped)** | 1.000 | 0.938-1.000 | 0.644 | 0.627 | 0 | 0 | 6 | 26 | 60.0 | 44.0 | 54/58 | 12 | 24 (4) |
| unseen-scenario test (n=275, RED 105) | rules (default) | 0.057 | 0.026-0.119 | 0.500 | 0.273 | 81 | 18 | 4 | 2 | 4.4 | 4.4 | 6/105 | 6 |  |
| unseen-scenario test (n=275, RED 105) | classifier only (thresholded) | 0.848 | 0.767-0.904 | 0.636 | 0.604 | 6 | 10 | 13 | 38 | 50.9 |  |  |  |  |
| unseen-scenario test (n=275, RED 105) | **hybrid (shipped)** | 0.971 | 0.919-0.990 | 0.667 | 0.640 | 1 | 2 | 13 | 38 | 55.6 | 36.7 | 80/105 | 21 | 52 (22) |

Shipped classifier: `M2:m2_main_it3_seed4`, t_red 0.217, t_yel 0.237, t_alert 0.637. Unseen-scenario rows use the unseen-split M2 (seed 0) cached probabilities with that split's val thresholds (t_red 0.097, t_alert 0.604); 191 of its 275 test rows are in the main train split, so the shipped weights are not scored there. "classifier only" is the same run without overrides (no gate). Rules mode emails on every RED.

Per-scenario RED recall, unseen-scenario test:

| scenario | RED rows | rules | classifier only | hybrid |
|---|---:|---:|---:|---:|
| ALLERGIC_REACTION | 40 | 1/40 | 38/40 | 38/40 |
| FOLLOWUP_ADMIN | 3 | 0/3 | 2/3 | 2/3 |
| HIGH_FEVER | 50 | 1/50 | 38/50 | 50/50 |
| MOOD_SLEEP | 4 | 1/4 | 3/4 | 4/4 |
| UNCONTROLLED_PAIN | 8 | 3/8 | 8/8 | 8/8 |

The 7 audit_regression rows (challenge set):

| id | text | label | rules | rules email | hybrid | reasons | p(RED) | email |
|---|---|---|---|---|---|---|---:|---|
| CH-144 | No chest pain, no chills | GREEN | **RED** | yes | **YELLOW** | classifier | 0.082 | no |
| CH-145 | I don't have shortness of breath | GREEN | **RED** | yes | **RED** | classifier | 0.744 | yes |
| CH-146 | I cannot breathe properly | RED | **GREEN** | no | RED | classifier | 0.919 | yes |
| CH-147 | I can’t breathe | RED | **GREEN** | no | RED | classifier | 0.966 | yes |
| CH-148 | fever of 39 | RED | **GREEN** | no | RED | high_fever, classifier | 0.695 | yes |
| CH-149 | My knee is a little red and swollen | YELLOW | **RED** | yes | **RED** | classifier | 0.920 | yes |
| CH-150 | fluid coming from my incision | YELLOW | **GREEN** | no | **RED** | classifier | 0.669 | yes |

Bold = differs from the label.

RED messages the hybrid pipeline still does not call RED:

| set | id | hybrid | p(RED) | text |
|---|---|---|---:|---|
| test | ALLERGIC_REACTION-013 | YELLOW | 0.101 | Wheezy and chest tight since the tramadol, never had asthma |
| test | COMPARTMENT-012 | YELLOW | 0.123 | My father is shouting with pain in leg after knee surgery. Tramadol given 1 hour back but no relief. Leg is tight. |
| test | COMPARTMENT-058 | YELLOW | 0.041 | Is so much pain normal on day 2? Leg is very tight and stiff like wood and no medicine is working. |
| test | WOUND_OPEN-030 | YELLOW | 0.096 | When I bend the knee the cut gapes and I can see right into it; when I straighten it closes again |
| unseen_test | ALLERGIC_REACTION-013 | YELLOW | 0.036 | Wheezy and chest tight since the tramadol, never had asthma |
| unseen_test | ALLERGIC_REACTION-032 | GREEN | 0.007 | Is it normal for my throat to feel tight after the antibiotic? |
| unseen_test | FOLLOWUP_ADMIN-014 | YELLOW | 0.015 | Waiting for my wound check next week but the dressing has soaked right through with blood twice today. |

**Finding S1: the overrides close the number and self-harm gaps without adding a single false
RED.** Against the classifier alone, RED recall rises from 0.923 to 0.962 on main test (RED->GREEN
2 -> 0: `HIGH_FEVER-048` via the temperature parser, `MOOD_SLEEP-013` via self-harm), from 0.966 to
1.000 on the challenge set, and from 0.848 to 0.971 on the unseen-scenario test, where HIGH_FEVER goes
from 38/50 to 50/50 (all 12 misses of Finding 8) and MOOD_SLEEP from 3/4 to 4/4. GREEN->RED and
YELLOW->RED are identical with and without the overrides on all three sets. The intervals still
overlap (main test 0.856-0.961 vs 0.905-0.985).

**Finding S2: hybrid sends about three times as many doctor emails, and they are more often about a
real RED.** Emails per 100 messages: main test 11.3 (rules) vs 35.3 (hybrid), challenge 21.3 vs 44.0,
unseen-scenario test 4.4 vs 36.7. The rules send few emails because they find few REDs (20 of 104
on test). The share of emails about a RED-labelled message goes from 0.67 to 0.88 (test), 0.44 to 0.82
(challenge) and 0.50 to 0.79 (unseen). These rates are at 38-39% RED prevalence; on real traffic both
modes would email far less often, and hybrid's precision would be lower.

**Finding S3: the gate trades doctor-email recall for precision.** On main test it suppresses 46
emails, 17 of them for RED-labelled messages: those patients get the RED advice, but the doctor is
told about 83 of 104 RED messages (0.80), against 100 of 104 RED calls. Challenge: 54 of 58 emailed.
Unseen-scenario: 80 of 105. Without the gate the email rate would equal the RED-call rate (52.6 per
100 on test). Whether 0.90 is the right precision target is a clinical decision that has not been
made.

**Finding S4: over-triage is the cost, and it shows up in the existing tests.** Hybrid calls about
half the YELLOW messages RED (34 of 62 on test), as the thresholded classifier already did (Finding
2). In `test_multi_agent_orchestration.py` two of five tests fail in hybrid mode for this reason:
"Since I didn't take my medicine yesterday, my knee wound is worse" (p(RED) 0.74, so it also emails)
and "I am anxious, my knee hurts, and I need help with exercises" (p(RED) 0.54, RED without email)
become RED, and the RED branch returns before the multi-agent plan runs. Rules mode calls both GREEN.

**Test suites in both modes** (SMTP and DOCTOR_ALERT variables cleared, temporary patient database):

| suite | rules | hybrid |
|---|---|---|
| agent suites (`test_pain_symptoms_agent.py`, `test_recovery_progress_agent.py`, `test_rehabilitation_agent.py`, the set `run_agent_tests.py` runs) | 66 passed | 66 passed |
| `test_phase2_intent.py` | ALL CHECKS PASSED | ALL CHECKS PASSED |
| `test_multi_agent_orchestration.py` | 5/5 OK | **3/5**: 1 failure, 1 error (Finding S4) |
| `triage/test_overrides.py`, `triage/test_classifier_triage.py` | 146 passed | (mode-independent) |

`run_agent_tests.py` is not on this branch (it is on `feature/agents-proactive`); the same three files
were run under pytest with the same isolation it applies.

**Known limitations of the wiring.**
- If the single-message result is a gated RED (no email) and the cumulative Pain result is a RED that
  would email, the orchestrator's `_more_severe_triage` keeps the first one on a tie, so no email is
  sent. A one-line tie-break in `lam/orchestrator.py` would fix it; the orchestrator was left untouched.
- The orchestrator's RED reply lists `reasons` to the patient, so hybrid mode shows "classifier" /
  "high_fever" there instead of the rules' descriptive strings.
- The classifier was never trained on the cumulative Pain fact list ("pain 8/10; sudden onset;
  location my calf; swelling present"). Spot checks: calf cases are RED (p(RED) 0.76-0.93); "pain
  6/10; gradual onset; location knee; swelling present" is also RED (0.66, rules YELLOW).
- If the classifier cannot load or fails on an input, the classifier component falls back to the
  rules engine (`model_used = "rules_fallback"`, every RED emails).
- Every caller of `SafetyTriageEngine.evaluate` (orchestrator, `chat_agent.py`, `symptom_agent.py`,
  `specialized_agents.py`) switches with the flag. The first call loads the model (a few seconds);
  after that about 10 ms per call, and the cumulative check adds a second call.

