# Routing benchmark -- `heldout_v3_hip_precautions`

- commit `4286cd5`, 2026-11-12; case set `heldout_v3`, 12 cases; semantic_first=False; thresholds {'SEMANTIC_MIN_SCORE': 0.35, 'SEMANTIC_MIN_MARGIN': 0.04}
- classifier run 20.0s, orchestrator run 0.3s
- a prediction is correct when it is in the case's acceptable set; *clear only* excludes debatable cases; *openings* excludes answers to a pending question (cases.py has six; heldout_v2 none), which carry no routable signal on their own
- orchestrator *lenient*: at least one dispatched agent is acceptable (the eval/agents definition); *strict*: every dispatched agent is acceptable

## Per agent

| Agent | n | Classifier | Classifier, clear only | Classifier, openings | Orchestrator (lenient) | Orchestrator (strict) | Orchestrator, openings |
|---|---|---|---|---|---|---|---|
| Rehabilitation | 3 | 2/3 (67%) | - | 2/3 (67%) | 2/3 (67%) | 2/3 (67%) | 2/3 (67%) |
| Daily Activity | 9 | 7/9 (78%) | - | 7/9 (78%) | 7/9 (78%) | 7/9 (78%) | 7/9 (78%) |
| **All** | 12 | **9/12 (75%)** | - | 9/12 (75%) | **9/12 (75%)** | 9/12 (75%) | 9/12 (75%) |

Orchestrator pre-emption cases (emergency / out_of_scope expected): -; multi-agent turns: 0; pre-empted: {}.

Decision paths: `deterministic` 6, `fallback_low_margin` 1, `semantic` 5

## Classifier misses, grouped by rule

### overbroad keyword (1)

| Case | Message | Expected (acceptable) | Got | Path | Rule |
|---|---|---|---|---|---|
| V001 | "Which hip movements are banned for the first few weeks after my hip replacement?" *debatable* | rehabilitation (rehabilitation, daily_activity) | recovery_progress | deterministic | overbroad keyword: recovery_progress matched weeks |

### semantic prototype pull (1)

| Case | Message | Expected (acceptable) | Got | Path | Rule |
|---|---|---|---|---|---|
| V011 | "Can I put on my socks myself or should I use a sock aid?" *debatable* | daily_activity (daily_activity, rehabilitation) | wound_care | semantic | semantic prototype pull: wound_care 0.35 via 'Can I change my wound dressing today?', margin 0.09 |

### semantic threshold (1)

| Case | Message | Expected (acceptable) | Got | Path | Rule |
|---|---|---|---|---|---|
| V003 | "Doctor said don't cross the legs, till when I have to follow that?" *debatable* | daily_activity (daily_activity, rehabilitation) | recovery_progress | fallback_low_margin | semantic threshold (margin 0.04 < 0.04) -> no keyword -> default recovery_progress |

## Orchestrator misses (lenient)

| Case | Message | Expected (acceptable) | Orchestrator intent | Target agent | Classifier said |
|---|---|---|---|---|---|
| V001 | "Which hip movements are banned for the first few weeks after my hip replacement?" | rehabilitation (rehabilitation, daily_activity) | recovery_progress | RecoveryProgressAgent | recovery_progress (deterministic) |
| V003 | "Doctor said don't cross the legs, till when I have to follow that?" | daily_activity (daily_activity, rehabilitation) | recovery_progress | RecoveryProgressAgent | recovery_progress (fallback_low_margin) |
| V011 | "Can I put on my socks myself or should I use a sock aid?" | daily_activity (daily_activity, rehabilitation) | wound_care | WoundCareAgent | wound_care (semantic) |

## Orchestrator differs from the classifier

| Case | Message | Classifier | Orchestrator | Why |
|---|---|---|---|---|

## Every case

| Case | Source | Message | Expected (acceptable) | Conf. | Classifier | Path | Orchestrator |
|---|---|---|---|---|---|---|---|
| V001 | heldout_v3:hip_precautions | "Which hip movements are banned for the first few weeks after my hip replacement?" | rehabilitation (rehabilitation, daily_activity) | debatable | recovery_progress **x** | deterministic | recovery_progress **x** |
| V002 | heldout_v3:hip_precautions | "Is it safe to sit on the low sofa in our hall or is it too low for my new hip?" | daily_activity (daily_activity, rehabilitation) | debatable | daily_activity | deterministic | daily_activity |
| V003 | heldout_v3:hip_precautions | "Doctor said don't cross the legs, till when I have to follow that?" | daily_activity (daily_activity, rehabilitation) | debatable | recovery_progress **x** | fallback_low_margin | recovery_progress **x** |
| V004 | heldout_v3:hip_precautions | "How do I tie my shoe laces without bending too much at the hip?" | daily_activity (daily_activity, rehabilitation) | debatable | rehabilitation | semantic | rehabilitation |
| V005 | heldout_v3:hip_precautions | "Can I lie on my side at night, and should I keep a pillow between the knees?" | daily_activity (daily_activity, rehabilitation) | debatable | daily_activity | semantic | daily_activity |
| V006 | heldout_v3:hip_precautions | "My in-laws' house has only an Indian-style toilet, can I squat on it with the new hip?" | daily_activity (daily_activity, rehabilitation) | debatable | daily_activity | deterministic | daily_activity |
| V007 | heldout_v3:hip_precautions | "Sitting cross-legged on the floor for meals, is that allowed after hip surgery?" | daily_activity (daily_activity, rehabilitation) | debatable | daily_activity | deterministic | daily_activity |
| V008 | heldout_v3:hip_precautions | "What positions should my hip not go into while it heals?" | rehabilitation (rehabilitation, daily_activity) | debatable | daily_activity | semantic | daily_activity |
| V009 | heldout_v3:hip_precautions | "Is twisting my body while standing at the kitchen counter risky for the new hip?" | daily_activity (daily_activity, rehabilitation) | debatable | daily_activity | deterministic | daily_activity |
| V010 | heldout_v3:hip_precautions | "How low can a chair be before it is unsafe for my operated hip?" | daily_activity (daily_activity, rehabilitation) | debatable | daily_activity | deterministic | daily_activity |
| V011 | heldout_v3:hip_precautions | "Can I put on my socks myself or should I use a sock aid?" | daily_activity (daily_activity, rehabilitation) | debatable | wound_care **x** | semantic | wound_care **x** |
| V012 | heldout_v3:knee_precautions | "After my knee replacement, are there positions I must avoid, like kneeling or keeping a pillow under the knee?" | rehabilitation (rehabilitation, daily_activity) | debatable | daily_activity | semantic | daily_activity |
