# Agent conversation eval -- baseline_b8f0cc5

- backend: git worktree at b8f0cc5 (commit `b8f0cc5`)
- mode: direct agent calls; LLM: stubbed
- run at 2026-10-08 03:22:00, 12.5s

## Summary

| Conversation | Agent | Properties | Questions | Fields collected per turn | Record fields reused | Rows persisted |
|---|---|---|---|---|---|---|
| c01_pain_tka_calf | pain | 14/20 | 7 | 0 · 0 · 0 · 3 · 1 · 1 · 1 · 1 (=7) | 0/2 | 1 |
| c02_pain_tha_groin | pain | 9/15 | 4 | 1 · 1 · 1 · 1 · 1 (=4) | 0/2 | 1 |
| c03_recovery_tka_day10 | recovery | 4/14 | 6 | 0 · 0 · 0 · 0 · 1 · 0 (=1) | 0/2 | 0 |
| c04_recovery_tha_day30 | recovery | 5/11 | 0 | 0 · 0 · 0 · 0 · 0 (=0) | 0/0 | 0 |
| c05_rehab_tka_stairs | rehab | 6/9 | 0 | 0 · 0 (=0) | 0/1 | 0 |
| c06_rehab_tha_missed_days | rehab | 6/11 | 0 | 0 · 0 · 0 (=0) | 0/1 | 0 |
| c07_rehab_safety_hold | rehab | 7/10 | 0 | 0 · 0 (=0) | 0/0 | 0 |
| c08_pain_bug_nonnumeric_score | pain | 12/15 | 5 | 1 · 0 · 1 · 1 · 1 · 1 (=5) | 0/1 | 1 |
| c09_pain_bug_offtopic_reply | pain | 8/14 | 5 | 0 · 1 · 1 · 1 · 1 · 1 (=4) | 0/1 | 1 |
| c10_pain_bug_detour_resume | pain | 6/13 | 5 | 0 · 1 · 1 · 0 · 1 (=3) | 0/1 | 0 |
| c11_pain_multislot_opening | pain | 10/12 | 1 | 3 · 1 (=4) | 1/1 | 1 |
| c12_pain_abandoned | pain | 7/7 | 3 | 1 · 1 · 1 (=3) | 0/0 | 0 |
| c13_pain_mild_medication | pain | 10/12 | 4 | 0 · 1 · 1 · 1 · 1 (=4) | 0/1 | 1 |
| c14_recovery_tka_day4_target | recovery | 8/13 | 1 | 0 · 1 · 1 · 1 · 0 · 0 (=3) | 0/0 | 0 |
| c15_recovery_request_current_rom | recovery | 4/12 | 4 | 0 · 1 · 0 · 0 (=1) | 0/2 | 0 |
| c16_recovery_multislot | recovery | 6/13 | 2 | 2 · 0 · 0 (=2) | 0/0 | 0 |
| c17_recovery_abandoned | recovery | 6/6 | 1 | 0 · 1 (=1) | 0/0 | 0 |
| c18_recovery_tka_day90_longterm | recovery | 7/13 | 0 | 0 · 0 · 1 · 1 · 0 · 0 (=2) | 0/0 | 0 |
| c19_recovery_unknown_twice | recovery | 6/14 | 6 | 0 · 0 · 0 · 1 · 1 · 0 · 0 (=2) | 0/0 | 0 |
| c20_rehab_direct_question | rehab | 6/9 | 0 | 0 · 0 (=0) | 0/1 | 0 |
| c21_rehab_status_unknown | rehab | 6/11 | 0 | 0 · 0 · 0 (=0) | 0/0 | 0 |
| c22_rehab_multislot | rehab | 6/11 | 0 | 0 (=0) | 0/1 | 0 |
| c23_rehab_abandoned | rehab | 7/7 | 0 | 0 · 0 (=0) | 0/0 | 0 |
| c24_rehab_request_nwb_override | rehab | 7/10 | 0 | 0 · 0 (=0) | 0/1 | 0 |

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
| 5 | collects_field | PASS | swelling -> yes it's swollen |
| 6 | collects_field | PASS | warmth_or_redness -> no |
| 7 | collects_field | PASS | numbness_or_weakness -> no |
| 8 | collects_field | PASS | fever_or_temperature -> no fever |
| - | no_question_for_record_data | **FAIL** | turn 1: pain_score; turn 2: pain_score; turn 3: pain_score |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 7 asked, max 7 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /Compared with last time/ |
| - | final_has_next_step | **FAIL** | /Next step:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** My knee has been hurting since this morning.

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields -*

