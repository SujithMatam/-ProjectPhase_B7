# Agent conversation eval -- head_orchestrator

- backend: this checkout (commit `86c40ab`)
- mode: via LAMOrchestrator.process; LLM: stubbed
- run at 2026-10-08 03:22:13, 19.1s

## Summary

| Conversation | Agent | Properties | Questions | Fields collected per turn | Record fields reused | Rows persisted | Misrouted turns |
|---|---|---|---|---|---|---|---|
| c01_pain_tka_calf | pain | 13/21 | 7 | 0 · 1 · 0 · 3 · 2 · 0 · 0 · 1 (=5) | 2/2 | 0 | 4 (RED pre-empted) |
| c02_pain_tha_groin | pain | 16/16 | 4 | 0 · 1 · 1 · 1 · 1 (=4) | 2/2 | 2 | - |
| c03_recovery_tka_day10 | recovery | 15/15 | 5 | 0 · 1 · 0 · 1 · 2 · 1 (=5) | 2/2 | 1 | - |
| c04_recovery_tha_day30 | recovery | 12/12 | 4 | 0 · 1 · 1 · 1 · 1 (=4) | 0/0 | 0 | - |
| c05_rehab_tka_stairs | rehab | 6/10 | 0 | 0 · 0 (=0) | 0/1 | 0 | 1 (fresh), 2 (fresh) |
| c06_rehab_tha_missed_days | rehab | 5/12 | 3 | 0 · 0 · 0 (=0) | 1/1 | 0 | 2 (pending answer), 3 (pending answer) |
| c07_rehab_safety_hold | rehab | 11/11 | 1 | 0 · 3 (=3) | 0/0 | 0 | - |
| c08_pain_bug_nonnumeric_score | pain | 16/16 | 5 | 1 · 0 · 1 · 1 · 1 · 1 (=5) | 1/1 | 2 | - |
| c09_pain_bug_offtopic_reply | pain | 15/15 | 4 | 0 · 1 · 0 · 1 · 1 · 1 (=4) | 1/1 | 2 | - |
| c10_pain_bug_detour_resume | pain | 14/14 | 4 | 0 · 1 · 1 · 1 · 1 (=4) | 1/1 | 2 | - |
| c11_pain_multislot_opening | pain | 5/13 | 0 | 0 · 0 (=0) | 0/1 | 0 | 1 (fresh), 2 (fresh) |
| c12_pain_abandoned | pain | 8/8 | 3 | 1 · 1 · 1 (=3) | 0/0 | 0 | - |
| c13_pain_mild_medication | pain | 5/13 | 0 | 0 · 0 · 0 · 0 · 0 (=0) | 0/1 | 0 | 1 (fresh), 2 (fresh), 3 (fresh), 4 (fresh), 5 (fresh) |
| c14_recovery_tka_day4_target | recovery | 5/14 | 5 | 0 · 0 · 1 · 0 · 1 · 0 (=2) | 0/0 | 0 | 4 (pending answer), 1 (fresh) |
| c15_recovery_request_current_rom | recovery | 6/13 | 3 | 0 · 1 · 1 · 0 (=2) | 0/2 | 0 | 4 (pending answer) |
| c16_recovery_multislot | recovery | 14/14 | 2 | 3 · 1 · 1 (=5) | 0/0 | 1 | - |
| c17_recovery_abandoned | recovery | 7/7 | 2 | 0 · 1 (=1) | 0/0 | 0 | - |
| c18_recovery_tka_day90_longterm | recovery | 13/14 | 5 | 0 · 1 · 1 · 1 · 1 · 1 (=5) | 0/0 | 1 | - |
| c19_recovery_unknown_twice | recovery | 15/15 | 6 | 0 · 0 · 0 · 1 · 1 · 1 · 1 (=4) | 0/0 | 1 | - |
| c20_rehab_direct_question | rehab | 4/10 | 2 | 0 · 0 (=0) | 0/1 | 0 | 2 (pending answer) |
| c21_rehab_status_unknown | rehab | 4/12 | 3 | 0 · 0 · 0 (=0) | 0/0 | 0 | 2 (pending answer), 3 (pending answer) |
| c22_rehab_multislot | rehab | 12/12 | 0 | 2 (=2) | 1/1 | 1 | - |
| c23_rehab_abandoned | rehab | 7/8 | 2 | 0 · 0 (=0) | 0/0 | 0 | 2 (pending answer) |
| c24_rehab_request_nwb_override | rehab | 5/11 | 2 | 0 · 0 (=0) | 0/1 | 0 | 2 (pending answer) |

## Properties

### c01_pain_tka_calf -- TKA calf case: memory confirm, non-numeric reply, multi-slot correction

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | pain_score -> 6 |
| 2 | reply_does_not_match | PASS | /None pain/ |
| 3 | does_not_collect | PASS | onset -> not collected |
| 3 | reply_does_not_match | PASS | /\bNone\b/ |
| 4 | collects_field | PASS | pain_score -> 7 |
| 4 | collects_field | PASS | onset -> sudden |
| 4 | collects_field | PASS | location -> in the calf |
| 5 | collects_field | PASS | swelling -> swollen |
| 6 | collects_field | **FAIL** | warmth_or_redness -> not collected |
| 7 | collects_field | **FAIL** | numbness_or_weakness -> not collected |
| 8 | collects_field | PASS | fever_or_temperature -> no |
| - | no_question_for_record_data | PASS | never asked: pain_score |
| - | no_reask_of_collected_field | **FAIL** | turn 5: location |
| - | max_questions | PASS | 7 asked, max 7 |
| - | triage_equals_engine | **FAIL** | turn 6: got YELLOW, engine GREEN; turn 7: got YELLOW, engine GREEN; turn 8: got YELLOW, engine GREEN; turn 4: RED from cumulative triage (engine on turn text GREEN) |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks worsening_or_improving |
| - | final_has_trend_or_checkpoint | **FAIL** | /Compared with last time/ |
| - | final_has_next_step | **FAIL** | /Next step:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** My knee has been hurting since this morning.

