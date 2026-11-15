# Routing benchmark -- `heldout_v2_before`

- commit `932beaa`, 2026-11-12; case set `heldout_v2`, 30 cases; semantic_first=False; thresholds {'SEMANTIC_MIN_SCORE': 0.35, 'SEMANTIC_MIN_MARGIN': 0.04}
- classifier run 12.2s, orchestrator run 0.2s
- a prediction is correct when it is in the case's acceptable set; *clear only* excludes debatable cases; *openings* excludes answers to a pending question (cases.py has six; heldout_v2 none), which carry no routable signal on their own
- orchestrator *lenient*: at least one dispatched agent is acceptable (the eval/agents definition); *strict*: every dispatched agent is acceptable

## Per agent

| Agent | n | Classifier | Classifier, clear only | Classifier, openings | Orchestrator (lenient) | Orchestrator (strict) | Orchestrator, openings |
|---|---|---|---|---|---|---|---|
| Pain & Symptoms | 2 | 0/2 (0%) | - | 0/2 (0%) | 2/2 (100%) | 0/2 (0%) | 2/2 (100%) |
| Recovery Progress | 5 | 4/5 (80%) | 4/4 (100%) | 4/5 (80%) | 4/5 (80%) | 4/5 (80%) | 4/5 (80%) |
| Rehabilitation | 5 | 5/5 (100%) | 4/4 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) |
| Wound Care | 2 | 0/2 (0%) | 0/2 (0%) | 0/2 (0%) | 2/2 (100%) | 2/2 (100%) | 2/2 (100%) |
| Medication | 8 | 8/8 (100%) | 5/5 (100%) | 8/8 (100%) | 8/8 (100%) | 8/8 (100%) | 8/8 (100%) |
| Daily Activity | 4 | 4/4 (100%) | 2/2 (100%) | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) |
| Nutrition | 4 | 0/4 (0%) | 0/3 (0%) | 0/4 (0%) | 4/4 (100%) | 0/4 (0%) | 4/4 (100%) |
| **All** | 30 | **21/30 (70%)** | 15/20 (75%) | 21/30 (70%) | **29/30 (97%)** | 23/30 (77%) | 29/30 (97%) |

Orchestrator pre-emption cases (emergency / out_of_scope expected): -; multi-agent turns: 7; pre-empted: {}.

Decision paths: `deterministic` 24, `fallback_low_confidence` 1, `semantic` 5

## Classifier misses, grouped by rule

### keyword order (8)

| Case | Message | Expected (acceptable) | Got | Path | Rule |
|---|---|---|---|---|---|
| H009 | "The skin along my incision line is very itchy" | wound_care (wound_care) | medication | deterministic | keyword order: medication (itchy) is checked before wound_care (incision) |
| H010 | "Itching near the stitches at night, does that mean it is healing?" | wound_care (wound_care) | medication | deterministic | keyword order: medication (itching) is checked before wound_care (stitches) |
| H011 | "Feeling bloated and gassy after eating rice, what should I avoid?" | nutrition (nutrition) | medication | deterministic | keyword order: medication (bloated) is checked before nutrition (eating) |
| H012 | "Bloated after meals, which foods are lighter on the stomach?" | nutrition (nutrition) | medication | deterministic | keyword order: medication (bloated) is checked before nutrition (foods) |
| H013 | "I get dizzy when I stand up after physio" *debatable* | pain_symptoms (pain_symptoms, rehabilitation, daily_activity) | medication | deterministic | keyword order: medication (dizzy) is checked before rehabilitation (physio) |
| H014 | "Feeling light-headed when I get out of bed in the morning" *debatable* | pain_symptoms (pain_symptoms, daily_activity) | medication | deterministic | keyword order: medication (light-headed) is checked before daily_activity (bed) |
| H015 | "Constipated since the operation, which foods will help?" | nutrition (nutrition) | medication | deterministic | keyword order: medication (constipated) is checked before nutrition (foods) |
| H016 | "I feel nauseous when I smell cooking these days, what can I eat?" *debatable* | nutrition (nutrition, pain_symptoms) | medication | deterministic | keyword order: medication (nauseous) is checked before nutrition (eat) |

