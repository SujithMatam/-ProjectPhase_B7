# Agent conversation eval -- baseline_b8f0cc5_orchestrator

- backend: git worktree at b8f0cc5 (commit `b8f0cc5`)
- mode: via LAMOrchestrator.process; LLM: stubbed
- run at 2026-10-08 03:38:22, 22.0s

## Summary

| Conversation | Agent | Properties | Questions | Fields collected per turn | Record fields reused | Rows persisted | Misrouted turns |
|---|---|---|---|---|---|---|---|
| c01_pain_tka_calf | pain | 9/21 | 7 | 0 · 0 · 0 · 3 · 1 · 0 · 0 · 1 (=5) | 0/2 | 0 | 4 (RED pre-empted) |
| c02_pain_tha_groin | pain | 10/16 | 3 | 1 · 1 · 1 · 1 · 0 (=4) | 0/2 | 1 | 5 (fresh) |
| c03_recovery_tka_day10 | recovery | 5/15 | 6 | 0 · 0 · 0 · 0 · 1 · 0 (=1) | 0/2 | 0 | - |
| c04_recovery_tha_day30 | recovery | 5/12 | 0 | 0 · 0 · 0 · 0 · 0 (=0) | 0/0 | 0 | 2 (fresh), 4 (fresh) |
| c05_rehab_tka_stairs | rehab | 5/10 | 1 | 0 · 0 (=0) | 0/1 | 0 | 1 (fresh), 2 (fresh) |
| c06_rehab_tha_missed_days | rehab | 6/12 | 2 | 0 · 0 · 0 (=0) | 0/1 | 0 | 2 (fresh), 3 (fresh) |
| c07_rehab_safety_hold | rehab | 7/11 | 1 | 0 · 0 (=0) | 0/0 | 0 | - |
| c08_pain_bug_nonnumeric_score | pain | 13/16 | 5 | 1 · 0 · 1 · 1 · 1 · 1 (=5) | 0/1 | 1 | - |
| c09_pain_bug_offtopic_reply | pain | 10/15 | 5 | 0 · 1 · 0 · 1 · 1 · 1 (=4) | 0/1 | 0 | - |
| c10_pain_bug_detour_resume | pain | 7/14 | 5 | 0 · 1 · 1 · 0 · 1 (=3) | 0/1 | 0 | - |
| c11_pain_multislot_opening | pain | 5/13 | 0 | 0 · 0 (=0) | 0/1 | 0 | 1 (fresh), 2 (fresh) |
| c12_pain_abandoned | pain | 8/8 | 3 | 1 · 1 · 1 (=3) | 0/0 | 0 | - |
| c13_pain_mild_medication | pain | 5/13 | 0 | 0 · 0 · 0 · 0 · 0 (=0) | 0/1 | 0 | 1 (fresh), 2 (fresh), 3 (fresh), 4 (fresh), 5 (fresh) |
| c14_recovery_tka_day4_target | recovery | 5/14 | 3 | 0 · 0 · 1 · 0 · 0 · 0 (=1) | 0/0 | 0 | 1 (fresh), 4 (fresh) |
| c15_recovery_request_current_rom | recovery | 6/13 | 3 | 0 · 1 · 0 · 0 (=1) | 0/2 | 0 | 4 (pending answer) |
| c16_recovery_multislot | recovery | 7/14 | 2 | 2 · 0 · 0 (=2) | 0/0 | 0 | - |
| c17_recovery_abandoned | recovery | 7/7 | 1 | 0 · 1 (=1) | 0/0 | 0 | - |
| c18_recovery_tka_day90_longterm | recovery | 8/14 | 0 | 0 · 0 · 1 · 1 · 0 · 0 (=2) | 0/0 | 0 | - |
| c19_recovery_unknown_twice | recovery | 5/15 | 5 | 0 · 0 · 0 · 1 · 0 · 0 · 0 (=1) | 0/0 | 0 | 5 (fresh) |
| c20_rehab_direct_question | rehab | 4/10 | 2 | 0 · 0 (=0) | 0/1 | 0 | 2 (fresh) |
| c21_rehab_status_unknown | rehab | 5/12 | 2 | 0 · 0 · 0 (=0) | 0/0 | 0 | 2 (fresh), 3 (fresh) |
| c22_rehab_multislot | rehab | 5/12 | 1 | 0 (=0) | 0/1 | 0 | - |
| c23_rehab_abandoned | rehab | 7/8 | 1 | 0 · 0 (=0) | 0/0 | 0 | 2 (fresh) |
| c24_rehab_request_nwb_override | rehab | 6/11 | 1 | 0 · 0 (=0) | 0/1 | 0 | 2 (fresh) |

## Properties