> Last time you had 7/10 behind the knee and it was getting worse -- let's see where things are now. Your log says 6/10 earlier today -- still about that? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields - [routed to PainSymptomsAgent]*

**Patient (2):** yes

> Okay, that helps me understand how strong it is -- so far: 6/10. Did it come on suddenly, or has it been building up gradually? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score [routed to PainSymptomsAgent]*

**Patient (3):** it really hurts

> So far: 6/10. Sorry, I didn't quite catch that. Would you say the pain started all at once, or built up gradually? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields - [routed to PainSymptomsAgent]*

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

> No worries -- I'll leave that as unclear for now; so far: 6/10, swelling: swollen. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage YELLOW (engine YELLOW); asked location; new fields pain_score, swelling [routed to PainSymptomsAgent]*

**Patient (6):** no

> So far: 6/10, swelling: swollen. Sorry, I didn't catch where it is. Just roughly, is it more in the knee, behind it, or lower down toward the calf? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage YELLOW (engine GREEN); asked location; new fields - [routed to PainSymptomsAgent]*

**Patient (7):** no

> No worries -- I'll leave that as unclear for now; so far: 6/10, swelling: swollen. Is it getting worse, getting better, or staying about the same? (last question)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage YELLOW (engine GREEN); asked worsening_or_improving; new fields - [routed to PainSymptomsAgent]*

**Patient (8):** no fever

> So far: 6/10, swelling: swollen, fever: no. Sorry, I didn't quite catch that. Compared to earlier, does it feel any different at all, or about the same? (last question)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage YELLOW (engine GREEN); asked worsening_or_improving; new fields fever_or_temperature [routed to PainSymptomsAgent]*

</details>

### c02_pain_tha_groin -- THA groin case: hip wording, location asked, groin not stored as trend

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | pain_score -> 6 |
| 3 | collects_field | PASS | onset -> gradual |
| 4 | collects_field | PASS | location -> in the groin |
| 4 | does_not_store_unfitting_reply | PASS | worsening_or_improving = '' must not contain 'groin' |
| 5 | collects_field | PASS | worsening_or_improving -> stable |
| 5 | does_not_store_unfitting_reply | PASS | location = 'in the groin' must not contain 'hip' |
| - | no_question_for_record_data | PASS | never asked: pain_score |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 4 asked, max 4 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | PASS | /Compared with last time/ |
| - | final_has_next_step | PASS | /Next step:/ |
| - | persists_on_completion | PASS | 2 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** My hip is sore today.

> Last time you had 5/10 in the thigh and it was about the same -- let's see where things are now. Your log says 4/10 earlier today -- still about that? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields - [routed to PainSymptomsAgent]*

**Patient (2):** no, it's more like a 6

> Okay, that helps me understand how strong it is -- so far: 6/10. Did it come on suddenly, or has it been building up gradually? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score [routed to PainSymptomsAgent]*

**Patient (3):** gradually

> Got it -- so far: 6/10, gradual onset. Where are you feeling it most -- in the groin, the thigh, the buttock, the calf, or somewhere else? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset [routed to PainSymptomsAgent]*

**Patient (4):** in the groin

> Got it -- so far: 6/10, gradual onset, in the groin. Is it getting worse, getting better, or staying about the same? (last question)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked worsening_or_improving; new fields location [routed to PainSymptomsAgent]*

**Patient (5):** about the same

> Thanks for going through that with me. Based on what you've told me:
> - pain score: 6/10
> - how it started: gradual
> - where it's felt: in the groin
> - how it's trending: stable
> 
> Compared with last time: That's higher than the pain score of 5/10 recorded last time. Last time it was in the thigh and about the same; now it's in the groin and about the same.
> 
> Following your surgical team's guidance: Continue prescribed home rehabilitation exercises, cryotherapy, elevation, and oral medication schedule. Log next check-in as scheduled.
> 
> Next step: note how the pain feels again this evening so we can compare it with today. Say 'pain check' any time and I'll compare with today.
> 
> This is a preliminary read based on what you've described and isn't a diagnosis.

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields worsening_or_improving [routed to PainSymptomsAgent]*

</details>

### c03_recovery_tka_day10 -- TKA day 10: confirm logged ROM, flat-on-the-bed rephrase, walking and stairs

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | rom_flexion_degrees -> 85.0 |
| 4 | collects_field | PASS | rom_extension_degrees -> ValueRange(low=0.0, high=5.0, label='nearly flat', low_exclusive=False) |
| 5 | collects_field | PASS | mobility_status -> cane |
| 5 | collects_field | PASS | walking_duration_minutes -> 15.0 |
| 6 | collects_field | PASS | stairs -> one_at_a_time |
| - | no_question_for_record_data | PASS | never asked: rom_flexion_degrees, rom_extension_degrees |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 5 asked, max 5 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | PASS | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | PASS | /Next milestone:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** How is my recovery going?

> Let's see where you are on post-op day 10. Your log from yesterday says you could bend to 80° -- still about that? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (2):** it's about 85 now

