### Shipping rule (stated before training)

| condition | v2 | v3 | pass |
|---|---|---|---|
| 1. main test RED rows called RED (v3 >= v2 - 2) | 96/104 | 93/104 | no |
| 2. RED->GREEN not higher: main test | 0 | 0 | yes |
| 2. RED->GREEN not higher: challenge | 0 | 0 | yes |
| 2. RED->GREEN not higher: challenge_v2 | 0 | 0 | yes |
| 2. RED->GREEN not higher: challenge_v3 | 2 | 3 | no |
| 2. RED->GREEN not higher: integration set | 1 | 1 | yes |
| 2. RED->GREEN not higher: unseen-scenario test | 1 | 1 | yes |
| 3. over-triage (Y->R + G->R) lower: challenge_v3 | 8 | 2 | yes |
| 3. over-triage (Y->R + G->R) lower: integration set | 75 | 40 | yes |

**Ship v3: NO.**

### v2 vs v3 shipped pipeline

| set | pipeline | RED recall | 95% CI | RED->GREEN | RED->YELLOW | YELLOW->RED | GREEN->RED | over-triage | RED prec. | macro F1 | RED calls / 100 | emails / 100 | RED rows emailed |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| main test (n=266: R 104 / Y 62 / G 100) | rules (TRIAGE_MODE=rules) | 0.192 | 0.128-0.278 | 74 | 10 | 5 | 5 | 10 | 0.667 | 0.357 | 11.3 | 11.3 | 20/104 |
| main test (n=266: R 104 / Y 62 / G 100) | v2 hybrid (current default) | 0.923 | 0.856-0.961 | 0 | 8 | 18 | 6 | 24 | 0.800 | 0.803 | 45.1 | 32.0 | 79/104 |
| main test (n=266: R 104 / Y 62 / G 100) | **v3 hybrid** | 0.894 | 0.820-0.940 | 0 | 11 | 15 | 4 | 19 | 0.830 | 0.809 | 42.1 | 35.0 | 84/104 |
| challenge (n=150: R 58 / Y 38 / G 54) | rules (TRIAGE_MODE=rules) | 0.241 | 0.150-0.365 | 39 | 5 | 6 | 12 | 18 | 0.438 | 0.333 | 21.3 | 21.3 | 14/58 |
| challenge (n=150: R 58 / Y 38 / G 54) | v2 hybrid (current default) | 0.983 | 0.909-0.997 | 0 | 1 | 17 | 3 | 20 | 0.740 | 0.736 | 51.3 | 41.3 | 53/58 |
| challenge (n=150: R 58 / Y 38 / G 54) | **v3 hybrid** | 0.948 | 0.859-0.982 | 0 | 3 | 12 | 1 | 13 | 0.809 | 0.763 | 45.3 | 38.0 | 53/58 |
| challenge_v2 (n=90: R 26 / Y 32 / G 32) | rules (TRIAGE_MODE=rules) | 0.500 | 0.321-0.679 | 7 | 6 | 10 | 11 | 21 | 0.382 | 0.449 | 37.8 | 37.8 | 13/26 |
| challenge_v2 (n=90: R 26 / Y 32 / G 32) | v2 hybrid (current default) | 0.962 | 0.811-0.993 | 0 | 1 | 10 | 2 | 12 | 0.676 | 0.742 | 41.1 | 31.1 | 22/26 |
| challenge_v2 (n=90: R 26 / Y 32 / G 32) | **v3 hybrid** | 0.962 | 0.811-0.993 | 0 | 1 | 8 | 1 | 9 | 0.735 | 0.755 | 37.8 | 32.2 | 23/26 |
| challenge_v3 (n=91: R 33 / Y 33 / G 25) | rules (TRIAGE_MODE=rules) | 0.364 | 0.222-0.534 | 18 | 3 | 3 | 2 | 5 | 0.706 | 0.430 | 18.7 | 18.7 | 12/33 |
| challenge_v3 (n=91: R 33 / Y 33 / G 25) | v2 hybrid (current default) | 0.636 | 0.466-0.778 | 2 | 10 | 5 | 3 | 8 | 0.724 | 0.696 | 31.9 | 16.5 | 13/33 |
| challenge_v3 (n=91: R 33 / Y 33 / G 25) | **v3 hybrid** | 0.758 | 0.590-0.872 | 3 | 5 | 1 | 1 | 2 | 0.926 | 0.779 | 29.7 | 26.4 | 23/33 |
| integration set (n=272: R 22 / Y 83 / G 167) | rules (TRIAGE_MODE=rules) | 0.773 | 0.566-0.899 | 2 | 3 | 2 | 0 | 2 | 0.895 | 0.695 | 7.0 | 7.0 | 17/22 |
| integration set (n=272: R 22 / Y 83 / G 167) | v2 hybrid (current default) | 0.955 | 0.782-0.992 | 1 | 0 | 59 | 16 | 75 | 0.219 | 0.466 | 35.3 | 21.7 | 21/22 |
| integration set (n=272: R 22 / Y 83 / G 167) | **v3 hybrid** | 0.955 | 0.782-0.992 | 1 | 0 | 32 | 8 | 40 | 0.344 | 0.616 | 22.4 | 16.9 | 21/22 |
| unseen-scenario test (n=275: R 105 / Y 62 / G 108) | rules (TRIAGE_MODE=rules) | 0.057 | 0.026-0.119 | 81 | 18 | 2 | 4 | 6 | 0.500 | 0.273 | 4.4 | 4.4 | 6/105 |
| unseen-scenario test (n=275: R 105 / Y 62 / G 108) | v2 hybrid (current default) | 0.952 | 0.893-0.979 | 1 | 4 | 32 | 7 | 39 | 0.719 | 0.708 | 50.5 | 32.0 | 71/105 |
| unseen-scenario test (n=275: R 105 / Y 62 / G 108) | **v3 hybrid** | 0.876 | 0.800-0.926 | 1 | 12 | 28 | 4 | 32 | 0.742 | 0.651 | 45.1 | 29.8 | 68/105 |

v3 seed spread (all 5 main-split v3 seeds, each with its own val-chosen thresholds; mean ± sd):