### c01_pain_tka_calf -- TKA calf case: memory confirm, non-numeric reply, multi-slot correction

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | pain_score -> not collected |
| 2 | reply_does_not_match | **FAIL** | /None pain/ hit 'None pain' |
| 3 | does_not_collect | PASS | onset -> not collected |
| 3 | reply_does_not_match | **FAIL** | /\bNone\b/ hit 'None' |
| 4 | collects_field | PASS | pain_score -> 7 |
| 4 | collects_field | PASS | onset -> sudden |
| 4 | collects_field | PASS | location -> in the calf |
| 5 | collects_field | PASS | swelling -> swollen |
| 6 | collects_field | **FAIL** | warmth_or_redness -> not collected |
| 7 | collects_field | **FAIL** | numbness_or_weakness -> not collected |
| 8 | collects_field | PASS | fever_or_temperature -> no |
| - | no_question_for_record_data | **FAIL** | turn 1: pain_score; turn 2: pain_score; turn 3: pain_score; turn 5: pain_score; turn 6: pain_score; turn 7: pain_score; turn 8: pain_score |
| - | no_reask_of_collected_field | **FAIL** | turn 5: pain_score |
| - | max_questions | PASS | 7 asked, max 7 |
| - | triage_equals_engine | **FAIL** | turn 6: got YELLOW, engine GREEN; turn 7: got YELLOW, engine GREEN; turn 8: got YELLOW, engine GREEN; turn 4: RED from cumulative triage (engine on turn text GREEN) |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks pain_score |
| - | final_has_trend_or_checkpoint | **FAIL** | /Compared with last time/ |
| - | final_has_next_step | **FAIL** | /Next step:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** My knee has been hurting since this morning.

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields - [routed to PainSymptomsAgent]*

**Patient (2):** yes

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields - [routed to PainSymptomsAgent]*

**Patient (3):** it really hurts

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields - [routed to PainSymptomsAgent]*

**Patient (4):** 7 out of 10, started suddenly yesterday in the calf

> 🚨 **CRITICAL EMERGENCY ALERT**
> 
> Your reported symptoms require urgent medical evaluation: **DVT / Thromboembolism indicator: 'calf' + 'pain'**.
> 
> Immediate contact with hospital emergency triage or operating surgeon. Do NOT wait. Suspected complication requires physical examination and immediate Doppler/bloodwork.
> 
> Please contact your hospital emergency line or visit the nearest emergency department right away.

*engine Deterministic Safety Triage; triage RED (engine GREEN); asked -; new fields location, onset, pain_score [routed to SafetyTriageAgent, red_preempted]*

**Patient (5):** yes it's swollen

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage YELLOW (engine YELLOW); asked pain_score; new fields swelling [routed to PainSymptomsAgent]*

**Patient (6):** no

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage YELLOW (engine GREEN); asked pain_score; new fields - [routed to PainSymptomsAgent]*

**Patient (7):** no

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage YELLOW (engine GREEN); asked pain_score; new fields - [routed to PainSymptomsAgent]*

**Patient (8):** no fever

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage YELLOW (engine GREEN); asked pain_score; new fields fever_or_temperature [routed to PainSymptomsAgent]*

</details>

### c02_pain_tha_groin -- THA groin case: hip wording, location asked, groin not stored as trend

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | pain_score -> 6 |
| 3 | collects_field | PASS | onset -> gradual |
| 4 | collects_field | PASS | location -> My hip |
| 4 | does_not_store_unfitting_reply | **FAIL** | worsening_or_improving = 'in the groin' must not contain 'groin' |
| 5 | collects_field | PASS | worsening_or_improving -> in the groin |
| 5 | does_not_store_unfitting_reply | **FAIL** | location = 'My hip' must not contain 'hip' |
| - | no_question_for_record_data | **FAIL** | turn 1: pain_score |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 3 asked, max 4 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /Compared with last time/ |
| - | final_has_next_step | **FAIL** | /Next step:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | **FAIL** | turn 5: RecoveryProgressAgent (fresh_classification, expected PainSymptomsAgent) |

<details><summary>Transcript</summary>

**Patient (1):** My hip is sore today.

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields location [routed to PainSymptomsAgent]*

**Patient (2):** no, it's more like a 6

> Okay, 6 out of 10 -- that helps me understand how strong the pain is. Did it come on suddenly, or has it been building up gradually?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score [routed to PainSymptomsAgent]*

**Patient (3):** gradually

> Got it -- that's useful to know. Is it getting worse, getting better, or staying about the same?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked worsening_or_improving; new fields onset [routed to PainSymptomsAgent]*

**Patient (4):** in the groin

> Thanks for going through that with me. Based on what you've told me:
> - pain score: 6/10
> - how it started: gradual
> - where it's felt: My hip
> - how it's trending: in the groin
> 
> Following your surgical team's guidance: Continue prescribed home rehabilitation exercises, cryotherapy, elevation, and oral medication schedule. Log next check-in as scheduled. That's higher than the pain score of 5/10 recorded last time.
> 
> This is a preliminary read based on what you've described and isn't a diagnosis.

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields worsening_or_improving [routed to PainSymptomsAgent]*

**Patient (5):** about the same

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent, fresh_classification]*

</details>