> Okay -- flexion of 85°, within the day-7 range of 70°-90° (according to the discharge guidance), and improving: 70 -> 80 -> 85. Your log from yesterday says your extension was 5° -- still about that? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields rom_flexion_degrees [routed to RecoveryProgressAgent]*

**Patient (3):** I don't know the number

> That's okay. Can you get the knee fully flat on the bed? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (4):** almost, there's a small gap

> Got it -- extension (nearly flat), within the day-7 range of 0°-5° (according to the discharge guidance), and improving: 8 -> 5. How are you currently getting around -- walking independently, or using a walker, cane, or crutches? (one or two more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked mobility_status; new fields rom_extension_degrees [routed to RecoveryProgressAgent]*

**Patient (5):** I'm using a cane and I can walk about 15 minutes

> Thanks for sharing that -- walking aid: a cane, matches the day-7 checkpoint (according to the discharge guidance): walking with a frame, crutches or cane on a level surface. walking duration: 15 minutes; the day-7 guidance gives no number, it expects walking little and often around the home. How are you managing stairs -- not yet, one step at a time holding the rail, or foot over foot? (last question)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked stairs; new fields mobility_status, walking_duration_minutes [routed to RecoveryProgressAgent]*

**Patient (6):** one step at a time holding the rail

> Here's how things compare on post-op day 10, according to the discharge guidance:
> - flexion: 85° -- within the day-7 range of 70°-90°; over the week 70 -> 80 -> 85, improving
> - extension: nearly flat -- within the day-7 range of 0°-5°; over the week 8 -> 5, improving
> - walking aid: a cane -- as the day-7 checkpoint describes (walking with a frame, crutches or cane on a level surface)
> - walking duration: 15 minutes -- no number in the day-7 guidance; it expects walking little and often around the home
> - stairs: one step at a time -- as the day-7 checkpoint describes (managing two or three steps up and down with your aid)
> 
> Next milestone: day 14 -- flexion: about 80 degrees or more of active bending, improving week by week; extension: straightening to within 10 degrees of fully straight. Say 'recovery check' at day 14 and I'll compare.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields stairs [routed to RecoveryProgressAgent]*

</details>

### c04_recovery_tha_day30 -- THA day 30: walking aid, duration, stairs, hip precautions

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | mobility_status -> crutches |
| 3 | collects_field | PASS | walking_duration_minutes -> 20.0 |
| 4 | collects_field | PASS | stairs -> foot_over_foot |
| 5 | collects_field | PASS | hip_precautions -> following |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 4 asked, max 4 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | PASS | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | PASS | /Next milestone:/ |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** How is my hip recovery going?

> Let's see where you are on post-op day 30. How are you currently getting around -- walking independently, or using a walker, cane, or crutches? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked mobility_status; new fields - [routed to RecoveryProgressAgent]*

**Patient (2):** I'm still using one crutch

> Okay -- walking aid: crutches, matches the day-21 checkpoint (according to the discharge guidance): one crutch or a cane once you can stand and walk for over ten minutes; there is no fixed date for giving up the aid. Roughly how many minutes can you walk at a stretch at the moment? (one or two more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked walking_duration_minutes; new fields mobility_status [routed to RecoveryProgressAgent]*

**Patient (3):** about 20 minutes

> Got it -- walking duration of 20 minutes, meets the day-21 mark of more than 10 minutes (according to the discharge guidance). How are you managing stairs -- not yet, one step at a time holding the rail, or foot over foot? (one more question after this)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked stairs; new fields walking_duration_minutes [routed to RecoveryProgressAgent]*

**Patient (4):** foot over foot now

> Thanks for sharing that -- stairs: foot over foot, matches the day-21 checkpoint (according to the discharge guidance): one step at a time with a handrail at first, foot over foot as you get stronger. Are you still keeping to your hip precautions -- not bending the hip past a right angle, not crossing your legs, avoiding low chairs? (last question)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked hip_precautions; new fields stairs [routed to RecoveryProgressAgent]*

**Patient (5):** yes, still following them

> Here's how things compare on post-op day 30, according to the discharge guidance:
> - walking aid: crutches -- as the day-21 checkpoint describes (one crutch or a cane once you can stand and walk for over ten minutes; there is no fixed date for giving up the aid)
> - walking duration: 20 minutes -- meets the day-21 mark of more than 10 minutes
> - stairs: foot over foot -- as the day-21 checkpoint describes (one step at a time with a handrail at first, foot over foot as you get stronger)
> - hip precautions: keeping to your hip precautions -- as the day-21 checkpoint describes (still following the hip precautions, which usually last about the first six weeks)
> 
> Next milestone: day 42 -- hip precautions: precautions commonly apply for about the first six weeks; wait for your surgeon to confirm they have ended; walking aid: reducing or stopping the walking aid when your physiotherapist advises. Say 'recovery check' at day 42 and I'll compare.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields hip_precautions [routed to RecoveryProgressAgent]*

</details>

### c05_rehab_tka_stairs -- TKA day 5 stairs: status from record, one safety question, sourced answer

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | exercise_safety -> not collected |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 0 asked, max 1 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
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

> Let's see where you are on post-op day 5. Your log from yesterday says you could bend to 75° -- still about that? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent, fresh_classification]*

</details>

### c06_rehab_tha_missed_days -- THA day 20: missed-days opener, barrier carried into the close, unknown status

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | exercise_barrier -> not collected |
| 3 | collects_field | **FAIL** | exercise_safety -> not collected |
| 3 | reply_does_not_match | PASS | /(?i)knee flexion\|seated knee extension\|swelling .* is normal/ |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | **FAIL** | 3 asked, max 2 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks exercise_barrier |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | **FAIL** | /Next session:/ |
| - | weight_bearing_record_unchanged | PASS | None -> None |
| - | routed_to_expected_agent | **FAIL** | turn 2: PainSymptomsAgent (continuation, expected RehabilitationAgent); turn 3: PainSymptomsAgent (continuation, expected RehabilitationAgent) |

<details><summary>Transcript</summary>

**Patient (1):** What exercises should I be doing now?

> Your log shows exercises missed on 2 of the last 7 days; anything making them hard? (one more question after this)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercise_barrier; new fields - [routed to RehabilitationAgent]*

**Patient (2):** the evenings are too sore to face them

> Thanks for telling me -- I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked exercise_barrier; new fields - [routed to PainSymptomsAgent, continuation]*

**Patient (3):** no sharp pain and no swelling

> So far: sharp, swelling: no. Sorry, I didn't catch a number there. Would you put it roughly in the mild range (1-3), moderate range (4-6), or severe range (7-10)? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked exercise_barrier; new fields - [routed to PainSymptomsAgent, continuation]*

</details>

### c07_rehab_safety_hold -- TKA day 12 safety hold: sharp pain from heel slides pauses the exercise

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | exercise_safety -> True |
| 2 | reply_matches | PASS | /(?i)pause heel slides/ |
| 2 | reply_does_not_match | PASS | /(?i)\b(is normal\|nothing to worry\|perfectly fine)\b/ |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 1 asked, max 1 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_next_step | PASS | /Next session:/ |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** How do I do heel slides?

> Before I answer: Does any exercise cause sharp pain, or swelling that lasts into the next day? (last question)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercise_safety; new fields - [routed to RehabilitationAgent]*

**Patient (2):** yes, heel slides give me a sharp pain

> **PainSymptomsAgent**
> Thanks for telling me -- I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now? (one or two more questions)
> 
> **RehabilitationAgent**
> Please pause heel slides for now and tell your physiotherapist about the sharp pain before your next session, so they can check it and adjust your programme. Keep to the rest of the programme as your physiotherapist set it.
> 
> Next session: wait for your physiotherapist's advice before repeating heel slides. Say 'rehab check' tomorrow and I'll see how it went.

*engine Deterministic Multi-Agent Coordinator; triage GREEN (engine GREEN); asked -; new fields exercise_safety, exercise_safety_exercise, exercise_safety_kind [routed to PainSymptomsAgent,RehabilitationAgent]*

</details>

### c08_pain_bug_nonnumeric_score -- Bug 1a: a non-numeric reply to the score question is clarified, never 'None pain'

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | does_not_collect | PASS | pain_score -> not collected |
| 2 | reply_does_not_match | PASS | /\bNone\b/ |
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
| - | final_has_trend_or_checkpoint | PASS | /Compared with last time/ |
| - | final_has_next_step | PASS | /Next step:/ |
| - | persists_on_completion | PASS | 2 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** My knee is aching today.

> Last time you had 4/10 around the kneecap and it was getting better -- let's see where things are now. On a scale from 0 to 10, how bad is the pain right now? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields pain_characteristics [routed to PainSymptomsAgent]*

**Patient (2):** it really hurts

> So far: aching. Sorry, I didn't catch a number there. Would you put it roughly in the mild range (1-3), moderate range (4-6), or severe range (7-10)? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields - [routed to PainSymptomsAgent]*

**Patient (3):** about a 5

> Okay, that helps me understand how strong it is -- so far: 5/10, aching. Did it come on suddenly, or has it been building up gradually? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score [routed to PainSymptomsAgent]*

**Patient (4):** gradually

> Got it -- so far: 5/10, gradual onset, aching. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset [routed to PainSymptomsAgent]*

**Patient (5):** around the kneecap

> Got it -- so far: 5/10, gradual onset, around the kneecap, aching. Is it getting worse, getting better, or staying about the same? (last question)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked worsening_or_improving; new fields location [routed to PainSymptomsAgent]*

**Patient (6):** getting a bit better

> Thanks for going through that with me. Based on what you've told me:
> - pain score: 5/10
> - how it started: gradual
> - where it's felt: around the kneecap
> - how it's trending: improving
> - what the pain feels like: aching
> 
> Compared with last time: That's higher than the pain score of 4/10 recorded last time. Last time it was around the kneecap and getting better; now it's around the kneecap and getting better.
> 
> Following your surgical team's guidance: Continue prescribed home rehabilitation exercises, cryotherapy, elevation, and oral medication schedule. Log next check-in as scheduled.
> 
> Next step: note how the pain feels again this evening so we can compare it with today. Say 'pain check' any time and I'll compare with today.
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
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 4 asked, max 5 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | PASS | /Compared with last time/ |
| - | final_has_next_step | PASS | /Next step:/ |
| - | persists_on_completion | PASS | 2 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** My knee hurts quite a lot today.

> Last time you had 5/10 behind the knee and it was about the same -- let's see where things are now. On a scale from 0 to 10, how bad is the pain right now? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields - [routed to PainSymptomsAgent]*

**Patient (2):** 6

> Okay, that helps me understand how strong it is -- so far: 6/10. Did it come on suddenly, or has it been building up gradually? (one or two more questions)

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

> Got it -- so far: 6/10, gradual onset. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset [routed to PainSymptomsAgent]*

**Patient (5):** behind the knee

> Got it -- so far: 6/10, gradual onset, behind the knee. Is it getting worse, getting better, or staying about the same? (last question)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked worsening_or_improving; new fields location [routed to PainSymptomsAgent]*

**Patient (6):** getting worse

> Thanks for going through that with me. Based on what you've told me:
> - pain score: 6/10
> - how it started: gradual
> - where it's felt: behind the knee
> - how it's trending: worsening
> 
> Compared with last time: That's higher than the pain score of 5/10 recorded last time. Last time it was behind the knee and about the same; now it's behind the knee and getting worse.
> 
> Following your surgical team's guidance: Continue prescribed home rehabilitation exercises, cryotherapy, elevation, and oral medication schedule. Log next check-in as scheduled.
> 
> Next step: note how the pain feels again this evening so we can compare it with today. Say 'pain check' any time and I'll compare with today.
> 
> This is a preliminary read based on what you've described and isn't a diagnosis.

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields worsening_or_improving [routed to PainSymptomsAgent]*

</details>

### c10_pain_bug_detour_resume -- Bug 1c: after a stairs detour the open onset question resumes, nothing re-asked

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | pain_score -> 5 |
| 4 | collects_field | PASS | pain_score -> 5 |
| 4 | collects_field | PASS | onset -> gradual |
| 5 | collects_field | PASS | location -> on the inside |
| 6 | collects_field | PASS | worsening_or_improving -> worsening |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 4 asked, max 6 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | PASS | /Compared with last time/ |
| - | final_has_next_step | PASS | /Next step:/ |
| - | persists_on_completion | PASS | 2 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** My knee is really sore today.

> Last time you had 6/10 behind the knee and it was about the same -- let's see where things are now. On a scale from 0 to 10, how bad is the pain right now? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields - [routed to PainSymptomsAgent]*

**Patient (2):** 5

> Okay, that helps me understand how strong it is -- so far: 5/10. Did it come on suddenly, or has it been building up gradually? (one or two more questions)

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

> Got it -- so far: 5/10, gradual onset. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset [routed to PainSymptomsAgent]*

**Patient (5):** on the inside of the knee

> Got it -- so far: 5/10, gradual onset, on the inside. Is it getting worse, getting better, or staying about the same? (last question)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked worsening_or_improving; new fields location [routed to PainSymptomsAgent]*

**Patient (6):** getting worse

> Thanks for going through that with me. Based on what you've told me:
> - pain score: 5/10
> - how it started: gradual
> - where it's felt: on the inside
> - how it's trending: worsening
> 
> Compared with last time: That's lower than the pain score of 6/10 recorded last time. Last time it was behind the knee and about the same; now it's on the inside and getting worse.
> 
> Following your surgical team's guidance: Continue prescribed home rehabilitation exercises, cryotherapy, elevation, and oral medication schedule. Log next check-in as scheduled.
> 
> Next step: note how the pain feels again this evening so we can compare it with today. Say 'pain check' any time and I'll compare with today.
> 
> This is a preliminary read based on what you've described and isn't a diagnosis.

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields worsening_or_improving [routed to PainSymptomsAgent]*

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

> Let's see where you are on post-op day 9. About how many degrees can you currently bend your knee? (a few more questions)

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

> Thanks for telling me -- I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields pain_characteristics [routed to PainSymptomsAgent]*

**Patient (2):** 6

> Okay, that helps me understand how strong it is -- so far: 6/10, throbbing. Did it come on suddenly, or has it been building up gradually? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score [routed to PainSymptomsAgent]*

**Patient (3):** it came on suddenly

> Got it -- so far: 6/10, sudden onset, throbbing. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset [routed to PainSymptomsAgent]*

</details>

### c13_pain_mild_medication -- Mild pain after painkillers: short joint branch plus the medication-effect question

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
| - | routed_to_expected_agent | **FAIL** | turn 1: IntakeContextAgent (fresh_classification, expected PainSymptomsAgent); turn 2: RecoveryProgressAgent (fresh_classification, expected PainSymptomsAgent); turn 3: RecoveryProgressAgent (fresh_classification, expected PainSymptomsAgent); turn 4: IntakeContextAgent (fresh_classification, expected PainSymptomsAgent); turn 5: MedicationAgent (fresh_classification, expected PainSymptomsAgent) |

<details><summary>Transcript</summary>

**Patient (1):** My knee aches a little, I took my painkillers an hour ago.

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to IntakeContextAgent, fresh_classification]*

**Patient (2):** 3

> Let's see where you are on post-op day 14. About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent, fresh_classification]*

**Patient (3):** gradually

> Just circling back to this -- About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to RecoveryProgressAgent, fresh_classification]*