| set | RED recall | RED rows called RED | RED->GREEN | YELLOW->RED | GREEN->RED | over-triage | emails / 100 | macro F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| main test | 0.902 ± 0.007 | 93.8 ± 0.7 | 0.8 ± 0.7 | 17.4 ± 1.4 | 4.8 ± 0.7 | 22.2 ± 1.9 | 36.2 ± 0.8 | 0.793 ± 0.008 |
| challenge | 0.955 ± 0.008 | 55.4 ± 0.5 | 0.0 ± 0.0 | 14.0 ± 2.2 | 2.0 ± 0.6 | 16.0 ± 2.5 | 37.9 ± 1.1 | 0.760 ± 0.013 |
| challenge_v2 | 0.977 ± 0.019 | 25.4 ± 0.5 | 0.0 ± 0.0 | 8.6 ± 1.0 | 2.0 ± 0.9 | 10.6 ± 1.6 | 34.2 ± 1.3 | 0.749 ± 0.013 |
| challenge_v3 | 0.824 ± 0.045 | 27.2 ± 1.5 | 2.4 ± 0.5 | 1.6 ± 0.8 | 1.0 ± 0.0 | 2.6 ± 0.8 | 27.7 ± 0.8 | 0.811 ± 0.023 |
| integration set | 0.955 ± 0.000 | 21.0 ± 0.0 | 1.0 ± 0.0 | 41.8 ± 5.2 | 10.0 ± 1.4 | 51.8 ± 6.3 | 18.2 ± 0.9 | 0.565 ± 0.028 |

### Prevalence-adjusted (5% RED, 25% YELLOW, 70% GREEN)

Per-class rates from each set (share of RED / YELLOW / GREEN rows called RED, and emailed), re-weighted to the mix. Email precision = share of emails that are about a RED message at that mix.

| set | pipeline | RED-call rate R / Y / G | email rate R / Y / G | RED calls / 100 | emails / 100 | email precision |
|---|---|---|---|---:|---:|---:|
| main test | rules (TRIAGE_MODE=rules) | 0.19 / 0.08 / 0.05 | 0.19 / 0.08 / 0.05 | 6.5 | 6.5 | 0.15 |
| main test | v2 hybrid (current default) | 0.92 / 0.29 / 0.06 | 0.76 / 0.06 / 0.02 | 16.1 | 6.8 | 0.56 |
| main test | **v3 hybrid** | 0.89 / 0.24 / 0.04 | 0.81 / 0.11 / 0.02 | 13.3 | 8.3 | 0.49 |
| challenge | rules (TRIAGE_MODE=rules) | 0.24 / 0.16 / 0.22 | 0.24 / 0.16 / 0.22 | 20.7 | 20.7 | 0.06 |
| challenge | v2 hybrid (current default) | 0.98 / 0.45 / 0.06 | 0.91 / 0.24 / 0.00 | 20.0 | 10.5 | 0.44 |
| challenge | **v3 hybrid** | 0.95 / 0.32 / 0.02 | 0.91 / 0.11 / 0.00 | 13.9 | 7.2 | 0.63 |
| challenge_v2 | rules (TRIAGE_MODE=rules) | 0.50 / 0.31 / 0.34 | 0.50 / 0.31 / 0.34 | 34.4 | 34.4 | 0.07 |
| challenge_v2 | v2 hybrid (current default) | 0.96 / 0.31 / 0.06 | 0.85 / 0.16 / 0.03 | 17.0 | 10.3 | 0.41 |
| challenge_v2 | **v3 hybrid** | 0.96 / 0.25 / 0.03 | 0.88 / 0.16 / 0.03 | 13.2 | 10.5 | 0.42 |
| challenge_v3 | rules (TRIAGE_MODE=rules) | 0.36 / 0.09 / 0.08 | 0.36 / 0.09 / 0.08 | 9.7 | 9.7 | 0.19 |
| challenge_v3 | v2 hybrid (current default) | 0.64 / 0.15 / 0.12 | 0.39 / 0.03 / 0.04 | 15.4 | 5.5 | 0.36 |
| challenge_v3 | **v3 hybrid** | 0.76 / 0.03 / 0.04 | 0.70 / 0.00 / 0.04 | 7.3 | 6.3 | 0.55 |
| integration set | rules (TRIAGE_MODE=rules) | 0.77 / 0.02 / 0.00 | 0.77 / 0.02 / 0.00 | 4.5 | 4.5 | 0.87 |
| integration set | v2 hybrid (current default) | 0.95 / 0.71 / 0.10 | 0.95 / 0.39 / 0.04 | 29.3 | 16.9 | 0.28 |
| integration set | **v3 hybrid** | 0.95 / 0.39 / 0.05 | 0.95 / 0.23 / 0.04 | 17.8 | 13.0 | 0.37 |
| unseen-scenario test | rules (TRIAGE_MODE=rules) | 0.06 / 0.03 / 0.04 | 0.06 / 0.03 / 0.04 | 3.7 | 3.7 | 0.08 |
| unseen-scenario test | v2 hybrid (current default) | 0.95 / 0.52 / 0.06 | 0.68 / 0.26 / 0.01 | 22.2 | 10.5 | 0.32 |
| unseen-scenario test | **v3 hybrid** | 0.88 / 0.45 / 0.04 | 0.65 / 0.21 / 0.01 | 18.3 | 9.1 | 0.35 |

### Per category

| set:category | n (R/Y/G) | v2 RED caught | v3 RED caught | v2 RED->GREEN | v3 RED->GREEN | v2 non-RED called RED | v3 non-RED called RED |
|---|---|---:|---:|---:|---:|---:|---:|
| challenge_v3:short_single_symptom | 37 (8/16/13) | 8/8 | 5/8 | 0 | 1 | 8 | 2 |
| challenge_v3:red_in_routine_question | 30 (20/5/5) | 9/20 | 17/20 | 2 | 1 | 0 | 0 |
| challenge_v3:mixed | 24 (5/12/7) | 4/5 | 3/5 | 0 | 1 | 0 | 0 |
| challenge_v2:negation | 30 (6/8/16) | 5/6 | 6/6 | 0 | 0 | 2 | 3 |
| challenge_v2:wound_minimal_pair | 36 (18/18/0) | 18/18 | 17/18 | 0 | 0 | 8 | 5 |
| challenge_v2:routine_multi_topic | 24 (2/6/16) | 2/2 | 2/2 | 0 | 0 | 2 | 1 |
| challenge:negation | 20 (4/4/12) | 4/4 | 4/4 | 0 | 0 | 1 | 2 |
| challenge:keyword_free_red | 20 (20/0/0) | 20/20 | 19/20 | 0 | 0 | 0 | 0 |
| challenge:indian_english | 21 (7/7/7) | 6/7 | 6/7 | 0 | 0 | 2 | 2 |
| challenge:typo_or_slang | 21 (8/7/6) | 8/8 | 7/8 | 0 | 0 | 5 | 2 |
| challenge:numeric_in_text | 21 (7/7/7) | 7/7 | 7/7 | 0 | 0 | 3 | 1 |
| challenge:multi_symptom | 20 (9/8/3) | 9/9 | 9/9 | 0 | 0 | 3 | 2 |
| challenge:benign_scary_word | 20 (0/3/17) |  |  | 0 | 0 | 3 | 2 |
| challenge:audit_regression | 7 (3/2/2) | 3/3 | 3/3 | 0 | 0 | 3 | 2 |