### overbroad keyword (1)

| Case | Message | Expected (acceptable) | Got | Path | Rule |
|---|---|---|---|---|---|
| H017 | "Very fatigued after walking to the gate and back, is that normal at this stage?" *debatable* | recovery_progress (recovery_progress, rehabilitation, daily_activity) | medication | deterministic | overbroad keyword: medication matched fatigued |

## Orchestrator misses (lenient)

| Case | Message | Expected (acceptable) | Orchestrator intent | Target agent | Classifier said |
|---|---|---|---|---|---|
| H017 | "Very fatigued after walking to the gate and back, is that normal at this stage?" | recovery_progress (recovery_progress, rehabilitation, daily_activity) | medication | MedicationAgent | medication (deterministic) |

## Orchestrator differs from the classifier

| Case | Message | Classifier | Orchestrator | Why |
|---|---|---|---|---|
| H007 | "Nausea comes after every dose, should I eat something first?" | medication | medication,nutrition | multi-agent: detect_applicable_intents |
| H009 | "The skin along my incision line is very itchy" | medication | wound_care | recorded medication / context |
| H010 | "Itching near the stitches at night, does that mean it is healing?" | medication | wound_care | recorded medication / context |
| H011 | "Feeling bloated and gassy after eating rice, what should I avoid?" | medication | medication,nutrition | multi-agent: detect_applicable_intents |
| H012 | "Bloated after meals, which foods are lighter on the stomach?" | medication | medication,nutrition | multi-agent: detect_applicable_intents |
| H013 | "I get dizzy when I stand up after physio" | medication | medication,rehabilitation,daily_activity | multi-agent: detect_applicable_intents |
| H014 | "Feeling light-headed when I get out of bed in the morning" | medication | medication,daily_activity | multi-agent: detect_applicable_intents |
| H015 | "Constipated since the operation, which foods will help?" | medication | medication,nutrition | multi-agent: detect_applicable_intents |
| H016 | "I feel nauseous when I smell cooking these days, what can I eat?" | medication | medication,nutrition | multi-agent: detect_applicable_intents |

## Every case

