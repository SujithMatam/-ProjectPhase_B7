### v1 vs v2 shipped pipeline

| set | pipeline | RED recall | 95% CI | RED->GREEN | RED->YELLOW | YELLOW->RED | GREEN->RED | RED prec. | macro F1 | RED calls / 100 | emails / 100 | RED rows emailed |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| main test (n=266: R 104 / Y 62 / G 100) | rules (default) | 0.192 | 0.128-0.278 | 74 | 10 | 5 | 5 | 0.667 | 0.357 | 11.3 | 11.3 | 20/104 |
| main test (n=266: R 104 / Y 62 / G 100) | v1 hybrid (shipped before) | 0.962 | 0.905-0.985 | 0 | 4 | 34 | 6 | 0.714 | 0.703 | 52.6 | 35.3 | 83/104 |
| main test (n=266: R 104 / Y 62 / G 100) | v1 model, v2 rule (ablation) | 0.952 | 0.892-0.979 | 0 | 5 | 30 | 6 | 0.733 | 0.726 | 50.8 | 35.3 | 83/104 |
| main test (n=266: R 104 / Y 62 / G 100) | **v2 hybrid (shipped)** | 0.923 | 0.856-0.961 | 0 | 8 | 18 | 6 | 0.800 | 0.803 | 45.1 | 32.0 | 79/104 |
| main test (n=266: R 104 / Y 62 / G 100) | v2 data, M1 head (not shipped) | 0.865 | 0.787-0.918 | 3 | 11 | 23 | 9 | 0.738 | 0.750 | 45.9 | 30.5 | 75/104 |
| challenge (n=150: R 58 / Y 38 / G 54) | rules (default) | 0.241 | 0.150-0.365 | 39 | 5 | 6 | 12 | 0.438 | 0.333 | 21.3 | 21.3 | 14/58 |
| challenge (n=150: R 58 / Y 38 / G 54) | v1 hybrid (shipped before) | 1.000 | 0.938-1.000 | 0 | 0 | 26 | 6 | 0.644 | 0.627 | 60.0 | 44.0 | 54/58 |
| challenge (n=150: R 58 / Y 38 / G 54) | v1 model, v2 rule (ablation) | 1.000 | 0.938-1.000 | 0 | 0 | 25 | 5 | 0.659 | 0.638 | 58.7 | 44.0 | 54/58 |
| challenge (n=150: R 58 / Y 38 / G 54) | **v2 hybrid (shipped)** | 0.983 | 0.909-0.997 | 0 | 1 | 17 | 3 | 0.740 | 0.736 | 51.3 | 41.3 | 53/58 |
| challenge (n=150: R 58 / Y 38 / G 54) | v2 data, M1 head (not shipped) | 0.966 | 0.883-0.990 | 1 | 1 | 16 | 8 | 0.700 | 0.736 | 53.3 | 40.0 | 51/58 |
| challenge_v2 (n=90: R 26 / Y 32 / G 32) | rules (default) | 0.500 | 0.321-0.679 | 7 | 6 | 10 | 11 | 0.382 | 0.449 | 37.8 | 37.8 | 13/26 |
| challenge_v2 (n=90: R 26 / Y 32 / G 32) | v1 hybrid (shipped before) | 1.000 | 0.871-1.000 | 0 | 0 | 19 | 4 | 0.531 | 0.621 | 54.4 | 33.3 | 21/26 |
| challenge_v2 (n=90: R 26 / Y 32 / G 32) | v1 model, v2 rule (ablation) | 1.000 | 0.871-1.000 | 0 | 0 | 18 | 4 | 0.542 | 0.636 | 53.3 | 33.3 | 21/26 |
| challenge_v2 (n=90: R 26 / Y 32 / G 32) | **v2 hybrid (shipped)** | 0.962 | 0.811-0.993 | 0 | 1 | 10 | 2 | 0.676 | 0.742 | 41.1 | 31.1 | 22/26 |
| challenge_v2 (n=90: R 26 / Y 32 / G 32) | v2 data, M1 head (not shipped) | 0.808 | 0.621-0.915 | 1 | 4 | 8 | 5 | 0.618 | 0.757 | 37.8 | 25.6 | 18/26 |
| unseen-scenario test (n=275: R 105 / Y 62 / G 108) | rules (default) | 0.057 | 0.026-0.119 | 81 | 18 | 2 | 4 | 0.500 | 0.273 | 4.4 | 4.4 | 6/105 |
| unseen-scenario test (n=275: R 105 / Y 62 / G 108) | v1 hybrid (shipped before) | 0.971 | 0.919-0.990 | 1 | 2 | 38 | 13 | 0.667 | 0.640 | 55.6 | 36.7 | 80/105 |
| unseen-scenario test (n=275: R 105 / Y 62 / G 108) | v1 model, v2 rule (ablation) | 0.971 | 0.919-0.990 | 1 | 2 | 34 | 8 | 0.708 | 0.663 | 52.4 | 36.7 | 80/105 |
| unseen-scenario test (n=275: R 105 / Y 62 / G 108) | **v2 hybrid (shipped)** | 0.952 | 0.893-0.979 | 1 | 4 | 32 | 7 | 0.719 | 0.708 | 50.5 | 32.0 | 71/105 |

