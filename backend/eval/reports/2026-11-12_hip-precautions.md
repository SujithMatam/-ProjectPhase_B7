# Hip-precaution routing gap: final report

Date: 2026-11-12. Branch `feature/agents-proactive`. Before = `2e5d622`.

| Step | Commit | What |
|---|---|---|
| 2 | `4286cd5` | `eval/routing/heldout_v3.py`: 12 new hip-precaution / movement-restriction messages (11 THA, 1 TKA). Committed and scored before any classifier change. Max cosine 0.709 to cases.py + heldout_v2. `check_near_duplicates.py` gains `heldout --set heldout_v3`, and v3 is now in its prototype pool. |
| 3 | `bb2b132` | Two Daily Activity prototypes in `lam/intent_classifier.py`. No keyword. |
| 5 | this commit | Suite results and this report |

Setup for every run:
- every `SMTP*` / `DOCTOR_ALERT*` variable unset (0 left)
- temp `PATIENT_DATABASE_PATH`
- `TRIAGE_MODE=rules`
- suites run one after the other

## 1. Reply before the fix

Patient: THA, right side, post-op day 5. Message: "What movements should I avoid after my hip replacement?"

Routing: `recovery_progress` via `fallback_low_margin`. Top-1 Recovery 0.488, top-2 Mental Wellbeing, margin 0.023. Agent: RecoveryProgressAgent (Recovery Deterministic Assessment Engine).

- **No surgery date:**
  > I'm not able to compare this to a day-specific target right now, since I can't verify your surgery date. Please check the surgery date in your profile and I'll pick this up from there.
- **Surgery date 2026-11-08:**
  > Let's see where you are on post-op day 5. How are you currently getting around -- walking independently, or using a walker, cane, or crutches? (a few more questions)

Neither reply answers the question.

## 3. Fix

Two new Daily Activity prototypes:
- "Which hip precautions should I follow in everyday life?" (nearest case: V001, 0.658)
- "Are there postures or movements I must stay away from after the operation?" (nearest case: V012, 0.628)

Neither is the phase-4 sentence or a held-out sentence. Both are ≤ 0.85 to every case in cases.py, heldout_v2 and heldout_v3.

The candidates were tried on cases.py and the phase-4 sentence only. heldout_v3 was scored once, after the change.

Result: the phase-4 sentence now routes to `daily_activity` by semantic match (0.698, margin 0.210). No keyword was needed.

## 4. Reply after the fix

Routing: `daily_activity`, semantic. Agent: DailyActivityAgent. Engine: "Daily Activity Agent - Guided Fallback". Sources: Hip Precautions & Dislocation Prevention, Kinesiophobia & Post-Surgical Psychological Coping. The reply is the same with and without a surgery date:

> Good question about daily activities on Day 5 after your Total Hip Arthroplasty (THA) (Right). Here's some general guidance:
>
> • Pace yourself -- alternate activity with rest rather than pushing through fatigue.
> • Follow your prescribed weight-bearing status for this activity, the same way you would for walking.
> • If an activity causes a sharp increase in pain or swelling, stop and rest, and mention it to your surgical team if it continues.
>
> This is general guidance -- always follow your surgical team's specific instructions for your case, especially your prescribed weight-bearing status.

**Weak; reported only, not changed (Daily Activity is not my agent).**

- It never names a hip precaution: no bending past 90°, no crossing the legs, no inward twisting, no low seats. The "Hip Precautions & Dislocation Prevention" passage is retrieved but not used.
- Why: the local Ollama server was not running (`127.0.0.1:11434` gave no response), so `DailyActivityAgent.handle` used its deterministic fallback. `_detect_activity_type` has no precautions type, so the message gets the general steps.
- With Ollama up, the LLM answer would be grounded in that passage. That answer was not tested here.
- For the Daily Activity owner: a precautions type in the fallback that uses the retrieved precautions passage would fix the offline case.

## 5. Results

### Routing (acceptance: no agent below current numbers)

| Set | Classifier | Orchestrator lenient | Orchestrator strict |
|---|---|---|---|
| cases.py, before | 204/230 | 206/230 | 192/230 |
| cases.py, after | **204/230** | **206/230** | **192/230** |
| heldout_v2, before | 30/30 | 30/30 | 30/30 |
| heldout_v2, after | **30/30** | **30/30** | **30/30** |
| heldout_v3, before (at `2e5d622`) | 8/12 | 8/12 | 8/12 |
| heldout_v3, after | **9/12** | **9/12** | **9/12** |

**Acceptance holds.** Every agent on cases.py has exactly the same three numbers as before, and heldout_v2 is 30/30 on every agent.

Rows that changed:
- **R088** "When can I go back to office after hip replacement?": still correct (Recovery). It now comes from the low-margin default (margin 0.018) rather than a semantic win. Weaker, not wrong.
- **V008** "What positions should my hip not go into while it heals?": fixed. It was Recovery via the default; it is now Daily Activity, semantic, margin 0.13.
- **V003** "Doctor said don't cross the legs, till when I have to follow that?": still wrong. It was Mental Wellbeing (semantic); it is now Recovery (low-margin default, Daily Activity 2nd).

heldout_v3 misses left. Not tuned on, because v3 is the judge set:
- **V001** "Which hip movements are banned for the first few weeks...": the Recovery keyword `weeks` fires deterministically (overbroad keyword).
- **V003**: low margin (0.036). Mental Wellbeing's "anxious about moving my operated leg" is still top-1.
- **V011** "Can I put on my socks myself or should I use a sock aid?": goes to Wound Care ("change my wound dressing", 0.35).

### Suites

| Suite | Before | After |
|---|---|---|
| `run_agent_tests.py` | 110/110 | 110/110 |
| Conversation eval, direct | 282/282 | 282/282 |
| Conversation eval, via orchestrator | 271/306 | 271/306 (all 24 conversation rows identical to `final_v2_steps`) |
| `test_phase2_intent.py` | ALL CHECKS PASSED | ALL CHECKS PASSED |
| `test_phase4_agents.py` | ALL CHECKS PASSED | ALL CHECKS PASSED (the THA check now routes to DailyActivityAgent, 1 generation call, procedure THA) |
| `test_multi_agent_orchestration.py` | 5/5 | 5/5 |

Results:
- `eval/routing/results/{heldout_v3_before,hip_precautions,heldout_v2_hip_precautions,heldout_v3_hip_precautions}.{json,md}`
- `eval/agents/results/hip_precautions{,_orchestrator}.{json,md}`
