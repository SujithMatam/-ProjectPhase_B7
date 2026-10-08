"""
Routing benchmark: labelled single patient messages with the expected IntentLabel.

Every case is one message, classified with no chat history and no pending
question, so this measures fresh classification only.  Fields:

    text         the patient's message, verbatim
    expected     the primary IntentLabel value
    acceptable   every label a reasonable reviewer would accept (always
                 includes `expected`); a prediction in this set is correct
    confidence   "clear" (one obvious owner) or "debatable" (two agents could
                 reasonably take it; then `acceptable` lists both)
    kind         "opening" (a message that starts a topic) or "answer" (a
                 reply to a question an agent asked earlier; in isolation
                 these carry no routable signal, so they are reported
                 separately and are not expected to be fixed by this work)
    source       where the case comes from
    surgery      "TKA" or "THA" (only affects the orchestrator run)
    orchestrator_expected
                 optional; "emergency" / "out_of_scope" when the orchestrator
                 must pre-empt the message before any agent (those cases are
                 excluded from the per-agent classifier table)

Sources:
    phase2:*        every assertion in test_phase2_intent.py (benchmarks,
                    unseen paraphrases, ambiguous + boundary acceptable sets)
    orchestration   test_multi_agent_orchestration.py
    recovery_test   test_recovery_progress_agent.py classifier assertions
    report          the ten fresh-classification misroutes in
                    eval/agents/REPORT.md
    audit           the six audit sentences
    new:<agent>     20 new patient-language openings per agent
                    (Indian-English phrasing, spelling slips)
    intake_guard    introductions / intake statements that must keep
                    routing to IntakeContextAgent
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

RP, PS, RH, MD, WC, DA, NU, MW, IC = (
    "recovery_progress", "pain_symptoms", "rehabilitation", "medication",
    "wound_care", "daily_activity", "nutrition", "mental_wellbeing", "intake_context",
)

ALL_ROUTABLE = (RP, PS, RH, MD, WC, DA, NU, MW, IC)

CASES: List[Dict[str, Any]] = []


def C(text: str, expected: str, acceptable=None, *, confidence: str = "clear",
      source: str, kind: str = "opening", note: str = "", surgery: str = "TKA",
      orchestrator_expected: Optional[str] = None) -> None:
    acc = list(acceptable) if acceptable else [expected]
    if expected not in acc:
        acc.insert(0, expected)
    if confidence == "debatable" and len(acc) < 2:
        raise ValueError(f"debatable case needs two acceptable labels: {text!r}")
    case = {
        "id": f"R{len(CASES) + 1:03d}",
        "text": text,
        "expected": expected,
        "acceptable": acc,
        "confidence": confidence,
        "kind": kind,
        "source": source,
        "surgery": surgery,
    }
    if note:
        case["note"] = note
    if orchestrator_expected:
        case["orchestrator_expected"] = orchestrator_expected
    CASES.append(case)


# ---------------------------------------------------------------------------
# (a) test_phase2_intent.py -- BENCHMARKS (hard assertions)
# ---------------------------------------------------------------------------
S = "phase2:benchmark"
C("When should I expect to walk normally again?", RP, source=S)
C("My knee is more swollen today and hurts.", PS, source=S)
C("How many heel slides should I do?", RH, source=S)
C("I forgot my evening pain tablet.", MD, source=S)
C("Can I change my incision dressing today?", WC, source=S)
C("When can I climb stairs and drive again?", DA, source=S)
C("What foods and protein should I eat while recovering?", NU, source=S)
C("I am anxious about moving my operated leg.", MW, source=S)

# (a) test_phase2_intent.py -- UNSEEN_PARAPHRASES (soft assertions)
S = "phase2:unseen"
C("How long does it typically take to fully recover from this kind of operation?", RP, source=S)
C("Am I healing at the pace the surgeon expected?", RP, source=S)
C("What can I expect in terms of getting back to my usual life?", RP, source=S)
C("The area around my joint feels really tender and inflamed.", PS, source=S)
C("I've got a burning sensation and some numbness in my foot.", PS, source=S)
C("Why does my leg feel so stiff and achy this morning?", PS, source=S)
C("What kind of stretching routine should I follow for physio?", RH, source=S)
C("Can you tell me how to improve my range of motion?", RH, source=S)
C("Should I be doing strengthening drills for my leg yet?", RH, source=S)
C("Is it fine to skip a dose of my blood thinner occasionally?", MD, source=S)
C("What happens if I take my antibiotic later than scheduled?", MD, source=S)
C("Can you tell me the right dosage for my prescribed painkiller?", MD, source=S)
C("There's some fluid coming from my surgical cut, is that normal?", WC, source=S)
C("How often should I clean the area where the stitches are?", WC, source=S)
C("My scar looks a bit red around the edges, should I worry?", WC, source=S)
C("Is it alright to take a shower on my own yet?", DA, source=S)
C("What's the safest way to get in and out of bed?", DA, source=S)
C("Can I sit in a regular chair or do I need something special?", DA, source=S)
C("Should I be taking any vitamins to help my body heal?", NU, source=S)
C("How much water should I drink each day while recovering?", NU, source=S)
C("Is alcohol okay to have during my recovery period?", NU, source=S)
C("I keep feeling down and unmotivated during this recovery.", MW, source=S)
C("I'm scared to put any weight on my leg, is that normal to feel?", MW, source=S)
C("I feel isolated and low because I can't do my usual routine.", MW, source=S)

# (a) test_phase2_intent.py -- AMBIGUOUS_QUERIES + BOUNDARY_PAIR_QUERIES
#     (acceptable-set accuracy, report only)
S = "phase2:ambiguous"
C("I don't feel like doing anything today and my leg feels stiff.", PS, [PS, MW], confidence="debatable", source=S)
C("Is it normal to feel this way after the procedure?", RP, [RP, MW], confidence="debatable", source=S)
C("I'm not sure if this is a side effect or just soreness.", MD, [MD, PS], confidence="debatable", source=S)
C("Should I be worried about how slow this is going?", RP, [RP, MW], confidence="debatable", source=S)
C("My leg feels weird when I try to move it during exercises.", PS, [PS, RH], confidence="debatable", source=S)
S = "phase2:boundary"
C("Is it normal that I still can't manage the stairs at this point in my recovery?", RP, [RP, DA], confidence="debatable", source=S)
C("There's soreness and some fluid leaking near my stitches.", WC, [WC, PS], confidence="debatable", source=S)
C("My leg hurts a lot after doing my exercises today.", PS, [PS, RH], confidence="debatable", source=S)
C("Since starting the new tablets my pain has gotten worse.", MD, [MD, PS], confidence="debatable", source=S)
C("I'm discouraged because my recovery doesn't feel like it's improving.", MW, [MW, RP], confidence="debatable", source=S)

# (a) test_multi_agent_orchestration.py
S = "orchestration"
C("Since I didn't take my medicine yesterday, my knee wound is worse", MD, [MD, WC], confidence="debatable", source=S,
  note="test expects the plan [medication, wound_care]; either agent is an acceptable first owner")
C("I am anxious, my knee hurts, and I need help with exercises", PS, [PS, RH, MW], confidence="debatable", source=S,
  note="test expects the plan [pain_symptoms, rehabilitation, mental_wellbeing]")
C("I can't breathe and my knee wound is worse", WC, source=S, orchestrator_expected="emergency",
  note="classifier must stay routable (wound); the orchestrator must answer with the RED path")
C("What is the weather like today?", RP, list(ALL_ROUTABLE), confidence="debatable", source=S, orchestrator_expected="out_of_scope",
  note="classifier may return any routable intent; the orchestrator must deflect")

# (a) test_recovery_progress_agent.py classifier assertions
S = "recovery_test"
C("I can bend my knee to around 80 degrees.", RH, [RH, RP], confidence="debatable", source=S,
  note="section 12 asserts the FRESH classification is rehabilitation (the misroute the Recovery continuation hook prevents); a reviewer would accept Recovery too")
C("How is my recovery progressing compared to a normal timeline?", RP, source=S)

# ---------------------------------------------------------------------------
# (b) the ten fresh-classification misroutes in eval/agents/REPORT.md
# ---------------------------------------------------------------------------
S = "report"
C("Can I go up and down the stairs yet?", RH, [RH, DA], confidence="debatable", source=S,
  note="c05 turn 1; went to DailyActivityAgent. Stairs are both a daily activity and a rehab progression question")
C("no, nothing sharp", RH, kind="answer", source=S, note="c05 turn 2; answer to the Rehab safety question. Went to RecoveryProgressAgent")
C("It's about a 5 out of 10, it came on gradually, and it's behind the knee.", PS, source=S,
  note="c11 turn 1; multi-slot Pain opening. Went to IntakeContextAgent")
C("getting a bit better", PS, kind="answer", source=S, note="c11 turn 2; answer to worsening_or_improving. Went to RecoveryProgressAgent")
C("My knee aches a little, I took paracetamol an hour ago.", PS, [PS, MD], confidence="debatable", source=S,
  note="c13 turn 1; symptom report that also names a drug. Went to MedicationAgent")
C("3", PS, kind="answer", source=S, note="c13 turn 2; pain score. Went to RecoveryProgressAgent")
C("gradually", PS, kind="answer", source=S, note="c13 turn 3; onset. Went to RecoveryProgressAgent")
C("around the kneecap", PS, kind="answer", source=S, note="c13 turn 4; location. Went to IntakeContextAgent")
C("yes it helped", PS, [PS, MD], confidence="debatable", kind="answer", source=S, note="c13 turn 5; medication_effect answer. Went to MedicationAgent")
C("Am I on track with my knee?", RP, source=S, note="c14 turn 1; went to IntakeContextAgent")

# ---------------------------------------------------------------------------
# (c) audit sentences
# ---------------------------------------------------------------------------
S = "audit"
C("Is it safe to climb stairs?", DA, [DA, RH], confidence="debatable", source=S)
C("What is the schedule for my exercises?", RH, source=S)
C("fluid coming from my incision", WC, source=S)
C("I'm walking with a walker now", RP, [RP, RH], confidence="debatable", source=S, note="mobility status report")
C("I am feeling okay today", RP, [RP, MW], confidence="debatable", source=S, note="general status report")
C("On the other hand my knee feels better", PS, [PS, RP], confidence="debatable", source=S)

# ---------------------------------------------------------------------------
# (d) 20 new patient-language openings per agent
# ---------------------------------------------------------------------------
S = "new:pain"
C("My knee is paining alot since morning, what to do?", PS, source=S)
C("There is swelling near the operated leg and it feels tight", PS, source=S)
C("The pain is not reducing even after 3 days, is this normal?", PS, [PS, RP], source=S)
C("Calf muscle is paining when I walk", PS, source=S, note="calf + pain may be escalated by SafetyTriageEngine")
C("Knee feels very stiff in the morning time", PS, source=S)
C("Thigh is numb from yesterday night, like no sensation", PS, source=S)
C("Pain level is around 7 today, yesterday it was 4", PS, source=S)
C("Burning type pain behind the knee only", PS, source=S)
C("My leg is throbing badly at night and sleep is not coming", PS, [PS, DA], source=S)
C("Hip is hurting more when I try to turn in bed", PS, [PS, DA], source=S, surgery="THA")
C("Is it normal to have this much pain on day 4?", PS, [PS, RP], confidence="debatable", source=S)
C("Knee got swolen after walking little bit, should I worry?", PS, source=S)
C("Sharp pain came suddenly in the knee when I stood up", PS, source=S)
C("The operated area feels warm and tender to touch", PS, [PS, WC], confidence="debatable", source=S)
C("Pain is 8 out of 10 and the tablet is not helping", PS, [PS, MD], confidence="debatable", source=S)
C("Having tingling sensation in my toes of the operated leg", PS, source=S)
C("Ankle also got swelling now along with knee", PS, source=S)
C("Dull ache in the groin area whole day", PS, source=S, surgery="THA")
C("Pain increased after physio session yesterday, is it ok?", PS, [PS, RH], confidence="debatable", source=S)
C("Leg feels heavy and sore when I keep it down", PS, source=S)

S = "new:recovery"
C("Am I recovering properly for day 10?", RP, source=S)
C("How many days it will take to walk normally without walker?", RP, [RP, RH], confidence="debatable", source=S)
C("Is my recovry going fine or slow?", RP, source=S)
C("When can I go back to office after hip replacement?", RP, [RP, DA], confidence="debatable", source=S, surgery="THA")
C("I can bend my knee to 90 degrees now, is that good for 2 weeks?", RP, [RP, RH], confidence="debatable", source=S)
C("Compared to last week I am walking better, is this the expected progress?", RP, source=S)
C("What milestones should I reach by one month?", RP, source=S)
C("By when I can sit cross legged on floor?", RP, [RP, DA], confidence="debatable", source=S)
C("Recovery check please, I am on day 21 now", RP, source=S)
C("How is my healing compared to other patients of my age?", RP, source=S)
C("Still limping after 6 weeks, is this normal at this stage?", RP, [RP, RH], confidence="debatable", source=S)
C("What should I be able to do by now, 3 weeks post op?", RP, source=S)
C("Doctor said 6 weeks for full recovery, am I on schedule?", RP, source=S)
C("My knee extension is still 10 degrees short, is my progress ok?", RP, [RP, RH], confidence="debatable", source=S)
C("I want to know where I stand in my recovery timeline", RP, source=S)
C("When will the knee feel like normal again?", RP, source=S)
C("Next week I complete one month, what improvement is expected by then?", RP, source=S)
C("Is it fine that I am still using one crutch at day 30?", RP, [RP, RH], confidence="debatable", source=S)
C("Can you tell me if I am behind or ahead for my post op day?", RP, source=S)
C("How much more time for complete healing of the hip?", RP, source=S, surgery="THA")

S = "new:rehab"
C("Which excercises I should do today for my knee?", RH, source=S)
C("How many times a day I have to do heel slides?", RH, source=S)
C("Physio told to do quad sets but I forgot how, can you explain?", RH, source=S)
C("Can I start cycling on static cycle now?", RH, [RH, DA], confidence="debatable", source=S)
C("Is it ok to skip physiotheraphy for 2 days, I am very tired", RH, source=S)
C("How to straigten my knee fully, it is not going straight", RH, source=S)
C("My range of motion is stuck at 80 degrees, what excercise will help?", RH, source=S)
C("Should I use walker or can I shift to stick now?", RH, [RH, RP, DA], confidence="debatable", source=S)
C("Ankle pump exercise is boring, any alternative?", RH, source=S)
C("Can I put full weight on my operated leg while doing exercises?", RH, source=S)
C("How long each stretching should be held?", RH, source=S)
C("I missed my exercises for 3 days, how to restart?", RH, source=S)
C("Is climbing stairs a good exercise for strengthening the knee?", RH, [RH, DA], confidence="debatable", source=S)
C("What is the correct way to do straight leg raise?", RH, source=S)
C("Can I do my exercises twice daily instead of thrice?", RH, source=S)
C("Hip abduction excercise is paining little, should I continue?", RH, [RH, PS], confidence="debatable", source=S, surgery="THA")
C("When can I start walking without walker?", RH, [RH, RP], confidence="debatable", source=S)
C("Do I need to go to physio centre or home exercises are enough?", RH, source=S)
C("Pls tell me the exercise plan for this week", RH, source=S)
C("How much should I bend my knee during the exercises, it is week 2", RH, source=S)

S = "new:wound"
C("There is some yellow fluid coming from the stiches", WC, source=S)
C("When can I remove the bandge and take proper bath?", WC, [WC, DA], confidence="debatable", source=S)
C("Wound area is red and little warm, is it infection?", WC, source=S)
C("Can I apply any ointment or turmeric on the scar?", WC, source=S)
C("The dressing got wet in the bathroom, what should I do?", WC, source=S)
C("Staples are still there, when will they remove?", WC, source=S)
C("My incision is itching alot, is it normal?", WC, source=S)
C("One side of the cut is looking open slightly", WC, source=S)
C("How often I should change the dressing at home?", WC, source=S)
C("Small blood spots on the bandage today morning", WC, source=S)
C("Can I keep the wound open to air now?", WC, source=S)
C("The skin around the stitches is peeling", WC, source=S)
C("Is it ok if water touches the incision while bathing?", WC, [WC, DA], confidence="debatable", source=S)
C("There is a hard lump under the scar, is that normal?", WC, source=S)
C("The suture line is paining and oozing", WC, [WC, PS], confidence="debatable", source=S)
C("Discharge from the wound has bad smell", WC, source=S)
C("How should I clean the wound, with dettol or just water?", WC, source=S)
C("Can I put a waterproof plaster over the incision?", WC, source=S)
C("Stitch removal is due tomorrow, anything to take care?", WC, source=S)
C("Redness is spreading around the wound since yesterday", WC, source=S)

S = "new:medication"
C("I forgot to take my blood thinner injection today", MD, source=S)
C("Can I take Dolo 650 along with the prescribed painkiller?", MD, source=S)
C("How many hours gap between two paracetamol tablates?", MD, source=S)
C("Is it ok to stop the antibiotics now, I am feeling fine", MD, source=S)
C("I vomited after taking the morning medecine, should I take again?", MD, source=S)
C("What is this tablet Pantop for, doctor gave it with others?", MD, source=S)
C("Missed my night dose of enoxaparin, what to do now?", MD, source=S)
C("Can I take the pain killer on empty stomach?", MD, source=S)
C("The pain medicine is making me very drowsy and constipated", MD, source=S)
C("When should I take the next dose if I took one at 2pm?", MD, source=S)
C("Are there any side effects of rivaroxaban I should know?", MD, source=S)
C("Can I take my regular BP tablet with these new medicines?", MD, source=S)
C("Doctor prescribed Ultracet, is it a strong medicine?", MD, source=S)
C("I took double dose by mistake this morning", MD, source=S)
C("How long I have to continue the blood thinner?", MD, source=S)
C("Is ibuprofen safe for me after knee replacement?", MD, source=S)
C("What is the timing for the antibiotic, before food or after food?", MD, source=S)
C("Can I drink alcohol while on these tablets?", MD, [MD, NU], confidence="debatable", source=S)
C("My prescription says 1-0-1, what does it mean?", MD, source=S)
C("Pharmacy gave a different brand of the same medicine, is it ok?", MD, source=S)

S = "new:daily"
C("Can I use Indian toilet or only western commode?", DA, source=S)
C("When can I start driving my scooty again?", DA, source=S)
C("How should I sleep, on my back or can I turn to side?", DA, source=S)
C("Can I take bath with bucket while standing?", DA, source=S)
C("Is it ok to climb the stairs at home, we have no lift", DA, source=S)
C("Can I sit on the floor for pooja?", DA, source=S)
C("How do I get into the car without hurting the hip?", DA, [DA, PS], confidence="debatable", source=S, surgery="THA")
C("When can I travel by bus or auto to the hospital?", DA, source=S)
C("Can I do light kitchen work like making chapati?", DA, source=S)
C("Is it safe to walk to the temple nearby, around 500 metres?", DA, [DA, RH, RP], confidence="debatable", source=S)
C("How to get up from bed properly in the morning?", DA, source=S)
C("Can I sleep on the operated side?", DA, source=S)
C("Which chair is good to sit, sofa or plastic chair?", DA, source=S)
C("Can I do sweeping and mopping of the house?", DA, source=S)
C("When can I resume my office work, I have desk job", DA, [DA, RP], confidence="debatable", source=S)
C("Is it ok to go for a short walk outside daily?", DA, [DA, RH], confidence="debatable", source=S)
C("How to climb up and down stairs with crutches?", DA, [DA, RH], confidence="debatable", source=S)
C("Can I carry my grandchild while standing?", DA, source=S)
C("Can I kneel down for prayer?", DA, source=S)
C("Is it ok to wear slippers or should I use proper shoes?", DA, source=S)

S = "new:nutrition"
C("What food I should eat for faster healing of the bone?", NU, source=S)
C("Is non-veg good or should I stick to veg diet now?", NU, source=S)
C("How much protien I need daily after the surgery?", NU, source=S)
C("Can I eat curd and rice at night?", NU, source=S)
C("I am having constipaton since the operation, what to eat?", NU, source=S)
C("Is drinking coconut water good for recovery?", NU, source=S)
C("Should I take calcium and vitamin D tablets?", NU, [NU, MD], confidence="debatable", source=S)
C("My appetite is very less since surgery, is it normal?", NU, [NU, RP], confidence="debatable", source=S)
C("Can I eat sweets, I am diabetic also", NU, source=S)
C("How many litres of water to drink per day?", NU, source=S)
C("Are eggs and milk enough for protein or need supplements?", NU, source=S)
C("Can I take tea and coffee normally?", NU, source=S)
C("Is spicy food bad for the wound healing?", NU, [NU, WC], confidence="debatable", source=S)
C("What fruits are good during recovery?", NU, source=S)
C("I feel bloated after meals, any diet advice?", NU, source=S)
C("Can I have beer once in a while now?", NU, [NU, MD], confidence="debatable", source=S)
C("Should I reduce weight to help my knee, what diet?", NU, source=S)
C("Is it ok to fast during Navratri with this recovery?", NU, [NU, RP], confidence="debatable", source=S)
C("Dal, roti, sabzi daily is fine or need to change?", NU, source=S)
C("Doctor said eat iron rich food, which ones?", NU, source=S)

S = "new:mental"
C("I am feeling very low and crying since the surgery", MW, source=S)
C("Getting tension that I will never walk properly again", MW, [MW, RP], source=S)
C("I feel scared to put weight on my leg even though physio said ok", MW, source=S)
C("Not able to sleep because of worry about the recovery", MW, [MW, DA], confidence="debatable", source=S)
C("I am frustrated, everything is so slow", MW, source=S)
C("Feeling like a burden on my family", MW, source=S)
C("I have no motivation to do the exercises anymore", MW, [MW, RH], confidence="debatable", source=S)
C("Is it normal to feel depressed after knee replacement?", MW, source=S)
C("My mood is very irritable these days, snapping at everyone", MW, source=S)
C("I keep thinking something will go wrong with the implant", MW, source=S)
C("Feeling lonely sitting at home whole day", MW, source=S)
C("I am anxiuos about my follow up visit tomorrow", MW, source=S)
C("Sometimes I feel hopeless about getting back to normal", MW, source=S)
C("How to deal with the stress of this long recovery?", MW, [MW, RP], source=S)
C("I panic whenever I feel any small pain in the knee", MW, [MW, PS], confidence="debatable", source=S)
C("My wife says I have become very negative after the operation", MW, source=S)
C("I feel overwhelmed with all the instructions and exercises", MW, [MW, RH], confidence="debatable", source=S)
C("Can't stop worrying that the surgery has failed", MW, source=S)
C("I am not feeling like talking to anyone", MW, source=S)
C("Mentally very tired of this whole thing, any tips?", MW, source=S)

# ---------------------------------------------------------------------------
# intake guard -- introductions that must keep going to IntakeContextAgent
# ---------------------------------------------------------------------------
S = "intake_guard"
C("Hi", IC, source=S)
C("Good morning", IC, source=S)
C("Hi, I am Rishi", IC, source=S)
C("My name is John and I had knee surgery two days ago", IC, source=S)
C("I had a knee replacement yesterday", IC, source=S)
C("I want to provide my baseline information", IC, source=S)
C("I underwent hip replacement last week", IC, source=S, surgery="THA")
C("Hello, I am a new patient here", IC, source=S)


def by_id() -> Dict[str, Dict[str, Any]]:
    return {case["id"]: case for case in CASES}


if __name__ == "__main__":
    from collections import Counter
    print(len(CASES), "cases")
    print(Counter(c["expected"] for c in CASES))
    print(Counter(c["confidence"] for c in CASES))
    print(Counter(c["kind"] for c in CASES))
    print(Counter(c["source"].split(":")[0] for c in CASES))
