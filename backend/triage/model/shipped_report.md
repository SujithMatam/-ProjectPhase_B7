| set | mode | RED recall | 95% CI | RED prec. | macro F1 | RED->GREEN | RED->YELLOW | GREEN->RED | YELLOW->RED | RED calls / 100 | emails / 100 | RED rows emailed | non-RED emails | suppressed (of which RED) |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| main test (n=266, RED 104) | rules (default) | 0.192 | 0.128-0.278 | 0.667 | 0.357 | 74 | 10 | 5 | 5 | 11.3 | 11.3 | 20/104 | 10 |  |
| main test (n=266, RED 104) | classifier only (thresholded) | 0.923 | 0.856-0.961 | 0.706 | 0.678 | 2 | 6 | 6 | 34 | 51.1 |  |  |  |  |
| main test (n=266, RED 104) | **hybrid (shipped)** | 0.962 | 0.905-0.985 | 0.714 | 0.703 | 0 | 4 | 6 | 34 | 52.6 | 35.3 | 83/104 | 11 | 46 (17) |
| challenge (n=150, RED 58) | rules (default) | 0.241 | 0.150-0.365 | 0.438 | 0.333 | 39 | 5 | 12 | 6 | 21.3 | 21.3 | 14/58 | 18 |  |
| challenge (n=150, RED 58) | classifier only (thresholded) | 0.966 | 0.883-0.990 | 0.636 | 0.618 | 0 | 2 | 6 | 26 | 58.7 |  |  |  |  |
| challenge (n=150, RED 58) | **hybrid (shipped)** | 1.000 | 0.938-1.000 | 0.644 | 0.627 | 0 | 0 | 6 | 26 | 60.0 | 44.0 | 54/58 | 12 | 24 (4) |
| unseen-scenario test (n=275, RED 105) | rules (default) | 0.057 | 0.026-0.119 | 0.500 | 0.273 | 81 | 18 | 4 | 2 | 4.4 | 4.4 | 6/105 | 6 |  |
| unseen-scenario test (n=275, RED 105) | classifier only (thresholded) | 0.848 | 0.767-0.904 | 0.636 | 0.604 | 6 | 10 | 13 | 38 | 50.9 |  |  |  |  |
| unseen-scenario test (n=275, RED 105) | **hybrid (shipped)** | 0.971 | 0.919-0.990 | 0.667 | 0.640 | 1 | 2 | 13 | 38 | 55.6 | 36.7 | 80/105 | 21 | 52 (22) |

Shipped classifier: `M2:m2_main_it3_seed4`, t_red 0.217, t_yel 0.237, t_alert 0.637. Unseen-scenario rows use the unseen-split M2 (seed 0) cached probabilities with that split's val thresholds (t_red 0.097, t_alert 0.604); 191 of its 275 test rows are in the main train split, so the shipped weights are not scored there. "classifier only" is the same run without overrides (no gate). Rules mode emails on every RED.

Per-scenario RED recall, unseen-scenario test:

| scenario | RED rows | rules | classifier only | hybrid |
|---|---:|---:|---:|---:|
| ALLERGIC_REACTION | 40 | 1/40 | 38/40 | 38/40 |
| FOLLOWUP_ADMIN | 3 | 0/3 | 2/3 | 2/3 |
| HIGH_FEVER | 50 | 1/50 | 38/50 | 50/50 |
| MOOD_SLEEP | 4 | 1/4 | 3/4 | 4/4 |
| UNCONTROLLED_PAIN | 8 | 3/8 | 8/8 | 8/8 |

The 7 audit_regression rows (challenge set):

| id | text | label | rules | rules email | hybrid | reasons | p(RED) | email |
|---|---|---|---|---|---|---|---:|---|
| CH-144 | No chest pain, no chills | GREEN | **RED** | yes | **YELLOW** | classifier | 0.082 | no |
| CH-145 | I don't have shortness of breath | GREEN | **RED** | yes | **RED** | classifier | 0.744 | yes |
| CH-146 | I cannot breathe properly | RED | **GREEN** | no | RED | classifier | 0.919 | yes |
| CH-147 | I can’t breathe | RED | **GREEN** | no | RED | classifier | 0.966 | yes |
| CH-148 | fever of 39 | RED | **GREEN** | no | RED | high_fever, classifier | 0.695 | yes |
| CH-149 | My knee is a little red and swollen | YELLOW | **RED** | yes | **RED** | classifier | 0.920 | yes |
| CH-150 | fluid coming from my incision | YELLOW | **GREEN** | no | **RED** | classifier | 0.669 | yes |

Bold = differs from the label.

RED messages the hybrid pipeline still does not call RED:

| set | id | hybrid | p(RED) | text |
|---|---|---|---:|---|
| test | ALLERGIC_REACTION-013 | YELLOW | 0.101 | Wheezy and chest tight since the tramadol, never had asthma |
| test | COMPARTMENT-012 | YELLOW | 0.123 | My father is shouting with pain in leg after knee surgery. Tramadol given 1 hour back but no relief. Leg is tight. |
| test | COMPARTMENT-058 | YELLOW | 0.041 | Is so much pain normal on day 2? Leg is very tight and stiff like wood and no medicine is working. |
| test | WOUND_OPEN-030 | YELLOW | 0.096 | When I bend the knee the cut gapes and I can see right into it; when I straighten it closes again |
| unseen_test | ALLERGIC_REACTION-013 | YELLOW | 0.036 | Wheezy and chest tight since the tramadol, never had asthma |
| unseen_test | ALLERGIC_REACTION-032 | GREEN | 0.007 | Is it normal for my throat to feel tight after the antibiotic? |
| unseen_test | FOLLOWUP_ADMIN-014 | YELLOW | 0.015 | Waiting for my wound check next week but the dressing has soaked right through with blood twice today. |
