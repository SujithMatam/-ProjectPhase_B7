# Step 2: why R110, R172 and R180 fell to `fallback_low_margin`, and the fix

Date: 2026-11-12. Branch `feature/agents-proactive`, on top of `07e6774` (step 1).

## Diagnosis

Main added five Recovery prototypes. In the semantic step, intake is removed from the ranking (no intake cue), so each message's best Recovery prototype competes directly with the right agent's best prototype. Similarities are cosine scores with all-MiniLM-L6-v2:

| Case | Message | Right agent (best prototype, score) | Recovery (best prototype, score) | Margin | Recovery best without main's 5 |
|---|---|---|---|---|---|
| R110 | "How to straigten my knee fully, it is not going straight" | Rehab: "How should I do my rehab stretches?" 0.438 | "What are the typical recovery milestones for knee surgery?" 0.403 | 0.035 < 0.04 | 0.214 |
| R172 | "When can I travel by bus or auto to the hospital?" | Daily: "When am I allowed to go up steps and get behind the wheel?" 0.411 | "When do most patients walk without a walking stick?" **0.438** (top 1) | 0.027 | 0.275 |
| R180 | "Is it ok to go for a short walk outside daily?" | Daily: same prototype 0.463 | "When do most patients walk without a walking stick?" **0.480** (top 1) | 0.016 | 0.369 |

When the margin is under `SEMANTIC_MIN_MARGIN` (0.04), the classifier falls back to the keyword rules. No keyword matches, so the message gets the default, `recovery_progress`.

Two of main's prototypes are behind this:
- "What are the typical recovery milestones for knee surgery?" scores about 0.36 to 0.41 on almost any sentence with "knee" in it.
- "When do most patients walk without a walking stick?" pulls "when can I ... / walk ..." activity questions.

**Neither is mislabelled.** Both are real recovery-milestone questions, and both are why R100 ("When will the knee feel like normal again?", 0.590) and R102 now route correctly. **Nothing was deleted or reworded.**

The real gap is on the other side. Rehab had no prototype about a joint that will not straighten or bend fully. Daily Activity had none about going outside or travelling. Its only "when can I go/drive" prototype is about stairs and driving.

## Fix: four prototypes added (two Rehab, two Daily Activity)

| Intent | New prototype | Nearest routing case (cases.py + heldout_v2) | Cosine |
|---|---|---|---|
| Rehabilitation | "Which exercises help the leg straighten out fully?" | H020 "How many times a day should I practise straightening the leg?" | 0.687 |
| Rehabilitation | "How can I get more bend and straightening in the operated joint?" | H022 "The knee will not fully bend yet, what can I practise at home?" | 0.647 |
| Daily Activity | "Can I step out of the house for a short stroll?" | R180 "Is it ok to go for a short walk outside daily?" | 0.642 |
| Daily Activity | "When can I travel by car or public transport?" | R172 "When can I travel by bus or auto to the hospital?" | 0.644 |

All four are at most 0.687 to every one of the 262 routing cases (limit 0.85). Checked with `eval/routing/check_near_duplicates.py prototypes ...`.

**How they were chosen**
- The first candidates used "knee" in a Rehab prototype ("Which exercises help me get my knee fully straight?") and "neighbourhood" in a Daily one. That fixed the three cases but sent R058 "Am I on track with my knee?" to Rehab.
- That first try was scored on both sets, so one held-out result was seen: H029 "My neighbour was walking freely by now, am I slow?" went to Daily Activity.
- After that, candidates were scored on `cases.py` only. `heldout_v2` was scored once, on the final four.
- A fifth candidate ("Is it all right to go out for errands on my own?") changed nothing, so it was dropped.

## Result

| Set | Before step 2 (step 1) | After step 2 |
|---|---|---|
| cases.py, classifier | 200/230 | **204/230** (R110 rehab, R172/R178/R180 daily activity) |
| cases.py, orchestrator lenient / strict | 202 / 188 | **206 / 192** |
| heldout_v2, classifier | 30/30 | 30/30 |
| heldout_v2, orchestrator lenient / strict | 30 / 30 | 30 / 30 |

These are the only rows that changed. R178 "Can I do sweeping and mopping of the house?" was a low-confidence miss and now wins semantically for Daily Activity.

**Main's earlier fixes still hold:**
- R100: recovery, semantic
- R021: wound, keyword `surgical cut`
- R030: mental wellbeing, keyword `feeling down`
- R102: recovery, semantic

**One weaker held-out row.** H029 "My neighbour was walking freely by now, am I slow?" is still `recovery_progress`. But its margin fell from 0.046 to 0.022, so it now gets recovery from the low-margin default, not from a semantic win.

Results:
- `eval/routing/results/step2_recovery_margin.{json,md}`
- `eval/routing/results/heldout_v2_step2.{json,md}`