### c03_recovery_tka_day10 -- TKA day 10: confirm logged ROM, flat-on-the-bed rephrase, walking and stairs

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | rom_flexion_degrees -> not collected |
| 4 | collects_field | **FAIL** | rom_extension_degrees -> not collected |
| 5 | collects_field | PASS | mobility_status -> cane |
| 5 | collects_field | **FAIL** | walking_duration_minutes -> not collected |
| 6 | collects_field | **FAIL** | stairs -> not collected |
| - | no_question_for_record_data | **FAIL** | turn 1: rom_flexion_degrees; turn 2: rom_flexion_degrees; turn 3: rom_flexion_degrees; turn 4: rom_flexion_degrees; turn 5: rom_flexion_degrees; turn 6: rom_flexion_degrees |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | **FAIL** | 6 asked, max 5 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks rom_flexion_degrees |
| - | final_has_trend_or_checkpoint | **FAIL** | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | **FAIL** | /Next milestone:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** How is my recovery going?

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (2):** it's about 85 now

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (3):** I don't know the number

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (4):** almost, there's a small gap

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (5):** I'm using a cane and I can walk about 15 minutes

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields mobility_status [routed to RecoveryProgressAgent]*

**Patient (6):** one step at a time holding the rail

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

</details>

### c04_recovery_tha_day30 -- THA day 30: walking aid, duration, stairs, hip precautions

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | mobility_status -> not collected |
| 3 | collects_field | **FAIL** | walking_duration_minutes -> not collected |
| 4 | collects_field | **FAIL** | stairs -> not collected |
| 5 | collects_field | **FAIL** | hip_precautions -> not collected |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 0 asked, max 4 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | **FAIL** | /Next milestone:/ |
| - | routed_to_expected_agent | **FAIL** | turn 2: IntakeContextAgent (fresh_classification, expected RecoveryProgressAgent); turn 4: RehabilitationAgent (fresh_classification, expected RecoveryProgressAgent) |

<details><summary>Transcript</summary>

**Patient (1):** How is my hip recovery going?

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent]*

**Patient (2):** I'm still using one crutch

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to IntakeContextAgent, fresh_classification]*

**Patient (3):** about 20 minutes

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent]*

**Patient (4):** foot over foot now

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RehabilitationAgent, fresh_classification]*

**Patient (5):** yes, still following them

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent]*

</details>

### c05_rehab_tka_stairs -- TKA day 5 stairs: status from record, one safety question, sourced answer

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | exercise_safety -> not collected |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 1 asked, max 1 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks a question |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | **FAIL** | /Next session:/ |
| - | routed_to_expected_agent | **FAIL** | turn 1: DailyActivityAgent (fresh_classification, expected RehabilitationAgent); turn 2: RecoveryProgressAgent (fresh_classification, expected RehabilitationAgent) |

<details><summary>Transcript</summary>

**Patient (1):** Can I go up and down the stairs yet?

> Good question about climbing stairs on Day 5 after your Total Knee Arthroplasty (TKA) (Right). Here's some general guidance:
> 
> • Going up: lead with your non-operated ("good") leg first, then bring your operated leg and any walking aid up to meet it -- "up with the good, down with the bad."
> • Going down: lead with your operated leg and your walking aid first, then bring your non-operated leg down to meet them.
> • Always use the handrail if one is available, and go at a slow, steady pace -- there's no need to rush.
> • If you feel unsteady, ask someone to spot you, or avoid stairs alone until you feel more confident.
> 
> This is general guidance -- always follow your surgical team's specific instructions for your case, especially your prescribed weight-bearing status.

*engine Daily Activity Agent - Guided Fallback; triage GREEN (engine GREEN); asked -; new fields - [routed to DailyActivityAgent, fresh_classification]*

**Patient (2):** no, nothing sharp

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent, fresh_classification]*

</details>

### c06_rehab_tha_missed_days -- THA day 20: missed-days opener, barrier carried into the close, unknown status

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | exercise_barrier -> not collected |
| 3 | collects_field | **FAIL** | exercise_safety -> not collected |
| 3 | reply_does_not_match | PASS | /(?i)knee flexion\|seated knee extension\|swelling .* is normal/ |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 2 asked, max 2 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks a question |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | **FAIL** | /Next session:/ |
| - | weight_bearing_record_unchanged | PASS | None -> None |
| - | routed_to_expected_agent | **FAIL** | turn 2: PainSymptomsAgent (fresh_classification, expected RehabilitationAgent); turn 3: PainSymptomsAgent (fresh_classification, expected RehabilitationAgent) |

<details><summary>Transcript</summary>

**Patient (1):** What exercises should I be doing now?

> At Day 20, work on progressing your passive flexion past 90°, standing calf raises, seated knee extension, and increasing your independent walking endurance as tolerated.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RehabilitationAgent]*

**Patient (2):** the evenings are too sore to face them

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked -; new fields - [routed to PainSymptomsAgent, fresh_classification]*

