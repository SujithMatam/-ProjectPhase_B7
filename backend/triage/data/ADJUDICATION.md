# Adjudication (guideline v1 -> v1.1)

Outcome of the 6 disagreements in `ANNOTATION_DISAGREEMENTS.md`, the guideline rules added to settle
them, and every other row (splits and challenge) that the new rules label differently. Changes are
listed in `adjudication.tsv` and applied by the builders **after** split assignment, which still runs
on the pre-adjudication labels. The rebuild was checked row by row against commit 52f83d6: every id is
in the same split as before and `label` is the only field that changed, on exactly the 12 rows below.
`authored/*.tsv` and `challenge_source.tsv` keep the original author labels.

The adjudication decisions (section 1) were made by the project owner. The rule search (section 3)
was done by claude-opus-5-5 on all 1,945 rows (splits + challenge): a keyword filter (blood, bleed,
dressing, bandage, pad, plaster, ooze, seep, spot, stain, bruise, injection, stitch, suture, thread,
staple, strip, plus loose/poking/sticking out/streak/blotch) found 320 rows, of which all 222 non-RED
rows and the RED rows mentioning bruises, dressings or stitches were read; a second filter found 62
rows mentioning a clinician's assessment, all read. It was not reviewed by a clinician.

## 1. Guideline additions (LABELLING_GUIDELINE.md v1.1)

- **GREEN:** a small spot or line of blood on the dressing that is not spreading; a small bruise near
  the operated joint or an injection site; a loose suture end with no redness, pulling or discharge.
- **YELLOW:** dressing ooze that is spreading or increasing.
- **Rule 3 addition:** a finding a clinician has already assessed and called fine stays GREEN while it
  is unchanged; if it gets worse, label by the change.

## 2. The 6 annotation disagreements

| id | set | text | old | new | decision |
|---|---|---|---|---|---|
| `MINOR_BLEEDING-029` | train | A thin line of blood along the edge of the dressing. Temp 37.1, feel OK. | YELLOW | **GREEN** | new GREEN bullet (line of blood, not spreading) |
| `MINOR_BLEEDING-036` | train | Small blood spot on dressing and some bruise also near knee. Is it due to the injection they are giving? | YELLOW | **GREEN** | new GREEN bullet (spot + bruise near joint) |
| `SEPSIS_WOUND-060` | train | I was worried it was infected but the nurse said the pink fluid is just normal drainage; still a little damp today | YELLOW | **GREEN** | rule 3 addition (assessed, called fine, unchanged) |
| `WOUND_IRRITATION-021` | train | A loose thread is hanging from the end of my incision. Should I cut it? | YELLOW | **GREEN** | new GREEN bullet (loose suture end) |
| `CH-131` | challenge (benign_scary_word) | Had beetroot salad last night and my urine is pinkish today, that's the beetroot, right? | GREEN | **YELLOW** | rule 7 (patient's own explanation does not lower the label) |
| `CH-102` | challenge (numeric_in_text) | Ankle swelling is 2 cm bigger than last week but goes down overnight | YELLOW | YELLOW (kept) | YELLOW bullet "swelling getting worse over the weeks but still settling" |

## 3. Other rows the new rules decide differently (applied)

| id | split | text | old | new |
|---|---|---|---|---|
| `MINOR_BLEEDING-001` | test | A small spot of fresh blood has come through my dressing, about the size of a fingernail. | YELLOW | GREEN |
| `MINOR_BLEEDING-008` | train | bit of blood on my plaster agn, not much, shud i change it | YELLOW | GREEN |
| `MINOR_BLEEDING-014` | train | Week 2. The pad over my knee has a small fresh red streak this evening after I walked more than usual. | YELLOW | GREEN |
| `MINOR_BLEEDING-016` | val | Small ooze of blood on the dressing and a new bruise on my tummy where I inject. | YELLOW | GREEN |
| `MINOR_BLEEDING-051` | train | knee dressing pe thoda blood stain aa gaya, i am on clexane injection. shud i change dressing? | YELLOW | GREEN |
| `BLEEDING_ANTICOAG-056` | train | small ooze of blood on the dressin, about the size of a 10p | YELLOW | GREEN |
| `WOUND_IRRITATION-017` | test | stich at the bottm of my knee is sticking out and rubbing on my trousers | YELLOW | GREEN |

