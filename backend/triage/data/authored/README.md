# Authored patient messages

One file per scenario: `<SCENARIO_ID>.tsv`. These are synthetic messages written by an LLM
(claude-opus-5-5) following `../LABELLING_GUIDELINE.md`. `../build_dataset.py` reads them.

## File format

UTF-8, one message per line, 4 tab-separated fields. Lines starting with `#` are comments.

```
LABEL<TAB>SURGERY<TAB>TAGS<TAB>TEXT
RED	ANY	hard_pos,indirect	my leg looks funny and I can't feel my toes
GREEN	TKA	hard_neg,negation	knee is sore after physio but no calf pain and no swelling, just checking how often to ice
```

- `LABEL`: RED, YELLOW or GREEN, decided by the guideline (not by the scenario).
- `SURGERY`: TKA, THA, or ANY (wording fits both; the builder picks one). Hip-only content
  (dislocation, hip precautions) is THA; knee-only content is TKA.
- `TAGS`: comma-separated, any of
  `hard_pos` (RED/YELLOW with no obvious keyword), `hard_neg` (GREEN/YELLOW containing a scary word
  in a benign, negated or resolved context), `negation`, `temp_in_text`, `indian_english`, `typo`,
  `indirect`, `multi_symptom`, `question`, `carer` (written by a family member). Use `-` for none.
- `TEXT`: the message. No tabs.

## Writing rules

- 3 to 40 words. Mix very short ("calf hot n swollen"), medium, and longer rambling messages.
- Vary register: plain, anxious, formal, texting style, elderly, carer writing for a parent.
- About 1 in 5 lines in Indian-English phrasing ("my leg is paining since morning", "kindly
  advise", "doctor sir", "having fever from 2 days", "motion not passed", "what to do now",
  occasional light Hindi words such as "bahut dard").
- About 1 in 8 lines with realistic spelling slips or texting shortcuts ("calf", "swolen",
  "cant", "abt", "pls", "temprature").