### The calf message and short-message examples (integration set)

| set | text | label | v2 | v2 p(RED) | v2 email | v3 | v3 p(RED) | v3 email |
|---|---|---|---|---:|---|---|---:|---|
| integration | I have severe calf pain and swelling, can I still do my exercises? | RED | **GREEN** | 0.011 | no | **GREEN** | 0.016 | no |
| integration | My knee is swollen. | YELLOW | **RED** | 0.721 | yes | YELLOW | 0.349 | no |
| integration | My knee pain suddenly got much worse today. | YELLOW | **RED** | 0.762 | yes | **RED** | 0.555 | no |
| integration | My pain suddenly got much worse today. | YELLOW | **RED** | 0.739 | yes | **RED** | 0.553 | no |
| integration | My knee is more swollen today and hurts. | YELLOW | **RED** | 0.809 | yes | **RED** | 0.559 | no |
| integration | My knee is swollen and sore. | YELLOW | **RED** | 0.740 | yes | YELLOW | 0.359 | no |
| integration | My hip is swollen and sore. | YELLOW | **RED** | 0.771 | yes | **RED** | 0.441 | no |
| integration | My ankle is swollen and sore. | YELLOW | **RED** | 0.844 | yes | **RED** | 0.722 | yes |
| integration | My hip has started aching today. | YELLOW | **RED** | 0.665 | no | YELLOW | 0.336 | no |
| integration | My knee is sore. | GREEN | **RED** | 0.570 | no | **YELLOW** | 0.133 | no |
| integration | My knee hurts. | YELLOW | **RED** | 0.725 | yes | YELLOW | 0.298 | no |
| integration | My pain suddenly got worse today, and it's mostly behind the knee. | YELLOW | **RED** | 0.544 | no | YELLOW | 0.400 | no |
| integration | My knee is sore and a bit tender. It started suddenly, I feel it mostly behind the knee, it's been getting worse, and the knee feels stiff. | YELLOW | **RED** | 0.864 | yes | **RED** | 0.714 | yes |
| integration | My knee pain is 6 out of 10, it started suddenly behind the knee and it is swollen. | YELLOW | **RED** | 0.877 | yes | **RED** | 0.780 | yes |
| integration | My incision hurts and there is yellow fluid coming out. | RED | RED | 0.894 | yes | RED | 0.884 | yes |
| integration | My wound looks more red today and it's leaking some fluid. | YELLOW | **RED** | 0.740 | yes | **RED** | 0.690 | yes |
| integration | My wound looks a bit red today. | YELLOW | **RED** | 0.477 | no | **RED** | 0.430 | no |
| integration | Since I didn't take my medicine yesterday, my knee wound is worse | YELLOW | **RED** | 0.756 | yes | **RED** | 0.548 | no |
| integration | I am anxious, my knee hurts, and I need help with exercises | YELLOW | YELLOW | 0.252 | no | YELLOW | 0.077 | no |
| integration | I cannot keep fluids down and I am hardly urinating. | YELLOW | **RED** | 0.782 | yes | **RED** | 0.674 | yes |
| integration | I feel hopeless and cannot function. | YELLOW | **RED** | 0.753 | yes | **RED** | 0.527 | no |
| integration | I feel scared to move my leg. | GREEN | **RED** | 0.601 | no | **RED** | 0.632 | yes |
| integration | I have severe calf pain and swelling in my calf. | RED | RED | 0.793 | yes | RED | 0.751 | yes |
| integration | My calf is swollen. | RED | RED | 0.858 | yes | RED | 0.815 | yes |
| integration | I have severe chest pain and can't breathe. | RED | RED | 0.970 | yes | RED | 0.965 | yes |

Bold = differs from the guideline label.

### challenge_v3 short single-symptom rows