v2 seed spread (all 5 main-split v2 seeds, each with its own val-chosen thresholds; mean ± sd):

| set | RED recall | RED->GREEN | YELLOW->RED | GREEN->RED | emails / 100 | macro F1 |
|---|---:|---:|---:|---:|---:|---:|
| main test | 0.910 ± 0.010 | 0.0 ± 0.0 | 19.6 ± 2.2 | 5.0 ± 0.9 | 33.8 ± 1.5 | 0.792 ± 0.013 |
| challenge | 0.983 ± 0.000 | 0.0 ± 0.0 | 19.4 ± 2.9 | 2.6 ± 0.5 | 41.3 ± 1.5 | 0.706 ± 0.035 |
| challenge_v2 | 0.969 ± 0.015 | 0.0 ± 0.0 | 11.0 ± 1.4 | 3.2 ± 1.0 | 31.6 ± 0.5 | 0.732 ± 0.015 |

### Prevalence-adjusted (5% RED, 25% YELLOW, 70% GREEN)

Per-class rates from each set: share of RED / YELLOW / GREEN rows called RED and share emailed, re-weighted to the mix. Email precision = share of emails that are about a RED message at that mix.

| set | pipeline | RED-call rate R / Y / G | email rate R / Y / G | RED calls / 100 | emails / 100 | email precision |
|---|---|---|---|---:|---:|---:|
| main test | rules (default) | 0.19 / 0.08 / 0.05 | 0.19 / 0.08 / 0.05 | 6.5 | 6.5 | 0.15 |
| main test | v1 hybrid (shipped before) | 0.96 / 0.55 / 0.06 | 0.80 / 0.13 / 0.03 | 22.7 | 9.3 | 0.43 |
| main test | v1 model, v2 rule (ablation) | 0.95 / 0.48 / 0.06 | 0.80 / 0.13 / 0.03 | 21.1 | 9.3 | 0.43 |
| main test | **v2 hybrid (shipped)** | 0.92 / 0.29 / 0.06 | 0.76 / 0.06 / 0.02 | 16.1 | 6.8 | 0.56 |
| challenge | rules (default) | 0.24 / 0.16 / 0.22 | 0.24 / 0.16 / 0.22 | 20.7 | 20.7 | 0.06 |
| challenge | v1 hybrid (shipped before) | 1.00 / 0.68 / 0.11 | 0.93 / 0.26 / 0.04 | 29.9 | 13.8 | 0.34 |
| challenge | v1 model, v2 rule (ablation) | 1.00 / 0.66 / 0.09 | 0.93 / 0.26 / 0.04 | 27.9 | 13.8 | 0.34 |
| challenge | **v2 hybrid (shipped)** | 0.98 / 0.45 / 0.06 | 0.91 / 0.24 / 0.00 | 20.0 | 10.5 | 0.44 |
| challenge_v2 | rules (default) | 0.50 / 0.31 / 0.34 | 0.50 / 0.31 / 0.34 | 34.4 | 34.4 | 0.07 |
| challenge_v2 | v1 hybrid (shipped before) | 1.00 / 0.59 / 0.12 | 0.81 / 0.19 / 0.09 | 28.6 | 15.3 | 0.26 |
| challenge_v2 | v1 model, v2 rule (ablation) | 1.00 / 0.56 / 0.12 | 0.81 / 0.19 / 0.09 | 27.8 | 15.3 | 0.26 |
| challenge_v2 | **v2 hybrid (shipped)** | 0.96 / 0.31 / 0.06 | 0.85 / 0.16 / 0.03 | 17.0 | 10.3 | 0.41 |
| unseen-scenario test | rules (default) | 0.06 / 0.03 / 0.04 | 0.06 / 0.03 / 0.04 | 3.7 | 3.7 | 0.08 |
| unseen-scenario test | v1 hybrid (shipped before) | 0.97 / 0.61 / 0.12 | 0.76 / 0.31 / 0.02 | 28.6 | 12.8 | 0.30 |
| unseen-scenario test | v1 model, v2 rule (ablation) | 0.97 / 0.55 / 0.07 | 0.76 / 0.31 / 0.02 | 23.8 | 12.8 | 0.30 |
| unseen-scenario test | **v2 hybrid (shipped)** | 0.95 / 0.52 / 0.06 | 0.68 / 0.26 / 0.01 | 22.2 | 10.5 | 0.32 |