**Patient (2):** yes

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields -*

**Patient (3):** it really hurts

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields -*

**Patient (4):** 7 out of 10, started suddenly yesterday in the calf

> Okay, 7 out of 10 -- that helps me understand how strong the pain is. Have you noticed any swelling in that area?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked swelling; new fields location, onset, pain_score*

**Patient (5):** yes it's swollen

> Thanks, that's useful to know. Does the area feel warmer than usual, or look red?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage YELLOW (engine YELLOW); asked warmth_or_redness; new fields swelling*

**Patient (6):** no

> Thanks, that's useful to know. Any numbness or weakness in that leg?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked numbness_or_weakness; new fields warmth_or_redness*

**Patient (7):** no

> Thanks, that's useful to know. Have you felt feverish at all, or checked your temperature?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked fever_or_temperature; new fields numbness_or_weakness*

**Patient (8):** no fever

> Thanks for going through that with me. Based on what you've told me:
> - pain score: 7/10
> - how it started: sudden
> - where it's felt: in the calf
> - swelling: yes it's swollen
> - warmth or redness: no
> - numbness or weakness: no
> - fever/temperature: no fever
> 
> Following your surgical team's guidance: Continue prescribed home rehabilitation exercises, cryotherapy, elevation, and oral medication schedule. Log next check-in as scheduled. That's the same as the pain score of 7/10 recorded last time.
> 
> This is a preliminary read based on what you've described and isn't a diagnosis.

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields fever_or_temperature*

</details>

### c02_pain_tha_groin -- THA groin case: hip wording, location asked, groin not stored as trend

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | pain_score -> 6 |
| 3 | collects_field | PASS | onset -> gradual |
| 4 | collects_field | PASS | location -> My hip |
| 4 | does_not_store_unfitting_reply | **FAIL** | worsening_or_improving = 'in the groin' must not contain 'groin' |
| 5 | collects_field | PASS | worsening_or_improving -> stable |
| 5 | does_not_store_unfitting_reply | PASS | location = '' must not contain 'hip' |
| - | no_question_for_record_data | **FAIL** | turn 1: pain_score; turn 5: pain_score |
| - | no_reask_of_collected_field | **FAIL** | turn 5: pain_score |
| - | max_questions | PASS | 4 asked, max 4 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks pain_score |
| - | final_has_trend_or_checkpoint | **FAIL** | /Compared with last time/ |
| - | final_has_next_step | **FAIL** | /Next step:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** My hip is sore today.

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields location*

**Patient (2):** no, it's more like a 6

> Okay, 6 out of 10 -- that helps me understand how strong the pain is. Did it come on suddenly, or has it been building up gradually?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score*

**Patient (3):** gradually

> Got it -- that's useful to know. Is it getting worse, getting better, or staying about the same?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked worsening_or_improving; new fields onset*

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

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields worsening_or_improving*

**Patient (5):** about the same

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields worsening_or_improving*

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

<details><summary>Transcript</summary>

**Patient (1):** How is my recovery going?

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (2):** it's about 85 now

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (3):** I don't know the number

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (4):** almost, there's a small gap

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (5):** I'm using a cane and I can walk about 15 minutes

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields mobility_status*

**Patient (6):** one step at a time holding the rail

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

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

<details><summary>Transcript</summary>

