# Routing benchmark -- `semantic_first`

- commit `b6c1730`, 2026-10-08; 232 cases; semantic_first=True; thresholds {'SEMANTIC_MIN_SCORE': 0.35, 'SEMANTIC_MIN_MARGIN': 0.04}
- classifier run 31.4s, orchestrator run 7.7s
- a prediction is correct when it is in the case's acceptable set; *clear only* excludes debatable cases; *openings* excludes the six answers-to-a-pending-question, which carry no routable signal on their own
- orchestrator *lenient*: at least one dispatched agent is acceptable (the eval/agents definition); *strict*: every dispatched agent is acceptable

## Per agent

| Agent | n | Classifier | Classifier, clear only | Classifier, openings | Orchestrator (lenient) | Orchestrator (strict) | Orchestrator, openings |
|---|---|---|---|---|---|---|---|
| Pain & Symptoms | 36 | 29/36 (81%) | 20/25 (80%) | 29/31 (94%) | 29/36 (81%) | 27/36 (75%) | 29/31 (94%) |
| Recovery Progress | 31 | 26/31 (84%) | 16/19 (84%) | 26/31 (84%) | 28/31 (90%) | 25/31 (81%) | 28/31 (90%) |
| Rehabilitation | 28 | 25/28 (89%) | 19/21 (90%) | 25/27 (93%) | 26/28 (93%) | 24/28 (86%) | 26/27 (96%) |
| Wound Care | 26 | 24/26 (92%) | 20/22 (91%) | 24/26 (92%) | 26/26 (100%) | 22/26 (85%) | 26/26 (100%) |
| Medication | 27 | 26/27 (96%) | 23/23 (100%) | 26/27 (96%) | 27/27 (100%) | 24/27 (89%) | 27/27 (100%) |
| Daily Activity | 25 | 21/25 (84%) | 15/19 (79%) | 21/25 (84%) | 21/25 (84%) | 21/25 (84%) | 21/25 (84%) |
| Nutrition | 24 | 20/24 (83%) | 17/19 (89%) | 20/24 (83%) | 21/24 (88%) | 15/24 (62%) | 21/24 (88%) |
| Mental Wellbeing | 25 | 19/25 (76%) | 14/20 (70%) | 19/25 (76%) | 21/25 (84%) | 16/25 (64%) | 21/25 (84%) |
| Intake / Context | 8 | 8/8 (100%) | 8/8 (100%) | 8/8 (100%) | 8/8 (100%) | 8/8 (100%) | 8/8 (100%) |
| **All** | 230 | **198/230 (86%)** | 152/176 (86%) | 198/224 (88%) | **207/230 (90%)** | 182/230 (79%) | 207/224 (92%) |

Orchestrator pre-emption cases (emergency / out_of_scope expected): 2/2 (100%); multi-agent turns: 45; pre-empted: {'red_triage': 1, 'scope_validator': 2}.

Decision paths: `semantic_first` 176, `semfirst_low_confidence` 27, `semfirst_tiebreak_deterministic` 5, `semfirst_tiebreak_keywords` 16, `semfirst_tiebreak_top1` 8

## Classifier misses, grouped by rule

### keyword order (1)

| Case | Message | Expected (acceptable) | Got | Path | Rule |
|---|---|---|---|---|---|
| R215 | "Feeling lonely sitting at home whole day" | mental_wellbeing (mental_wellbeing) | daily_activity | semfirst_low_confidence | keyword order: daily_activity (sitting) is checked before mental_wellbeing (lonely) |

### semantic prototype pull (18)

| Case | Message | Expected (acceptable) | Got | Path | Rule |
|---|---|---|---|---|---|
| R036 | "Should I be worried about how slow this is going?" *debatable* | recovery_progress (recovery_progress, mental_wellbeing) | daily_activity | semantic_first | semantic prototype pull: daily_activity 0.47 via 'Is it safe for me to drive yet?', margin 0.15 |
| R037 | "My leg feels weird when I try to move it during exercises." *debatable* | pain_symptoms (pain_symptoms, rehabilitation) | mental_wellbeing | semantic_first | semantic prototype pull: mental_wellbeing 0.68 via 'I feel anxious about moving my operated leg.', margin 0.12 |
| R043 | "Since I didn't take my medicine yesterday, my knee wound is worse" *debatable* | medication (medication, wound_care) | pain_symptoms | semantic_first | semantic prototype pull: pain_symptoms 0.60 via 'My joint seems more inflamed than yesterday and it is painful.', margin 0.05 |
| R052 | "getting a bit better" *answer* | pain_symptoms (pain_symptoms) | recovery_progress | semfirst_tiebreak_top1 | semantic prototype pull: recovery_progress 0.37 via 'How is my healing progressing so far?', margin 0.03 |
| R058 | "Am I on track with my knee?" | recovery_progress (recovery_progress) | pain_symptoms | semfirst_tiebreak_top1 | semantic prototype pull: pain_symptoms 0.48 via 'My joint seems more inflamed than yesterday and it is painful.', margin 0.01 |
| R061 | "fluid coming from my incision" | wound_care (wound_care) | pain_symptoms | semantic_first | semantic prototype pull: pain_symptoms 0.58 via 'There is tingling and throbbing pain near the incision.', margin 0.04 |
| R062 | "I'm walking with a walker now" *debatable* | recovery_progress (recovery_progress, rehabilitation) | daily_activity | semantic_first | semantic prototype pull: daily_activity 0.49 via 'When am I allowed to go up steps and get behind the wheel?', margin 0.06 |
| R100 | "When will the knee feel like normal again?" | recovery_progress (recovery_progress) | pain_symptoms | semantic_first | semantic prototype pull: pain_symptoms 0.51 via 'My joint seems more inflamed than yesterday and it is painful.', margin 0.07 |
| R103 | "Can you tell me if I am behind or ahead for my post op day?" | recovery_progress (recovery_progress) | daily_activity | semantic_first | semantic prototype pull: daily_activity 0.38 via 'When am I allowed to go up steps and get behind the wheel?', margin 0.08 |
| R114 | "Can I put full weight on my operated leg while doing exercises?" | rehabilitation (rehabilitation) | mental_wellbeing | semantic_first | semantic prototype pull: mental_wellbeing 0.55 via 'I feel scared to put weight on my leg.', margin 0.04 |
| R131 | "My incision is itching alot, is it normal?" | wound_care (wound_care) | pain_symptoms | semantic_first | semantic prototype pull: pain_symptoms 0.58 via 'There is tingling and throbbing pain near the incision.', margin 0.04 |
| R184 | "Is it ok to wear slippers or should I use proper shoes?" | daily_activity (daily_activity) | rehabilitation | semantic_first | semantic prototype pull: rehabilitation 0.45 via 'How many heel slides should I perform daily?', margin 0.18 |
| R192 | "My appetite is very less since surgery, is it normal?" *debatable* | nutrition (nutrition, recovery_progress) | mental_wellbeing | semantic_first | semantic prototype pull: mental_wellbeing 0.57 via 'My mood has been low since the surgery.', margin 0.06 |
| R196 | "Can I take tea and coffee normally?" | nutrition (nutrition) | daily_activity | semfirst_tiebreak_top1 | semantic prototype pull: daily_activity 0.42 via 'Can I take a bath or shower now?', margin 0.04 |
| R200 | "Can I have beer once in a while now?" *debatable* | nutrition (nutrition, medication) | daily_activity | semfirst_tiebreak_top1 | semantic prototype pull: daily_activity 0.35 via 'Can I take a bath or shower now?', margin 0.02 |
| R214 | "I keep thinking something will go wrong with the implant" | mental_wellbeing (mental_wellbeing) | pain_symptoms | semantic_first | semantic prototype pull: pain_symptoms 0.42 via 'There is tingling and throbbing pain near the incision.', margin 0.13 |
| R217 | "Sometimes I feel hopeless about getting back to normal" | mental_wellbeing (mental_wellbeing) | recovery_progress | semantic_first | semantic prototype pull: recovery_progress 0.56 via 'Am I recovering normally?', margin 0.07 |
| R222 | "Can't stop worrying that the surgery has failed" | mental_wellbeing (mental_wellbeing) | recovery_progress | semantic_first | semantic prototype pull: recovery_progress 0.51 via 'Is my recovery on track for this stage after surgery?', margin 0.05 |