### Per category

| set:category | n (R/Y/G) | rules acc. | v1 acc. | v2 acc. | v1 RED recall | v2 RED recall | v1 non-RED called RED | v2 non-RED called RED | v1 under-triaged | v2 under-triaged |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| challenge_v2:negation | 30 (6/8/16) | 27% | 67% | 77% | 6/6 | 5/6 | 6 | 2 | 1 | 2 |
| challenge_v2:wound_minimal_pair | 36 (18/18/0) | 47% | 61% | 78% | 18/18 | 18/18 | 14 | 8 | 0 | 0 |
| challenge_v2:routine_multi_topic | 24 (2/6/16) | 67% | 67% | 67% | 2/2 | 2/2 | 3 | 2 | 3 | 3 |
| challenge:negation | 20 (4/4/12) | 30% | 75% | 90% | 4/4 | 4/4 | 3 | 1 | 0 | 0 |
| challenge:keyword_free_red | 20 (20/0/0) | 0% | 100% | 100% | 20/20 | 20/20 | 0 | 0 | 0 | 0 |
| challenge:indian_english | 21 (7/7/7) | 57% | 76% | 86% | 7/7 | 6/7 | 4 | 2 | 0 | 1 |
| challenge:typo_or_slang | 21 (8/7/6) | 43% | 67% | 67% | 8/8 | 8/8 | 5 | 5 | 2 | 2 |
| challenge:numeric_in_text | 21 (7/7/7) | 43% | 67% | 71% | 7/7 | 7/7 | 4 | 3 | 0 | 1 |
| challenge:multi_symptom | 20 (9/8/3) | 45% | 55% | 75% | 9/9 | 9/9 | 8 | 3 | 0 | 0 |
| challenge:benign_scary_word | 20 (0/3/17) | 65% | 50% | 60% |  |  | 5 | 3 | 0 | 1 |
| challenge:audit_regression | 7 (3/2/2) | 0% | 43% | 57% | 3/3 | 3/3 | 3 | 3 | 0 | 0 |

### The 7 audit rows

| id | text | label | rules | v1 | v1 p(RED) | v1 email | v2 | v2 p(RED) | v2 email | v2 reason codes |
|---|---|---|---|---|---:|---|---|---:|---|---|
| CH-144 | No chest pain, no chills | GREEN | **RED** | **YELLOW** | 0.082 | no | GREEN | 0.025 | no | classifier |
| CH-145 | I don't have shortness of breath | GREEN | **RED** | **RED** | 0.744 | yes | **RED** | 0.673 | no | classifier |
| CH-146 | I cannot breathe properly | RED | **GREEN** | RED | 0.919 | yes | RED | 0.928 | yes | classifier |
| CH-147 | I can’t breathe | RED | **GREEN** | RED | 0.966 | yes | RED | 0.976 | yes | classifier |
| CH-148 | fever of 39 | RED | **GREEN** | RED | 0.695 | yes | RED | 0.682 | yes | high_fever, classifier |
| CH-149 | My knee is a little red and swollen | YELLOW | **RED** | **RED** | 0.920 | yes | **RED** | 0.853 | yes | classifier |
| CH-150 | fluid coming from my incision | YELLOW | **GREEN** | **RED** | 0.669 | yes | **RED** | 0.678 | no | classifier |