**Patient (4):** around the kneecap

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to IntakeContextAgent, fresh_classification]*

**Patient (5):** yes it helped

> Thanks. Do you know the name of the medication and the prescribed dose?

*engine Medication Proactive Adherence Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to MedicationAgent, fresh_classification]*

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
| - | max_questions | PASS | 5 asked, max 5 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks mobility_status |
| - | final_has_trend_or_checkpoint | **FAIL** | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | **FAIL** | /Next milestone:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | **FAIL** | turn 1: IntakeContextAgent (fresh_classification, expected RecoveryProgressAgent); turn 4: RehabilitationAgent (continuation, expected RecoveryProgressAgent) |

<details><summary>Transcript</summary>

**Patient (1):** Am I on track with my knee?

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields - [routed to IntakeContextAgent, fresh_classification]*

**Patient (2):** about 60 degrees

> Let's see where you are on post-op day 4. About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (3):** about 10 degrees off straight

> Got it -- extension of 10° on day 4; the first extension checkpoint is day 7, which looks for 0°-5° (according to the discharge guidance) -- the target to work towards. Just circling back to this -- About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields rom_extension_degrees [routed to RecoveryProgressAgent]*

**Patient (4):** I use a walker

> Before I answer: Does any exercise cause sharp pain, or swelling that lasts into the next day? (last question)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RehabilitationAgent, continuation]*