- Indirect descriptions: say what the patient sees or feels, not the clinical term ("my leg looks
  funny", "foot gone white and I can't wiggle my toes", "feels like I'm breathing through a straw").
- Temperatures: written in many forms (38.6, 38.6C, 101F, 100.4 F, "fever of 39", "temp 37.9").
  The label must follow the thresholds: >= 38.5 C / >= 101.3 F RED; 37.8-38.4 C / 100.0-101.2 F
  YELLOW; below that contributes nothing. Tag these lines `temp_in_text`.
- Every scenario file must include contrast rows: hard negatives (negated, resolved, benign or
  hypothetical uses of the scary words, labelled GREEN or YELLOW) and, where natural, hard
  positives. Info questions about the topic are GREEN.
- No two lines in a file may be near-paraphrases of each other; change the situation, not just
  the words. Do not copy or closely paraphrase the 63 source sentences in
  `../source_relabelled.jsonl`.
- Only TKA and THA patients. Do not mention ACL, rotator cuff or shoulder surgery.
- No names of real people, no phone numbers.

## Scenarios and targets

| scenario_id | lead label | lines | content |
|---|---|---:|---|
| DVT_CALF | RED | 70 | calf/leg pain not from incision, hot/hard/red calf, swelling not settling with elevation. Contrast: calf fine, swelling that settles, "how do I spot a clot" |
| PE_CHEST | RED | 70 | breathlessness, chest pain on breathing/coughing, coughing blood, fainting, racing heart. Contrast: negated chest pain, breathing-exercise questions, puffed after stairs but settles |
| NEUROVASCULAR | RED | 70 | numb/cold/pale/blue foot or toes, cannot move toes or foot. Contrast: mild tingling near scar that has been there since surgery (YELLOW/GREEN), numb patch beside incision |
| COMPARTMENT | RED | 70 | severe pain out of proportion, leg tight/rock hard, painkillers not working. Contrast: sore and tight after physio, settles with rest |
| DISLOCATION | RED | 70 | THA: pop, leg shorter/turned, cannot move or weight-bear, sudden severe groin pain. A few TKA: knee gave way and looks deformed. Contrast: precautions questions, a harmless click |
| FALL_INJURY | RED | 60 | fell and now can't bear weight / new deformity / hit head on blood thinner. Contrast: near-miss, fell but walking fine (YELLOW), how to get up safely (GREEN) |
| SEPSIS_WOUND | RED | 70 | pus, foul smell, spreading redness, wound plus fever >= 38.5 or shaking chills. Contrast: wound fine and no fever, "what does infection look like" |
| WOUND_OPEN | RED | 60 | wound split open, can see deep tissue, staples came out and gaping. Contrast: tiny scab came off (GREEN), small gap at one end, dry (YELLOW) |
| HIGH_FEVER | RED | 70 | temperature >= 38.5 C / >= 101.3 F, fever with shaking chills, very unwell/confused. Contrast: 37.2 normal, "what temperature is a fever" |
| BLEEDING_ANTICOAG | RED | 70 | black stool, vomiting blood, blood in urine, bleeding that won't stop, dressing soaked, huge bruises on blood thinner. Contrast: small bruise at injection site, beetroot-coloured urine after beetroot, red stool after eating beetroot (only if clearly explained), a spot of blood on dressing that stopped |
| ALLERGIC_REACTION | RED | 50 | face/lip/tongue swelling, throat tight, wheeze, widespread hives after a new medicine. Contrast: small itchy rash only (YELLOW), plaster itch (GREEN) |
| LOW_FEVER | YELLOW | 55 | 37.8-38.4 C / 100.0-101.2 F, "feeling feverish" with no number. Contrast: 37.1, 37.5 (GREEN), general fever questions (GREEN) |
| CLEAR_DRAINAGE | YELLOW | 55 | clear, pink or watery fluid coming from incision, damp dressing. Contrast: dry wound (GREEN); pus or smell would be SEPSIS, don't include |
| WOUND_REDNESS | YELLOW | 55 | a little redness, warmth or swelling along the incision. Contrast: pink scar line fading (GREEN) |
| WOUND_IRRITATION | YELLOW | 50 | staples/stitches pulling, itchy, puckered, irritated, steri-strips lifting. Contrast: healed scar itch (GREEN) |
| UNCONTROLLED_PAIN | YELLOW | 55 | pain not controlled by prescribed relief, getting worse day by day, can't sleep for pain, without RED features. Contrast: normal post-physio soreness (GREEN) |
| MINOR_BLEEDING | YELLOW | 50 | small ooze of blood on dressing, bruising spreading down the leg on blood thinners, nosebleed that stopped. Contrast: "doctor said a little blood is fine and it has stopped" (GREEN) |
| CONSTIPATION | YELLOW | 50 | no bowel movement 3+ days, bloated, straining, on painkillers. Contrast: diet questions, "went today, fine now" (GREEN) |
| MED_SIDE_EFFECT | YELLOW | 50 | nausea, vomiting, dizziness, drowsy, itchy without face swelling, after medicines. Contrast: questions about side effects (GREEN) |
| MISSED_DOSE | YELLOW | 50 | missed or doubled blood-thinner dose, vomited a tablet, ran out of medicine. Contrast: missed a vitamin (GREEN), "what if I miss a dose" (GREEN) |
| IMPLANT_NOISE | YELLOW | 50 | clicking/clunking WITH pain, swelling, giving way, feeling loose. Contrast: painless clicking (GREEN) |
| NORMAL_SWELLING | GREEN | 45 | ankle swelling that settles overnight/with elevation, ice/elevation questions. A few YELLOW (swelling worse over weeks but settling) |
| HIP_PRECAUTIONS | GREEN | 45 | THA: bending, crossing legs, low chairs, toilet seat, sleeping position, reacher |
| REHAB_EXERCISE | GREEN | 45 | exercise frequency, range of motion, physio, cycling, sore muscles after exercise |
| WALKING_AIDS | GREEN | 45 | walker, crutches, cane, stairs, weight bearing |
| STIFFNESS | GREEN | 45 | tight band, morning stiffness, can't fully straighten yet, slow progress |
| DAILY_ACTIVITY | GREEN | 45 | shower, driving, sleeping position, work, travel, sex, squatting/sitting cross-legged on floor |
| NUTRITION | GREEN | 45 | protein, vitamins, water, diabetic diet, weight |
| MOOD_SLEEP | GREEN | 45 | low mood, frustration, poor sleep, anxiety. Include ~5 YELLOW (not coping for days) and ~4 RED (thoughts of self-harm or not wanting to live) |
| MED_TIMING | GREEN | 45 | when to take painkillers, combining paracetamol/ibuprofen, how long on blood thinners, stopping opioids |
| FOLLOWUP_ADMIN | GREEN | 45 | appointments, staple removal date, reports, sick note, dressing supplies |

For RED-led scenarios aim for about 80% RED; for YELLOW-led about 65% YELLOW; for GREEN-led
about 85% GREEN. Labels always follow the guideline, so the actual mix may differ.