Split column = main split (`splits/`). In the unseen-scenario split all 11 changed split rows are in
train. No challenge row other than `CH-131` changed. No RED row changed. No GREEN row became YELLOW
under the spreading-ooze rule or the "got worse" half of rule 3 (the GREEN rows with a clinician's
assessment are all unchanged or improving, e.g. `BLEEDING_ANTICOAG-063`, `MINOR_BLEEDING-050`, `CH-126`).

## 4. Considered and kept (closest calls; the adjudicator may want to overrule)

The new GREEN bullet speaks of blood **on the dressing** that is **small** and **not spreading**. Rows
outside that wording were kept, with rule 6 (when torn, pick the higher level) as the tie-break.

| id | label | text | why kept |
|---|---|---|---|
| `MINOR_BLEEDING-025` | YELLOW | Couple of drops of blood when a staple got nicked by my trousers. | drops from the wound, not described on the dressing |
| `MINOR_BLEEDING-052` | YELLOW | lil bit of blood frm the staple line wen i stood up, seems to of stopped now | as above; stopped bleeding still counts (rule 3) |
| `MINOR_BLEEDING-047` | YELLOW | Every time I peel the dressing back there's a little bead of red sitting at one end of the wound. | at the wound, recurring each time |
| `MINOR_BLEEDING-015` | YELLOW | Doctor, from the stitches some drops of blood came after I was walking. Now it is less. Should I worry? | still bleeding ("now it is less") |
| `MINOR_BLEEDING-041` | YELLOW | Small bleed from the hip wound after I got out of the car awkwardly. Dabbed it and it's slowed. | active bleed, slowing |
| `MINOR_BLEEDING-004` | YELLOW | Little blood is coming on bandage from evening. I am taking blood thinner injection. Kindly advise. | ongoing ooze since the evening = increasing |
| `MINOR_BLEEDING-045` | YELLOW | Myself his son. Papa's wound is having some blood oozing since afternoon, we put cotton and it reduced. | ongoing ooze |
| `MINOR_BLEEDING-030` | YELLOW | How much blood on the dressing is too much? There's a patch about 3 cm across today. | 3 cm patch, not described as small |
| `MINOR_BLEEDING-031` | YELLOW | dressing has a red blotch on it, wasnt there this mornin | size not given |
| `MINOR_BLEEDING-042` | YELLOW | blood thinner tablet started, now small small bruises coming on legs. normal or not?? | several new bruises on the legs, not one near the joint or injection site |
| `MINOR_BLEEDING-024`, `-049`, `BLEEDING_ANTICOAG-060`, `MINOR_BLEEDING-044` | YELLOW | spots "keep showing through", bruise "crept round", spot "increasing slowly", blood "spreading out" | spreading/increasing: YELLOW under the new ooze rule |
| `WOUND_IRRITATION-038` | YELLOW | Sir, one staple is looking like coming out from skin. Should I push it back or leave? | a staple backing out, not a suture end |
| `WOUND_IRRITATION-005` | YELLOW | staples r really itchy and one looks like its poking out a bit | itchy = irritated (existing YELLOW bullet) |
| `HIGH_FEVER-059` | YELLOW | had 39 last night but ED checked me, bloods fine, today it's 38.1 | the clinician sent the patient home but did not call today's 38.1 fine; rule 5 decides the current temperature and the original rule 3 example ("labelled by what remains") was written for this case |
| `LOW_FEVER-029` | YELLOW | Was 38.7 last night but A&E checked me and sent me home, this morning it's 38.0 | as above |

## 5. Effect on counts

| | RED | YELLOW | GREEN |
|---|---:|---:|---:|
| main train (1,253) | 480 | 297 -> 289 | 476 -> 484 |
| main val (276) | 103 | 68 -> 67 | 105 -> 106 |
| main test (266) | 104 | 64 -> 62 | 98 -> 100 |
| unseen-scenario train (1,240) | 474 | 305 -> 294 | 461 -> 472 |
| unseen-scenario val / test | unchanged | unchanged | unchanged |
| challenge (150) | 58 | 37 -> 38 | 55 -> 54 |

RED counts are unchanged everywhere, so RED recall/precision on any split are unaffected by the
adjudication. Every scenario keeps its lead label.

## 6. Annotation agreement

The agreement numbers in `ANNOTATION_AGREEMENT.md` are kept **as measured before adjudication**
(98.7%, kappa 0.980 on 450 items). For information only: against the adjudicated labels the blind
annotator agrees on 449/450 (99.8%, kappa 0.997; the remaining one is `CH-102`). That number is
circular, because 5 of the changes were made on items where the second annotator had disagreed, and
should not be quoted as agreement. None of the 7 rows in section 3 was in the annotation sample.