### semantic threshold (13)

| Case | Message | Expected (acceptable) | Got | Path | Rule |
|---|---|---|---|---|---|
| R050 | "no, nothing sharp" *answer* | rehabilitation (rehabilitation) | recovery_progress | semfirst_low_confidence | semantic threshold (semfirst_low_confidence) -> no keyword -> default recovery_progress |
| R051 | "It's about a 5 out of 10, it came on gradually, and it's behind the knee." | pain_symptoms (pain_symptoms) | recovery_progress | semfirst_low_confidence | semantic threshold (semfirst_low_confidence) -> no keyword -> default recovery_progress |
| R054 | "3" *answer* | pain_symptoms (pain_symptoms) | recovery_progress | semfirst_low_confidence | semantic threshold (semfirst_low_confidence) -> no keyword -> default recovery_progress |
| R055 | "gradually" *answer* | pain_symptoms (pain_symptoms) | recovery_progress | semfirst_low_confidence | semantic threshold (semfirst_low_confidence) -> no keyword -> default recovery_progress |
| R056 | "around the kneecap" *answer* | pain_symptoms (pain_symptoms) | recovery_progress | semfirst_low_confidence | semantic threshold (semfirst_low_confidence) -> no keyword -> default recovery_progress |
| R057 | "yes it helped" *answer* *debatable* | pain_symptoms (pain_symptoms, medication) | recovery_progress | semfirst_low_confidence | semantic threshold (semfirst_low_confidence) -> no keyword -> default recovery_progress |
| R108 | "Can I start cycling on static cycle now?" *debatable* | rehabilitation (rehabilitation, daily_activity) | recovery_progress | semfirst_low_confidence | semantic threshold (semfirst_low_confidence) -> no keyword -> default recovery_progress |
| R173 | "Can I do light kitchen work like making chapati?" | daily_activity (daily_activity) | recovery_progress | semfirst_low_confidence | semantic threshold (semfirst_low_confidence) -> no keyword -> default recovery_progress |
| R178 | "Can I do sweeping and mopping of the house?" | daily_activity (daily_activity) | recovery_progress | semfirst_low_confidence | semantic threshold (semfirst_low_confidence) -> no keyword -> default recovery_progress |
| R183 | "Can I kneel down for prayer?" | daily_activity (daily_activity) | recovery_progress | semfirst_low_confidence | semantic threshold (semfirst_low_confidence) -> no keyword -> default recovery_progress |
| R203 | "Dal, roti, sabzi daily is fine or need to change?" | nutrition (nutrition) | recovery_progress | semfirst_low_confidence | semantic threshold (semfirst_low_confidence) -> no keyword -> default recovery_progress |
| R216 | "I am anxiuos about my follow up visit tomorrow" | mental_wellbeing (mental_wellbeing) | recovery_progress | semfirst_low_confidence | semantic threshold (semfirst_low_confidence) -> no keyword -> default recovery_progress |
| R223 | "I am not feeling like talking to anyone" | mental_wellbeing (mental_wellbeing) | recovery_progress | semfirst_low_confidence | semantic threshold (semfirst_low_confidence) -> no keyword -> default recovery_progress |

## Orchestrator misses (lenient)

| Case | Message | Expected (acceptable) | Orchestrator intent | Target agent | Classifier said |
|---|---|---|---|---|---|
| R050 | "no, nothing sharp" | rehabilitation (rehabilitation) | recovery_progress | RecoveryProgressAgent | recovery_progress (semfirst_low_confidence) |
| R051 | "It's about a 5 out of 10, it came on gradually, and it's behind the knee." | pain_symptoms (pain_symptoms) | recovery_progress | RecoveryProgressAgent | recovery_progress (semfirst_low_confidence) |
| R052 | "getting a bit better" | pain_symptoms (pain_symptoms) | recovery_progress | RecoveryProgressAgent | recovery_progress (semfirst_tiebreak_top1) |
| R054 | "3" | pain_symptoms (pain_symptoms) | recovery_progress | RecoveryProgressAgent | recovery_progress (semfirst_low_confidence) |
| R055 | "gradually" | pain_symptoms (pain_symptoms) | recovery_progress | RecoveryProgressAgent | recovery_progress (semfirst_low_confidence) |
| R056 | "around the kneecap" | pain_symptoms (pain_symptoms) | recovery_progress | RecoveryProgressAgent | recovery_progress (semfirst_low_confidence) |
| R057 | "yes it helped" | pain_symptoms (pain_symptoms, medication) | recovery_progress | RecoveryProgressAgent | recovery_progress (semfirst_low_confidence) |
| R058 | "Am I on track with my knee?" | recovery_progress (recovery_progress) | pain_symptoms | PainSymptomsAgent | pain_symptoms (semfirst_tiebreak_top1) |
| R064 | "On the other hand my knee feels better" | pain_symptoms (pain_symptoms, recovery_progress) | out_of_scope | DeflectionAgent | pain_symptoms (semantic_first) |
| R100 | "When will the knee feel like normal again?" | recovery_progress (recovery_progress) | pain_symptoms | PainSymptomsAgent | pain_symptoms (semantic_first) |
| R103 | "Can you tell me if I am behind or ahead for my post op day?" | recovery_progress (recovery_progress) | daily_activity | DailyActivityAgent | daily_activity (semantic_first) |
| R108 | "Can I start cycling on static cycle now?" | rehabilitation (rehabilitation, daily_activity) | recovery_progress | RecoveryProgressAgent | recovery_progress (semfirst_low_confidence) |
| R173 | "Can I do light kitchen work like making chapati?" | daily_activity (daily_activity) | recovery_progress | RecoveryProgressAgent | recovery_progress (semfirst_low_confidence) |
| R178 | "Can I do sweeping and mopping of the house?" | daily_activity (daily_activity) | recovery_progress | RecoveryProgressAgent | recovery_progress (semfirst_low_confidence) |
| R183 | "Can I kneel down for prayer?" | daily_activity (daily_activity) | recovery_progress | RecoveryProgressAgent | recovery_progress (semfirst_low_confidence) |
| R184 | "Is it ok to wear slippers or should I use proper shoes?" | daily_activity (daily_activity) | rehabilitation | RehabilitationAgent | rehabilitation (semantic_first) |
| R196 | "Can I take tea and coffee normally?" | nutrition (nutrition) | daily_activity | DailyActivityAgent | daily_activity (semfirst_tiebreak_top1) |
| R200 | "Can I have beer once in a while now?" | nutrition (nutrition, medication) | daily_activity | DailyActivityAgent | daily_activity (semfirst_tiebreak_top1) |
| R203 | "Dal, roti, sabzi daily is fine or need to change?" | nutrition (nutrition) | recovery_progress | RecoveryProgressAgent | recovery_progress (semfirst_low_confidence) |
| R214 | "I keep thinking something will go wrong with the implant" | mental_wellbeing (mental_wellbeing) | pain_symptoms | PainSymptomsAgent | pain_symptoms (semantic_first) |
| R216 | "I am anxiuos about my follow up visit tomorrow" | mental_wellbeing (mental_wellbeing) | recovery_progress | RecoveryProgressAgent | recovery_progress (semfirst_low_confidence) |
| R222 | "Can't stop worrying that the surgery has failed" | mental_wellbeing (mental_wellbeing) | recovery_progress | RecoveryProgressAgent | recovery_progress (semantic_first) |
| R223 | "I am not feeling like talking to anyone" | mental_wellbeing (mental_wellbeing) | recovery_progress | RecoveryProgressAgent | recovery_progress (semfirst_low_confidence) |

