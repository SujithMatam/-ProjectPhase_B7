# Agent conversation eval -- live_direct

- backend: this checkout (commit `77ab902`)
- mode: direct agent calls; LLM: live (Ollama)
- run at 2026-10-08 03:49:39, 52.7s

## Summary

| Conversation | Agent | Properties | Questions | Fields collected per turn | Record fields reused | Rows persisted |
|---|---|---|---|---|---|---|
| c01_pain_tka_calf | pain | 20/20 | 7 | 0 · 1 · 0 · 3 · 1 · 1 · 1 · 1 (=7) | 2/2 | 2 |
| c02_pain_tha_groin | pain | 15/15 | 4 | 0 · 1 · 1 · 1 · 1 (=4) | 2/2 | 2 |
| c03_recovery_tka_day10 | recovery | 14/14 | 5 | 0 · 1 · 0 · 1 · 2 · 1 (=5) | 2/2 | 1 |
| c04_recovery_tha_day30 | recovery | 11/11 | 4 | 0 · 1 · 1 · 1 · 1 (=4) | 0/0 | 0 |
| c05_rehab_tka_stairs | rehab | 8/9 | 1 | 0 · 1 (=1) | 1/1 | 0 |
| c06_rehab_tha_missed_days | rehab | 10/11 | 2 | 0 · 1 · 1 (=2) | 1/1 | 0 |
| c07_rehab_safety_hold | rehab | 10/10 | 1 | 0 · 3 (=3) | 0/0 | 0 |
| c08_pain_bug_nonnumeric_score | pain | 15/15 | 5 | 1 · 0 · 1 · 1 · 1 · 1 (=5) | 1/1 | 2 |
| c09_pain_bug_offtopic_reply | pain | 14/14 | 5 | 0 · 1 · 0 · 1 · 1 · 1 (=4) | 1/1 | 2 |
| c10_pain_bug_detour_resume | pain | 13/13 | 4 | 0 · 1 · 1 · 1 · 1 (=4) | 1/1 | 2 |
| c11_pain_multislot_opening | pain | 12/12 | 1 | 3 · 1 (=4) | 1/1 | 2 |
| c12_pain_abandoned | pain | 7/7 | 3 | 1 · 1 · 1 (=3) | 0/0 | 0 |
| c13_pain_mild_medication | pain | 12/12 | 4 | 0 · 1 · 1 · 1 · 1 (=4) | 1/1 | 2 |
| c14_recovery_tka_day4_target | recovery | 13/13 | 5 | 0 · 1 · 1 · 1 · 1 · 1 (=5) | 0/0 | 1 |
| c15_recovery_request_current_rom | recovery | 12/12 | 3 | 2 · 1 · 1 · 1 (=5) | 2/2 | 1 |
| c16_recovery_multislot | recovery | 13/13 | 2 | 3 · 1 · 1 (=5) | 0/0 | 1 |
| c17_recovery_abandoned | recovery | 6/6 | 2 | 0 · 1 (=1) | 0/0 | 0 |
| c18_recovery_tka_day90_longterm | recovery | 13/13 | 5 | 0 · 1 · 1 · 1 · 1 · 1 (=5) | 0/0 | 1 |
| c19_recovery_unknown_twice | recovery | 14/14 | 6 | 0 · 0 · 0 · 1 · 1 · 1 · 1 (=4) | 0/0 | 1 |
| c20_rehab_direct_question | rehab | 8/9 | 1 | 0 · 1 (=1) | 1/1 | 0 |
| c21_rehab_status_unknown | rehab | 10/11 | 2 | 0 · 1 · 1 (=2) | 0/0 | 1 |
| c22_rehab_multislot | rehab | 10/11 | 0 | 2 (=2) | 1/1 | 1 |
| c23_rehab_abandoned | rehab | 7/7 | 2 | 0 · 0 (=0) | 0/0 | 0 |
| c24_rehab_request_nwb_override | rehab | 10/10 | 1 | 0 · 1 (=1) | 1/1 | 0 |

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
| 5 | collects_field | PASS | swelling -> yes it's swollen |
| 6 | collects_field | PASS | warmth_or_redness -> no |
| 7 | collects_field | PASS | numbness_or_weakness -> no |
| 8 | collects_field | PASS | fever_or_temperature -> no fever |
| - | no_question_for_record_data | PASS | never asked: pain_score |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 7 asked, max 7 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | PASS | /Compared with last time/ |
| - | final_has_next_step | PASS | /Next step:/ |
| - | persists_on_completion | PASS | 2 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** My knee has been hurting since this morning.

> Last time you had 7/10 behind the knee and it was getting worse -- let's see where things are now. Your log says 6/10 earlier today -- still about that? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields -*

**Patient (2):** yes

> Okay, that helps me understand how strong it is -- so far: 6/10. Did it come on suddenly, or has it been building up gradually? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score*

**Patient (3):** it really hurts

> So far: 6/10. Sorry, I didn't quite catch that. Would you say the pain started all at once, or built up gradually? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields -*

**Patient (4):** 7 out of 10, started suddenly yesterday in the calf