**Patient (3):** no sharp pain and no swelling

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked -; new fields - [routed to PainSymptomsAgent, fresh_classification]*

</details>

### c07_rehab_safety_hold -- TKA day 12 safety hold: sharp pain from heel slides pauses the exercise

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | exercise_safety -> not collected |
| 2 | reply_matches | **FAIL** | /(?i)pause heel slides/ |
| 2 | reply_does_not_match | PASS | /(?i)\b(is normal\|nothing to worry\|perfectly fine)\b/ |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 1 asked, max 1 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks a question |
| - | final_has_next_step | **FAIL** | /Next session:/ |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** How do I do heel slides?

> Based on your Day 12 protocol for Total Knee Arthroplasty (TKA): Target milestones for Total Knee Arthroplasty: By Post-Op Day 7, patients should aim for 70°-90° of passive flexion and near-full extension (0°-5°). Full terminal extension is critical; patients should avoid putting pillows directly under the knee joint, placing pillows under the ankle/calf instead to promote gravity extension.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RehabilitationAgent]*

**Patient (2):** yes, heel slides give me a sharp pain

> **MedicationAgent**
> Mild to moderate soreness is typical on Day 12. Take your prescribed pain medication 30-45 minutes before starting physical therapy to keep your discomfort manageable.
> 
> **PainSymptomsAgent**
> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?
> 
> **RehabilitationAgent**
> Mild to moderate soreness is typical on Day 12. Take your prescribed pain medication 30-45 minutes before starting physical therapy to keep your discomfort manageable.

*engine Deterministic Multi-Agent Coordinator; triage GREEN (engine GREEN); asked -; new fields - [routed to MedicationAgent,PainSymptomsAgent,RehabilitationAgent]*

</details>

### c08_pain_bug_nonnumeric_score -- Bug 1a: a non-numeric reply to the score question is clarified, never 'None pain'

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | does_not_collect | PASS | pain_score -> not collected |
| 2 | reply_does_not_match | **FAIL** | /\bNone\b/ hit 'None' |
| 3 | collects_field | PASS | pain_score -> 5 |
| 3 | reply_does_not_match | PASS | /\bNone\b/ |
| 4 | collects_field | PASS | onset -> gradual |
| 5 | collects_field | PASS | location -> around the kneecap |
| 6 | collects_field | PASS | worsening_or_improving -> improving |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 5 asked, max 5 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /Compared with last time/ |
| - | final_has_next_step | **FAIL** | /Next step:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** My knee is aching today.

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields pain_characteristics [routed to PainSymptomsAgent]*

**Patient (2):** it really hurts

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields - [routed to PainSymptomsAgent]*

**Patient (3):** about a 5

> Okay, 5 out of 10 -- that helps me understand how strong the pain is. Did it come on suddenly, or has it been building up gradually?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score [routed to PainSymptomsAgent]*

**Patient (4):** gradually

> Got it -- that's useful to know. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset [routed to PainSymptomsAgent]*

**Patient (5):** around the kneecap

> Got it. Is it getting worse, getting better, or staying about the same?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked worsening_or_improving; new fields location [routed to PainSymptomsAgent]*

**Patient (6):** getting a bit better

> Thanks for going through that with me. Based on what you've told me:
> - pain score: 5/10
> - how it started: gradual
> - where it's felt: around the kneecap
> - how it's trending: improving
> - what the pain feels like: aching
> 
> Following your surgical team's guidance: Continue prescribed home rehabilitation exercises, cryotherapy, elevation, and oral medication schedule. Log next check-in as scheduled. That's higher than the pain score of 4/10 recorded last time.
> 
> This is a preliminary read based on what you've described and isn't a diagnosis.

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields worsening_or_improving [routed to PainSymptomsAgent]*

</details>

### c09_pain_bug_offtopic_reply -- Bug 1b: 'Can I shower tomorrow?' is never stored as the onset

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | pain_score -> 6 |
| 3 | does_not_store_unfitting_reply | PASS | onset = '' must not contain 'shower' |
| 4 | collects_field | PASS | onset -> gradual |
| 4 | does_not_store_unfitting_reply | PASS | onset = 'gradual' must not contain 'shower' |
| 5 | collects_field | PASS | location -> behind the knee |
| 6 | collects_field | PASS | worsening_or_improving -> worsening |
| - | no_reask_of_collected_field | **FAIL** | turn 4: pain_score |
| - | max_questions | PASS | 5 asked, max 5 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks pain_score |
| - | final_has_trend_or_checkpoint | **FAIL** | /Compared with last time/ |
| - | final_has_next_step | **FAIL** | /Next step:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** My knee hurts quite a lot today.

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields - [routed to PainSymptomsAgent]*

**Patient (2):** 6

> Okay, 6 out of 10 -- that helps me understand how strong the pain is. Did it come on suddenly, or has it been building up gradually?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score [routed to PainSymptomsAgent]*

**Patient (3):** Can I shower tomorrow?