## Orchestrator differs from the classifier

| Case | Message | Classifier | Orchestrator | Why |
|---|---|---|---|---|
| R016 | "Can you tell me how to improve my range of motion?" | rehabilitation | rehabilitation,recovery_progress | multi-agent: detect_applicable_intents |
| R023 | "My scar looks a bit red around the edges, should I worry?" | wound_care | wound_care,mental_wellbeing | multi-agent: detect_applicable_intents |
| R029 | "Is alcohol okay to have during my recovery period?" | nutrition | nutrition,recovery_progress | multi-agent: detect_applicable_intents |
| R030 | "I keep feeling down and unmotivated during this recovery." | mental_wellbeing | mental_wellbeing,recovery_progress | multi-agent: detect_applicable_intents |
| R035 | "I'm not sure if this is a side effect or just soreness." | medication | medication,pain_symptoms | multi-agent: detect_applicable_intents |
| R036 | "Should I be worried about how slow this is going?" | daily_activity | daily_activity,mental_wellbeing | multi-agent: detect_applicable_intents |
| R037 | "My leg feels weird when I try to move it during exercises." | mental_wellbeing | rehabilitation,mental_wellbeing | multi-agent: detect_applicable_intents |
| R038 | "Is it normal that I still can't manage the stairs at this point in my recovery?" | daily_activity | daily_activity,recovery_progress | multi-agent: detect_applicable_intents |
| R040 | "My leg hurts a lot after doing my exercises today." | pain_symptoms | pain_symptoms,rehabilitation | multi-agent: detect_applicable_intents |
| R041 | "Since starting the new tablets my pain has gotten worse." | pain_symptoms | medication,pain_symptoms | multi-agent: detect_applicable_intents |
| R043 | "Since I didn't take my medicine yesterday, my knee wound is worse" | pain_symptoms | medication,wound_care,pain_symptoms | multi-agent: detect_applicable_intents |
| R044 | "I am anxious, my knee hurts, and I need help with exercises" | pain_symptoms | pain_symptoms,rehabilitation,mental_wellbeing | multi-agent: detect_applicable_intents |
| R045 | "I can't breathe and my knee wound is worse" | wound_care | emergency | red_triage |
| R046 | "What is the weather like today?" | recovery_progress | out_of_scope | scope_validator |
| R061 | "fluid coming from my incision" | pain_symptoms | wound_care,pain_symptoms | multi-agent: detect_applicable_intents |
| R062 | "I'm walking with a walker now" | daily_activity | rehabilitation,daily_activity | multi-agent: detect_applicable_intents |
| R064 | "On the other hand my knee feels better" | pain_symptoms | out_of_scope | scope_validator |
| R073 | "My leg is throbing badly at night and sleep is not coming" | pain_symptoms | pain_symptoms,daily_activity | multi-agent: detect_applicable_intents |
| R074 | "Hip is hurting more when I try to turn in bed" | pain_symptoms | pain_symptoms,daily_activity | multi-agent: detect_applicable_intents |
| R076 | "Knee got swolen after walking little bit, should I worry?" | pain_symptoms | pain_symptoms,mental_wellbeing | multi-agent: detect_applicable_intents |
| R079 | "Pain is 8 out of 10 and the tablet is not helping" | medication | medication,pain_symptoms | multi-agent: detect_applicable_intents |
| R083 | "Pain increased after physio session yesterday, is it ok?" | pain_symptoms | pain_symptoms,rehabilitation | multi-agent: detect_applicable_intents |
| R086 | "How many days it will take to walk normally without walker?" | recovery_progress | rehabilitation,recovery_progress | multi-agent: detect_applicable_intents |
| R089 | "I can bend my knee to 90 degrees now, is that good for 2 weeks?" | rehabilitation | rehabilitation,recovery_progress | multi-agent: detect_applicable_intents |
| R098 | "My knee extension is still 10 degrees short, is my progress ok?" | rehabilitation | rehabilitation,recovery_progress | multi-agent: detect_applicable_intents |
| R099 | "I want to know where I stand in my recovery timeline" | recovery_progress | daily_activity,recovery_progress | multi-agent: detect_applicable_intents |
| R112 | "Should I use walker or can I shift to stick now?" | recovery_progress | rehabilitation,recovery_progress | multi-agent: detect_applicable_intents |
| R114 | "Can I put full weight on my operated leg while doing exercises?" | mental_wellbeing | rehabilitation,mental_wellbeing | multi-agent: detect_applicable_intents |
| R117 | "Is climbing stairs a good exercise for strengthening the knee?" | rehabilitation | rehabilitation,daily_activity | multi-agent: detect_applicable_intents |
| R129 | "The dressing got wet in the bathroom, what should I do?" | wound_care | wound_care,daily_activity | multi-agent: detect_applicable_intents |
| R131 | "My incision is itching alot, is it normal?" | pain_symptoms | wound_care | recorded medication / context |
| R137 | "Is it ok if water touches the incision while bathing?" | wound_care | wound_care,daily_activity,nutrition | multi-agent: detect_applicable_intents |
| R152 | "Can I take the pain killer on empty stomach?" | medication | medication,pain_symptoms | multi-agent: detect_applicable_intents |
| R161 | "What is the timing for the antibiotic, before food or after food?" | medication | medication,nutrition | multi-agent: detect_applicable_intents |
| R162 | "Can I drink alcohol while on these tablets?" | medication | medication,nutrition | multi-agent: detect_applicable_intents |
| R171 | "How do I get into the car without hurting the hip?" | daily_activity | pain_symptoms,daily_activity | multi-agent: detect_applicable_intents |
| R181 | "How to climb up and down stairs with crutches?" | daily_activity | rehabilitation,daily_activity | multi-agent: detect_applicable_intents |
| R185 | "What food I should eat for faster healing of the bone?" | nutrition | nutrition,recovery_progress | multi-agent: detect_applicable_intents |
| R190 | "Is drinking coconut water good for recovery?" | nutrition | nutrition,recovery_progress | multi-agent: detect_applicable_intents |
| R191 | "Should I take calcium and vitamin D tablets?" | nutrition | medication,nutrition | multi-agent: detect_applicable_intents |
| R192 | "My appetite is very less since surgery, is it normal?" | mental_wellbeing | nutrition,mental_wellbeing | multi-agent: detect_applicable_intents |
| R197 | "Is spicy food bad for the wound healing?" | wound_care | wound_care,nutrition,recovery_progress | multi-agent: detect_applicable_intents |
| R198 | "What fruits are good during recovery?" | nutrition | nutrition,recovery_progress | multi-agent: detect_applicable_intents |
| R207 | "I feel scared to put weight on my leg even though physio said ok" | mental_wellbeing | rehabilitation,mental_wellbeing | multi-agent: detect_applicable_intents |
| R208 | "Not able to sleep because of worry about the recovery" | mental_wellbeing | daily_activity,mental_wellbeing,recovery_progress | multi-agent: detect_applicable_intents |
| R215 | "Feeling lonely sitting at home whole day" | daily_activity | daily_activity,mental_wellbeing | multi-agent: detect_applicable_intents |
| R217 | "Sometimes I feel hopeless about getting back to normal" | recovery_progress | mental_wellbeing,recovery_progress | multi-agent: detect_applicable_intents |
| R218 | "How to deal with the stress of this long recovery?" | mental_wellbeing | mental_wellbeing,recovery_progress | multi-agent: detect_applicable_intents |
| R221 | "I feel overwhelmed with all the instructions and exercises" | rehabilitation | rehabilitation,mental_wellbeing | multi-agent: detect_applicable_intents |