| Case | Source | Message | Expected (acceptable) | Conf. | Classifier | Path | Orchestrator |
|---|---|---|---|---|---|---|---|
| H001 | heldout_v2:med_symptom | "Itching all over my arms since the new tablets started" | medication (medication) | clear | medication | deterministic | medication |
| H002 | heldout_v2:med_symptom | "I feel dizzy about an hour after my painkiller" | medication (medication) | clear | medication | deterministic | medication |
| H003 | heldout_v2:med_symptom | "Since I started the tramadol I am badly constipated" | medication (medication, nutrition) | debatable | medication | deterministic | medication |
| H004 | heldout_v2:med_symptom | "Is feeling drowsy all day a side effect of gabapentin?" | medication (medication) | clear | medication | deterministic | medication |
| H005 | heldout_v2:med_symptom | "The blood thinner injection makes me light headed, is that expected?" | medication (medication) | clear | medication | deterministic | medication |
| H006 | heldout_v2:med_symptom | "Tummy feels bloated ever since I began these pills" | medication (medication, nutrition) | debatable | medication | deterministic | medication |
| H007 | heldout_v2:med_symptom | "Nausea comes after every dose, should I eat something first?" | medication (medication, nutrition) | debatable | medication | deterministic | medication,nutrition |
| H008 | heldout_v2:med_symptom | "Queasy in the mornings after my medicine, what can I do?" | medication (medication) | clear | medication | deterministic | medication |
| H009 | heldout_v2:nonmed_symptom | "The skin along my incision line is very itchy" | wound_care (wound_care) | clear | medication **x** | deterministic | wound_care |
| H010 | heldout_v2:nonmed_symptom | "Itching near the stitches at night, does that mean it is healing?" | wound_care (wound_care) | clear | medication **x** | deterministic | wound_care |
| H011 | heldout_v2:nonmed_symptom | "Feeling bloated and gassy after eating rice, what should I avoid?" | nutrition (nutrition) | clear | medication **x** | deterministic | medication,nutrition |
| H012 | heldout_v2:nonmed_symptom | "Bloated after meals, which foods are lighter on the stomach?" | nutrition (nutrition) | clear | medication **x** | deterministic | medication,nutrition |
| H013 | heldout_v2:nonmed_symptom | "I get dizzy when I stand up after physio" | pain_symptoms (pain_symptoms, rehabilitation, daily_activity) | debatable | medication **x** | deterministic | medication,rehabilitation,daily_activity |
| H014 | heldout_v2:nonmed_symptom | "Feeling light-headed when I get out of bed in the morning" | pain_symptoms (pain_symptoms, daily_activity) | debatable | medication **x** | deterministic | medication,daily_activity |
| H015 | heldout_v2:nonmed_symptom | "Constipated since the operation, which foods will help?" | nutrition (nutrition) | clear | medication **x** | deterministic | medication,nutrition |
| H016 | heldout_v2:nonmed_symptom | "I feel nauseous when I smell cooking these days, what can I eat?" | nutrition (nutrition, pain_symptoms) | debatable | medication **x** | deterministic | medication,nutrition |
| H017 | heldout_v2:nonmed_symptom | "Very fatigued after walking to the gate and back, is that normal at this stage?" | recovery_progress (recovery_progress, rehabilitation, daily_activity) | debatable | medication **x** | deterministic | medication **x** |
| H018 | heldout_v2:rehab | "My physio wants a 90 degree bend by next week, how do I get there?" | rehabilitation (rehabilitation) | clear | rehabilitation | deterministic | rehabilitation |
| H019 | heldout_v2:rehab | "Should I do the quad exercises before or after icing?" | rehabilitation (rehabilitation) | clear | rehabilitation | deterministic | rehabilitation |
| H020 | heldout_v2:rehab | "How many times a day should I practise straightening the leg?" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic | rehabilitation |
| H021 | heldout_v2:rehab | "Can I start pedalling on the home exercise bike?" | rehabilitation (rehabilitation, daily_activity) | debatable | rehabilitation | deterministic | rehabilitation |
| H022 | heldout_v2:rehab | "The knee will not fully bend yet, what can I practise at home?" | rehabilitation (rehabilitation) | clear | rehabilitation | deterministic | rehabilitation |
| H023 | heldout_v2:daily | "Can I sit cross-legged on the floor for puja?" | daily_activity (daily_activity) | clear | daily_activity | deterministic | daily_activity |
| H024 | heldout_v2:daily | "When is it ok to travel by train for a family wedding?" | daily_activity (daily_activity, recovery_progress) | debatable | daily_activity | semantic | daily_activity |
| H025 | heldout_v2:daily | "Is a slow evening stroll in the colony park fine for me?" | daily_activity (daily_activity, rehabilitation) | debatable | daily_activity | semantic | daily_activity |
| H026 | heldout_v2:daily | "Is it fine to use an Indian-style toilet yet?" | daily_activity (daily_activity) | clear | daily_activity | deterministic | daily_activity |
| H027 | heldout_v2:recovery | "Is it normal to still need the stick at three weeks?" | recovery_progress (recovery_progress) | clear | recovery_progress | deterministic | recovery_progress |
| H028 | heldout_v2:recovery | "How far along should I be by the end of the first month?" | recovery_progress (recovery_progress) | clear | recovery_progress | semantic | recovery_progress |
| H029 | heldout_v2:recovery | "My neighbour was walking freely by now, am I slow?" | recovery_progress (recovery_progress) | clear | recovery_progress | semantic | recovery_progress |
| H030 | heldout_v2:recovery | "What should I be able to do by my six week check-up?" | recovery_progress (recovery_progress) | clear | recovery_progress | fallback_low_confidence | recovery_progress |