Bold = differs from the label.

### Orchestration-test messages

| message | rules | v1 | v1 p(RED) | v1 email | v2 | v2 p(RED) | v2 email |
|---|---|---|---:|---|---|---:|---|
| Since I didn't take my medicine yesterday, my knee wound is worse | GREEN | RED | 0.740 | yes | RED | 0.756 | yes |
| I am anxious, my knee hurts, and I need help with exercises | GREEN | RED | 0.539 | no | YELLOW | 0.252 | no |

### RED messages v2 does not call RED

| set | id | v2 | p(RED) | v1 | text |
|---|---|---|---:|---|---|
| test | ALLERGIC_REACTION-013 | YELLOW | 0.059 | YELLOW | Wheezy and chest tight since the tramadol, never had asthma |
| test | BLEEDING_ANTICOAG-037 | YELLOW | 0.202 | RED | My mother is passing blood with stool and she is on blood thinner after knee replacement. Kindly guide. |
| test | COMPARTMENT-012 | YELLOW | 0.08 | YELLOW | My father is shouting with pain in leg after knee surgery. Tramadol given 1 hour back but no relief. Leg is tight. |
| test | COMPARTMENT-058 | YELLOW | 0.058 | YELLOW | Is so much pain normal on day 2? Leg is very tight and stiff like wood and no medicine is working. |
| test | COMPARTMENT-059 | YELLOW | 0.197 | RED | The pain is getting worse hour by hour and it's out of all proportion. I've had the other knee done and it was nothing like this. |
| test | LOW_FEVER-040 | YELLOW | 0.164 | RED | Mum's mild temp of 38.2 but she's muddled and forgetting things today |
| test | SRC-SEPSIS_WOUND-03 | YELLOW | 0.316 | RED | The redness around the surgical cut has spread 4 inches with burning pain and fever. |
| test | WOUND_OPEN-030 | YELLOW | 0.194 | YELLOW | When I bend the knee the cut gapes and I can see right into it; when I straighten it closes again |
| challenge | CH-061 | YELLOW | 0.295 | RED | Thoda chest mein dard hai and saans lene mein problem, since one hour |
| challenge_v2 | CH2-030 | YELLOW | 0.282 | RED | Not dizzy, but I've had black tarry poo twice since starting the blood thinner |
| unseen_test | ALLERGIC_REACTION-013 | YELLOW | 0.028 | YELLOW | Wheezy and chest tight since the tramadol, never had asthma |
| unseen_test | ALLERGIC_REACTION-017 | YELLOW | 0.1 | RED | Itchy everywhere, lips fat, and feel dizzy since taking the first amoxicillin |
| unseen_test | ALLERGIC_REACTION-028 | YELLOW | 0.083 | RED | Lumpy itchy welts head to toe since the new tablets yesterday |
| unseen_test | ALLERGIC_REACTION-032 | GREEN | 0.004 | GREEN | Is it normal for my throat to feel tight after the antibiotic? |
| unseen_test | FOLLOWUP_ADMIN-014 | YELLOW | 0.031 | YELLOW | Waiting for my wound check next week but the dressing has soaked right through with blood twice today. |

Live code path (`classifier_triage.evaluate`) vs cached probabilities, v2:
- test: model `M2:m2_main_v2_it3_seed0`, 0 level/email mismatches, max |p(RED) diff| 8.05e-07
- challenge: model `M2:m2_main_v2_it3_seed0`, 0 level/email mismatches, max |p(RED) diff| 5.66e-07
- challenge_v2: model `M2:m2_main_v2_it3_seed0`, 0 level/email mismatches, max |p(RED) diff| 6.56e-07