| set | text | label | v2 | v2 p(RED) | v2 email | v3 | v3 p(RED) | v3 email |
|---|---|---|---|---:|---|---|---:|---|
| challenge_v3 | Knee is stiff first thing in the morning. | GREEN | **YELLOW** | 0.105 | no | GREEN | 0.005 | no |
| challenge_v3 | scar is itchy, all healed over | GREEN | **RED** | 0.401 | no | **YELLOW** | 0.060 | no |
| challenge_v3 | Little bruise on my tummy where the injections go. | GREEN | **YELLOW** | 0.075 | no | GREEN | 0.013 | no |
| challenge_v3 | Ankle puffs up by evening, gone by morning. | GREEN | GREEN | 0.023 | no | GREEN | 0.010 | no |
| challenge_v3 | Temp is 37.2 today. | GREEN | **YELLOW** | 0.086 | no | **YELLOW** | 0.038 | no |
| challenge_v3 | Hip clicks sometimes, doesn't hurt. | GREEN | GREEN | 0.008 | no | GREEN | 0.003 | no |
| challenge_v3 | Thigh feels tight like a band. | GREEN | GREEN | 0.064 | no | GREEN | 0.019 | no |
| challenge_v3 | Bit achy after my physio session, settles with rest. | GREEN | GREEN | 0.013 | no | GREEN | 0.009 | no |
| challenge_v3 | Numb patch next to the scar, same as since the op. | GREEN | GREEN | 0.008 | no | GREEN | 0.011 | no |
| challenge_v3 | Feeling a bit low today but managing. | GREEN | GREEN | 0.018 | no | GREEN | 0.006 | no |
| challenge_v3 | Bruise on my thigh is turning yellow. | GREEN | **RED** | 0.864 | yes | **RED** | 0.746 | yes |
| challenge_v3 | Not sleeping great, but coping. | GREEN | GREEN | 0.007 | no | GREEN | 0.006 | no |
| challenge_v3 | tiny dot of blood on the dressing, not growing | GREEN | **RED** | 0.548 | no | **YELLOW** | 0.088 | no |
| challenge_v3 | My knee is puffy. | YELLOW | **RED** | 0.774 | yes | **RED** | 0.599 | no |
| challenge_v3 | Hip looks swollen today. | YELLOW | **RED** | 0.469 | no | YELLOW | 0.310 | no |
| challenge_v3 | Running 38.1 on the thermometer since lunch. | YELLOW | YELLOW | 0.078 | no | YELLOW | 0.084 | no |
| challenge_v3 | Clear fluid leaking from the bottom of the cut. | YELLOW | **RED** | 0.485 | no | YELLOW | 0.300 | no |
| challenge_v3 | Stitches are pulling and sore. | YELLOW | YELLOW | 0.348 | no | YELLOW | 0.068 | no |
| challenge_v3 | Haven't managed to open my bowels since Monday and it's Friday now. | YELLOW | YELLOW | 0.110 | no | YELLOW | 0.070 | no |
| challenge_v3 | Feel sick after my painkillers. | YELLOW | YELLOW | 0.297 | no | YELLOW | 0.101 | no |
| challenge_v3 | Itchy rash on my chest since the new pills. | YELLOW | YELLOW | 0.055 | no | YELLOW | 0.032 | no |
| challenge_v3 | Pain gets a little worse every day. | YELLOW | YELLOW | 0.102 | no | YELLOW | 0.022 | no |
| challenge_v3 | Forgot yesterday's blood thinner injection. | YELLOW | YELLOW | 0.131 | no | YELLOW | 0.051 | no |
| challenge_v3 | Knee clunks and feels like it might give way. | YELLOW | YELLOW | 0.241 | no | YELLOW | 0.097 | no |
| challenge_v3 | Edge of the scar is a bit red and warm. | YELLOW | YELLOW | 0.283 | no | YELLOW | 0.216 | no |
| challenge_v3 | Feeling feverish tonight. | YELLOW | **RED** | 0.526 | no | YELLOW | 0.329 | no |
| challenge_v3 | Dizzy when I stand up. | YELLOW | YELLOW | 0.343 | no | YELLOW | 0.213 | no |
| challenge_v3 | Knee aches more today. | YELLOW | YELLOW | 0.346 | no | YELLOW | 0.033 | no |
| challenge_v3 | Wound feels hot. | YELLOW | **RED** | 0.610 | no | YELLOW | 0.247 | no |
| challenge_v3 | Back of my calf is rock hard and burning. | RED | RED | 0.951 | yes | RED | 0.976 | yes |
| challenge_v3 | Toes have gone white and cold. | RED | RED | 0.837 | yes | RED | 0.861 | yes |
| challenge_v3 | Breathless just sitting still. | RED | RED | 0.398 | no | **GREEN** | 0.161 | no |
| challenge_v3 | Thermometer says 102.4F. | RED | RED | 0.114 | yes | RED | 0.088 | yes |
| challenge_v3 | Wound has burst open. | RED | RED | 0.837 | yes | RED | 0.809 | yes |
| challenge_v3 | Hip went pop, can't stand on it. | RED | RED | 0.947 | yes | RED | 0.936 | yes |
| challenge_v3 | Peeing blood since this morning. | RED | RED | 0.553 | no | **YELLOW** | 0.365 | no |
| challenge_v3 | Coughed up blood just now. | RED | RED | 0.575 | no | **YELLOW** | 0.373 | no |

### RED rows missed by v2 or v3 (every set)