> Good question about showering or bathing on Day 4 after your Total Knee Arthroplasty (TKA) (Right). Here's some general guidance:
> 
> • Follow your surgical team's specific guidance on when the incision is allowed to get wet -- this varies by procedure and how it's healing.
> • Use a shower chair or non-slip mat, and consider a handheld showerhead if getting in and out of a tub is difficult.
> • Keep the incision covered as instructed until you're cleared for regular showering.
> 
> This is general guidance -- always follow your surgical team's specific instructions for your case, especially your prescribed weight-bearing status.

*engine Daily Activity Agent - Guided Fallback; triage GREEN (engine GREEN); asked -; new fields - [routed to DailyActivityAgent]*

**Patient (4):** it came on gradually

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields onset [routed to PainSymptomsAgent]*

**Patient (5):** behind the knee

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields location [routed to PainSymptomsAgent]*

**Patient (6):** getting worse

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields worsening_or_improving [routed to PainSymptomsAgent]*

</details>

### c10_pain_bug_detour_resume -- Bug 1c: after a stairs detour the open onset question resumes, nothing re-asked

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | pain_score -> 5 |
| 4 | collects_field | **FAIL** | pain_score -> not collected |
| 4 | collects_field | PASS | onset -> gradual |
| 5 | collects_field | **FAIL** | location -> not collected |
| 6 | collects_field | PASS | worsening_or_improving -> worsening |
| - | no_reask_of_collected_field | **FAIL** | turn 4: pain_score |
| - | max_questions | PASS | 5 asked, max 6 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks pain_score |
| - | final_has_trend_or_checkpoint | **FAIL** | /Compared with last time/ |
| - | final_has_next_step | **FAIL** | /Next step:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** My knee is really sore today.

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields - [routed to PainSymptomsAgent]*

**Patient (2):** 5

> Okay, 5 out of 10 -- that helps me understand how strong the pain is. Did it come on suddenly, or has it been building up gradually?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score [routed to PainSymptomsAgent]*

**Patient (3):** Can I climb stairs?

> Good question about climbing stairs on Day 5 after your Total Knee Arthroplasty (TKA) (Right). Here's some general guidance:
> 
> • Going up: lead with your non-operated ("good") leg first, then bring your operated leg and any walking aid up to meet it -- "up with the good, down with the bad."
> • Going down: lead with your operated leg and your walking aid first, then bring your non-operated leg down to meet them.
> • Always use the handrail if one is available, and go at a slow, steady pace -- there's no need to rush.
> • If you feel unsteady, ask someone to spot you, or avoid stairs alone until you feel more confident.
> 
> This is general guidance -- always follow your surgical team's specific instructions for your case, especially your prescribed weight-bearing status.

*engine Daily Activity Agent - Guided Fallback; triage GREEN (engine GREEN); asked -; new fields - [routed to DailyActivityAgent]*

**Patient (4):** gradually

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields onset [routed to PainSymptomsAgent]*

**Patient (5):** on the inside of the knee

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields - [routed to PainSymptomsAgent]*

**Patient (6):** getting worse

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields worsening_or_improving [routed to PainSymptomsAgent]*

</details>

### c11_pain_multislot_opening -- Multi-slot: score, onset and location in the opening message

| Turn | Property | Result | Detail |
|---|---|---|---|
| 1 | collects_field | **FAIL** | pain_score -> not collected |
| 1 | collects_field | **FAIL** | onset -> not collected |
| 1 | collects_field | **FAIL** | location -> not collected |
| 2 | collects_field | **FAIL** | worsening_or_improving -> not collected |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 0 asked, max 1 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /Compared with last time/ |
| - | final_has_next_step | **FAIL** | /Next step:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | **FAIL** | turn 1: IntakeContextAgent (fresh_classification, expected PainSymptomsAgent); turn 2: RecoveryProgressAgent (fresh_classification, expected PainSymptomsAgent) |

<details><summary>Transcript</summary>

**Patient (1):** It's about a 5 out of 10, it came on gradually, and it's behind the knee.

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to IntakeContextAgent, fresh_classification]*

**Patient (2):** getting a bit better

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent, fresh_classification]*

</details>

### c12_pain_abandoned -- Abandoned interview: the patient stops after two answers, nothing persisted

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | pain_score -> 6 |
| 3 | collects_field | PASS | onset -> sudden |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 3 asked, max 3 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | abandoned_persists_nothing | PASS | 0 row(s) written |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** My knee is throbbing.

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields pain_characteristics [routed to PainSymptomsAgent]*

**Patient (2):** 6

> Okay, 6 out of 10 -- that helps me understand how strong the pain is. Did it come on suddenly, or has it been building up gradually?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score [routed to PainSymptomsAgent]*

**Patient (3):** it came on suddenly

> Got it -- that's useful to know. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset [routed to PainSymptomsAgent]*

</details>