**Patient (1):** How is my hip recovery going?

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (2):** I'm still using one crutch

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (3):** about 20 minutes

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (4):** foot over foot now

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (5):** yes, still following them

> *(empty reply)*

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

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

<details><summary>Transcript</summary>

**Patient (1):** Can I go up and down the stairs yet?

> Go up stairs leading with your non-operated leg, then bring your operated leg and any walking aid up to meet it -- "up with the good, down with the bad." Coming down, lead with your operated leg and walking aid first. Always use the handrail and go at a slow, steady pace, and follow your prescribed weight-bearing status.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (2):** no, nothing sharp

> Hello! On Day 5 of your recovery from Total Knee Arthroplasty (TKA) (Right), make sure to keep up with your daily physical therapy routine, elevate your leg when resting, and stay hydrated.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

</details>

### c06_rehab_tha_missed_days -- THA day 20: missed-days opener, barrier carried into the close, unknown status

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | exercise_barrier -> not collected |
| 3 | collects_field | **FAIL** | exercise_safety -> not collected |
| 3 | reply_does_not_match | **FAIL** | /(?i)knee flexion\|seated knee extension\|swelling .* is normal/ hit 'Swelling in your Right hip on Day 20 is normal' |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 0 asked, max 2 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | **FAIL** | /Next session:/ |
| - | weight_bearing_record_unchanged | PASS | None -> None |

<details><summary>Transcript</summary>

**Patient (1):** What exercises should I be doing now?

> At Day 20, work on progressing your passive flexion past 90°, standing calf raises, seated knee extension, and increasing your independent walking endurance as tolerated.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (2):** the evenings are too sore to face them

> Hello! On Day 20 of your recovery from Total Hip Arthroplasty (THA) (Right), make sure to keep up with your daily physical therapy routine, elevate your leg when resting, and stay hydrated.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (3):** no sharp pain and no swelling

> Swelling in your Right hip on Day 20 is normal due to increased circulation during healing. Lie down with your foot elevated above heart level and apply an ice pack for 20 minutes.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

</details>

### c07_rehab_safety_hold -- TKA day 12 safety hold: sharp pain from heel slides pauses the exercise

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | exercise_safety -> not collected |
| 2 | reply_matches | **FAIL** | /(?i)pause heel slides/ |
| 2 | reply_does_not_match | PASS | /(?i)\b(is normal\|nothing to worry\|perfectly fine)\b/ |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 0 asked, max 1 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_next_step | **FAIL** | /Next session:/ |

<details><summary>Transcript</summary>

**Patient (1):** How do I do heel slides?

> Based on your Day 12 protocol for Total Knee Arthroplasty (TKA): Target milestones for Total Knee Arthroplasty: By Post-Op Day 7, patients should aim for 70°-90° of passive flexion and near-full extension (0°-5°). Full terminal extension is critical; patients should avoid putting pillows directly under the knee joint, placing pillows under the ankle/calf instead to promote gravity extension.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (2):** yes, heel slides give me a sharp pain

> Mild to moderate soreness is typical on Day 12. Take your prescribed pain medication 30-45 minutes before starting physical therapy to keep your discomfort manageable.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

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

<details><summary>Transcript</summary>

**Patient (1):** My knee is aching today.

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields pain_characteristics*

**Patient (2):** it really hurts

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields -*

**Patient (3):** about a 5

> Okay, 5 out of 10 -- that helps me understand how strong the pain is. Did it come on suddenly, or has it been building up gradually?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score*

**Patient (4):** gradually

> Got it -- that's useful to know. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset*

**Patient (5):** around the kneecap

> Got it. Is it getting worse, getting better, or staying about the same?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked worsening_or_improving; new fields location*

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

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields worsening_or_improving*

</details>