| set | text | label | v2 | v2 p(RED) | v2 email | v3 | v3 p(RED) | v3 email |
|---|---|---|---|---:|---|---|---:|---|
| test | Wheezy and chest tight since the tramadol, never had asthma | RED | **YELLOW** | 0.059 | no | **YELLOW** | 0.041 | no |
| test | My mother is passing blood with stool and she is on blood thinner after knee replacement. Kindly guide. | RED | **YELLOW** | 0.202 | no | **YELLOW** | 0.069 | no |
| test | My father is shouting with pain in leg after knee surgery. Tramadol given 1 hour back but no relief. Leg is tight. | RED | **YELLOW** | 0.080 | no | **YELLOW** | 0.044 | no |
| test | Is so much pain normal on day 2? Leg is very tight and stiff like wood and no medicine is working. | RED | **YELLOW** | 0.058 | no | **YELLOW** | 0.144 | no |
| test | The pain is getting worse hour by hour and it's out of all proportion. I've had the other knee done and it was nothing like this. | RED | **YELLOW** | 0.197 | no | **YELLOW** | 0.211 | no |
| test | Nearly passed out on the toilet while straining, my husband had to help me back to bed. Still nothing out after four days. | RED | RED | 0.369 | no | **YELLOW** | 0.177 | no |
| test | Swelling in my thigh is getting bigger by the day and it's painful to touch, even after resting with it up. | RED | RED | 0.405 | no | **YELLOW** | 0.344 | no |
| test | Mum's mild temp of 38.2 but she's muddled and forgetting things today | RED | **YELLOW** | 0.164 | no | **YELLOW** | 0.214 | no |
| test | drew a pen line round the redness at lunch like the nurse said, it's gone past the line by two fingers already | RED | RED | 0.483 | no | **YELLOW** | 0.357 | no |
| test | The redness around the surgical cut has spread 4 inches with burning pain and fever. | RED | **YELLOW** | 0.316 | no | **YELLOW** | 0.295 | no |
| test | When I bend the knee the cut gapes and I can see right into it; when I straighten it closes again | RED | **YELLOW** | 0.194 | no | **YELLOW** | 0.174 | no |
| challenge | Every few steps I have to stop and lean on the wall to get air | RED | RED | 0.528 | no | **YELLOW** | 0.316 | no |
| challenge | Thoda chest mein dard hai and saans lene mein problem, since one hour | RED | **YELLOW** | 0.295 | no | **YELLOW** | 0.236 | no |
| challenge | puss comin out n it stinks | RED | RED | 0.627 | no | **YELLOW** | 0.323 | no |
| challenge_v2 | Not dizzy, but I've had black tarry poo twice since starting the blood thinner | RED | **YELLOW** | 0.282 | no | RED | 0.456 | no |
| challenge_v2 | The red patch next to the scar was coin-sized yesterday, now it's the size of my hand | RED | RED | 0.439 | no | **YELLOW** | 0.378 | no |
| challenge_v3 | Breathless just sitting still. | RED | RED | 0.398 | no | **GREEN** | 0.161 | no |
| challenge_v3 | Peeing blood since this morning. | RED | RED | 0.553 | no | **YELLOW** | 0.365 | no |
| challenge_v3 | Coughed up blood just now. | RED | RED | 0.575 | no | **YELLOW** | 0.373 | no |
| challenge_v3 | Is it fine to go to physio tomorrow even though my chest hurts when I take a deep breath? | RED | **GREEN** | 0.016 | no | **GREEN** | 0.123 | no |
| challenge_v3 | What's a good iron-rich diet? I've had black sticky stools twice since starting the blood thinner. | RED | **YELLOW** | 0.069 | no | **YELLOW** | 0.323 | no |
| challenge_v3 | How many laps of the corridor should I do? I got really breathless and nearly passed out on the first one. | RED | **YELLOW** | 0.304 | no | RED | 0.898 | yes |
| challenge_v3 | Which foods help with nausea? I vomited and it looked like coffee grounds. | RED | **YELLOW** | 0.328 | no | RED | 0.628 | yes |
| challenge_v3 | When do I start the stairs exercise? Also my foot has gone numb and cold since this afternoon. | RED | **YELLOW** | 0.259 | no | RED | 0.690 | yes |
| challenge_v3 | Do I need to keep the pillow between my legs at night? I heard a pop when I turned and now my leg looks shorter. | RED | **YELLOW** | 0.051 | no | RED | 0.532 | no |
| challenge_v3 | Should I still take my walk today? My calf hurts when I flex my foot and it's warmer than the other side. | RED | **YELLOW** | 0.260 | no | RED | 0.715 | yes |
| challenge_v3 | My physio said 3 sets of 10, is that too much? The pain is unbearable, the leg feels tight as a drum and the tablets do nothing. | RED | **YELLOW** | 0.065 | no | **YELLOW** | 0.225 | no |
| challenge_v3 | Can I sit in the recliner? My lips and tongue started swelling after the new antibiotic. | RED | **YELLOW** | 0.352 | no | RED | 0.736 | yes |
| challenge_v3 | Is it okay to drive to my physio appointment? I fainted in the kitchen this morning. | RED | **GREEN** | 0.053 | no | RED | 0.434 | no |
| challenge_v3 | shud i still do the quad sets? wound split open when i bent it, can see inside | RED | **YELLOW** | 0.249 | no | RED | 0.823 | yes |
| challenge_v3 | Calf is sore and swollen, and my knee is stiff. Can I do my stretches? | RED | **YELLOW** | 0.148 | no | **GREEN** | 0.050 | no |
| challenge_v3 | Mum's knee is swollen and she seems confused today. Kindly advise. | RED | RED | 0.384 | no | **YELLOW** | 0.396 | no |
| integration | I have severe calf pain and swelling, can I still do my exercises? | RED | **GREEN** | 0.011 | no | **GREEN** | 0.016 | no |
| unseen_test | lips swelling up after the new antibiotic | RED | RED | 0.173 | no | **YELLOW** | 0.042 | no |
| unseen_test | Throat feels tight and I'm wheezing after my first dose of the new painkiller | RED | RED | 0.295 | no | **YELLOW** | 0.166 | no |
| unseen_test | face puffin up after codeine, feels weird to swallow | RED | RED | 0.317 | no | **YELLOW** | 0.108 | no |
| unseen_test | Wheezy and chest tight since the tramadol, never had asthma | RED | **YELLOW** | 0.028 | no | **YELLOW** | 0.031 | no |
| unseen_test | throat closin up i think, took antibiotic 30 min ago | RED | RED | 0.368 | no | **YELLOW** | 0.205 | no |
| unseen_test | Itchy everywhere, lips fat, and feel dizzy since taking the first amoxicillin | RED | **YELLOW** | 0.100 | no | **YELLOW** | 0.092 | no |
| unseen_test | There's a whistling sound when I breathe out, began after the new medication | RED | RED | 0.211 | no | **YELLOW** | 0.180 | no |
| unseen_test | Lumpy itchy welts head to toe since the new tablets yesterday | RED | **YELLOW** | 0.083 | no | **YELLOW** | 0.061 | no |
| unseen_test | Allergy reaction came after antibiotic, lips swollen, little breathless also. Kindly guide. | RED | RED | 0.208 | no | **YELLOW** | 0.164 | no |
| unseen_test | Is it normal for my throat to feel tight after the antibiotic? | RED | **GREEN** | 0.004 | no | **GREEN** | 0.005 | no |
| unseen_test | puffy lips after antibiotic | RED | RED | 0.164 | no | **YELLOW** | 0.038 | no |
| unseen_test | Waiting for my wound check next week but the dressing has soaked right through with blood twice today. | RED | **YELLOW** | 0.031 | no | **YELLOW** | 0.036 | no |
| unseen_test | Since this afternoon my lower leg feels like it's about to burst and nothing I take makes any difference. | RED | RED | 0.213 | no | **YELLOW** | 0.191 | no |

### Integration rows whose level or email changed v2 -> v3