> Got it -- so far: 7/10, sudden onset, in the calf. Have you noticed any swelling in that area? (a few more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked swelling; new fields location, onset, pain_score*

**Patient (5):** yes it's swollen

> Thanks, that's useful to know -- so far: 7/10, sudden onset, in the calf, swelling: yes. Does the area feel warmer than usual, or look red? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage YELLOW (engine YELLOW); asked warmth_or_redness; new fields swelling*

**Patient (6):** no

> Thanks, that's useful to know -- so far: 7/10, sudden onset, in the calf, swelling: yes, warmth/redness: no. Any numbness or weakness in that leg? (one more question after this)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked numbness_or_weakness; new fields warmth_or_redness*

**Patient (7):** no

> Thanks, that's useful to know -- so far: 7/10, sudden onset, in the calf, swelling: yes, warmth/redness: no, numbness/weakness: no. Have you felt feverish at all, or checked your temperature? (last question)

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
> Compared with last time: That's the same as the pain score of 7/10 recorded last time. Last time it was behind the knee and getting worse; now it's in the calf.
> 
> Following your surgical team's guidance: Continue prescribed home rehabilitation exercises, cryotherapy, elevation, and oral medication schedule. Log next check-in as scheduled.
> 
> Next step: note how the pain feels again this evening so we can compare it with today. Say 'pain check' any time and I'll compare with today.
> 
> This is a preliminary read based on what you've described and isn't a diagnosis.

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields fever_or_temperature*

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

<details><summary>Transcript</summary>

**Patient (1):** My hip is sore today.

> Last time you had 5/10 in the thigh and it was about the same -- let's see where things are now. Your log says 4/10 earlier today -- still about that? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields -*

**Patient (2):** no, it's more like a 6

> Okay, that helps me understand how strong it is -- so far: 6/10. Did it come on suddenly, or has it been building up gradually? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score*

**Patient (3):** gradually

> Got it -- so far: 6/10, gradual onset. Where are you feeling it most -- in the groin, the thigh, the buttock, the calf, or somewhere else? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset*

**Patient (4):** in the groin

> Got it -- so far: 6/10, gradual onset, in the groin. Is it getting worse, getting better, or staying about the same? (last question)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked worsening_or_improving; new fields location*

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

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields worsening_or_improving*

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

<details><summary>Transcript</summary>

**Patient (1):** How is my recovery going?

> Let's see where you are on post-op day 10. Your log from yesterday says you could bend to 80° -- still about that? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (2):** it's about 85 now

> Got it -- flexion of 85°, within the day-7 range of 70°-90° (according to the discharge guidance), and improving: 70 -> 80 -> 85. Your log from yesterday says your extension was 5° -- still about that? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields rom_flexion_degrees*

**Patient (3):** I don't know the number

> That's okay. Can you get the knee fully flat on the bed? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields -*

**Patient (4):** almost, there's a small gap

> Got it -- extension (nearly flat), within the day-7 range of 0°-5° (according to the discharge guidance), and improving: 8 -> 5. How are you currently getting around -- walking independently, or using a walker, cane, or crutches? (one or two more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked mobility_status; new fields rom_extension_degrees*

**Patient (5):** I'm using a cane and I can walk about 15 minutes

> Thanks for sharing that -- walking aid: a cane, matches the day-7 checkpoint (according to the discharge guidance): walking with a frame, crutches or cane on a level surface. walking duration: 15 minutes; the day-7 guidance gives no number, it expects walking little and often around the home. How are you managing stairs -- not yet, one step at a time holding the rail, or foot over foot? (last question)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked stairs; new fields mobility_status, walking_duration_minutes*

**Patient (6):** one step at a time holding the rail

> Here's how things compare on post-op day 10, according to the discharge guidance:
> - flexion: 85° -- within the day-7 range of 70°-90°; over the week 70 -> 80 -> 85, improving
> - extension: nearly flat -- within the day-7 range of 0°-5°; over the week 8 -> 5, improving
> - walking aid: a cane -- as the day-7 checkpoint describes (walking with a frame, crutches or cane on a level surface)
> - walking duration: 15 minutes -- no number in the day-7 guidance; it expects walking little and often around the home
> - stairs: one step at a time -- as the day-7 checkpoint describes (managing two or three steps up and down with your aid)
> 
> Next milestone: day 14 -- flexion: about 80 degrees or more of active bending, improving week by week; extension: straightening to within 10 degrees of fully straight. Say 'recovery check' at day 14 and I'll compare.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields stairs*

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

<details><summary>Transcript</summary>

**Patient (1):** How is my hip recovery going?

> Let's see where you are on post-op day 30. How are you currently getting around -- walking independently, or using a walker, cane, or crutches? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked mobility_status; new fields -*

**Patient (2):** I'm still using one crutch

> Got it -- walking aid: crutches, matches the day-21 checkpoint (according to the discharge guidance): one crutch or a cane once you can stand and walk for over ten minutes; there is no fixed date for giving up the aid. Roughly how many minutes can you walk at a stretch at the moment? (one or two more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked walking_duration_minutes; new fields mobility_status*

**Patient (3):** about 20 minutes

> Got it -- walking duration of 20 minutes, meets the day-21 mark of more than 10 minutes (according to the discharge guidance). How are you managing stairs -- not yet, one step at a time holding the rail, or foot over foot? (one more question after this)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked stairs; new fields walking_duration_minutes*

**Patient (4):** foot over foot now

> Thanks for sharing that -- stairs: foot over foot, matches the day-21 checkpoint (according to the discharge guidance): one step at a time with a handrail at first, foot over foot as you get stronger. Are you still keeping to your hip precautions -- not bending the hip past a right angle, not crossing your legs, avoiding low chairs? (last question)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked hip_precautions; new fields stairs*

**Patient (5):** yes, still following them

> Here's a friendly answer to the user's question:
> 
> You're making great progress on day 30 after your Total Hip Arthroplasty (THA)! You're doing a great job of following your hip precautions, which is helping your hip heal properly. Now that you're walking for 20 minutes at a stretch, your next goal is to work on reducing your walking aid, which your physiotherapist will advise on. In the meantime, don't forget to take care of your hip by icing it after activities and elevating your leg to reduce swelling.
> 
> Here's how things compare on post-op day 30, according to the discharge guidance:
> - walking aid: crutches -- as the day-21 checkpoint describes (one crutch or a cane once you can stand and walk for over ten minutes; there is no fixed date for giving up the aid)
> - walking duration: 20 minutes -- meets the day-21 mark of more than 10 minutes
> - stairs: foot over foot -- as the day-21 checkpoint describes (one step at a time with a handrail at first, foot over foot as you get stronger)
> - hip precautions: keeping to your hip precautions -- as the day-21 checkpoint describes (still following the hip precautions, which usually last about the first six weeks)
> 
> Next milestone: day 42 -- hip precautions: precautions commonly apply for about the first six weeks; wait for your surgeon to confirm they have ended; walking aid: reducing or stopping the walking aid when your physiotherapist advises. Say 'recovery check' at day 42 and I'll compare.

*engine Recovery Progress Agent - Grounded Assessment; triage GREEN (engine GREEN); asked -; new fields hip_precautions*

</details>

### c05_rehab_tka_stairs -- TKA day 5 stairs: status from record, one safety question, sourced answer

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | exercise_safety -> False |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 1 asked, max 1 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | PASS | /Next session:/ |

<details><summary>Transcript</summary>

**Patient (1):** Can I go up and down the stairs yet?

> Before I answer: Does any exercise cause sharp pain, or swelling that lasts into the next day? (last question)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercise_safety; new fields -*

**Patient (2):** no, nothing sharp

> On post-op day 5 after Total Knee Arthroplasty (TKA), it's generally recommended to use a walking aid when navigating stairs, especially in the first week. This will help you maintain balance and reduce the risk of further injury. I recommend using a walking aid and icing the knee as directed by your surgeon to help manage pain and swelling, and also elevating your leg to reduce swelling.
> 
> Your weight-bearing status on record is weight-bearing as tolerated, so nothing here should take you beyond it.
> 
> Next session: a short walk with your aid, then two or three stairs up and down with the handrail, one step at a time. Say 'rehab check' tomorrow and I'll see how it went.

*engine Rehabilitation Agent - Grounded Guidance; triage GREEN (engine GREEN); asked -; new fields exercise_safety*

</details>

### c06_rehab_tha_missed_days -- THA day 20: missed-days opener, barrier carried into the close, unknown status

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | exercise_barrier -> the evenings are too sore to face them |
| 3 | collects_field | PASS | exercise_safety -> False |
| 3 | reply_does_not_match | PASS | /(?i)knee flexion\|seated knee extension\|swelling .* is normal/ |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 2 asked, max 2 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | PASS | /Next session:/ |
| - | weight_bearing_record_unchanged | PASS | None -> None |

<details><summary>Transcript</summary>

**Patient (1):** What exercises should I be doing now?

> Your log shows exercises missed on 2 of the last 7 days; anything making them hard? (one more question after this)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercise_barrier; new fields -*

**Patient (2):** the evenings are too sore to face them

> Thanks -- that helps me understand what's making them hard. Does any exercise cause sharp pain, or swelling that lasts into the next day? (last question)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercise_safety; new fields exercise_barrier*

**Patient (3):** no sharp pain and no swelling

> On post-op day 20 after Total Hip Arthroplasty (THA), your exercises should focus on gentle movements to maintain range of motion and promote healing. Try to do some light leg swings, ankle rotations, and toe wiggles while sitting or standing with support, and don't forget to ice your hip for 15-20 minutes, 2-3 times a day, to help reduce pain and swelling.
> 
> I don't have your weight-bearing status, so don't put more weight through the leg than your team has told you until they confirm it.
> 
> You said "the evenings are too sore to face them" is making the exercises hard -- tell your physiotherapist so the programme can be adjusted.
> 
> Next session: the three standing exercises (knee raises, hip abduction, hip extension), about ten times each, holding on to something firm. Say 'rehab check' tomorrow and I'll see how it went.

*engine Rehabilitation Agent - Grounded Guidance; triage GREEN (engine GREEN); asked -; new fields exercise_safety*

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

<details><summary>Transcript</summary>

**Patient (1):** How do I do heel slides?

> Before I answer: Does any exercise cause sharp pain, or swelling that lasts into the next day? (last question)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercise_safety; new fields -*

**Patient (2):** yes, heel slides give me a sharp pain

> Please pause heel slides for now and tell your physiotherapist about the sharp pain before your next session, so they can check it and adjust your programme. Keep to the rest of the programme as your physiotherapist set it.
> 
> Next session: wait for your physiotherapist's advice before repeating heel slides. Say 'rehab check' tomorrow and I'll see how it went.

*engine Rehabilitation Agent - Safety Hold; triage GREEN (engine GREEN); asked -; new fields exercise_safety, exercise_safety_exercise, exercise_safety_kind*

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

<details><summary>Transcript</summary>

**Patient (1):** My knee is aching today.

> Last time you had 4/10 around the kneecap and it was getting better -- let's see where things are now. On a scale from 0 to 10, how bad is the pain right now? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields pain_characteristics*

**Patient (2):** it really hurts

> So far: aching. Sorry, I didn't catch a number there. Would you put it roughly in the mild range (1-3), moderate range (4-6), or severe range (7-10)? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields -*

**Patient (3):** about a 5

> Okay, that helps me understand how strong it is -- so far: 5/10, aching. Did it come on suddenly, or has it been building up gradually? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score*

**Patient (4):** gradually

> Got it -- so far: 5/10, gradual onset, aching. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset*

**Patient (5):** around the kneecap

> Got it -- so far: 5/10, gradual onset, around the kneecap, aching. Is it getting worse, getting better, or staying about the same? (last question)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked worsening_or_improving; new fields location*

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

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields worsening_or_improving*

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
| - | max_questions | PASS | 5 asked, max 5 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | PASS | /Compared with last time/ |
| - | final_has_next_step | PASS | /Next step:/ |
| - | persists_on_completion | PASS | 2 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** My knee hurts quite a lot today.

> Last time you had 5/10 behind the knee and it was about the same -- let's see where things are now. On a scale from 0 to 10, how bad is the pain right now? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields -*

**Patient (2):** 6

> Okay, that helps me understand how strong it is -- so far: 6/10. Did it come on suddenly, or has it been building up gradually? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score*

**Patient (3):** Can I shower tomorrow?

> So far: 6/10. Sorry, I didn't quite catch that. Would you say the pain started all at once, or built up gradually? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields -*

**Patient (4):** it came on gradually

> Got it -- so far: 6/10, gradual onset. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset*

**Patient (5):** behind the knee

> Got it -- so far: 6/10, gradual onset, behind the knee. Is it getting worse, getting better, or staying about the same? (last question)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked worsening_or_improving; new fields location*

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

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields worsening_or_improving*

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

<details><summary>Transcript</summary>

**Patient (1):** My knee is really sore today.

> Last time you had 6/10 behind the knee and it was about the same -- let's see where things are now. On a scale from 0 to 10, how bad is the pain right now? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields -*

**Patient (2):** 5

> Okay, that helps me understand how strong it is -- so far: 5/10. Did it come on suddenly, or has it been building up gradually? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score*

**Patient (3):** Can I climb stairs?

> Take stairs one step at a time with the handrail: up with the good leg, down with the operated leg.

*engine scripted detour; triage GREEN (engine GREEN); asked -; new fields -*

**Patient (4):** gradually

> Got it -- so far: 5/10, gradual onset. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset*

**Patient (5):** on the inside of the knee

> Got it -- so far: 5/10, gradual onset, on the inside. Is it getting worse, getting better, or staying about the same? (last question)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked worsening_or_improving; new fields location*

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

*engine Pain & Symptoms Agent - Safe Conclusion Fallback; triage GREEN (engine GREEN); asked -; new fields worsening_or_improving*

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
| - | final_has_trend_or_checkpoint | PASS | /Compared with last time/ |
| - | final_has_next_step | PASS | /Next step:/ |
| - | persists_on_completion | PASS | 2 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** It's about a 5 out of 10, it came on gradually, and it's behind the knee.

> Last time you had 6/10 behind the knee and it was getting worse -- let's see where things are now. Is it getting worse, getting better, or staying about the same? (last question)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked worsening_or_improving; new fields location, onset, pain_score*

**Patient (2):** getting a bit better

> Thanks for going through that with me. Based on what you've told me:
> - pain score: 5/10
> - how it started: gradual
> - where it's felt: behind the knee
> - how it's trending: improving
> 
> Compared with last time: That's lower than the pain score of 6/10 recorded last time. Last time it was behind the knee and getting worse; now it's behind the knee and getting better.
> 
> Following your surgical team's guidance: Continue prescribed home rehabilitation exercises, cryotherapy, elevation, and oral medication schedule. Log next check-in as scheduled.
> 
> Next step: note how the pain feels again this evening so we can compare it with today. Say 'pain check' any time and I'll compare with today.
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

> Thanks for telling me -- I'd like to understand this a little better. On a scale from 0 to 10, how bad is the pain right now? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields pain_characteristics*

**Patient (2):** 6

> Okay, that helps me understand how strong it is -- so far: 6/10, throbbing. Did it come on suddenly, or has it been building up gradually? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score*

**Patient (3):** it came on suddenly

> Got it -- so far: 6/10, sudden onset, throbbing. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset*

</details>

### c13_pain_mild_medication -- Mild pain after paracetamol: short joint branch plus the medication-effect question

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
| - | final_has_trend_or_checkpoint | PASS | /Compared with last time/ |
| - | final_has_next_step | PASS | /Next step:/ |
| - | persists_on_completion | PASS | 2 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** My knee aches a little, I took paracetamol an hour ago.

> Last time you had 5/10 around the kneecap and it was getting better -- let's see where things are now. On a scale from 0 to 10, how bad is the pain right now? (a few more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked pain_score; new fields -*

**Patient (2):** 3

> Okay, that helps me understand how strong it is -- so far: 3/10. Did it come on suddenly, or has it been building up gradually? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked onset; new fields pain_score*

**Patient (3):** gradually

> Got it -- so far: 3/10, gradual onset. Where are you feeling it most -- in the knee itself, behind the knee, around the incision, in the calf, or somewhere else? (one or two more questions)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked location; new fields onset*

**Patient (4):** around the kneecap

> Got it -- so far: 3/10, gradual onset, around the kneecap. Did taking your pain medication help, or not really? (last question)

*engine Pain & Symptoms Agent - Multi-turn Assessment; triage GREEN (engine GREEN); asked medication_effect; new fields location*

**Patient (5):** yes it helped

> Thanks for going through that with me. Based on what you've told me:
> - pain score: 3/10
> - how it started: gradual
> - where it's felt: around the kneecap
> - effect of medication: yes it helped
> 
> Compared with last time: That's lower than the pain score of 5/10 recorded last time. Last time it was around the kneecap and getting better; now it's around the kneecap.
> 
> Following your surgical team's guidance: Continue prescribed home rehabilitation exercises, cryotherapy, elevation, and oral medication schedule. Log next check-in as scheduled.
> 
> Next step: note how the pain feels again this evening so we can compare it with today. Say 'pain check' any time and I'll compare with today.
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
| 5 | collects_field | PASS | walking_duration_minutes -> 5.0 |
| 6 | collects_field | PASS | stairs -> not_yet |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 5 asked, max 5 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | PASS | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | PASS | /Next milestone:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** Am I on track with my knee?

> Let's see where you are on post-op day 4. About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (2):** about 60 degrees

> Okay -- flexion of 60° on day 4; the first flexion checkpoint is day 7, which looks for 70°-90° (according to the discharge guidance) -- the target to work towards. Do you know your current knee extension measurement in degrees (how close to fully straight)? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields rom_flexion_degrees*

**Patient (3):** about 10 degrees off straight

> Okay -- extension of 10° on day 4; the first extension checkpoint is day 7, which looks for 0°-5° (according to the discharge guidance) -- the target to work towards. How are you currently getting around -- walking independently, or using a walker, cane, or crutches? (one or two more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked mobility_status; new fields rom_extension_degrees*

**Patient (4):** I use a walker

> Okay -- walking aid: a walker/frame on day 4; the first walking aid checkpoint is day 7, which describes walking with a frame, crutches or cane on a level surface (according to the discharge guidance) -- the target to work towards. Roughly how many minutes can you walk at a stretch at the moment? (one more question after this)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked walking_duration_minutes; new fields mobility_status*

**Patient (5):** about 5 minutes

> Got it -- walking duration: 5 minutes on day 4; the first walking duration checkpoint is day 7, which describes walking little and often around the home (according to the discharge guidance) -- the target to work towards. How are you managing stairs -- not yet, one step at a time holding the rail, or foot over foot? (last question)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked stairs; new fields walking_duration_minutes*

**Patient (6):** not yet

> Here's how things compare on post-op day 4, according to the discharge guidance:
> - flexion: 60° -- the first flexion checkpoint is day 7, which looks for 70°-90°; the target to work towards
> - extension: 10° -- the first extension checkpoint is day 7, which looks for 0°-5°; the target to work towards
> - walking aid: a walker/frame -- the first walking aid checkpoint is day 7, which describes walking with a frame, crutches or cane on a level surface; the target to work towards
> - walking duration: 5 minutes -- the first walking duration checkpoint is day 7, which describes walking little and often around the home; the target to work towards
> - stairs: not yet -- the first stairs checkpoint is day 7, which describes managing two or three steps up and down with your aid; the target to work towards
> 
> Next milestone: day 7 -- flexion: 70-90 degrees of passive flexion; extension: near-full extension (0-5 degrees). Say 'recovery check' at day 7 and I'll compare.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields stairs*

</details>

### c15_recovery_request_current_rom -- current_rom in the request: flexion and extension are fed back, never asked

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | mobility_status -> cane |
| 3 | collects_field | PASS | walking_duration_minutes -> 20.0 |
| 4 | collects_field | PASS | stairs -> one_at_a_time |
| - | no_question_for_record_data | PASS | never asked: rom_flexion_degrees, rom_extension_degrees |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 3 asked, max 3 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | PASS | /day-\d+ (range\|checkpoint\|mark\|target\|guidance)\|long-term guidance\|checkpoint is day \d+/ |
| - | final_has_next_step | PASS | /Next milestone:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** How's my progress looking?

> Got it -- flexion of 95°, meets the day-14 mark of more than 80° (according to the discharge guidance). extension of 2°, within the day-14 range of 0°-10°. How are you currently getting around -- walking independently, or using a walker, cane, or crutches? (one or two more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked mobility_status; new fields rom_extension_degrees, rom_flexion_degrees*

**Patient (2):** a cane

> Thanks for sharing that -- walking aid: a cane, matches the day-14 checkpoint (according to the discharge guidance): a frame or two crutches, moving to a single crutch or cane once you can stand and walk for more than ten minutes. Roughly how many minutes can you walk at a stretch at the moment? (one more question after this)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked walking_duration_minutes; new fields mobility_status*

**Patient (3):** about 20 minutes

> Okay -- walking duration of 20 minutes, meets the day-14 mark of more than 10 minutes (according to the discharge guidance). How are you managing stairs -- not yet, one step at a time holding the rail, or foot over foot? (last question)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked stairs; new fields walking_duration_minutes*

**Patient (4):** one step at a time

> Here's how things compare on post-op day 16, according to the discharge guidance:
> - flexion: 95° -- meets the day-14 mark of more than 80°
> - extension: 2° -- within the day-14 range of 0°-10°
> - walking aid: a cane -- as the day-14 checkpoint describes (a frame or two crutches, moving to a single crutch or cane once you can stand and walk for more than ten minutes)
> - walking duration: 20 minutes -- meets the day-14 mark of more than 10 minutes
> - stairs: one step at a time -- as the day-14 checkpoint describes (one step at a time using the handrail; stepping foot over foot comes later)
> 
> Next milestone: day 21 -- flexion: bending improving week by week, working towards more than 110 degrees by the end of week six; extension: straightening improving week by week, working towards a fully straight knee by the end of week six. Say 'recovery check' at day 21 and I'll compare.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields stairs*

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

<details><summary>Transcript</summary>

**Patient (1):** I can bend my knee to 95 degrees and walk with a cane for about 20 minutes. How am I doing?

> Okay -- walking aid: a cane, matches the day-14 checkpoint (according to the discharge guidance): a frame or two crutches, moving to a single crutch or cane once you can stand and walk for more than ten minutes. flexion of 95°, meets the day-14 mark of more than 80°. walking duration of 20 minutes, meets the day-14 mark of more than 10 minutes. Do you know your current knee extension measurement in degrees (how close to fully straight)? (one more question after this)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields mobility_status, rom_flexion_degrees, walking_duration_minutes*

**Patient (2):** about 3 degrees

> Thanks for sharing that -- extension of 3°, within the day-14 range of 0°-10° (according to the discharge guidance). How are you managing stairs -- not yet, one step at a time holding the rail, or foot over foot? (last question)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked stairs; new fields rom_extension_degrees*

**Patient (3):** foot over foot

> Here's how things compare on post-op day 15, according to the discharge guidance:
> - flexion: 95° -- meets the day-14 mark of more than 80°
> - extension: 3° -- within the day-14 range of 0°-10°
> - walking aid: a cane -- as the day-14 checkpoint describes (a frame or two crutches, moving to a single crutch or cane once you can stand and walk for more than ten minutes)
> - walking duration: 20 minutes -- meets the day-14 mark of more than 10 minutes
> - stairs: foot over foot -- beyond what the day-14 checkpoint describes (one step at a time using the handrail; stepping foot over foot comes later)
> 
> Next milestone: day 21 -- flexion: bending improving week by week, working towards more than 110 degrees by the end of week six; extension: straightening improving week by week, working towards a fully straight knee by the end of week six. Say 'recovery check' at day 21 and I'll compare.

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked -; new fields stairs*

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

<details><summary>Transcript</summary>

**Patient (1):** How is my knee recovery going?

> Let's see where you are on post-op day 12. About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (2):** about 90 degrees

> Got it -- flexion of 90°, within the day-7 range of 70°-90° (according to the discharge guidance). Do you know your current knee extension measurement in degrees (how close to fully straight)? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields rom_flexion_degrees*

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
| - | final_has_next_step | PASS | /Next milestone:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** Is my recovery on track now?

> Let's see where you are on post-op day 90. About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (2):** 115 degrees

> Okay -- flexion: 115°; the long-term guidance (according to the discharge guidance) gives no number, it expects some stiffness when bending the knee a long way is common; keep up the prescribed exercises. Do you know your current knee extension measurement in degrees (how close to fully straight)? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields rom_flexion_degrees*

**Patient (3):** 0 degrees, it goes fully straight

> Got it -- extension of 0°, meets the day-84 target of 0° (according to the discharge guidance). How are you currently getting around -- walking independently, or using a walker, cane, or crutches? (one or two more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked mobility_status; new fields rom_extension_degrees*

**Patient (4):** walking without any aid now

> Thanks for sharing that -- walking aid: walking without an aid, matches the day-84 checkpoint (according to the discharge guidance): walking further and more steadily, with less need for a walking aid. Roughly how many minutes can you walk at a stretch at the moment? (one more question after this)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked walking_duration_minutes; new fields mobility_status*

**Patient (5):** about 60 minutes

> Got it -- walking duration: 60 minutes; the long-term guidance (according to the discharge guidance) gives no number, it expects regular walking as a preferred low-impact activity. How are you managing stairs -- not yet, one step at a time holding the rail, or foot over foot? (last question)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked stairs; new fields walking_duration_minutes*

**Patient (6):** foot over foot

> Based on your progress, it sounds like your knee recovery is going well! You're making good progress with your knee flexion and extension, and you're able to walk without any aid, which is a big step forward. Now, let's focus on the next steps - your goal is to get back to doing many of the activities you enjoyed before your surgery, and that's something to work towards.
> 
> Here's how things compare on post-op day 90, according to the discharge guidance:
> - flexion: 115° -- no number in the long-term guidance; it expects some stiffness when bending the knee a long way is common; keep up the prescribed exercises
> - extension: 0° -- meets the day-84 target of 0°
> - walking aid: walking without an aid -- as the day-84 checkpoint describes (walking further and more steadily, with less need for a walking aid)
> - walking duration: 60 minutes -- no number in the long-term guidance; it expects regular walking as a preferred low-impact activity
> - stairs: foot over foot -- as the day-84 checkpoint describes (climbing stairs step over step with little pain)
> 
> Next milestone: longer term -- daily activities: back to many previous activities, preferring low-impact ones. Say 'recovery check' any time and I'll compare with today.

*engine Recovery Progress Agent - Grounded Assessment; triage GREEN (engine GREEN); asked -; new fields stairs*

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

<details><summary>Transcript</summary>

**Patient (1):** How am I doing with my knee?

> Let's see where you are on post-op day 20. About how many degrees can you currently bend your knee? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (2):** I don't know

> That's okay. Even a rough number helps -- when you sit and bend the knee back, roughly how many degrees would you say? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_flexion_degrees; new fields -*

**Patient (3):** no idea, sorry

> No problem -- I'll leave flexion for now. Do you know your current knee extension measurement in degrees (how close to fully straight)? (a few more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked rom_extension_degrees; new fields -*

**Patient (4):** about 5 degrees

> Okay -- extension of 5°, within the day-14 range of 0°-10° (according to the discharge guidance). How are you currently getting around -- walking independently, or using a walker, cane, or crutches? (one or two more questions)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked mobility_status; new fields rom_extension_degrees*

**Patient (5):** a walker

> Thanks for sharing that -- walking aid: a walker/frame, matches the day-14 checkpoint (according to the discharge guidance): a frame or two crutches, moving to a single crutch or cane once you can stand and walk for more than ten minutes. Roughly how many minutes can you walk at a stretch at the moment? (one more question after this)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked walking_duration_minutes; new fields mobility_status*

**Patient (6):** 10 minutes

> Thanks for sharing that -- walking duration of 10 minutes, meets the day-14 mark of more than 10 minutes (according to the discharge guidance). How are you managing stairs -- not yet, one step at a time holding the rail, or foot over foot? (last question)

*engine Recovery Deterministic Assessment Engine; triage GREEN (engine GREEN); asked stairs; new fields walking_duration_minutes*

**Patient (7):** not yet

> Here's a friendly answer to the user's question:
> 
> "Hi! On day 20 after your Total Knee Arthroplasty (TKA), your knee is making good progress. You're doing great with your walking aid - using a walker is right where you should be at this stage. For next steps, focus on bending your knee a bit more each day, aiming to get closer to 110 degrees by the end of week six. Don't forget to take care of your knee by icing it after activities and elevating your leg to reduce swelling. Keep up the good work!"
> 
> Here's how things compare on post-op day 20, according to the discharge guidance:
> - extension: 5° -- within the day-14 range of 0°-10°
> - walking aid: a walker/frame -- as the day-14 checkpoint describes (a frame or two crutches, moving to a single crutch or cane once you can stand and walk for more than ten minutes)
> - walking duration: 10 minutes -- meets the day-14 mark of more than 10 minutes
> - stairs: not yet -- not yet at what the day-14 checkpoint describes (one step at a time using the handrail; stepping foot over foot comes later)
> - flexion: I don't have a value from you for this one, so I can't compare it.
> 
> Next milestone: day 21 -- flexion: bending improving week by week, working towards more than 110 degrees by the end of week six; extension: straightening improving week by week, working towards a fully straight knee by the end of week six. Say 'recovery check' at day 21 and I'll compare.

*engine Recovery Progress Agent - Grounded Assessment; triage GREEN (engine GREEN); asked -; new fields stairs*

</details>

### c20_rehab_direct_question -- Direct question naming an exercise: one question, today's log not re-asked

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | exercise_safety -> False |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status, exercises_done_today |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 1 asked, max 1 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | PASS | /Next session:/ |

<details><summary>Transcript</summary>

**Patient (1):** How do I do heel slides?

> Before I answer: Does any exercise cause sharp pain, or swelling that lasts into the next day? (last question)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercise_safety; new fields -*

**Patient (2):** no, nothing hurts

> On post-op day 8 after Total Knee Arthroplasty (TKA), heel slides can be a helpful exercise to strengthen your knee. Since you're at the 8-day mark, your goal is to aim for gentle movements, and it's essential to remember that your knee is still recovering. Before attempting heel slides, make sure to ice your knee for 10-15 minutes, 2-3 times a day, and elevate your leg above the level of your heart to reduce swelling.
> 
> Your weight-bearing status on record is weight-bearing as tolerated, so nothing here should take you beyond it.
> 
> Next session: the first-week set (quad sets, straight leg raises, ankle pumps, knee straightening, heel slides and sitting knee bends), each repeated until the muscles feel tired. Say 'rehab check' tomorrow and I'll see how it went.

*engine Rehabilitation Agent - Grounded Guidance; triage GREEN (engine GREEN); asked -; new fields exercise_safety*

</details>

### c21_rehab_status_unknown -- No status on record: two questions, 'not yet' persisted, surgeries untouched

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | exercise_safety -> False |
| 3 | collects_field | PASS | exercises_done_today -> False |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 2 asked, max 2 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | PASS | /Next session:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |
| - | weight_bearing_record_unchanged | PASS | None -> None |

<details><summary>Transcript</summary>

**Patient (1):** What exercises should I do today?

> Before I answer: Does any exercise cause sharp pain, or swelling that lasts into the next day? (one more question after this)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercise_safety; new fields -*

**Patient (2):** no

> Thanks -- no sharp pain or lasting swelling. Have you done today's exercises yet? (last question)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercises_done_today; new fields exercise_safety*

**Patient (3):** not yet

> On post-op day 10 after Total Knee Arthroplasty (TKA), your goal is to focus on gentle exercises to help your knee recover. Since you're in the strengthening phase, we'll start with some gentle movements to promote flexibility and range of motion. Please try some gentle knee bends and straightening, and don't forget to ice your knee for 15-20 minutes, 2-3 times a day, to help reduce pain and swelling.
> 
> I don't have your weight-bearing status, so don't put more weight through the leg than your team has told you until they confirm it.
> 
> Next session: walking practice landing on the heel, sit-to-stands from a chair and small step-ups on a low step, as your physiotherapist set. Say 'rehab check' tomorrow and I'll see how it went.

*engine Rehabilitation Agent - Grounded Guidance; triage GREEN (engine GREEN); asked -; new fields exercises_done_today*

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
| - | final_has_trend_or_checkpoint | **FAIL** | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | PASS | /Next session:/ |
| - | persists_on_completion | PASS | 1 row(s) written, expected >= 1 |

<details><summary>Transcript</summary>

**Patient (1):** I did my exercises this morning and nothing hurts, no sharp pain. What exercises should I add next?

> On post-op day 9, your exercises should focus on gentle range of motion and strengthening. Aim to maintain your current range of motion and continue to work on strengthening your knee muscles. Remember to follow your doctor's orders for icing and limb elevation as needed to support your recovery.
> 
> Your weight-bearing status on record is weight-bearing as tolerated, so nothing here should take you beyond it.
> 
> Next session: walking practice landing on the heel, sit-to-stands from a chair and small step-ups on a low step, as your physiotherapist set. Say 'rehab check' tomorrow and I'll see how it went.

*engine Rehabilitation Agent - Grounded Guidance; triage GREEN (engine GREEN); asked -; new fields exercise_safety, exercises_done_today*

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

<details><summary>Transcript</summary>

**Patient (1):** What exercises should I be doing?

> Before I answer: Does any exercise cause sharp pain, or swelling that lasts into the next day? (one more question after this)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercise_safety; new fields -*

**Patient (2):** hmm, let me think about that

> Sorry, I didn't catch that -- a simple yes or no is fine. Is any exercise leaving you with sharp pain, or a joint that is still more swollen the next morning? (one more question after this)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercise_safety; new fields -*

</details>

### c24_rehab_request_nwb_override -- Request NWB overrides the WBAT record: squats question, no loading advice

| Turn | Property | Result | Detail |
|---|---|---|---|
| 2 | collects_field | PASS | exercise_safety -> False |
| 2 | reply_does_not_match | PASS | /(?i)\b(put (your )?(full )?weight\|bear (your )?full weight\|try (a )?squat)/ |
| - | no_question_for_record_data | PASS | never asked: weight_bearing_status |
| - | no_reask_of_collected_field | PASS |  |
| - | max_questions | PASS | 1 asked, max 1 |
| - | triage_equals_engine | PASS |  |
| - | no_passage_id_in_text | PASS |  |
| - | final_turn_closes_interview | PASS | no question pending |
| - | final_has_trend_or_checkpoint | PASS | /on day \d+ after your (knee\|hip) replacement\|for day \d+ after your/ |
| - | final_has_next_step | PASS | /Next session:/ |

<details><summary>Transcript</summary>

**Patient (1):** Can I start doing squats?

> Before I answer: Does any exercise cause sharp pain, or swelling that lasts into the next day? (last question)

*engine Rehabilitation Agent - Exercise Check; triage GREEN (engine GREEN); asked exercise_safety; new fields -*

**Patient (2):** no

> I don't have discharge guidance on squats for day 3 after your knee replacement, so please check with your surgeon or physiotherapist before trying it.
> 
> Your weight-bearing status from this request is non-weight-bearing, so nothing here should take you beyond it.
> 
> Next session: keep to the exercises your physiotherapist has already set until they have advised on this. Say 'rehab check' tomorrow and I'll see how it went.

*engine Rehabilitation Agent - Sourced Fallback; triage GREEN (engine GREEN); asked -; new fields exercise_safety*

</details>