### c09_pain_bug_offtopic_reply -- Bug 1b: 'Can I shower tomorrow?' is never stored as the onset

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | pain_score -> 6 |
| 3 | does_not_store_unfitting_reply | **FAIL** | onset = 'Can I shower tomorrow?' must not contain 'shower' |
| 4 | collects_field | PASS | onset -> Can I shower tomorrow? |
| 4 | does_not_store_unfitting_reply | **FAIL** | onset = 'Can I shower tomorrow?' must not contain 'shower' |
| 5 | collects_field | PASS | location -> it came on gradually |
| 6 | collects_field | PASS | worsening_or_improving -> worsening |
| - | no_reask_of_collected_field | **FAIL** | turn 6: pain_score |
| - | max_questions | PASS | 5 asked, max 5 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks pain_score |
| - | final_has_trend_or_checkpoint | **FAIL** | /Compared with last time/ |
| - | final_has_next_step | **FAIL** | /Next step:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** My knee hurts quite a lot today.

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields -*

**Patient (2):** 6

> Okay, 6 out of 10 -- that helps me understand how strong the pain is. Did it come on suddenly, or has it been building up gradually?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score*

**Patient (3):** Can I shower tomorrow?

> Got it -- that's useful to know. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset*

**Patient (4):** it came on gradually

> Got it. Is it getting worse, getting better, or staying about the same?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked worsening_or_improving; new fields location*

**Patient (5):** behind the knee

> Thanks for going through that with me. Based on what you've told me:
> - pain score: 6/10
> - how it started: Can I shower tomorrow?
> - where it's felt: it came on gradually
> - how it's trending: behind the knee
> 
> Following your surgical team's guidance: Continue prescribed home rehabilitation exercises, cryotherapy, elevation, and oral medication schedule. Log next check-in as scheduled. That's higher than the pain score of 5/10 recorded last time.
> 
> This is a preliminary read based on what you've described and isn't a diagnosis.

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields worsening_or_improving*

**Patient (6):** getting worse

> Thanks for telling me -- I'd like to understand this change a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields worsening_or_improving*

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

<details><summary>Transcript</summary>

**Patient (1):** My knee is really sore today.

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields -*

**Patient (2):** 5

> Okay, 5 out of 10 -- that helps me understand how strong the pain is. Did it come on suddenly, or has it been building up gradually?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score*

**Patient (3):** Can I climb stairs?

> Take stairs one step at a time with the handrail: up with the good leg, down with the operated leg.

*engine scripted detour; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (4):** gradually

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields onset*

**Patient (5):** on the inside of the knee

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields -*

**Patient (6):** getting worse

> Okay, None pain -- that helps me understand how strong it is. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields worsening_or_improving*

</details>

### c11_pain_multislot_opening -- Multi-slot: score, onset and location in the opening message

| Turn | Property | Result | Detail |
|---|---|---|---|
| 1 | collects_field | PASS | pain_score -> 5 |
| 1 | collects_field | PASS | onset -> gradual |
| 1 | collects_field | PASS | location -> behind the knee |
| 2 | collects_field | PASS | worsening_or_improving -> improving |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 1 asked, max 1 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /Compared with last time/ |
| - | final_has_next_step | **FAIL** | /Next step:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** It's about a 5 out of 10, it came on gradually, and it's behind the knee.

> Thanks for telling me. I'd like to understand this a little better. Is it getting worse, getting better, or staying about the same?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked worsening_or_improving; new fields location, onset, pain_score*

**Patient (2):** getting a bit better

> Thanks for going through that with me. Based on what you've told me:
> - pain score: 5/10
> - how it started: gradual
> - where it's felt: behind the knee
> - how it's trending: improving
> 
> Following your surgical team's guidance: Continue prescribed home rehabilitation exercises, cryotherapy, elevation, and oral medication schedule. Log next check-in as scheduled. That's lower than the pain score of 6/10 recorded last time.
> 
> This is a preliminary read based on what you've described and isn't a diagnosis.

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields worsening_or_improving*

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

<details><summary>Transcript</summary>

**Patient (1):** My knee is throbbing.

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields pain_characteristics*

**Patient (2):** 6

> Okay, 6 out of 10 -- that helps me understand how strong the pain is. Did it come on suddenly, or has it been building up gradually?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score*