### c13_pain_mild_medication -- Mild pain after paracetamol: short joint branch plus the medication-effect question

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | pain_score -> not collected |
| 3 | collects_field | **FAIL** | onset -> not collected |
| 4 | collects_field | **FAIL** | location -> not collected |
| 5 | collects_field | **FAIL** | medication_effect -> not collected |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 0 asked, max 4 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /Compared with last time/ |
| - | final_has_next_step | **FAIL** | /Next step:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | **FAIL** | turn 1: MedicationAgent (fresh_classification, expected PainSymptomsAgent); turn 2: RecoveryProgressAgent (fresh_classification, expected PainSymptomsAgent); turn 3: RecoveryProgressAgent (fresh_classification, expected PainSymptomsAgent); turn 4: IntakeContextAgent (fresh_classification, expected PainSymptomsAgent); turn 5: MedicationAgent (fresh_classification, expected PainSymptomsAgent) |

<details><summary>Transcript</summary>

**Patient (1):** My knee aches a little, I took paracetamol an hour ago.

> I can help explain a medication in your postoperative record. Tell me its name, or ask about its purpose, prescribed dose, timing, or a possible side effect.

*engine Medication Proactive Information Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to MedicationAgent, fresh_classification]*

**Patient (2):** 3

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent, fresh_classification]*

**Patient (3):** gradually

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent, fresh_classification]*

**Patient (4):** around the kneecap

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to IntakeContextAgent, fresh_classification]*

**Patient (5):** yes it helped

> *(empty reply)*

*engine Medication Proactive + Clinical Synthesis; triage GREEN (engine GREEN); asked -; new fields - [routed to MedicationAgent, fresh_classification]*

</details>

### c14_recovery_tka_day4_target -- TKA day 4: before the first checkpoint, the day-7 target is given

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | rom_flexion_degrees -> not collected |
| 3 | collects_field | PASS | rom_extension_degrees -> 10.0 |
| 4 | collects_field | **FAIL** | mobility_status -> not collected |
| 5 | collects_field | **FAIL** | walking_duration_minutes -> not collected |
| 6 | collects_field | **FAIL** | stairs -> not collected |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 3 asked, max 5 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks rom_flexion_degrees |
| - | final_has_trend_or_checkpoint | **FAIL** | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | **FAIL** | /Next milestone:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | **FAIL** | turn 1: IntakeContextAgent (fresh_classification, expected RecoveryProgressAgent); turn 4: RehabilitationAgent (fresh_classification, expected RecoveryProgressAgent) |

<details><summary>Transcript</summary>

**Patient (1):** Am I on track with my knee?

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to IntakeContextAgent, fresh_classification]*

**Patient (2):** about 60 degrees

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (3):** about 10 degrees off straight

> Got it -- 10° helps me understand where you are. You're currently on post-op day 4, and the first extension checkpoint I have is for day 7, so it's a little early to compare you against that target.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields rom_extension_degrees [routed to RecoveryProgressAgent]*

**Patient (4):** I use a walker

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RehabilitationAgent, fresh_classification]*

**Patient (5):** about 5 minutes

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (6):** not yet

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

</details>

### c15_recovery_request_current_rom -- current_rom in the request: flexion and extension are fed back, never asked

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | mobility_status -> cane |
| 3 | collects_field | **FAIL** | walking_duration_minutes -> not collected |
| 4 | collects_field | **FAIL** | stairs -> not collected |
| - | no_question_for_record_data | **FAIL** | turn 1: rom_flexion_degrees; turn 2: rom_flexion_degrees; turn 3: rom_flexion_degrees |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 3 asked, max 3 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | **FAIL** | /Next milestone:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | **FAIL** | turn 4: DailyActivityAgent (continuation, expected RecoveryProgressAgent) |

<details><summary>Transcript</summary>

**Patient (1):** How's my progress looking?

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (2):** a cane

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields mobility_status [routed to RecoveryProgressAgent]*

**Patient (3):** about 20 minutes

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (4):** one step at a time

> Good question about daily activities on Day 16 after your Total Knee Arthroplasty (TKA) (Right). Here's some general guidance:
> 
> • Pace yourself -- alternate activity with rest rather than pushing through fatigue.
> • Follow your prescribed weight-bearing status for this activity, the same way you would for walking.
> • If an activity causes a sharp increase in pain or swelling, stop and rest, and mention it to your surgical team if it continues.
> 
> This is general guidance -- always follow your surgical team's specific instructions for your case, especially your prescribed weight-bearing status.

*engine Daily Activity Agent - Guided Fallback; triage GREEN (engine GREEN); asked -; new fields - [routed to DailyActivityAgent, continuation]*

</details>

### c16_recovery_multislot -- Multi-slot: flexion, walking aid and walking time in one message