| set | text | label | v2 | v2 p(RED) | v2 email | v3 | v3 p(RED) | v3 email |
|---|---|---|---|---:|---|---|---:|---|
| integration | I have some swelling today | YELLOW | **RED** | 0.433 | no | YELLOW | 0.203 | no |
| integration | It hurts today | YELLOW | **RED** | 0.719 | yes | YELLOW | 0.334 | no |
| integration | Dizzy after the medicine this morning | YELLOW | **RED** | 0.575 | no | YELLOW | 0.255 | no |
| integration | I get dizzy after every dose | YELLOW | **RED** | 0.376 | no | YELLOW | 0.248 | no |
| integration | I feel dizzy on tramadol | YELLOW | **RED** | 0.687 | yes | **RED** | 0.508 | no |
| integration | Dizzy since I started the new course | YELLOW | **RED** | 0.444 | no | YELLOW | 0.350 | no |
| integration | Queasy in the mornings after my meds | YELLOW | YELLOW | 0.072 | no | **GREEN** | 0.017 | no |
| integration | My incision is itching alot, is it normal? | YELLOW | YELLOW | 0.036 | no | **GREEN** | 0.011 | no |
| integration | The skin along my incision line is very itchy | YELLOW | **RED** | 0.544 | no | YELLOW | 0.300 | no |
| integration | I get dizzy when I stand up after physio | YELLOW | **RED** | 0.444 | no | YELLOW | 0.357 | no |
| integration | Very fatigued after walking to the gate and back | GREEN | **RED** | 0.765 | yes | **RED** | 0.547 | no |
| integration | So drowsy in the afternoons these days | YELLOW | YELLOW | 0.055 | no | **GREEN** | 0.011 | no |
| integration | I forgot to take my pill | YELLOW | **RED** | 0.406 | no | YELLOW | 0.301 | no |
| integration | I accidentally took two tablets instead of one | YELLOW | **RED** | 0.731 | yes | **RED** | 0.589 | no |
| integration | I have a rash after taking my medicine | YELLOW | **RED** | 0.605 | no | YELLOW | 0.357 | no |
| integration | I stopped taking my blood thinner | YELLOW | **RED** | 0.581 | no | YELLOW | 0.299 | no |
| integration | Since I didn't take my medicine yesterday, my knee wound is worse | YELLOW | **RED** | 0.756 | yes | **RED** | 0.548 | no |
| integration | I feel scared to move my leg. | GREEN | **RED** | 0.601 | no | **RED** | 0.632 | yes |
| integration | I feel hopeless and cannot function. | YELLOW | **RED** | 0.753 | yes | **RED** | 0.527 | no |
| integration | I am not suicidal and have no thoughts of self-harm. | GREEN | **YELLOW** | 0.062 | no | GREEN | 0.024 | no |
| integration | Can you tell me a joke? | GREEN | **YELLOW** | 0.350 | no | **RED** | 0.426 | no |
| integration | My knee pain suddenly got much worse today. | YELLOW | **RED** | 0.762 | yes | **RED** | 0.555 | no |
| integration | My knee hurts. | YELLOW | **RED** | 0.725 | yes | YELLOW | 0.298 | no |
| integration | My knee pain is a 7 out of 10, it built up gradually, it's mostly behind the knee, it's been getting worse, and the joint feels stiff. | YELLOW | **RED** | 0.751 | yes | **RED** | 0.457 | no |
| integration | My pain suddenly got much worse today. | YELLOW | **RED** | 0.739 | yes | **RED** | 0.553 | no |
| integration | yes, it's swollen | YELLOW | **RED** | 0.427 | no | YELLOW | 0.252 | no |
| integration | My knee is swollen. | YELLOW | **RED** | 0.721 | yes | YELLOW | 0.349 | no |
| integration | My incision is swollen. | YELLOW | **RED** | 0.614 | no | YELLOW | 0.375 | no |
| integration | My hip hurts today. | YELLOW | **RED** | 0.681 | no | YELLOW | 0.353 | no |
| integration | My hip has started aching today. | YELLOW | **RED** | 0.665 | no | YELLOW | 0.336 | no |
| integration | My hip pain started gradually and it's about the same as before. | GREEN | **RED** | 0.387 | no | **YELLOW** | 0.111 | no |
| integration | My knee pain suddenly got worse today. | YELLOW | **RED** | 0.668 | no | YELLOW | 0.374 | no |
| integration | its getting worse | YELLOW | **RED** | 0.529 | no | YELLOW | 0.298 | no |
| integration | it's getting worse | YELLOW | **RED** | 0.616 | no | YELLOW | 0.345 | no |
| integration | my incision is more red today | YELLOW | **RED** | 0.649 | no | YELLOW | 0.398 | no |
| integration | I feel pain around the incision, near the staples. | YELLOW | **RED** | 0.388 | no | YELLOW | 0.203 | no |
| integration | My knee pain is 6 out of 10. | YELLOW | **RED** | 0.589 | no | YELLOW | 0.145 | no |
| integration | My knee is more swollen today and hurts. | YELLOW | **RED** | 0.809 | yes | **RED** | 0.559 | no |
| integration | I am anxious about moving my operated leg. | GREEN | GREEN | 0.053 | no | **YELLOW** | 0.057 | no |
| integration | I feel isolated and low because I can't do my usual routine. | GREEN | **RED** | 0.423 | no | **YELLOW** | 0.408 | no |
| integration | My leg hurts a lot after doing my exercises today. | YELLOW | **RED** | 0.533 | no | YELLOW | 0.410 | no |
| integration | My shoulder has been hurting for a week. | YELLOW | **RED** | 0.619 | no | YELLOW | 0.229 | no |
| integration | There is drainage and redness around my incision. | YELLOW | **RED** | 0.366 | no | YELLOW | 0.322 | no |
| integration | I'm not using the walker anymore. | GREEN | **YELLOW** | 0.028 | no | GREEN | 0.016 | no |
| integration | I can bend to 80 degrees, my pain is 3/10, and I am walking independently. | GREEN | **RED** | 0.414 | no | **YELLOW** | 0.319 | no |
| integration | I can bend my knee to around 80 degrees. | GREEN | **YELLOW** | 0.079 | no | GREEN | 0.020 | no |
| integration | I can bend to 80 degrees. | GREEN | **YELLOW** | 0.151 | no | GREEN | 0.032 | no |
| integration | I can bend to about 85 degrees | GREEN | **YELLOW** | 0.194 | no | GREEN | 0.024 | no |
| integration | I'm using a cane | GREEN | **YELLOW** | 0.091 | no | GREEN | 0.034 | no |
| integration | I can bend to 90 degrees | GREEN | **RED** | 0.423 | no | GREEN | 0.061 | no |
| integration | I can bend to 85 degrees | GREEN | **YELLOW** | 0.313 | no | GREEN | 0.044 | no |
| integration | I can walk for half an hour | GREEN | **YELLOW** | 0.066 | no | GREEN | 0.012 | no |
| integration | walking more than ten minutes now | GREEN | **YELLOW** | 0.260 | no | GREEN | 0.045 | no |
| integration | I go up the stairs foot over foot | GREEN | **RED** | 0.553 | no | GREEN | 0.110 | no |
| integration | I can bend to 85 degrees and I did my exercises | GREEN | **YELLOW** | 0.126 | no | GREEN | 0.041 | no |
| integration | I'm using a stick | GREEN | **YELLOW** | 0.073 | no | GREEN | 0.035 | no |
| integration | I can bend to 95 | GREEN | **RED** | 0.357 | no | GREEN | 0.094 | no |
| integration | yes, heel slides give me a sharp pain | YELLOW | YELLOW | 0.083 | no | **GREEN** | 0.029 | no |
| integration | My knee hurts today. It came on gradually, I feel it mostly behind the knee, and it's about the same as before. | GREEN | **RED** | 0.521 | no | **YELLOW** | 0.365 | no |
| integration | My pain suddenly got worse today, and it's mostly behind the knee. | YELLOW | **RED** | 0.544 | no | YELLOW | 0.400 | no |
| integration | My knee is swollen and sore. | YELLOW | **RED** | 0.740 | yes | YELLOW | 0.359 | no |
| integration | My hip is swollen and sore. | YELLOW | **RED** | 0.771 | yes | **RED** | 0.441 | no |
| integration | My knee hurts a bit. | GREEN | **RED** | 0.425 | no | **YELLOW** | 0.054 | no |
| integration | My knee is sore. | GREEN | **RED** | 0.570 | no | **YELLOW** | 0.133 | no |