**Patient (3):** it came on suddenly

> Got it -- that's useful to know. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset*

</details>

### c13_pain_mild_medication -- Mild pain after painkillers: short joint branch plus the medication-effect question

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | pain_score -> 3 |
| 3 | collects_field | PASS | onset -> gradual |
| 4 | collects_field | PASS | location -> around the kneecap |
| 5 | collects_field | PASS | medication_effect -> yes it helped |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 4 asked, max 4 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /Compared with last time/ |
| - | final_has_next_step | **FAIL** | /Next step:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** My knee aches a little, I took my painkillers an hour ago.

> Thanks for telling me. I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields -*

**Patient (2):** 3

> Okay, 3 out of 10 -- that helps me understand how strong the pain is. Did it come on suddenly, or has it been building up gradually?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score*

**Patient (3):** gradually

> Got it -- that's useful to know. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset*

**Patient (4):** around the kneecap

> Got it. Did taking your pain medication help, or not really?

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked medication_effect; new fields location*

**Patient (5):** yes it helped

> Thanks for going through that with me. Based on what you've told me:
> - pain score: 3/10
> - how it started: gradual
> - where it's felt: around the kneecap
> - effect of medication: yes it helped
> 
> Following your surgical team's guidance: Continue prescribed home rehabilitation exercises, cryotherapy, elevation, and oral medication schedule. Log next check-in as scheduled. That's lower than the pain score of 5/10 recorded last time.
> 
> This is a preliminary read based on what you've described and isn't a diagnosis.

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields medication_effect*

</details>

### c14_recovery_tka_day4_target -- TKA day 4: before the first checkpoint, the day-7 target is given

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | rom_flexion_degrees -> 60.0 |
| 3 | collects_field | PASS | rom_extension_degrees -> 10.0 |
| 4 | collects_field | PASS | mobility_status -> walker |
| 5 | collects_field | **FAIL** | walking_duration_minutes -> not collected |
| 6 | collects_field | **FAIL** | stairs -> not collected |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 1 asked, max 5 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | **FAIL** | /Next milestone:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** Am I on track with my knee?

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (2):** about 60 degrees

> Okay, 60° -- that helps. You're currently on post-op day 4, and the first flexion checkpoint I have is for day 7, so it's a little early to compare you against that target.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields rom_flexion_degrees*

**Patient (3):** about 10 degrees off straight

> Got it -- 10° helps me understand where you are. You're currently on post-op day 4, and the first extension checkpoint I have is for day 7, so it's a little early to compare you against that target.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields rom_extension_degrees*

**Patient (4):** I use a walker

> Okay, 60° -- that helps. You're currently on post-op day 4, and the first flexion checkpoint I have is for day 7, so it's a little early to compare you against that target.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields mobility_status*

**Patient (5):** about 5 minutes

> Okay, 60° -- that helps. You're currently on post-op day 4, and the first flexion checkpoint I have is for day 7, so it's a little early to compare you against that target.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (6):** not yet

> Okay, 60° -- that helps. You're currently on post-op day 4, and the first flexion checkpoint I have is for day 7, so it's a little early to compare you against that target.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields -*

</details>

### c15_recovery_request_current_rom -- current_rom in the request: flexion and extension are fed back, never asked

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | mobility_status -> cane |
| 3 | collects_field | **FAIL** | walking_duration_minutes -> not collected |
| 4 | collects_field | **FAIL** | stairs -> not collected |
| - | no_question_for_record_data | **FAIL** | turn 1: rom_flexion_degrees; turn 2: rom_flexion_degrees; turn 3: rom_flexion_degrees; turn 4: rom_flexion_degrees |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | **FAIL** | 4 asked, max 3 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks rom_flexion_degrees |
| - | final_has_trend_or_checkpoint | **FAIL** | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | **FAIL** | /Next milestone:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** How's my progress looking?

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (2):** a cane

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields mobility_status*