**Patient (5):** about 5 minutes

> Thanks for sharing that -- flexion of 5° on day 4; the first flexion checkpoint is day 7, which looks for 70°-90° (according to the discharge guidance) -- the target to work towards. How are you currently getting around -- walking independently, or using a walker, cane, or crutches? (one or two more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked mobility_status; new fields rom_flexion_degrees [routed to RecoveryProgressAgent]*

**Patient (6):** not yet

> Just circling back to this -- How are you currently getting around -- walking independently, or using a walker, cane, or crutches? (one or two more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked mobility_status; new fields - [routed to RecoveryProgressAgent]*

</details>

### c15_recovery_request_current_rom -- current_rom in the request: flexion and extension are fed back, never asked

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | mobility_status -> cane |
| 3 | collects_field | **FAIL** | walking_duration_minutes -> not collected |
| 4 | collects_field | **FAIL** | stairs -> not collected |
| - | no_question_for_record_data | **FAIL** | turn 1: rom_flexion_degrees; turn 2: rom_flexion_degrees; turn 3: rom_extension_degrees |
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

> Let's see where you are on post-op day 16. About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (2):** a cane

> Thanks for sharing that -- walking aid: a cane, matches the day-14 checkpoint (according to the discharge guidance): a frame or two crutches, moving to a single crutch or cane once you can stand and walk for more than ten minutes. Just circling back to this -- About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields mobility_status [routed to RecoveryProgressAgent]*

**Patient (3):** about 20 minutes

> Okay -- flexion of 20°, below the day-14 mark of more than 80° (according to the discharge guidance). Do you know your current knee extension measurement in degrees (how close to fully straight)? (one or two more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields rom_flexion_degrees [routed to RecoveryProgressAgent]*

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
| 1 | collects_field | PASS | walking_duration_minutes -> 20.0 |
| 2 | collects_field | PASS | rom_extension_degrees -> 3.0 |
| 3 | collects_field | PASS | stairs -> foot_over_foot |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 2 asked, max 2 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | PASS | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | PASS | /Next milestone:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** I can bend my knee to 95 degrees and walk with a cane for about 20 minutes. How am I doing?

> **RehabilitationAgent**
> Before I answer: Does any exercise cause sharp pain, or swelling that lasts into the next day? (last question)
> 
> **RecoveryProgressAgent**
> Okay -- walking aid: a cane, matches the day-14 checkpoint (according to the discharge guidance): a frame or two crutches, moving to a single crutch or cane once you can stand and walk for more than ten minutes. flexion of 95°, meets the day-14 mark of more than 80°. walking duration of 20 minutes, meets the day-14 mark of more than 10 minutes. Do you know your current knee extension measurement in degrees (how close to fully straight)? (one more question after this)

*engine Deterministic Multi-Agent Coordinator; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields mobility_status, rom_flexion_degrees, walking_duration_minutes [routed to RehabilitationAgent,RecoveryProgressAgent]*

**Patient (2):** about 3 degrees

> Thanks for sharing that -- extension of 3°, within the day-14 range of 0°-10° (according to the discharge guidance). How are you managing stairs -- not yet, one step at a time holding the rail, or foot over foot? (last question)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked stairs; new fields rom_extension_degrees [routed to RecoveryProgressAgent]*

**Patient (3):** foot over foot

> Here's how things compare on post-op day 15, according to the discharge guidance:
> - flexion: 95° -- meets the day-14 mark of more than 80°
> - extension: 3° -- within the day-14 range of 0°-10°
> - walking aid: a cane -- as the day-14 checkpoint describes (a frame or two crutches, moving to a single crutch or cane once you can stand and walk for more than ten minutes)
> - walking duration: 20 minutes -- meets the day-14 mark of more than 10 minutes
> - stairs: foot over foot -- beyond what the day-14 checkpoint describes (one step at a time using the handrail; stepping foot over foot comes later)
> 
> Next milestone: day 21 -- flexion: bending improving week by week, working towards more than 110 degrees by the end of week six; extension: straightening improving week by week, working towards a fully straight knee by the end of week six. Say 'recovery check' at day 21 and I'll compare.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields stairs [routed to RecoveryProgressAgent]*

</details>

### c17_recovery_abandoned -- Abandoned interview: flexion given, then the patient leaves; nothing persisted

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | rom_flexion_degrees -> 90.0 |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 2 asked, max 2 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | abandoned_persists_nothing | PASS | 0 row(s) written |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** How is my knee recovery going?

> Let's see where you are on post-op day 12. About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (2):** about 90 degrees

> Got it -- flexion of 90°, within the day-7 range of 70°-90° (according to the discharge guidance). Do you know your current knee extension measurement in degrees (how close to fully straight)? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields rom_flexion_degrees [routed to RecoveryProgressAgent]*

</details>

### c18_recovery_tka_day90_longterm -- TKA day 90: compared with the long-term guidance

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | rom_flexion_degrees -> 115.0 |
| 3 | collects_field | PASS | rom_extension_degrees -> 0.0 |
| 4 | collects_field | PASS | mobility_status -> independent |
| 5 | collects_field | PASS | walking_duration_minutes -> 60.0 |
| 6 | collects_field | PASS | stairs -> foot_over_foot |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 5 asked, max 5 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | PASS | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | **FAIL** | /Next milestone:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** Is my recovery on track now?

> Let's see where you are on post-op day 90. About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (2):** 115 degrees

> Thanks for sharing that -- flexion: 115°; the long-term guidance (according to the discharge guidance) gives no number, it expects some stiffness when bending the knee a long way is common; keep up the prescribed exercises. Do you know your current knee extension measurement in degrees (how close to fully straight)? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields rom_flexion_degrees [routed to RecoveryProgressAgent]*

**Patient (3):** 0 degrees, it goes fully straight

> Got it -- extension of 0°, meets the day-84 target of 0° (according to the discharge guidance). How are you currently getting around -- walking independently, or using a walker, cane, or crutches? (one or two more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked mobility_status; new fields rom_extension_degrees [routed to RecoveryProgressAgent]*

**Patient (4):** walking without any aid now

> Thanks for sharing that -- walking aid: walking without an aid, matches the day-84 checkpoint (according to the discharge guidance): walking further and more steadily, with less need for a walking aid. Roughly how many minutes can you walk at a stretch at the moment? (one more question after this)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked walking_duration_minutes; new fields mobility_status [routed to RecoveryProgressAgent]*

**Patient (5):** about 60 minutes

> Thanks for sharing that -- walking duration: 60 minutes; the long-term guidance (according to the discharge guidance) gives no number, it expects regular walking as a preferred low-impact activity. How are you managing stairs -- not yet, one step at a time holding the rail, or foot over foot? (last question)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked stairs; new fields walking_duration_minutes [routed to RecoveryProgressAgent]*

**Patient (6):** foot over foot

> Here's how things compare on post-op day 90, according to the discharge guidance:
> - flexion: 115° -- no number in the long-term guidance; it expects some stiffness when bending the knee a long way is common; keep up the prescribed exercises
> - extension: 0° -- meets the day-84 target of 0°
> - walking aid: walking without an aid -- as the day-84 checkpoint describes (walking further and more steadily, with less need for a walking aid)
> - walking duration: 60 minutes -- no number in the long-term guidance; it expects regular walking as a preferred low-impact activity
> - stairs: foot over foot -- as the day-84 checkpoint describes (climbing stairs step over step with little pain)
> 
> Longer term, the guidance describes daily activities: back to many previous activities, preferring low-impact ones; flexion: some stiffness when bending the knee a long way is common; keep up the prescribed exercises. Say 'recovery check' any time and I'll compare with today.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields stairs [routed to RecoveryProgressAgent]*

</details>

### c19_recovery_unknown_twice -- Two 'I don't know' answers: flexion is left, the interview moves on and names the gap

| Turn | Property | Result | Detail |
|---|---|---|---|
| 3 | does_not_collect | PASS | rom_flexion_degrees -> not collected |
| 4 | collects_field | PASS | rom_extension_degrees -> 5.0 |
| 5 | collects_field | PASS | mobility_status -> walker |
| 6 | collects_field | PASS | walking_duration_minutes -> 10.0 |
| 7 | collects_field | PASS | stairs -> not_yet |
| 7 | reply_matches | PASS | /(?i)flexion: I don't have a value/ |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 6 asked, max 6 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | PASS | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | PASS | /Next milestone:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** How am I doing with my knee?

> Let's see where you are on post-op day 20. About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (2):** I don't know

> That's okay. Even a rough number helps -- when you sit and bend the knee back, roughly how many degrees would you say? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (3):** no idea, sorry

> No problem -- I'll leave flexion for now. Do you know your current knee extension measurement in degrees (how close to fully straight)? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields - [routed to RecoveryProgressAgent]*

**Patient (4):** about 5 degrees

> Got it -- extension of 5°, within the day-14 range of 0°-10° (according to the discharge guidance). How are you currently getting around -- walking independently, or using a walker, cane, or crutches? (one or two more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked mobility_status; new fields rom_extension_degrees [routed to RecoveryProgressAgent]*

**Patient (5):** a walker

> Thanks for sharing that -- walking aid: a walker/frame, matches the day-14 checkpoint (according to the discharge guidance): a frame or two crutches, moving to a single crutch or cane once you can stand and walk for more than ten minutes. Roughly how many minutes can you walk at a stretch at the moment? (one more question after this)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked walking_duration_minutes; new fields mobility_status [routed to RecoveryProgressAgent]*

**Patient (6):** 10 minutes

> Okay -- walking duration of 10 minutes, meets the day-14 mark of more than 10 minutes (according to the discharge guidance). How are you managing stairs -- not yet, one step at a time holding the rail, or foot over foot? (last question)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked stairs; new fields walking_duration_minutes [routed to RecoveryProgressAgent]*

**Patient (7):** not yet

> Here's how things compare on post-op day 20, according to the discharge guidance:
> - extension: 5° -- within the day-14 range of 0°-10°
> - walking aid: a walker/frame -- as the day-14 checkpoint describes (a frame or two crutches, moving to a single crutch or cane once you can stand and walk for more than ten minutes)
> - walking duration: 10 minutes -- meets the day-14 mark of more than 10 minutes
> - stairs: not yet -- not yet at what the day-14 checkpoint describes (one step at a time using the handrail; stepping foot over foot comes later)
> - flexion: I don't have a value from you for this one, so I can't compare it.
> 
> Next milestone: day 21 -- flexion: bending improving week by week, working towards more than 110 degrees by the end of week six; extension: straightening improving week by week, working towards a fully straight knee by the end of week six. Say 'recovery check' at day 21 and I'll compare.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields stairs [routed to RecoveryProgressAgent]*

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
| - | final_turn_closes_interview | **FAIL** | final turn still asks exercise_safety |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | **FAIL** | /Next session:/ |
| - | routed_to_expected_agent | **FAIL** | turn 2: PainSymptomsAgent (continuation, expected RehabilitationAgent) |

<details><summary>Transcript</summary>

**Patient (1):** How do I do heel slides?

> Before I answer: Does any exercise cause sharp pain, or swelling that lasts into the next day? (last question)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercise_safety; new fields - [routed to RehabilitationAgent]*

**Patient (2):** no, nothing hurts

> Thanks for telling me -- I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked exercise_safety; new fields - [routed to PainSymptomsAgent, continuation]*

</details>

### c21_rehab_status_unknown -- No status on record: two questions, 'not yet' persisted, surgeries untouched

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | exercise_safety -> not collected |
| 3 | collects_field | **FAIL** | exercises_done_today -> not collected |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | **FAIL** | 3 asked, max 2 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks exercise_safety |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | **FAIL** | /Next session:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | weight_bearing_record_unchanged | PASS | None -> None |
| - | routed_to_expected_agent | **FAIL** | turn 2: RecoveryProgressAgent (continuation, expected RehabilitationAgent); turn 3: RecoveryProgressAgent (continuation, expected RehabilitationAgent) |

<details><summary>Transcript</summary>

**Patient (1):** What exercises should I do today?

> Before I answer: Does any exercise cause sharp pain, or swelling that lasts into the next day? (one more question after this)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercise_safety; new fields - [routed to RehabilitationAgent]*

**Patient (2):** no

> Let's see where you are on post-op day 10. About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked exercise_safety; new fields - [routed to RecoveryProgressAgent, continuation]*

**Patient (3):** not yet

> Just circling back to this -- About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked exercise_safety; new fields - [routed to RecoveryProgressAgent, continuation]*

</details>

### c22_rehab_multislot -- Multi-slot: done today and no sharp pain in one message, answered at once

| Turn | Property | Result | Detail |
|---|---|---|---|
| 1 | collects_field | PASS | exercises_done_today -> True |
| 1 | collects_field | PASS | exercise_safety -> False |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 0 asked, max 0 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | PASS | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | PASS | /Next session:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |
| - | routed_to_expected_agent | PASS |  |

<details><summary>Transcript</summary>

**Patient (1):** I did my exercises this morning and nothing hurts, no sharp pain. What exercises should I add next?

> **PainSymptomsAgent**
> Thanks for telling me -- I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now? (one or two more questions)
> 
> **RehabilitationAgent**
> Here's the discharge guidance I have for your exercises on day 9 after your knee replacement:
> • Walking practice that focuses on landing on the heel, a normal step pattern and equal weight on both legs.
> • Stretching of the front thigh, hamstring and calf muscles, and strengthening that prioritises the quadriceps, hip and hamstring muscles.
> • Straight leg raises in several directions once the knee can fully straighten.
> • Repeated sit-to-stands from a chair.
> • Small step-ups and step-downs, starting on a low step of about two to four inches.
> • Balance work that progresses from standing on both legs to standing on one.
> • Light ankle weights can usually be added to the basic exercises from about four to six weeks after surgery, increasing gradually as strength returns.
> • Avoid long periods of sitting, and avoid any exercise that causes severe pain or a marked increase in swelling; your physiotherapist will adapt the programme to your progress.
> 
> Your weight-bearing status on record is weight-bearing as tolerated, so nothing here should take you beyond it.
> 
> Next session: walking practice landing on the heel, sit-to-stands from a chair and small step-ups on a low step, as your physiotherapist set. Say 'rehab check' tomorrow and I'll see how it went.

*engine Deterministic Multi-Agent Coordinator; triage GREEN (engine GREEN); asked -; new fields exercise_safety, exercises_done_today [routed to PainSymptomsAgent,RehabilitationAgent]*

</details>

### c23_rehab_abandoned -- Abandoned interview: the safety question is never answered; nothing persisted

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | does_not_collect | PASS | exercise_safety -> not collected |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 2 asked, max 2 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | abandoned_persists_nothing | PASS | 0 row(s) written |
| - | routed_to_expected_agent | **FAIL** | turn 2: RecoveryProgressAgent (continuation, expected RehabilitationAgent) |

<details><summary>Transcript</summary>

**Patient (1):** What exercises should I be doing?

> Before I answer: Does any exercise cause sharp pain, or swelling that lasts into the next day? (one more question after this)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercise_safety; new fields - [routed to RehabilitationAgent]*

**Patient (2):** hmm, let me think about that

> Let's see where you are on post-op day 6. About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked exercise_safety; new fields - [routed to RecoveryProgressAgent, continuation]*

</details>

### c24_rehab_request_nwb_override -- Request NWB overrides the WBAT record: squats question, no loading advice

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | exercise_safety -> not collected |
| 2 | reply_does_not_match | PASS | /(?i)\b(put (your )?(full )?weight\|bear (your )?full weight\|try (a )?squat)/ |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | **FAIL** | 2 asked, max 1 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks exercise_safety |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | **FAIL** | /Next session:/ |
| - | routed_to_expected_agent | **FAIL** | turn 2: RecoveryProgressAgent (continuation, expected RehabilitationAgent) |

<details><summary>Transcript</summary>

**Patient (1):** Can I start doing squats?

> Before I answer: Does any exercise cause sharp pain, or swelling that lasts into the next day? (last question)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercise_safety; new fields - [routed to RehabilitationAgent]*

**Patient (2):** no

> Let's see where you are on post-op day 3. About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked exercise_safety; new fields - [routed to RecoveryProgressAgent, continuation]*

</details>