| Turn | Property | Result | Detail |
|---|---|---|---|
| 1 | collects_field | PASS | rom_flexion_degrees -> 95.0 |
| 1 | collects_field | PASS | mobility_status -> cane |
| 1 | collects_field | **FAIL** | walking_duration_minutes -> not collected |
| 2 | collects_field | **FAIL** | rom_extension_degrees -> not collected |
| 3 | collects_field | **FAIL** | stairs -> not collected |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 2 asked, max 2 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks rom_extension_degrees |
| - | final_has_trend_or_checkpoint | **FAIL** | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | **FAIL** | /Next milestone:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** I can bend my knee to 95 degrees and walk with a cane for about 20 minutes. How am I doing?

> **RehabilitationAgent**
> 
> 
> **RecoveryProgressAgent**
> Okay -- your flexion of 95° exceeds the 70°-90° range stated for the earlier Post-Op Day 7 checkpoint.

*engine Deterministic Multi-Agent Coordinator; triage GREEN (engine GREEN); asked -; new fields mobility_status, rom_flexion_degrees [routed to RehabilitationAgent,RecoveryProgressAgent]*

**Patient (2):** about 3 degrees

> Do you know your current knee extension measurement in degrees (how close to fully straight)?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (3):** foot over foot

> Just circling back to this -- Do you know your current knee extension measurement in degrees (how close to fully straight)?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields - [routed to RecoveryProgressAgent]*

</details>

### c17_recovery_abandoned -- Abandoned interview: flexion given, then the patient leaves; nothing persisted

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | rom_flexion_degrees -> 90.0 |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 1 asked, max 2 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | abandoned_persists_nothing | PASS | 0 row(s) written |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** How is my knee recovery going?

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (2):** about 90 degrees

> Thanks for sharing that -- your flexion of 90° is within the 70°-90° range stated for the earlier Post-Op Day 7 checkpoint.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields rom_flexion_degrees [routed to RecoveryProgressAgent]*

</details>

### c18_recovery_tka_day90_longterm -- TKA day 90: compared with the long-term guidance

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | rom_flexion_degrees -> not collected |
| 3 | collects_field | PASS | rom_extension_degrees -> 0.0 |
| 4 | collects_field | PASS | mobility_status -> independent |
| 5 | collects_field | **FAIL** | walking_duration_minutes -> not collected |
| 6 | collects_field | **FAIL** | stairs -> not collected |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 0 asked, max 5 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | **FAIL** | /Next milestone:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** Is my recovery on track now?

> The source I have only supports comparison within its stated day range, and your current day falls outside that range, so I can't give a supported verdict right now.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent]*

**Patient (2):** 115 degrees

> The source I have only supports comparison within its stated day range, and your current day falls outside that range, so I can't give a supported verdict right now.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent]*

**Patient (3):** 0 degrees, it goes fully straight

> The source I have only supports comparison within its stated day range, and your current day falls outside that range, so I can't give a supported verdict right now.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields rom_extension_degrees [routed to RecoveryProgressAgent]*

**Patient (4):** walking without any aid now

> The source I have only supports comparison within its stated day range, and your current day falls outside that range, so I can't give a supported verdict right now.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields mobility_status [routed to RecoveryProgressAgent]*

**Patient (5):** about 60 minutes

> The source I have only supports comparison within its stated day range, and your current day falls outside that range, so I can't give a supported verdict right now.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent]*

**Patient (6):** foot over foot

> The source I have only supports comparison within its stated day range, and your current day falls outside that range, so I can't give a supported verdict right now.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent]*

</details>

### c19_recovery_unknown_twice -- Two 'I don't know' answers: flexion is left, the interview moves on and names the gap

| Turn | Property | Result | Detail |
|---|---|---|---|
| 3 | does_not_collect | PASS | rom_flexion_degrees -> not collected |
| 4 | collects_field | **FAIL** | rom_extension_degrees -> not collected |
| 5 | collects_field | **FAIL** | mobility_status -> not collected |
| 6 | collects_field | **FAIL** | walking_duration_minutes -> not collected |
| 7 | collects_field | **FAIL** | stairs -> not collected |
| 7 | reply_matches | **FAIL** | /(?i)flexion: I don't have a value/ |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 5 asked, max 6 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks rom_extension_degrees |
| - | final_has_trend_or_checkpoint | **FAIL** | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | **FAIL** | /Next milestone:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | **FAIL** | turn 5: RehabilitationAgent (fresh_classification, expected RecoveryProgressAgent) |

<details><summary>Transcript</summary>

**Patient (1):** How am I doing with my knee?

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (2):** I don't know

> That's okay. About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (3):** no idea, sorry

> Coming back to my last question -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (4):** about 5 degrees

> Got it -- your flexion of 5° is below the 70°-90° range stated for the earlier Post-Op Day 7 checkpoint.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields rom_flexion_degrees [routed to RecoveryProgressAgent]*

**Patient (5):** a walker

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RehabilitationAgent, fresh_classification]*

**Patient (6):** 10 minutes

> Do you know your current knee extension measurement in degrees (how close to fully straight)?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (7):** not yet

> Just circling back to this -- Do you know your current knee extension measurement in degrees (how close to fully straight)?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields - [routed to RecoveryProgressAgent]*