**Patient (3):** about 20 minutes

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (4):** one step at a time

> Just circling back to this -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

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

<details><summary>Transcript</summary>

**Patient (1):** I can bend my knee to 95 degrees and walk with a cane for about 20 minutes. How am I doing?

> Okay -- your flexion of 95° exceeds the 70°-90° range stated for the earlier Post-Op Day 7 checkpoint.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields mobility_status, rom_flexion_degrees*

**Patient (2):** about 3 degrees

> Do you know your current knee extension measurement in degrees (how close to fully straight)?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields -*

**Patient (3):** foot over foot

> Just circling back to this -- Do you know your current knee extension measurement in degrees (how close to fully straight)?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields -*

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

<details><summary>Transcript</summary>

**Patient (1):** How is my knee recovery going?

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (2):** about 90 degrees

> Thanks for sharing that -- your flexion of 90° is within the 70°-90° range stated for the earlier Post-Op Day 7 checkpoint.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields rom_flexion_degrees*

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

<details><summary>Transcript</summary>

**Patient (1):** Is my recovery on track now?

> The source I have only supports comparison within its stated day range, and your current day falls outside that range, so I can't give a supported verdict right now.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (2):** 115 degrees

> The source I have only supports comparison within its stated day range, and your current day falls outside that range, so I can't give a supported verdict right now.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (3):** 0 degrees, it goes fully straight

> The source I have only supports comparison within its stated day range, and your current day falls outside that range, so I can't give a supported verdict right now.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields rom_extension_degrees*

**Patient (4):** walking without any aid now

> The source I have only supports comparison within its stated day range, and your current day falls outside that range, so I can't give a supported verdict right now.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields mobility_status*

**Patient (5):** about 60 minutes

> The source I have only supports comparison within its stated day range, and your current day falls outside that range, so I can't give a supported verdict right now.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (6):** foot over foot

> The source I have only supports comparison within its stated day range, and your current day falls outside that range, so I can't give a supported verdict right now.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields -*

</details>

### c19_recovery_unknown_twice -- Two 'I don't know' answers: flexion is left, the interview moves on and names the gap

| Turn | Property | Result | Detail |
|---|---|---|---|
| 3 | does_not_collect | PASS | rom_flexion_degrees -> not collected |
| 4 | collects_field | **FAIL** | rom_extension_degrees -> not collected |
| 5 | collects_field | PASS | mobility_status -> walker |
| 6 | collects_field | **FAIL** | walking_duration_minutes -> not collected |
| 7 | collects_field | **FAIL** | stairs -> not collected |
| 7 | reply_matches | **FAIL** | /(?i)flexion: I don't have a value/ |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 6 asked, max 6 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | **FAIL** | final turn still asks rom_extension_degrees |
| - | final_has_trend_or_checkpoint | **FAIL** | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | **FAIL** | /Next milestone:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** How am I doing with my knee?

> About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (2):** I don't know

> That's okay. About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (3):** no idea, sorry

> Coming back to my last question -- About how many degrees can you currently bend your knee?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (4):** about 5 degrees

> Got it -- your flexion of 5° is below the 70°-90° range stated for the earlier Post-Op Day 7 checkpoint.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields rom_flexion_degrees*

**Patient (5):** a walker

> Do you know your current knee extension measurement in degrees (how close to fully straight)?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields mobility_status*

**Patient (6):** 10 minutes

> Just circling back to this -- Do you know your current knee extension measurement in degrees (how close to fully straight)?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields -*

**Patient (7):** not yet

> Just circling back to this -- Do you know your current knee extension measurement in degrees (how close to fully straight)?

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields -*

</details>

### c20_rehab_direct_question -- Direct question naming an exercise: one question, today's log not re-asked

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | exercise_safety -> not collected |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status, exercises_done_today |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 0 asked, max 1 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | **FAIL** | /Next session:/ |

<details><summary>Transcript</summary>

**Patient (1):** How do I do heel slides?