## Every case

| Case | Source | Message | Expected (acceptable) | Conf. | Classifier | Path | Orchestrator |
|---|---|---|---|---|---|---|---|
| R001 | phase2:benchmark | "When should I expect to walk normally again?" | recovery_progress (recovery_progress) | clear | recovery_progress | semantic_first | recovery_progress |
| R002 | phase2:benchmark | "My knee is more swollen today and hurts." | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semantic_first | pain_symptoms |
| R003 | phase2:benchmark | "How many heel slides should I do?" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation |
| R004 | phase2:benchmark | "I forgot my evening pain tablet." | medication (medication) | clear | medication | semantic_first | medication |
| R005 | phase2:benchmark | "Can I change my incision dressing today?" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R006 | phase2:benchmark | "When can I climb stairs and drive again?" | daily_activity (daily_activity) | clear | daily_activity | semantic_first | daily_activity |
| R007 | phase2:benchmark | "What foods and protein should I eat while recovering?" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition |
| R008 | phase2:benchmark | "I am anxious about moving my operated leg." | mental_wellbeing (mental_wellbeing) | clear | mental_wellbeing | semantic_first | mental_wellbeing |
| R009 | phase2:unseen | "How long does it typically take to fully recover from this kind of operation?" | recovery_progress (recovery_progress) | clear | recovery_progress | semantic_first | recovery_progress |
| R010 | phase2:unseen | "Am I healing at the pace the surgeon expected?" | recovery_progress (recovery_progress) | clear | recovery_progress | semantic_first | recovery_progress |
| R011 | phase2:unseen | "What can I expect in terms of getting back to my usual life?" | recovery_progress (recovery_progress) | clear | recovery_progress | semantic_first | recovery_progress |
| R012 | phase2:unseen | "The area around my joint feels really tender and inflamed." | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semantic_first | pain_symptoms |
| R013 | phase2:unseen | "I've got a burning sensation and some numbness in my foot." | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semantic_first | pain_symptoms |
| R014 | phase2:unseen | "Why does my leg feel so stiff and achy this morning?" | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semantic_first | pain_symptoms |
| R015 | phase2:unseen | "What kind of stretching routine should I follow for physio?" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation |
| R016 | phase2:unseen | "Can you tell me how to improve my range of motion?" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation,recovery_progress |
| R017 | phase2:unseen | "Should I be doing strengthening drills for my leg yet?" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation |
| R018 | phase2:unseen | "Is it fine to skip a dose of my blood thinner occasionally?" | medication (medication) | clear | medication | semantic_first | medication |
| R019 | phase2:unseen | "What happens if I take my antibiotic later than scheduled?" | medication (medication) | clear | medication | semantic_first | medication |
| R020 | phase2:unseen | "Can you tell me the right dosage for my prescribed painkiller?" | medication (medication) | clear | medication | semantic_first | medication |
| R021 | phase2:unseen | "There's some fluid coming from my surgical cut, is that normal?" | wound_care (wound_care) | clear | wound_care | semfirst_tiebreak_top1 | wound_care |
| R022 | phase2:unseen | "How often should I clean the area where the stitches are?" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R023 | phase2:unseen | "My scar looks a bit red around the edges, should I worry?" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care,mental_wellbeing |
| R024 | phase2:unseen | "Is it alright to take a shower on my own yet?" | daily_activity (daily_activity) | clear | daily_activity | semantic_first | daily_activity |
| R025 | phase2:unseen | "What's the safest way to get in and out of bed?" | daily_activity (daily_activity) | clear | daily_activity | semantic_first | daily_activity |
| R026 | phase2:unseen | "Can I sit in a regular chair or do I need something special?" | daily_activity (daily_activity) | clear | daily_activity | semantic_first | daily_activity |
| R027 | phase2:unseen | "Should I be taking any vitamins to help my body heal?" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition |
| R028 | phase2:unseen | "How much water should I drink each day while recovering?" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition |
| R029 | phase2:unseen | "Is alcohol okay to have during my recovery period?" | nutrition (nutrition) | clear | nutrition | semfirst_tiebreak_deterministic | nutrition,recovery_progress |
| R030 | phase2:unseen | "I keep feeling down and unmotivated during this recovery." | mental_wellbeing (mental_wellbeing) | clear | mental_wellbeing | semantic_first | mental_wellbeing,recovery_progress |
| R031 | phase2:unseen | "I'm scared to put any weight on my leg, is that normal to feel?" | mental_wellbeing (mental_wellbeing) | clear | mental_wellbeing | semantic_first | mental_wellbeing |
| R032 | phase2:unseen | "I feel isolated and low because I can't do my usual routine." | mental_wellbeing (mental_wellbeing) | clear | mental_wellbeing | semfirst_tiebreak_top1 | mental_wellbeing |
| R033 | phase2:ambiguous | "I don't feel like doing anything today and my leg feels stiff." | pain_symptoms (pain_symptoms, mental_wellbeing) | debatable | pain_symptoms | semantic_first | pain_symptoms |
| R034 | phase2:ambiguous | "Is it normal to feel this way after the procedure?" | recovery_progress (recovery_progress, mental_wellbeing) | debatable | mental_wellbeing | semfirst_tiebreak_top1 | mental_wellbeing |
| R035 | phase2:ambiguous | "I'm not sure if this is a side effect or just soreness." | medication (medication, pain_symptoms) | debatable | medication | semfirst_tiebreak_keywords | medication,pain_symptoms |
| R036 | phase2:ambiguous | "Should I be worried about how slow this is going?" | recovery_progress (recovery_progress, mental_wellbeing) | debatable | daily_activity **x** | semantic_first | daily_activity,mental_wellbeing |
| R037 | phase2:ambiguous | "My leg feels weird when I try to move it during exercises." | pain_symptoms (pain_symptoms, rehabilitation) | debatable | mental_wellbeing **x** | semantic_first | rehabilitation,mental_wellbeing |
| R038 | phase2:boundary | "Is it normal that I still can't manage the stairs at this point in my recovery?" | recovery_progress (recovery_progress, daily_activity) | debatable | daily_activity | semantic_first | daily_activity,recovery_progress |
| R039 | phase2:boundary | "There's soreness and some fluid leaking near my stitches." | wound_care (wound_care, pain_symptoms) | debatable | wound_care | semantic_first | wound_care |
| R040 | phase2:boundary | "My leg hurts a lot after doing my exercises today." | pain_symptoms (pain_symptoms, rehabilitation) | debatable | pain_symptoms | semantic_first | pain_symptoms,rehabilitation |
| R041 | phase2:boundary | "Since starting the new tablets my pain has gotten worse." | medication (medication, pain_symptoms) | debatable | pain_symptoms | semantic_first | medication,pain_symptoms |
| R042 | phase2:boundary | "I'm discouraged because my recovery doesn't feel like it's improving." | mental_wellbeing (mental_wellbeing, recovery_progress) | debatable | recovery_progress | semfirst_tiebreak_keywords | recovery_progress |
| R043 | orchestration | "Since I didn't take my medicine yesterday, my knee wound is worse" | medication (medication, wound_care) | debatable | pain_symptoms **x** | semantic_first | medication,wound_care,pain_symptoms |
| R044 | orchestration | "I am anxious, my knee hurts, and I need help with exercises" | pain_symptoms (pain_symptoms, rehabilitation, mental_wellbeing) | debatable | pain_symptoms | semfirst_tiebreak_deterministic | pain_symptoms,rehabilitation,mental_wellbeing |
| R045 | orchestration | "I can't breathe and my knee wound is worse" | wound_care (wound_care) | clear | wound_care | semfirst_tiebreak_keywords | emergency |
| R046 | orchestration | "What is the weather like today?" | recovery_progress (recovery_progress, pain_symptoms, rehabilitation, medication, wound_care, daily_activity, nutrition, mental_wellbeing, intake_context) | debatable | recovery_progress | semfirst_low_confidence | out_of_scope |
| R047 | recovery_test | "I can bend my knee to around 80 degrees." | rehabilitation (rehabilitation, recovery_progress) | debatable | rehabilitation | semfirst_tiebreak_keywords | rehabilitation |
| R048 | recovery_test | "How is my recovery progressing compared to a normal timeline?" | recovery_progress (recovery_progress) | clear | recovery_progress | semantic_first | recovery_progress |
| R049 | report | "Can I go up and down the stairs yet?" | rehabilitation (rehabilitation, daily_activity) | debatable | daily_activity | semantic_first | daily_activity |
| R050 | report | "no, nothing sharp" | rehabilitation (rehabilitation) | clear/answer | recovery_progress **x** | semfirst_low_confidence | recovery_progress **x** |
| R051 | report | "It's about a 5 out of 10, it came on gradually, and it's behind the knee." | pain_symptoms (pain_symptoms) | clear | recovery_progress **x** | semfirst_low_confidence | recovery_progress **x** |
| R052 | report | "getting a bit better" | pain_symptoms (pain_symptoms) | clear/answer | recovery_progress **x** | semfirst_tiebreak_top1 | recovery_progress **x** |
| R053 | report | "My knee aches a little, I took paracetamol an hour ago." | pain_symptoms (pain_symptoms, medication) | debatable | medication | semantic_first | medication |
| R054 | report | "3" | pain_symptoms (pain_symptoms) | clear/answer | recovery_progress **x** | semfirst_low_confidence | recovery_progress **x** |
| R055 | report | "gradually" | pain_symptoms (pain_symptoms) | clear/answer | recovery_progress **x** | semfirst_low_confidence | recovery_progress **x** |
| R056 | report | "around the kneecap" | pain_symptoms (pain_symptoms) | clear/answer | recovery_progress **x** | semfirst_low_confidence | recovery_progress **x** |
| R057 | report | "yes it helped" | pain_symptoms (pain_symptoms, medication) | debatable/answer | recovery_progress **x** | semfirst_low_confidence | recovery_progress **x** |
| R058 | report | "Am I on track with my knee?" | recovery_progress (recovery_progress) | clear | pain_symptoms **x** | semfirst_tiebreak_top1 | pain_symptoms **x** |
| R059 | audit | "Is it safe to climb stairs?" | daily_activity (daily_activity, rehabilitation) | debatable | daily_activity | semantic_first | daily_activity |
| R060 | audit | "What is the schedule for my exercises?" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation |
| R061 | audit | "fluid coming from my incision" | wound_care (wound_care) | clear | pain_symptoms **x** | semantic_first | wound_care,pain_symptoms |
| R062 | audit | "I'm walking with a walker now" | recovery_progress (recovery_progress, rehabilitation) | debatable | daily_activity **x** | semantic_first | rehabilitation,daily_activity |
| R063 | audit | "I am feeling okay today" | recovery_progress (recovery_progress, mental_wellbeing) | debatable | recovery_progress | semantic_first | recovery_progress |
| R064 | audit | "On the other hand my knee feels better" | pain_symptoms (pain_symptoms, recovery_progress) | debatable | pain_symptoms | semantic_first | out_of_scope **x** |
| R065 | new:pain | "My knee is paining alot since morning, what to do?" | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semantic_first | pain_symptoms |
| R066 | new:pain | "There is swelling near the operated leg and it feels tight" | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semfirst_tiebreak_keywords | pain_symptoms |
| R067 | new:pain | "The pain is not reducing even after 3 days, is this normal?" | pain_symptoms (pain_symptoms, recovery_progress) | clear | pain_symptoms | semantic_first | pain_symptoms |
| R068 | new:pain | "Calf muscle is paining when I walk" | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semantic_first | pain_symptoms |
| R069 | new:pain | "Knee feels very stiff in the morning time" | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semantic_first | pain_symptoms |
| R070 | new:pain | "Thigh is numb from yesterday night, like no sensation" | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semantic_first | pain_symptoms |
| R071 | new:pain | "Pain level is around 7 today, yesterday it was 4" | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semantic_first | pain_symptoms |
| R072 | new:pain | "Burning type pain behind the knee only" | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semantic_first | pain_symptoms |
| R073 | new:pain | "My leg is throbing badly at night and sleep is not coming" | pain_symptoms (pain_symptoms, daily_activity) | clear | pain_symptoms | semantic_first | pain_symptoms,daily_activity |
| R074 | new:pain | "Hip is hurting more when I try to turn in bed" | pain_symptoms (pain_symptoms, daily_activity) | clear | pain_symptoms | semantic_first | pain_symptoms,daily_activity |
| R075 | new:pain | "Is it normal to have this much pain on day 4?" | pain_symptoms (pain_symptoms, recovery_progress) | debatable | pain_symptoms | semantic_first | pain_symptoms |
| R076 | new:pain | "Knee got swolen after walking little bit, should I worry?" | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semantic_first | pain_symptoms,mental_wellbeing |
| R077 | new:pain | "Sharp pain came suddenly in the knee when I stood up" | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semantic_first | pain_symptoms |
| R078 | new:pain | "The operated area feels warm and tender to touch" | pain_symptoms (pain_symptoms, wound_care) | debatable | pain_symptoms | semantic_first | pain_symptoms |
| R079 | new:pain | "Pain is 8 out of 10 and the tablet is not helping" | pain_symptoms (pain_symptoms, medication) | debatable | medication | semfirst_tiebreak_keywords | medication,pain_symptoms |
| R080 | new:pain | "Having tingling sensation in my toes of the operated leg" | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semantic_first | pain_symptoms |
| R081 | new:pain | "Ankle also got swelling now along with knee" | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semantic_first | pain_symptoms |
| R082 | new:pain | "Dull ache in the groin area whole day" | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semantic_first | pain_symptoms |
| R083 | new:pain | "Pain increased after physio session yesterday, is it ok?" | pain_symptoms (pain_symptoms, rehabilitation) | debatable | pain_symptoms | semantic_first | pain_symptoms,rehabilitation |
| R084 | new:pain | "Leg feels heavy and sore when I keep it down" | pain_symptoms (pain_symptoms) | clear | pain_symptoms | semfirst_tiebreak_keywords | pain_symptoms |
| R085 | new:recovery | "Am I recovering properly for day 10?" | recovery_progress (recovery_progress) | clear | recovery_progress | semantic_first | recovery_progress |
| R086 | new:recovery | "How many days it will take to walk normally without walker?" | recovery_progress (recovery_progress, rehabilitation) | debatable | recovery_progress | semantic_first | rehabilitation,recovery_progress |
| R087 | new:recovery | "Is my recovry going fine or slow?" | recovery_progress (recovery_progress) | clear | recovery_progress | semantic_first | recovery_progress |
| R088 | new:recovery | "When can I go back to office after hip replacement?" | recovery_progress (recovery_progress, daily_activity) | debatable | recovery_progress | semantic_first | recovery_progress |
| R089 | new:recovery | "I can bend my knee to 90 degrees now, is that good for 2 weeks?" | recovery_progress (recovery_progress, rehabilitation) | debatable | rehabilitation | semfirst_tiebreak_deterministic | rehabilitation,recovery_progress |
| R090 | new:recovery | "Compared to last week I am walking better, is this the expected progress?" | recovery_progress (recovery_progress) | clear | recovery_progress | semfirst_tiebreak_keywords | recovery_progress |
| R091 | new:recovery | "What milestones should I reach by one month?" | recovery_progress (recovery_progress) | clear | recovery_progress | semantic_first | recovery_progress |
| R092 | new:recovery | "By when I can sit cross legged on floor?" | recovery_progress (recovery_progress, daily_activity) | debatable | daily_activity | semantic_first | daily_activity |
| R093 | new:recovery | "Recovery check please, I am on day 21 now" | recovery_progress (recovery_progress) | clear | recovery_progress | semfirst_tiebreak_keywords | recovery_progress |
| R094 | new:recovery | "How is my healing compared to other patients of my age?" | recovery_progress (recovery_progress) | clear | recovery_progress | semantic_first | recovery_progress |
| R095 | new:recovery | "Still limping after 6 weeks, is this normal at this stage?" | recovery_progress (recovery_progress, rehabilitation) | debatable | recovery_progress | semantic_first | recovery_progress |
| R096 | new:recovery | "What should I be able to do by now, 3 weeks post op?" | recovery_progress (recovery_progress) | clear | recovery_progress | semfirst_low_confidence | recovery_progress |
| R097 | new:recovery | "Doctor said 6 weeks for full recovery, am I on schedule?" | recovery_progress (recovery_progress) | clear | recovery_progress | semantic_first | recovery_progress |
| R098 | new:recovery | "My knee extension is still 10 degrees short, is my progress ok?" | recovery_progress (recovery_progress, rehabilitation) | debatable | rehabilitation | semantic_first | rehabilitation,recovery_progress |
| R099 | new:recovery | "I want to know where I stand in my recovery timeline" | recovery_progress (recovery_progress) | clear | recovery_progress | semantic_first | daily_activity,recovery_progress |
| R100 | new:recovery | "When will the knee feel like normal again?" | recovery_progress (recovery_progress) | clear | pain_symptoms **x** | semantic_first | pain_symptoms **x** |
| R101 | new:recovery | "Next week I complete one month, what improvement is expected by then?" | recovery_progress (recovery_progress) | clear | recovery_progress | semantic_first | recovery_progress |
| R102 | new:recovery | "Is it fine that I am still using one crutch at day 30?" | recovery_progress (recovery_progress, rehabilitation) | debatable | recovery_progress | semfirst_low_confidence | recovery_progress |
| R103 | new:recovery | "Can you tell me if I am behind or ahead for my post op day?" | recovery_progress (recovery_progress) | clear | daily_activity **x** | semantic_first | daily_activity **x** |
| R104 | new:recovery | "How much more time for complete healing of the hip?" | recovery_progress (recovery_progress) | clear | recovery_progress | semantic_first | recovery_progress |
| R105 | new:rehab | "Which excercises I should do today for my knee?" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation |
| R106 | new:rehab | "How many times a day I have to do heel slides?" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation |
| R107 | new:rehab | "Physio told to do quad sets but I forgot how, can you explain?" | rehabilitation (rehabilitation) | clear | rehabilitation | semfirst_low_confidence | rehabilitation |
| R108 | new:rehab | "Can I start cycling on static cycle now?" | rehabilitation (rehabilitation, daily_activity) | debatable | recovery_progress **x** | semfirst_low_confidence | recovery_progress **x** |
| R109 | new:rehab | "Is it ok to skip physiotheraphy for 2 days, I am very tired" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation |
| R110 | new:rehab | "How to straigten my knee fully, it is not going straight" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation |
| R111 | new:rehab | "My range of motion is stuck at 80 degrees, what excercise will help?" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation |
| R112 | new:rehab | "Should I use walker or can I shift to stick now?" | rehabilitation (rehabilitation, recovery_progress, daily_activity) | debatable | recovery_progress | semantic_first | rehabilitation,recovery_progress |
| R113 | new:rehab | "Ankle pump exercise is boring, any alternative?" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation |
| R114 | new:rehab | "Can I put full weight on my operated leg while doing exercises?" | rehabilitation (rehabilitation) | clear | mental_wellbeing **x** | semantic_first | rehabilitation,mental_wellbeing |
| R115 | new:rehab | "How long each stretching should be held?" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation |
| R116 | new:rehab | "I missed my exercises for 3 days, how to restart?" | rehabilitation (rehabilitation) | clear | rehabilitation | semfirst_tiebreak_keywords | rehabilitation |
| R117 | new:rehab | "Is climbing stairs a good exercise for strengthening the knee?" | rehabilitation (rehabilitation, daily_activity) | debatable | rehabilitation | semfirst_tiebreak_keywords | rehabilitation,daily_activity |
| R118 | new:rehab | "What is the correct way to do straight leg raise?" | rehabilitation (rehabilitation) | clear | rehabilitation | semfirst_tiebreak_keywords | rehabilitation |
| R119 | new:rehab | "Can I do my exercises twice daily instead of thrice?" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation |
| R120 | new:rehab | "Hip abduction excercise is paining little, should I continue?" | rehabilitation (rehabilitation, pain_symptoms) | debatable | rehabilitation | semantic_first | rehabilitation |
| R121 | new:rehab | "When can I start walking without walker?" | rehabilitation (rehabilitation, recovery_progress) | debatable | rehabilitation | semfirst_tiebreak_deterministic | rehabilitation |
| R122 | new:rehab | "Do I need to go to physio centre or home exercises are enough?" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation |
| R123 | new:rehab | "Pls tell me the exercise plan for this week" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation |
| R124 | new:rehab | "How much should I bend my knee during the exercises, it is week 2" | rehabilitation (rehabilitation) | clear | rehabilitation | semantic_first | rehabilitation |
| R125 | new:wound | "There is some yellow fluid coming from the stiches" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R126 | new:wound | "When can I remove the bandge and take proper bath?" | wound_care (wound_care, daily_activity) | debatable | daily_activity | semantic_first | daily_activity |
| R127 | new:wound | "Wound area is red and little warm, is it infection?" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R128 | new:wound | "Can I apply any ointment or turmeric on the scar?" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R129 | new:wound | "The dressing got wet in the bathroom, what should I do?" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care,daily_activity |
| R130 | new:wound | "Staples are still there, when will they remove?" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R131 | new:wound | "My incision is itching alot, is it normal?" | wound_care (wound_care) | clear | pain_symptoms **x** | semantic_first | wound_care |
| R132 | new:wound | "One side of the cut is looking open slightly" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R133 | new:wound | "How often I should change the dressing at home?" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R134 | new:wound | "Small blood spots on the bandage today morning" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R135 | new:wound | "Can I keep the wound open to air now?" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R136 | new:wound | "The skin around the stitches is peeling" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R137 | new:wound | "Is it ok if water touches the incision while bathing?" | wound_care (wound_care, daily_activity) | debatable | wound_care | semfirst_tiebreak_keywords | wound_care,daily_activity,nutrition |
| R138 | new:wound | "There is a hard lump under the scar, is that normal?" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R139 | new:wound | "The suture line is paining and oozing" | wound_care (wound_care, pain_symptoms) | debatable | wound_care | semfirst_tiebreak_keywords | wound_care |
| R140 | new:wound | "Discharge from the wound has bad smell" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R141 | new:wound | "How should I clean the wound, with dettol or just water?" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R142 | new:wound | "Can I put a waterproof plaster over the incision?" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R143 | new:wound | "Stitch removal is due tomorrow, anything to take care?" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R144 | new:wound | "Redness is spreading around the wound since yesterday" | wound_care (wound_care) | clear | wound_care | semantic_first | wound_care |
| R145 | new:medication | "I forgot to take my blood thinner injection today" | medication (medication) | clear | medication | semantic_first | medication |
| R146 | new:medication | "Can I take Dolo 650 along with the prescribed painkiller?" | medication (medication) | clear | medication | semantic_first | medication |
| R147 | new:medication | "How many hours gap between two paracetamol tablates?" | medication (medication) | clear | medication | semantic_first | medication |
| R148 | new:medication | "Is it ok to stop the antibiotics now, I am feeling fine" | medication (medication) | clear | medication | semantic_first | medication |
| R149 | new:medication | "I vomited after taking the morning medecine, should I take again?" | medication (medication) | clear | medication | semantic_first | medication |
| R150 | new:medication | "What is this tablet Pantop for, doctor gave it with others?" | medication (medication) | clear | medication | semfirst_low_confidence | medication |
| R151 | new:medication | "Missed my night dose of enoxaparin, what to do now?" | medication (medication) | clear | medication | semantic_first | medication |
| R152 | new:medication | "Can I take the pain killer on empty stomach?" | medication (medication) | clear | medication | semantic_first | medication,pain_symptoms |
| R153 | new:medication | "The pain medicine is making me very drowsy and constipated" | medication (medication) | clear | medication | semantic_first | medication |
| R154 | new:medication | "When should I take the next dose if I took one at 2pm?" | medication (medication) | clear | medication | semantic_first | medication |
| R155 | new:medication | "Are there any side effects of rivaroxaban I should know?" | medication (medication) | clear | medication | semantic_first | medication |
| R156 | new:medication | "Can I take my regular BP tablet with these new medicines?" | medication (medication) | clear | medication | semantic_first | medication |
| R157 | new:medication | "Doctor prescribed Ultracet, is it a strong medicine?" | medication (medication) | clear | medication | semfirst_low_confidence | medication |
| R158 | new:medication | "I took double dose by mistake this morning" | medication (medication) | clear | medication | semantic_first | medication |
| R159 | new:medication | "How long I have to continue the blood thinner?" | medication (medication) | clear | medication | semantic_first | medication |
| R160 | new:medication | "Is ibuprofen safe for me after knee replacement?" | medication (medication) | clear | medication | semfirst_tiebreak_deterministic | medication |
| R161 | new:medication | "What is the timing for the antibiotic, before food or after food?" | medication (medication) | clear | medication | semfirst_low_confidence | medication,nutrition |
| R162 | new:medication | "Can I drink alcohol while on these tablets?" | medication (medication, nutrition) | debatable | medication | semfirst_low_confidence | medication,nutrition |
| R163 | new:medication | "My prescription says 1-0-1, what does it mean?" | medication (medication) | clear | medication | semantic_first | medication |
| R164 | new:medication | "Pharmacy gave a different brand of the same medicine, is it ok?" | medication (medication) | clear | medication | semantic_first | medication |
| R165 | new:daily | "Can I use Indian toilet or only western commode?" | daily_activity (daily_activity) | clear | daily_activity | semfirst_low_confidence | daily_activity |
| R166 | new:daily | "When can I start driving my scooty again?" | daily_activity (daily_activity) | clear | daily_activity | semantic_first | daily_activity |
| R167 | new:daily | "How should I sleep, on my back or can I turn to side?" | daily_activity (daily_activity) | clear | daily_activity | semantic_first | daily_activity |
| R168 | new:daily | "Can I take bath with bucket while standing?" | daily_activity (daily_activity) | clear | daily_activity | semantic_first | daily_activity |
| R169 | new:daily | "Is it ok to climb the stairs at home, we have no lift" | daily_activity (daily_activity) | clear | daily_activity | semantic_first | daily_activity |
| R170 | new:daily | "Can I sit on the floor for pooja?" | daily_activity (daily_activity) | clear | daily_activity | semfirst_low_confidence | daily_activity |
| R171 | new:daily | "How do I get into the car without hurting the hip?" | daily_activity (daily_activity, pain_symptoms) | debatable | daily_activity | semantic_first | pain_symptoms,daily_activity |
| R172 | new:daily | "When can I travel by bus or auto to the hospital?" | daily_activity (daily_activity) | clear | daily_activity | semantic_first | daily_activity |
| R173 | new:daily | "Can I do light kitchen work like making chapati?" | daily_activity (daily_activity) | clear | recovery_progress **x** | semfirst_low_confidence | recovery_progress **x** |
| R174 | new:daily | "Is it safe to walk to the temple nearby, around 500 metres?" | daily_activity (daily_activity, rehabilitation, recovery_progress) | debatable | daily_activity | semantic_first | daily_activity |
| R175 | new:daily | "How to get up from bed properly in the morning?" | daily_activity (daily_activity) | clear | daily_activity | semantic_first | daily_activity |
| R176 | new:daily | "Can I sleep on the operated side?" | daily_activity (daily_activity) | clear | daily_activity | semantic_first | daily_activity |
| R177 | new:daily | "Which chair is good to sit, sofa or plastic chair?" | daily_activity (daily_activity) | clear | daily_activity | semantic_first | daily_activity |
| R178 | new:daily | "Can I do sweeping and mopping of the house?" | daily_activity (daily_activity) | clear | recovery_progress **x** | semfirst_low_confidence | recovery_progress **x** |
| R179 | new:daily | "When can I resume my office work, I have desk job" | daily_activity (daily_activity, recovery_progress) | debatable | recovery_progress | semantic_first | recovery_progress |
| R180 | new:daily | "Is it ok to go for a short walk outside daily?" | daily_activity (daily_activity, rehabilitation) | debatable | daily_activity | semantic_first | daily_activity |
| R181 | new:daily | "How to climb up and down stairs with crutches?" | daily_activity (daily_activity, rehabilitation) | debatable | daily_activity | semantic_first | rehabilitation,daily_activity |
| R182 | new:daily | "Can I carry my grandchild while standing?" | daily_activity (daily_activity) | clear | daily_activity | semfirst_low_confidence | daily_activity |
| R183 | new:daily | "Can I kneel down for prayer?" | daily_activity (daily_activity) | clear | recovery_progress **x** | semfirst_low_confidence | recovery_progress **x** |
| R184 | new:daily | "Is it ok to wear slippers or should I use proper shoes?" | daily_activity (daily_activity) | clear | rehabilitation **x** | semantic_first | rehabilitation **x** |
| R185 | new:nutrition | "What food I should eat for faster healing of the bone?" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition,recovery_progress |
| R186 | new:nutrition | "Is non-veg good or should I stick to veg diet now?" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition |
| R187 | new:nutrition | "How much protien I need daily after the surgery?" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition |
| R188 | new:nutrition | "Can I eat curd and rice at night?" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition |
| R189 | new:nutrition | "I am having constipaton since the operation, what to eat?" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition |
| R190 | new:nutrition | "Is drinking coconut water good for recovery?" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition,recovery_progress |
| R191 | new:nutrition | "Should I take calcium and vitamin D tablets?" | nutrition (nutrition, medication) | debatable | nutrition | semantic_first | medication,nutrition |
| R192 | new:nutrition | "My appetite is very less since surgery, is it normal?" | nutrition (nutrition, recovery_progress) | debatable | mental_wellbeing **x** | semantic_first | nutrition,mental_wellbeing |
| R193 | new:nutrition | "Can I eat sweets, I am diabetic also" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition |
| R194 | new:nutrition | "How many litres of water to drink per day?" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition |
| R195 | new:nutrition | "Are eggs and milk enough for protein or need supplements?" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition |
| R196 | new:nutrition | "Can I take tea and coffee normally?" | nutrition (nutrition) | clear | daily_activity **x** | semfirst_tiebreak_top1 | daily_activity **x** |
| R197 | new:nutrition | "Is spicy food bad for the wound healing?" | nutrition (nutrition, wound_care) | debatable | wound_care | semantic_first | wound_care,nutrition,recovery_progress |
| R198 | new:nutrition | "What fruits are good during recovery?" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition,recovery_progress |
| R199 | new:nutrition | "I feel bloated after meals, any diet advice?" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition |
| R200 | new:nutrition | "Can I have beer once in a while now?" | nutrition (nutrition, medication) | debatable | daily_activity **x** | semfirst_tiebreak_top1 | daily_activity **x** |
| R201 | new:nutrition | "Should I reduce weight to help my knee, what diet?" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition |
| R202 | new:nutrition | "Is it ok to fast during Navratri with this recovery?" | nutrition (nutrition, recovery_progress) | debatable | recovery_progress | semantic_first | recovery_progress |
| R203 | new:nutrition | "Dal, roti, sabzi daily is fine or need to change?" | nutrition (nutrition) | clear | recovery_progress **x** | semfirst_low_confidence | recovery_progress **x** |
| R204 | new:nutrition | "Doctor said eat iron rich food, which ones?" | nutrition (nutrition) | clear | nutrition | semantic_first | nutrition |
| R205 | new:mental | "I am feeling very low and crying since the surgery" | mental_wellbeing (mental_wellbeing) | clear | mental_wellbeing | semantic_first | mental_wellbeing |
| R206 | new:mental | "Getting tension that I will never walk properly again" | mental_wellbeing (mental_wellbeing, recovery_progress) | clear | mental_wellbeing | semfirst_tiebreak_top1 | mental_wellbeing |
| R207 | new:mental | "I feel scared to put weight on my leg even though physio said ok" | mental_wellbeing (mental_wellbeing) | clear | mental_wellbeing | semantic_first | rehabilitation,mental_wellbeing |
| R208 | new:mental | "Not able to sleep because of worry about the recovery" | mental_wellbeing (mental_wellbeing, daily_activity) | debatable | mental_wellbeing | semantic_first | daily_activity,mental_wellbeing,recovery_progress |
| R209 | new:mental | "I am frustrated, everything is so slow" | mental_wellbeing (mental_wellbeing) | clear | mental_wellbeing | semfirst_low_confidence | mental_wellbeing |
| R210 | new:mental | "Feeling like a burden on my family" | mental_wellbeing (mental_wellbeing) | clear | mental_wellbeing | semantic_first | mental_wellbeing |
| R211 | new:mental | "I have no motivation to do the exercises anymore" | mental_wellbeing (mental_wellbeing, rehabilitation) | debatable | rehabilitation | semantic_first | rehabilitation |
| R212 | new:mental | "Is it normal to feel depressed after knee replacement?" | mental_wellbeing (mental_wellbeing) | clear | mental_wellbeing | semantic_first | mental_wellbeing |
| R213 | new:mental | "My mood is very irritable these days, snapping at everyone" | mental_wellbeing (mental_wellbeing) | clear | mental_wellbeing | semantic_first | mental_wellbeing |
| R214 | new:mental | "I keep thinking something will go wrong with the implant" | mental_wellbeing (mental_wellbeing) | clear | pain_symptoms **x** | semantic_first | pain_symptoms **x** |
| R215 | new:mental | "Feeling lonely sitting at home whole day" | mental_wellbeing (mental_wellbeing) | clear | daily_activity **x** | semfirst_low_confidence | daily_activity,mental_wellbeing |
| R216 | new:mental | "I am anxiuos about my follow up visit tomorrow" | mental_wellbeing (mental_wellbeing) | clear | recovery_progress **x** | semfirst_low_confidence | recovery_progress **x** |
| R217 | new:mental | "Sometimes I feel hopeless about getting back to normal" | mental_wellbeing (mental_wellbeing) | clear | recovery_progress **x** | semantic_first | mental_wellbeing,recovery_progress |
| R218 | new:mental | "How to deal with the stress of this long recovery?" | mental_wellbeing (mental_wellbeing, recovery_progress) | clear | mental_wellbeing | semantic_first | mental_wellbeing,recovery_progress |
| R219 | new:mental | "I panic whenever I feel any small pain in the knee" | mental_wellbeing (mental_wellbeing, pain_symptoms) | debatable | pain_symptoms | semfirst_tiebreak_keywords | pain_symptoms |
| R220 | new:mental | "My wife says I have become very negative after the operation" | mental_wellbeing (mental_wellbeing) | clear | mental_wellbeing | semantic_first | mental_wellbeing |
| R221 | new:mental | "I feel overwhelmed with all the instructions and exercises" | mental_wellbeing (mental_wellbeing, rehabilitation) | debatable | rehabilitation | semfirst_tiebreak_keywords | rehabilitation,mental_wellbeing |
| R222 | new:mental | "Can't stop worrying that the surgery has failed" | mental_wellbeing (mental_wellbeing) | clear | recovery_progress **x** | semantic_first | recovery_progress **x** |
| R223 | new:mental | "I am not feeling like talking to anyone" | mental_wellbeing (mental_wellbeing) | clear | recovery_progress **x** | semfirst_low_confidence | recovery_progress **x** |
| R224 | new:mental | "Mentally very tired of this whole thing, any tips?" | mental_wellbeing (mental_wellbeing) | clear | mental_wellbeing | semantic_first | mental_wellbeing |
| R225 | intake_guard | "Hi" | intake_context (intake_context) | clear | intake_context | semantic_first | intake_context |
| R226 | intake_guard | "Good morning" | intake_context (intake_context) | clear | intake_context | semfirst_low_confidence | intake_context |
| R227 | intake_guard | "Hi, I am Rishi" | intake_context (intake_context) | clear | intake_context | semantic_first | intake_context |
| R228 | intake_guard | "My name is John and I had knee surgery two days ago" | intake_context (intake_context) | clear | intake_context | semantic_first | intake_context |
| R229 | intake_guard | "I had a knee replacement yesterday" | intake_context (intake_context) | clear | intake_context | semantic_first | intake_context |
| R230 | intake_guard | "I want to provide my baseline information" | intake_context (intake_context) | clear | intake_context | semantic_first | intake_context |
| R231 | intake_guard | "I underwent hip replacement last week" | intake_context (intake_context) | clear | intake_context | semantic_first | intake_context |
| R232 | intake_guard | "Hello, I am a new patient here" | intake_context (intake_context) | clear | intake_context | semantic_first | intake_context |