</details>

### c20_rehab_direct_question -- Direct question naming an exercise: one question, today's log not re-asked

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | exercise_safety -> not collected |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status, exercises_done_today |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | **FAIL** | 2 asked, max 1 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks a question |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | **FAIL** | /Next session:/ |
| - | routed_to_expected_agent | **FAIL** | turn 2: MedicationAgent,PainSymptomsAgent (fresh_classification, expected RehabilitationAgent) |

<details><summary>Transcript</summary>

**Patient (1):** How do I do heel slides?

> Based on your Day 8 protocol for Total Knee Arthroplasty (TKA): Target milestones for Total Knee Arthroplasty: By Post-Op Day 7, patients should aim for 70°-90° of passive flexion and near-full extension (0°-5°). Full terminal extension is critical; patients should avoid putting pillows directly under the knee joint, placing pillows under the ankle/calf instead to promote gravity extension.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RehabilitationAgent]*

**Patient (2):** no, nothing hurts

> **MedicationAgent**
> Thank you for letting me know. Managing your medications on time is essential for optimal recovery. Which specific medication was missed, and was it your morning or evening dose?
> 
> **PainSymptomsAgent**
> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Deterministic Multi-Agent Coordinator; triage GREEN (engine GREEN); asked -; new fields - [routed to MedicationAgent,PainSymptomsAgent, fresh_classification]*

</details>

### c21_rehab_status_unknown -- No status on record: two questions, 'not yet' persisted, surgeries untouched

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | exercise_safety -> not collected |
| 3 | collects_field | **FAIL** | exercises_done_today -> not collected |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 2 asked, max 2 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks a question |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | **FAIL** | /Next session:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | weight_bearing_record_unchanged | PASS | None -> None |
| - | routed_to_expected_agent | **FAIL** | turn 2: RecoveryProgressAgent (fresh_classification, expected RehabilitationAgent); turn 3: RecoveryProgressAgent (fresh_classification, expected RehabilitationAgent) |

<details><summary>Transcript</summary>

**Patient (1):** What exercises should I do today?

> At Day 10, work on progressing your passive flexion past 90°, standing calf raises, seated knee extension, and increasing your independent walking endurance as tolerated.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RehabilitationAgent]*

**Patient (2):** no

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent, fresh_classification]*

**Patient (3):** not yet

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent, fresh_classification]*

</details>

### c22_rehab_multislot -- Multi-slot: done today and no sharp pain in one message, answered at once

| Turn | Property | Result | Detail |
|---|---|---|---|
| 1 | collects_field | **FAIL** | exercises_done_today -> not collected |
| 1 | collects_field | **FAIL** | exercise_safety -> not collected |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | **FAIL** | 1 asked, max 0 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks a question |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | **FAIL** | /Next session:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** I did my exercises this morning and nothing hurts, no sharp pain. What exercises should I add next?

> **PainSymptomsAgent**
> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?
> 
> **RehabilitationAgent**
> At Day 9, work on progressing your passive flexion past 90°, standing calf raises, seated knee extension, and increasing your independent walking endurance as tolerated.

*engine Deterministic Multi-Agent Coordinator; triage GREEN (engine GREEN); asked -; new fields - [routed to PainSymptomsAgent,RehabilitationAgent]*

</details>

### c23_rehab_abandoned -- Abandoned interview: the safety question is never answered; nothing persisted

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | does_not_collect | PASS | exercise_safety -> not collected |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 1 asked, max 2 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | abandoned_persists_nothing | PASS | 0 row(s) written |
| - | routed_to_expected_agent | **FAIL** | turn 2: RecoveryProgressAgent (fresh_classification, expected RehabilitationAgent) |

<details><summary>Transcript</summary>

**Patient (1):** What exercises should I be doing?

> On Day 6, your targets are active-assisted heel slides aiming for 70°–90° flexion, straight leg raises to rebuild quadriceps strength, and walking 5–10 minutes with your walker every 2 hours.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RehabilitationAgent]*

**Patient (2):** hmm, let me think about that

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent, fresh_classification]*

</details>

### c24_rehab_request_nwb_override -- Request NWB overrides the WBAT record: squats question, no loading advice

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | exercise_safety -> not collected |
| 2 | reply_does_not_match | PASS | /(?i)\b(put (your )?(full )?weight\|bear (your )?full weight\|try (a )?squat)/ |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 1 asked, max 1 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks a question |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | **FAIL** | /Next session:/ |
| - | routed_to_expected_agent | **FAIL** | turn 2: RecoveryProgressAgent (fresh_classification, expected RehabilitationAgent) |

<details><summary>Transcript</summary>

**Patient (1):** Can I start doing squats?

> Hello! On Day 3 of your recovery from Total Knee Arthroplasty (TKA) (Right), make sure to keep up with your daily physical therapy routine, elevate your leg when resting, and stay hydrated.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RehabilitationAgent]*

**Patient (2):** no

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent, fresh_classification]*

</details>