> Based on your Day 8 protocol for Total Knee Arthroplasty (TKA): Target milestones for Total Knee Arthroplasty: By Post-Op Day 7, patients should aim for 70°-90° of passive flexion and near-full extension (0°-5°). Full terminal extension is critical; patients should avoid putting pillows directly under the knee joint, placing pillows under the ankle/calf instead to promote gravity extension.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (2):** no, nothing hurts

> Mild to moderate soreness is typical on Day 8. Take your prescribed pain medication 30-45 minutes before starting physical therapy to keep your discomfort manageable.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

</details>

### c21_rehab_status_unknown -- No status on record: two questions, 'not yet' persisted, surgeries untouched

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | exercise_safety -> not collected |
| 3 | collects_field | **FAIL** | exercises_done_today -> not collected |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 0 asked, max 2 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | **FAIL** | /Next session:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |
| - | weight_bearing_record_unchanged | PASS | None -> None |

<details><summary>Transcript</summary>

**Patient (1):** What exercises should I do today?

> At Day 10, work on progressing your passive flexion past 90°, standing calf raises, seated knee extension, and increasing your independent walking endurance as tolerated.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (2):** no

> Hello! On Day 10 of your recovery from Total Knee Arthroplasty (TKA) (Right), make sure to keep up with your daily physical therapy routine, elevate your leg when resting, and stay hydrated.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (3):** not yet

> Hello! On Day 10 of your recovery from Total Knee Arthroplasty (TKA) (Right), make sure to keep up with your daily physical therapy routine, elevate your leg when resting, and stay hydrated.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

</details>

### c22_rehab_multislot -- Multi-slot: done today and no sharp pain in one message, answered at once

| Turn | Property | Result | Detail |
|---|---|---|---|
| 1 | collects_field | **FAIL** | exercises_done_today -> not collected |
| 1 | collects_field | **FAIL** | exercise_safety -> not collected |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 0 asked, max 0 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | **FAIL** | /Next session:/ |
| - | persists_on_completion | **FAIL** | 0 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** I did my exercises this morning and nothing hurts, no sharp pain. What exercises should I add next?

> At Day 9, work on progressing your passive flexion past 90°, standing calf raises, seated knee extension, and increasing your independent walking endurance as tolerated.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

</details>

### c23_rehab_abandoned -- Abandoned interview: the safety question is never answered; nothing persisted

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | does_not_collect | PASS | exercise_safety -> not collected |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 0 asked, max 2 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | abandoned_persists_nothing | PASS | 0 row(s) written |

<details><summary>Transcript</summary>

**Patient (1):** What exercises should I be doing?

> On Day 6, your targets are active-assisted heel slides aiming for 70°–90° flexion, straight leg raises to rebuild quadriceps strength, and walking 5–10 minutes with your walker every 2 hours.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (2):** hmm, let me think about that

> Hello! On Day 6 of your recovery from Total Knee Arthroplasty (TKA) (Right), make sure to keep up with your daily physical therapy routine, elevate your leg when resting, and stay hydrated.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

</details>

### c24_rehab_request_nwb_override -- Request NWB overrides the WBAT record: squats question, no loading advice

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | **FAIL** | exercise_safety -> not collected |
| 2 | reply_does_not_match | PASS | /(?i)\b(put (your )?(full )?weight\|bear (your )?full weight\|try (a )?squat)/ |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 0 asked, max 1 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | **FAIL** | /Next session:/ |

<details><summary>Transcript</summary>

**Patient (1):** Can I start doing squats?

> Hello! On Day 3 of your recovery from Total Knee Arthroplasty (TKA) (Right), make sure to keep up with your daily physical therapy routine, elevate your leg when resting, and stay hydrated.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (2):** no

> Hello! On Day 3 of your recovery from Total Knee Arthroplasty (TKA) (Right), make sure to keep up with your daily physical therapy routine, elevate your leg when resting, and stay hydrated.

*engine Clinical Synthesis Engine; triage GREEN (engine GREEN); asked -; new fields -*

</details>
