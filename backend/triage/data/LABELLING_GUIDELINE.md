# Triage labelling guideline (v1.1)

One label per patient message, for patients after total knee (TKA) or total hip (THA) replacement.
Sources: warning-sign passages in `backend/eval/eval_corpus.json` (EV-TKA-PAIN-01, EV-TKA-PAIN-06,
EV-THA-PAIN-01, EV-THA-PAIN-02, EV-THA-PAIN-06, EV-THA-REC-04, EV-THA-REC-05) and the temperature
thresholds in `backend/triage/safety_triage.py` (>= 38.5 °C RED, >= 37.8 °C YELLOW).

## Levels

**RED: needs same-day emergency or urgent assessment.** Any one of:
- **Lungs / heart:** new or sudden shortness of breath, chest pain (especially when breathing in or coughing), coughing up blood, fainting or near-fainting, racing heart with breathlessness. *Corpus: "call emergency services immediately".*
- **Clot in the leg:** calf or leg pain not related to the incision; a calf that is tender, hard, hot or red; new or increasing swelling of the thigh, calf, ankle or foot that does **not** go down when the leg is raised. *Corpus: "report these straight away".*
- **Dislocation (mainly THA):** sudden severe hip or groin pain, a pop, cannot move or bear weight on the leg, leg suddenly turned in/out or shorter. *Corpus: "call an ambulance".*
- **Circulation / nerves:** foot or toes numb, cold, pale, blue or "dead"; cannot move the toes or foot.
- **Compartment-type pain:** severe pain out of proportion, leg tight / rock hard, not touched by prescribed pain relief.
- **Infection with systemic or severe signs:** temperature **>= 38.5 °C (>= 101.3 °F)**; shaking chills together with a fever or a wound problem; pus or foul-smelling discharge; redness that is spreading fast; wound that has opened up.
- **Major bleeding:** vomiting blood or "coffee grounds", black/tarry stool, blood in urine, bleeding that will not stop, dressing soaked through, large unexplained bruises (especially on blood thinners).
- **Other emergencies:** swelling of face/lips/tongue, trouble breathing, or hives spreading over the whole body after a medicine; a fall followed by new inability to bear weight or a deformed joint; a head knock while on blood thinners; new confusion; thoughts of harming oneself.

**YELLOW: contact the care team within about 24 hours / needs review.**
- Temperature **37.8-38.4 °C (100.0-101.2 °F)**, or "feverish" / "running a temperature" with no number.
- Wound: a little redness, warmth or swelling around the incision; clear, pink or watery fluid coming from it; staples or stitches pulling, irritated or puckered; a small gap with no pus.
- Dressing ooze (blood or fluid) that is spreading or increasing. *(v1.1)*
- Pain not controlled by the prescribed relief, or pain that keeps increasing (without the RED features above). *Corpus: "contact your team if pain is not controlled".*
- Swelling getting worse over the weeks but still settling when raised, with no calf pain.
- Medicine problems: nausea or vomiting, no bowel movement for 3+ days, dizziness, itchy rash without face swelling or breathing trouble, a missed blood-thinner dose.
- Implant clicking or clunking **with** pain, swelling, or a feeling of giving way / looseness.
- A fall with no new injury (still walking as before); a numb or tingling patch beside the scar that is new, spreading or more painful.
- Not coping for several days (not sleeping, not eating, very low) without thoughts of self-harm.
- A symptom the patient is worried about that fits nowhere else. *Corpus: "contact your team if you are unsure".*

**GREEN: routine or informational.**
- Questions with no reported concerning symptom (exercises, precautions, diet, showering, driving, appointments, medicine timing, "is X normal?" asked in general).
- Expected recovery: soreness with exercise that settles, stiffness or a "tight band", ankle swelling at the end of the day that goes down with elevation, fading bruises, painless clicking, a numb patch beside the scar unchanged since surgery, temperature below 37.8 °C, a healed scar that itches, low mood or poor sleep the patient is managing.
- *(v1.1)* A small spot or line of blood on the dressing that is not spreading; a small bruise near the operated joint or an injection site; a loose suture end with no redness, pulling or discharge.

## Rules (apply in order)

1. **Label what the patient reports experiencing, not the topic.** "How do I spot a blood clot?" is GREEN; "my calf is hot and hard" is RED.
2. **A pure information question is GREEN,** including hypotheticals ("what if my wound leaks?").
3. **A negated symptom does not count.** "No chest pain, no chills" contributes nothing. A symptom that has stopped still counts (a nosebleed on blood thinners that stopped is YELLOW) unless a clinician has already said it is fine ("the doctor said a little blood on the dressing is fine and it has stopped" is GREEN; "A&E checked my calf, scan was clear" is labelled by what remains). *(v1.1)* A finding a clinician has already assessed and called fine stays GREEN while it is unchanged ("the nurse said the pink fluid is normal drainage; still a little damp" is GREEN); if it gets worse, label by the change.
4. **The highest finding wins** in a multi-symptom message.
5. **Temperatures in the text decide the fever part:** convert °F to °C; >= 38.5 RED, 37.8-38.4 YELLOW, < 37.8 contributes nothing. "Fever of 39" is RED.
6. **When torn between two levels, pick the higher one.**
7. Reassurance from the patient ("probably nothing, but...") does not lower the label.

## Out of scope for v1
Procedures other than TKA/THA; messages from carers are labelled the same as patient messages;
no clinician has reviewed this guideline (see `DATASET_CARD.md`).

## Changes
- **v1.1** (adjudication, `ADJUDICATION.md`): the GREEN dressing-blood / bruise / loose-suture bullet, the YELLOW spreading-ooze bullet and the rule 3 addition for clinician-assessed findings.