### Integration rows labelled non-RED that v2 or v3 calls RED

| set | text | label | v2 | v2 p(RED) | v2 email | v3 | v3 p(RED) | v3 email |
|---|---|---|---|---:|---|---|---:|---|
| integration | My wound looks a bit red today. | YELLOW | **RED** | 0.477 | no | **RED** | 0.430 | no |
| integration | I have some swelling today | YELLOW | **RED** | 0.433 | no | YELLOW | 0.203 | no |
| integration | My knee really hurts | YELLOW | **RED** | 0.890 | yes | **RED** | 0.715 | yes |
| integration | It hurts today | YELLOW | **RED** | 0.719 | yes | YELLOW | 0.334 | no |
| integration | Hi, I am Rishi and I feel dizzy | YELLOW | **RED** | 0.742 | yes | **RED** | 0.609 | yes |
| integration | I feel dizzy after my tablet | YELLOW | **RED** | 0.765 | yes | **RED** | 0.668 | yes |
| integration | Dizzy after the medicine this morning | YELLOW | **RED** | 0.575 | no | YELLOW | 0.255 | no |
| integration | I get dizzy after every dose | YELLOW | **RED** | 0.376 | no | YELLOW | 0.248 | no |
| integration | I feel dizzy after my painkiller | YELLOW | **RED** | 0.838 | yes | **RED** | 0.720 | yes |
| integration | I feel dizzy on tramadol | YELLOW | **RED** | 0.687 | yes | **RED** | 0.508 | no |
| integration | Dizzy since I started the new course | YELLOW | **RED** | 0.444 | no | YELLOW | 0.350 | no |
| integration | The blood thinner makes me light headed | YELLOW | **RED** | 0.621 | no | **RED** | 0.438 | no |
| integration | The skin along my incision line is very itchy | YELLOW | **RED** | 0.544 | no | YELLOW | 0.300 | no |
| integration | I get dizzy when I stand up after physio | YELLOW | **RED** | 0.444 | no | YELLOW | 0.357 | no |
| integration | Feeling light-headed when I get out of bed in the morning | YELLOW | **RED** | 0.672 | no | **RED** | 0.485 | no |
| integration | Very fatigued after walking to the gate and back | GREEN | **RED** | 0.765 | yes | **RED** | 0.547 | no |
| integration | Feeling queasy and dizzy this evening | YELLOW | **RED** | 0.715 | yes | **RED** | 0.643 | yes |
| integration | I forgot to take my pill | YELLOW | **RED** | 0.406 | no | YELLOW | 0.301 | no |
| integration | I accidentally took two tablets instead of one | YELLOW | **RED** | 0.731 | yes | **RED** | 0.589 | no |
| integration | I have a rash after taking my medicine | YELLOW | **RED** | 0.605 | no | YELLOW | 0.357 | no |
| integration | I stopped taking my blood thinner | YELLOW | **RED** | 0.581 | no | YELLOW | 0.299 | no |
| integration | It's been 2 hours and pain level is 5 | GREEN | **RED** | 0.848 | yes | **RED** | 0.629 | yes |
| integration | Since I didn't take my medicine yesterday, my knee wound is worse | YELLOW | **RED** | 0.756 | yes | **RED** | 0.548 | no |
| integration | I cannot keep fluids down and I am hardly urinating. | YELLOW | **RED** | 0.782 | yes | **RED** | 0.674 | yes |
| integration | I feel scared to move my leg. | GREEN | **RED** | 0.601 | no | **RED** | 0.632 | yes |
| integration | I feel hopeless and cannot function. | YELLOW | **RED** | 0.753 | yes | **RED** | 0.527 | no |
| integration | Can you tell me a joke? | GREEN | **YELLOW** | 0.350 | no | **RED** | 0.426 | no |
| integration | My knee pain suddenly got much worse today. | YELLOW | **RED** | 0.762 | yes | **RED** | 0.555 | no |
| integration | My pain is 8 out of 10 and suddenly got worse. | YELLOW | **RED** | 0.891 | yes | **RED** | 0.816 | yes |
| integration | My knee hurts. | YELLOW | **RED** | 0.725 | yes | YELLOW | 0.298 | no |
| integration | My knee is sore and a bit swollen. It started suddenly, I feel it mostly behind the knee, it's been getting worse, and the knee feels stiff. | YELLOW | **RED** | 0.840 | yes | **RED** | 0.696 | yes |
| integration | My knee pain is a 7 out of 10, it built up gradually, it's mostly behind the knee, it's been getting worse, and the joint feels stiff. | YELLOW | **RED** | 0.751 | yes | **RED** | 0.457 | no |
| integration | My pain suddenly got much worse today. | YELLOW | **RED** | 0.739 | yes | **RED** | 0.553 | no |
| integration | yes, it's swollen | YELLOW | **RED** | 0.427 | no | YELLOW | 0.252 | no |
| integration | My knee is swollen. | YELLOW | **RED** | 0.721 | yes | YELLOW | 0.349 | no |
| integration | My incision is swollen. | YELLOW | **RED** | 0.614 | no | YELLOW | 0.375 | no |
| integration | My wound is red and swollen. | YELLOW | **RED** | 0.866 | yes | **RED** | 0.795 | yes |
| integration | My hip hurts today. | YELLOW | **RED** | 0.681 | no | YELLOW | 0.353 | no |
| integration | My hip has started aching today. | YELLOW | **RED** | 0.665 | no | YELLOW | 0.336 | no |
| integration | My knee pain is a 6 out of 10, it came on suddenly. | YELLOW | **RED** | 0.896 | yes | **RED** | 0.802 | yes |
| integration | My knee pain is a 3 out of 10, it came on suddenly, I mostly feel it behind the knee, and I already took my pain medication. | GREEN | **RED** | 0.866 | yes | **RED** | 0.800 | yes |
| integration | My hip pain started gradually and it's about the same as before. | GREEN | **RED** | 0.387 | no | **YELLOW** | 0.111 | no |
| integration | My knee pain suddenly got worse today. | YELLOW | **RED** | 0.668 | no | YELLOW | 0.374 | no |
| integration | My knee pain is 6 out of 10, it started suddenly behind the knee and it is swollen. | YELLOW | **RED** | 0.877 | yes | **RED** | 0.780 | yes |
| integration | its getting worse | YELLOW | **RED** | 0.529 | no | YELLOW | 0.298 | no |
| integration | it's getting worse | YELLOW | **RED** | 0.616 | no | YELLOW | 0.345 | no |
| integration | my incision is more red today | YELLOW | **RED** | 0.649 | no | YELLOW | 0.398 | no |
| integration | My knee pain is 6 out of 10, it started suddenly, mostly behind the knee, it's swollen, and it's getting worse. | YELLOW | **RED** | 0.869 | yes | **RED** | 0.720 | yes |
| integration | I feel pain around the incision, near the staples. | YELLOW | **RED** | 0.388 | no | YELLOW | 0.203 | no |
| integration | My knee pain is 6 out of 10. | YELLOW | **RED** | 0.589 | no | YELLOW | 0.145 | no |
| integration | 7 out of 10, started suddenly | YELLOW | **RED** | 0.957 | yes | **RED** | 0.925 | yes |
| integration | My knee pain is 8 out of 10 and came on suddenly. | YELLOW | **RED** | 0.932 | yes | **RED** | 0.857 | yes |
| integration | it feels warm and I had chills last night | YELLOW | **RED** | 0.810 | yes | **RED** | 0.781 | yes |
| integration | My knee is more swollen today and hurts. | YELLOW | **RED** | 0.809 | yes | **RED** | 0.559 | no |
| integration | The area around my joint feels really tender and inflamed. | YELLOW | **RED** | 0.566 | no | **RED** | 0.440 | no |
| integration | Why does my leg feel so stiff and achy this morning? | GREEN | **RED** | 0.742 | yes | **RED** | 0.732 | yes |
| integration | I feel isolated and low because I can't do my usual routine. | GREEN | **RED** | 0.423 | no | **YELLOW** | 0.408 | no |
| integration | I don't feel like doing anything today and my leg feels stiff. | GREEN | **RED** | 0.882 | yes | **RED** | 0.881 | yes |
| integration | My leg hurts a lot after doing my exercises today. | YELLOW | **RED** | 0.533 | no | YELLOW | 0.410 | no |
| integration | My shoulder has been hurting for a week. | YELLOW | **RED** | 0.619 | no | YELLOW | 0.229 | no |
| integration | There is drainage and redness around my incision. | YELLOW | **RED** | 0.366 | no | YELLOW | 0.322 | no |
| integration | I can bend to 80 degrees, my pain is 3/10, and I am walking independently. | GREEN | **RED** | 0.414 | no | **YELLOW** | 0.319 | no |
| integration | My wound is red and leaking. | YELLOW | **RED** | 0.864 | yes | **RED** | 0.832 | yes |
| integration | My wound looks more red today and it's leaking some fluid. | YELLOW | **RED** | 0.740 | yes | **RED** | 0.690 | yes |
| integration | I can bend to 90 degrees | GREEN | **RED** | 0.423 | no | GREEN | 0.061 | no |
| integration | I go up the stairs foot over foot | GREEN | **RED** | 0.553 | no | GREEN | 0.110 | no |
| integration | I started driving again and I'm back at work | GREEN | **RED** | 0.877 | yes | **RED** | 0.682 | yes |
| integration | I can bend to 95 | GREEN | **RED** | 0.357 | no | GREEN | 0.094 | no |
| integration | My knee is sore and a bit tender. It started suddenly, I feel it mostly behind the knee, it's been getting worse, and the knee feels stiff. | YELLOW | **RED** | 0.864 | yes | **RED** | 0.714 | yes |
| integration | My knee hurts today. It came on gradually, I feel it mostly behind the knee, and it's about the same as before. | GREEN | **RED** | 0.521 | no | **YELLOW** | 0.365 | no |
| integration | My pain suddenly got worse today, and it's mostly behind the knee. | YELLOW | **RED** | 0.544 | no | YELLOW | 0.400 | no |
| integration | My knee is swollen and sore. | YELLOW | **RED** | 0.740 | yes | YELLOW | 0.359 | no |
| integration | My hip is swollen and sore. | YELLOW | **RED** | 0.771 | yes | **RED** | 0.441 | no |
| integration | My ankle is swollen and sore. | YELLOW | **RED** | 0.844 | yes | **RED** | 0.722 | yes |
| integration | My knee hurts a bit. | GREEN | **RED** | 0.425 | no | **YELLOW** | 0.054 | no |
| integration | My knee is sore. | GREEN | **RED** | 0.570 | no | **YELLOW** | 0.133 | no |

Live code path (`classifier_triage.evaluate`) vs cached probabilities, v3:
- test: skipped (default loads M2:m2_main_v2_it3_seed0, not M2:m2_main_v3_it3_seed0)
- challenge: skipped (default loads M2:m2_main_v2_it3_seed0, not M2:m2_main_v3_it3_seed0)
- challenge_v2: skipped (default loads M2:m2_main_v2_it3_seed0, not M2:m2_main_v3_it3_seed0)
- challenge_v3: skipped (default loads M2:m2_main_v2_it3_seed0, not M2:m2_main_v3_it3_seed0)
- integration: skipped (default loads M2:m2_main_v2_it3_seed0, not M2:m2_main_v3_it3_seed0)
