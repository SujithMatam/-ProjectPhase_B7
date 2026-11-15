# Blind abstention set, part 2 of 3: project_abstain, 7 partial/none queries × 4 models

Generated 2026-09-29T10:32:00+00:00. The full set is all 21 `partial`/`none` queries, split 7 per file in `eval_queries.jsonl` order. For each query, the four visible answers are labelled A-D in a random order that is different for every query across all three parts. The key is in `abstention_key.json` (base64). Don't decode it until all three parts are scored.

How to score: use the rubric in `score.py`. Judge each answer **only against the retrieved context below**. The reference answer shows what a good answer should cover, but it isn't evidence.

- `grounded` 0-2
- each claim labelled `supported` / `embellished` / `unsupported`
- `unanswerable_handling`: `correct` if the answer says the missing part isn't covered (or defers it to the care team) instead of supplying it, `invented` if it fills the gap with unsupported content. It is never `n/a` here, because every query is partial/none.
- `followed_format`: friendly, 2-3 sentences, plain language; a "not covered, check with your surgeon or physiotherapist" answer also counts

Answers are the visible text only, copied verbatim. Any reasoning trace was removed, exactly as `score.py` shows it to the judge. An answer shown as *(no answer was given)* produced no visible text; the judge sees the same placeholder.

---

## r04

| field | value |
|---|---|
| procedure | TKA |
| postop_day | 10 |
| domain | rehab |
| answerability | **partial** |

**Query:** the leg raises are too painful, can I skip them and just walk more instead

**Reference answer** (from EV-TKA-REHAB-04):

> Straight leg raises are one of the typical strengthening exercises at this stage, done once the knee can fully straighten, but the guidelines advise avoiding exercise that causes severe pain or a marked increase in swelling. The notes do not say whether more walking can replace them, so tell your physiotherapist that the leg raises are too painful; your physiotherapist will adapt the programme to your progress.

### Frozen context (4 chunk(s), as given to the models)

**[1] Building strength and function in weeks 2-6 after knee replacement**  
`EV-TKA-REHAB-04-c1` · TKA · days 8-42 · in window · distance 0.462

> Typical exercises are straight leg raises in several directions once the knee can fully straighten, repeated sit-to-stands from a chair, small step-ups and step-downs starting on a low step of about two to four inches, and balance work that progresses from standing on both legs to standing on one. Everyday tasks are practised too, such as getting in and out of a bath or shower and a car. The American Academy of Orthopaedic Surgeons notes that light ankle weights can usually be added to the basic exercises from about four to six weeks after surgery, increasing gradually as strength returns. The guiding rules are to avoid long periods of sitting and to avoid exercise that causes severe pain or a marked increase in swelling.

**[2] Building strength and function in weeks 2-6 after knee replacement**  
`EV-TKA-REHAB-04-c2` · TKA · days 8-42 · in window · distance 0.497

> By the end of this stage the usual aims are controlled swelling and pain, good bend with a fully straight knee, no lag when lifting the straight leg, a normal walking pattern with or without an aid, climbing a standard step with control, and independence in daily activities. Your physiotherapist will adapt the programme to your progress.

**[3] Walking aids and stairs after knee replacement**  
`EV-TKA-REHAB-03-c1` · TKA · days 1-21 · in window · distance 0.510

> NHS guidance describes going down to one crutch and then a walking stick as your confidence grows, and trying to walk without an aid after about six weeks if you feel ready. Rehabilitation guidelines also advise not walking without the aid until you can walk without limping. For stairs, remember 'up with the good, down with the bad': going up, lead with the non-operated leg; coming down, lead with the operated leg, taking one step at a time and using the handrail. Before going home, most people practise climbing up and down two or three stairs with their aid. Stepping foot over foot on stairs usually comes later, once walking is normal and the knee is strong. Your physiotherapist will tell you when to change aids and when you are ready to use stairs normally.

**[4] Walking aids and stairs after knee replacement**  
`EV-TKA-REHAB-03-c0` · TKA · days 1-21 · in window · distance 0.541

> You will usually walk with help soon after a knee replacement, first with a walking frame or crutches. Stand upright, move the frame or crutches a short distance forward, step forward with the operated leg so the heel touches the floor first, and then bring the other leg through. As you get stronger, walks can become longer and you can gradually take more weight through the leg. The American Academy of Orthopaedic Surgeons suggests changing to a single crutch or cane once you are able to stand and walk for over ten minutes and no longer need to lean on the frame or crutches, which is often about two to three weeks after surgery. Hold the cane in the hand opposite the operated knee.

### Answers

**A.**

> The discharge notes mention straight leg raises are a typical exercise for weeks 2-6, aiming for good knee bend and no lag. If these exercises cause severe pain, please discuss this with your physiotherapist. They can help you find the best way to manage your pain and continue your exercises safely.

**B.**

> I don't have that information in the discharge notes. It's best to check with your surgeon or physiotherapist to see what exercises are recommended for you at this stage. They can advise on the best way to progress your exercises and ensure you're not putting too much strain on your knee.

**C.**

> Okay, it sounds like those straight leg raises are causing you some pain – that’s really common after a knee replacement. You can definitely focus on increasing your walking as you feel able, and your physiotherapist will be monitoring your progress closely. Remember to continue icing your leg and elevating it when you’re resting to help manage any swelling, and please check with your physiotherapist about adjusting your exercises if the pain persists.

**D.**

> It is understandable that the leg raises feel painful right now, but skipping them entirely might slow down your recovery because these exercises help build the specific strength needed for walking without limping. Since you are on Day 10, please check with your physiotherapist before changing your routine, as they can advise whether to modify the leg raises or focus more on gentle walking and other safe movements that match your current pain level.

---

## r07

| field | value |
|---|---|
| procedure | TKA |
| postop_day | 28 |
| domain | rehab |
| answerability | **partial** |

**Query:** my physio wants me to do step ups and mini squats, isnt that too early

**Reference answer** (from EV-TKA-REHAB-04):

> Step-ups are part of the usual programme at this stage: for weeks two to six, the Hospital for Special Surgery guideline includes small step-ups and step-downs starting on a low step of about two to four inches, along with repeated sit-to-stands from a chair. The notes for this stage do not mention mini squats, so ask your physiotherapist about them. The guiding rule is to avoid exercise that causes severe pain or a marked increase in swelling, and your physiotherapist will adapt the programme to your progress.

### Frozen context (4 chunk(s), as given to the models)

**[1] Building strength and function in weeks 2-6 after knee replacement**  
`EV-TKA-REHAB-04-c2` · TKA · days 8-42 · in window · distance 0.611

> By the end of this stage the usual aims are controlled swelling and pain, good bend with a fully straight knee, no lag when lifting the straight leg, a normal walking pattern with or without an aid, climbing a standard step with control, and independence in daily activities. Your physiotherapist will adapt the programme to your progress.

**[2] Using a stationary exercise bike after knee replacement**  
`EV-TKA-REHAB-05-c0` · TKA · days 8-84 · in window · distance 0.614

> A stationary exercise bike is a common part of rehabilitation after a knee replacement because it helps rebuild muscle strength and knee movement without high impact, and your doctor may recommend riding one at physical therapy. The American Academy of Orthopaedic Surgeons advises raising the seat at first so that the sole of your foot only just reaches the pedal when the knee is nearly straight, and pedalling backwards to begin with, riding forwards only once a comfortable backward motion is possible. As you get stronger, at about four to six weeks, the tension can be increased slowly. Sessions typically start at 10 to 15 minutes twice a day and build up to 20 to 30 minutes three or four times a week, and the seat can be lowered slightly to encourage more bending during slow pedal turns.

**[3] Building strength and function in weeks 2-6 after knee replacement**  
`EV-TKA-REHAB-04-c1` · TKA · days 8-42 · in window · distance 0.620

> Typical exercises are straight leg raises in several directions once the knee can fully straighten, repeated sit-to-stands from a chair, small step-ups and step-downs starting on a low step of about two to four inches, and balance work that progresses from standing on both legs to standing on one. Everyday tasks are practised too, such as getting in and out of a bath or shower and a car. The American Academy of Orthopaedic Surgeons notes that light ankle weights can usually be added to the basic exercises from about four to six weeks after surgery, increasing gradually as strength returns. The guiding rules are to avoid long periods of sitting and to avoid exercise that causes severe pain or a marked increase in swelling.

**[4] Knee bend and straightening goals after knee replacement**  
`EV-TKA-REHAB-02-c1` · TKA · days 1-42 · in window · distance 0.665

> By the end of the phase covering weeks two to six it aims for more than 110 degrees of bending with the knee fully straight. Bending beyond 120 degrees is a later goal, mainly for people returning to sport or demanding activities. The guideline stresses that progression is based on reaching these criteria and is adjusted for each patient, and your surgeon may set different targets, so treat these numbers as a guide rather than a deadline. Stretching into the end of the movement is expected to feel tight or uncomfortable. However, if your range of motion stops improving and the end of the bend feels hard or very painful, the guideline advises that the surgeon should be contacted, so mention it to your physiotherapist early.

### Answers

**A.**

> It’s great you’re being proactive with your rehab! Step-ups and mini squats are common exercises around day 28 after your TKA, but it’s good to check in with your physio about them. They’ll be assessing your progress and adjusting the programme to your individual needs – remember to start slowly and listen to your body, and always prioritize avoiding pain or swelling.

**B.**

> It sounds like you're a bit concerned about the exercises your physiotherapist is having you do. The exercises your physio is recommending, such as step-ups and mini squats, are actually part of the usual rehabilitation plan after a knee replacement, and are typically introduced around 4-6 weeks after surgery. However, everyone's recovery is different, and your physiotherapist will be able to advise you on whether these exercises are suitable for you at this stage. Can you check with your physiotherapist to see what their specific advice is?

**C.**

> Based on the discharge notes, the section on "Building strength and function in weeks 2-6 after knee replacement" mentions "small step-ups and step-downs starting on a low step". The notes don't explicitly state when these exercises should be introduced or if they are appropriate for Day 28.
> 
> To know if step-ups and mini squats are right for you at Day 28, it's best to ask your physiotherapist or surgeon directly.

**D.**

> No, doing step-ups and mini-squats is not too early; these are standard exercises recommended for weeks 2–6 after your knee replacement to help rebuild strength and improve function. Your physiotherapist knows your specific progress and will adapt the intensity so that you can perform them without severe pain or a marked increase in swelling, which are the main signs to watch for.

---

## r08

| field | value |
|---|---|
| procedure | TKA |
| postop_day | 30 |
| domain | rehab |
| answerability | **none** |

**Query:** which brand of knee brace should I buy for walking outside

**Reference answer** (from no listed passages):

> The information I have does not cover knee braces or brands, so please ask your physiotherapist or surgeon whether you need one.

### Frozen context (4 chunk(s), as given to the models)

**[1] Is my knee recovery on track? What steady progress looks like**  
`EV-TKA-REC-05-c1` · TKA · days 22-84 · in window · distance 0.577

> Useful markers from the HSS guideline are about 80 degrees of bending by the end of the first week, more than 110 degrees with a fully straight knee by around six weeks, and more than 120 degrees for people aiming to return to demanding activities, but your own team's targets take priority. A knee that is still swollen and stiff at four to six weeks is common and does not by itself mean recovery is slow, because mild to moderate swelling can last three to six months. Talk to your physiotherapist or surgeon if your range of motion stops improving or the end of the bend feels hard and painful, if you cannot straighten the knee fully, if pain is increasing rather than decreasing, or if you cannot progress your walking.

**[2] Knee bend and straightening goals after knee replacement**  
`EV-TKA-REHAB-02-c0` · TKA · days 1-42 · in window · distance 0.578

> Regaining the knee's movement is a central goal of rehabilitation, and it has two parts: straightening (extension) and bending (flexion). Getting the knee fully straight is especially important for walking well, so do not rest with a pillow under the knee; instead, practise lying with the heel propped on a small rolled towel so the knee can straighten. Bending is increased gradually with heel slides, sitting knee bends and, later, cycling. As a general guide, the Hospital for Special Surgery rehabilitation guideline looks for about 80 degrees of active bending in sitting, with the knee straightening to within 10 degrees of fully straight, before patients move on from the first-week phase.

**[3] Knee bend and straightening goals after knee replacement**  
`EV-TKA-REHAB-02-c2` · TKA · days 1-42 · in window · distance 0.582

> Swelling makes the knee harder to bend, so controlling it with ice, raising the leg and sensible pacing also helps you regain movement.

**[4] Using a stationary exercise bike after knee replacement**  
`EV-TKA-REHAB-05-c1` · TKA · days 8-84 · in window · distance 0.602

> While riding, aim for as much bending and straightening as you comfortably can. The Hospital for Special Surgery guideline includes cycling in the weeks two to six phase, using a short-crank bike if the knee cannot yet bend to 90 degrees and a standard bike once bending is beyond about 110 degrees, and it continues cycling, treadmill and elliptical work in weeks seven to twelve. So, for many people, using a stationary bike at around six weeks is a normal part of recovery, provided the knee bends enough to pedal comfortably and the wound is healed. Check with your physiotherapist before starting or increasing resistance, stop if you get sharp pain, and expect some muscle tiredness afterwards. Road cycling outdoors is a later step to discuss with your surgeon.

### Answers

**A.**

> Based on the discharge notes provided, we don't have specific recommendations for knee brace brands for walking outside. The notes focus more on general recovery goals and exercises.
> 
> For the best advice on which brace is right for you, it's best to talk to your surgeon or physiotherapist directly. They can give you personalized guidance based on your specific needs and the type of brace they recommend for your situation.

**B.**

> Based on the discharge notes, it doesn’t specify a particular brand of knee brace for walking outside. However, it’s important to focus on getting your knee fully straight – try lying with your heel propped on a small rolled towel – and gradually increasing your bending with exercises like heel slides. Please check with your physiotherapist or surgeon before starting any activity to ensure it’s appropriate for your recovery and to discuss any specific support you might need.

**C.**

> I do not have information about which specific brand of knee brace you should buy, as the discharge notes focus on exercises, range of motion goals, and mobility progression rather than recommending particular medical devices. Please check with your surgeon or physiotherapist to find a brace that fits your needs and matches their specific advice for walking outside.

**D.**

> I don't have that information. You should check with your surgeon or physiotherapist for recommendations on knee braces and any specific requirements for your recovery.

---

## r09

| field | value |
|---|---|
| procedure | TKA |
| postop_day | 6 |
| domain | rehab |
| answerability | **none** |

**Query:** the hospital is asking me to rent a CPM machine, is it really necessary

**Reference answer** (from no listed passages):

> The information I have does not cover CPM machines, so please ask your surgeon or physiotherapist whether you need one.

### Frozen context (0 chunk(s), as given to the models)

*(no chunks were retrieved)*

### Answers

**A.**

> I don't have information on the specific needs of your recovery after Total Knee Arthroplasty (TKA). I recommend checking with your surgeon or physiotherapist for guidance on whether a Continuous Passive Motion (CPM) machine is necessary for your recovery. They can assess your progress and provide personalized advice on the best course of treatment for you.

**B.**

> Based on the discharge notes, the goal is to use the CPM machine to help maintain your knee's extension and prevent stiffness. The notes also say to continue it "as prescribed" by your physiotherapist. So, according to the plan, it seems necessary for achieving those goals.

**C.**

> Based on your discharge notes for Day 6 after Total Knee Arthroplasty, there is no specific information about renting a Continuous Passive Motion (CPM) machine or whether it is required for your recovery. Since the hospital's recommendation might depend on your specific surgery details and surgeon's preference, you should check directly with your surgeon or physiotherapist to confirm if this device is necessary for you.

**D.**

> Okay, let’s talk about that CPM machine. The discharge notes say you should continue with the exercises we’ve been doing, and icing your knee after each session – that’s really important for reducing swelling. While the hospital suggests a CPM machine, it’s not always necessary, and it’s best to discuss this with your surgeon or physiotherapist to see if it’s the right fit for your recovery.

---

## r17

| field | value |
|---|---|
| procedure | THA |
| postop_day | 45 |
| domain | rehab |
| answerability | **partial** |

**Query:** my 6 weeks precautions are over, can I sit on the low sofa now

**Reference answer** (from EV-THA-REHAB-02, EV-THA-REC-04):

> Most patients can do most of the movements restricted by their hip precautions again after six to eight weeks, but only once your surgeon confirms that your own precautions have ended. The notes do not say specifically when low sofas are fine; they note that low chairs and chairs without arms make standing up difficult, and that a firm, higher chair with arms helps. If you are unsure, check with your surgeon or physiotherapist.

### Frozen context (4 chunk(s), as given to the models)

**[1] Hip precautions during recovery**  
`EV-THA-REHAB-02-c1` · THA · days 1-56 · in window · distance 0.502

> Low chairs, low toilet seats and chairs without arms make standing up difficult, so a raised toilet seat and a firm, higher chair with arms help, as do aids such as a grabber, a long-handled sponge and a long shoehorn, so you can avoid bending too far. Your surgeon may also restrict some sleeping positions or suggest a pillow between the knees at night for a period. AAOS guidance adds that, whichever approach was used, most patients can do most of these movements again after six to eight weeks without affecting the implant, but wait until your surgeon confirms that your own precautions have ended. While the hip is recovering, NHS guidance is also to avoid exercises that involve jumping, sudden turns or a high risk of falling, and not to lift heavy objects until you are told it is safe.

**[2] Hip precautions during recovery**  
`EV-THA-REHAB-02-c0` · THA · days 1-56 · in window · distance 0.561

> After a hip replacement you may be given extra precautions for how you sit, bend and sleep, typically for around six weeks, to help prevent the new joint from dislocating while the tissues heal. The exact precautions depend on the surgical approach your surgeon used, and not all surgeons recommend the same ones, so follow the instructions you were given and ask if you are unsure which apply to you. Common precautions include: do not bend at the waist or hip beyond 90 degrees, a right angle; do not bring the knee on the operated side up higher than the hip; do not cross your legs at the knees; do not lean forwards when seated or while lowering yourself into a chair; and do not reach down to your feet or ankles.

**[3] Returning to sport and recreation after hip replacement**  
`EV-THA-REHAB-06-c1` · THA · days 43-84 · in window · distance 0.669

> While the hip is still recovering, NHS guidance is to avoid exercises that involve jumping, sudden turns or a high risk of falling, and not to lift heavy objects until you are told it is safe. This means that sports involving running, jumping, quick changes of direction or a risk of falls should be discussed with your surgeon before you return, even if you feel well. When you do restart an activity, build up gradually, keep doing your strengthening exercises, and notice how the hip feels the next day. Pain that lasts after activity or new swelling are signs to ease back and seek advice. Most people can return to an active lifestyle, but the right sports and the right time are an individual decision to make with your surgeon.

**[4] What you may be able to do two to three weeks after hip replacement**  
`EV-THA-REC-02-c1` · THA · days 8-21 · **outside the post-op window** · distance 0.600

> Your exercise programme will usually include bed exercises and standing exercises such as knee raises, hip abduction and hip extension several times a day. You should be able to get in and out of bed using the technique you were taught and manage stairs one step at a time with a handrail. At this stage you are still following your hip precautions, which usually last for about the first six weeks, such as not bending the hip beyond a right angle, not crossing your legs and avoiding low chairs. Some discomfort with activity and at night, and swelling in the leg and foot, are still common. It is too early to drive: NHS guidance is to wait at least six weeks. Most people resume light everyday activities within three to six weeks, so there is still steady progress to come.

### Answers

**A.**

> Since your six-week hip precautions have ended, you should be able to sit on a low sofa, but it is still wise to use a raised cushion or firm chair for comfort while avoiding bending your hip beyond 90 degrees. Before sitting down, please double-check with your surgeon or physiotherapist to confirm that your specific restrictions are fully lifted and that the low sofa does not cause you pain or instability.

**B.**

> Okay, it’s great that your 6-week precautions are over! While most people can do most movements without affecting the implant after six to eight weeks, it’s really important to continue listening to your body and following your surgeon’s advice. You can now sit on the low sofa, but be mindful of avoiding bending at the waist or hip beyond 90 degrees, and always prioritize keeping your leg elevated and iced if you experience any pain.

**C.**

> According to the discharge notes, your surgeon may have suggested specific precautions for how you sit, bend, and sleep, which typically last for around six weeks. It doesn't say that you can immediately stop following those precautions. Can you please check with your surgeon or physiotherapist to see what specific precautions they recommended for you and when they would be lifted?

**D.**

> Based on the discharge notes, the precautions, including avoiding low chairs, typically last for about six weeks. So, while you're past that timeframe, it's best to check with your surgeon or physiotherapist if sitting on a low sofa is still recommended for you.

---

## r18

| field | value |
|---|---|
| procedure | THA |
| postop_day | 60 |
| domain | rehab |
| answerability | **partial** |

**Query:** can I go swimming, will the chlorine water affect the wound

**Reference answer** (from EV-THA-REHAB-06):

> Swimming is a good low-impact activity once the wound has fully healed and your doctor agrees. The notes do not say anything specific about chlorine, so check with your doctor before you start.

### Frozen context (4 chunk(s), as given to the models)

**[1] The longer term after hip replacement**  
`EV-THA-REC-06-c1` · THA · days 43-365 · in window · distance 0.591

> Lower-impact activities such as walking, swimming, golf, cycling and doubles tennis put less stress on the hip and are generally preferred over high-impact sports such as jogging, singles tennis, basketball and skiing. Infection can occur even long after surgery if bacteria enter the bloodstream, for example during dental procedures or from urinary tract or skin infections, so tell your dentist and doctors that you have a joint replacement; some people with certain risk factors are advised to take antibiotics before dental work. Keep attending your follow-up appointments. Contact your team if the hip becomes increasingly painful, if you develop a fever or redness around the scar, or if you have sudden severe pain with difficulty moving the leg.

**[2] Returning to sport and recreation after hip replacement**  
`EV-THA-REHAB-06-c0` · THA · days 43-84 · in window · distance 0.666

> By two to three months after a hip replacement, many people are ready to add more activity, and your doctor will tell you when you can begin particular sports; timing depends on your surgical approach, your precautions and how your recovery is going. Walking is encouraged. Swimming is a good low-impact activity once the wound has fully healed and your doctor agrees. The American Academy of Orthopaedic Surgeons advises that lower-impact choices such as golf, cycling, and doubles tennis or pickleball load the hip less, so they are generally favoured over higher-impact sports such as jogging, basketball, singles tennis, racquetball or skiing.

**[3] Warning signs after hip replacement: blood clot, infection and dislocation**  
`EV-THA-PAIN-06-c0` · THA · days 1-84 · in window · distance 0.673

> Most discomfort after a hip replacement is part of normal healing, but some symptoms need prompt attention. Possible blood clot in the leg: pain in the calf or leg that is unrelated to the incision, tenderness or redness of the calf, or new or increasing swelling of the thigh, calf, ankle or foot, particularly severe swelling that does not go down when the leg is raised. Report these straight away. Possible clot in the lungs, which is an emergency: sudden shortness of breath, sudden chest pain, or chest pain in one place that comes on with coughing; call emergency services immediately.

**[4] Lingering discomfort and swelling two to three months after hip replacement**  
`EV-THA-PAIN-05-c1` · THA · days 43-84 · in window · distance 0.694

> Aching after a long walk or exercise can still happen, but it should be becoming less frequent and less intense. Your follow-up appointment is often between six and twelve weeks after surgery, which is a good time to raise ongoing pain, swelling or questions about your progress. Full recovery from a hip replacement takes several months, so slow, continued improvement at this stage is normal. Long journeys matter too: pressure changes and long periods without moving can make the operated leg swell, so talk to your doctor before flying or taking a long trip. Contact your surgical team sooner if swelling is new or severe, if pain increases at rest as well as with activity, or if you have a fever, shaking chills, or redness or drainage from the wound.

### Answers

**A.**

> Okay, let’s talk about swimming! The discharge notes say swimming is a good low-impact activity once your wound has fully healed and your doctor agrees – it’s definitely something to discuss with them. Chlorine in the water could potentially irritate the incision, so it’s really important to get the all-clear from your doctor before you start swimming and to keep the area clean afterward.

**B.**

> Yes, swimming is a good low-impact activity. However, you should wait until your wound has fully healed and your doctor agrees before starting swimming, as chlorine can potentially irritate the incision.

**C.**

> Yes, you can likely start swimming around two to three months after your surgery, but you must wait until your doctor confirms your incision has fully healed and there is no risk of infection. Chlorine itself does not typically harm a healed wound, but getting water in an open or healing cut could cause problems, so please check with your physiotherapist before entering the pool to ensure it is safe for you right now.

**D.**

> According to the discharge notes, swimming is a good low-impact activity once the wound has fully healed and your doctor agrees. However, it's recommended to check with your doctor first, as they can advise on the best timing for swimming after your surgery.

---

## r19

| field | value |
|---|---|
| procedure | THA |
| postop_day | 30 |
| domain | rehab |
| answerability | **none** |

**Query:** how many degrees of hip bending should I have at one month

**Reference answer** (from EV-THA-REHAB-02):

> The information I have does not give a target for how far the hip should bend at one month, so please ask your physiotherapist. Until your surgeon says your precautions have ended, the common advice is not to bend the hip beyond 90 degrees, a right angle.

### Frozen context (4 chunk(s), as given to the models)

**[1] Hip precautions during recovery**  
`EV-THA-REHAB-02-c0` · THA · days 1-56 · in window · distance 0.437

> After a hip replacement you may be given extra precautions for how you sit, bend and sleep, typically for around six weeks, to help prevent the new joint from dislocating while the tissues heal. The exact precautions depend on the surgical approach your surgeon used, and not all surgeons recommend the same ones, so follow the instructions you were given and ask if you are unsure which apply to you. Common precautions include: do not bend at the waist or hip beyond 90 degrees, a right angle; do not bring the knee on the operated side up higher than the hip; do not cross your legs at the knees; do not lean forwards when seated or while lowering yourself into a chair; and do not reach down to your feet or ankles.

**[2] Exercise bike and resistance exercises after hip replacement**  
`EV-THA-REHAB-05-c0` · THA · days 22-42 · in window · distance 0.438

> As walking improves, many hip replacement programmes add an exercise bike and resistance exercises. Your doctor may recommend a stationary bicycle, usually at physical therapy, because it helps maintain muscle tone and flexibility. The American Academy of Orthopaedic Surgeons advises raising the seat until the sole of your foot only just reaches the pedal when the knee is nearly straight. Pedal backwards at first, and ride forwards only once a comfortable backward cycling motion is possible. At about four to six weeks the tension can be increased slowly. Sessions typically start at 10 to 15 minutes twice a day and build up to 20 to 30 minutes three or four times a week.

**[3] Hip precautions during recovery**  
`EV-THA-REHAB-02-c1` · THA · days 1-56 · in window · distance 0.491

> Low chairs, low toilet seats and chairs without arms make standing up difficult, so a raised toilet seat and a firm, higher chair with arms help, as do aids such as a grabber, a long-handled sponge and a long shoehorn, so you can avoid bending too far. Your surgeon may also restrict some sleeping positions or suggest a pillow between the knees at night for a period. AAOS guidance adds that, whichever approach was used, most patients can do most of these movements again after six to eight weeks without affecting the implant, but wait until your surgeon confirms that your own precautions have ended. While the hip is recovering, NHS guidance is also to avoid exercises that involve jumping, sudden turns or a high risk of falling, and not to lift heavy objects until you are told it is safe.

**[4] Night discomfort and sleeping positions after hip replacement**  
`EV-THA-PAIN-03-c0` · THA · days 8-21 · **outside the post-op window** · distance 0.472

> For several weeks after a hip replacement it is common to feel some discomfort at night and when you are active. Evenings can be harder because the hip may feel sore after the day's walking and exercises, and it takes time to find a comfortable position in bed while protecting the new joint. For a while your surgeon may want you to stay out of some sleeping positions or to keep a pillow between your knees in bed; these instructions vary with the surgical approach, so ask your own surgeon or physiotherapist which positions are safe for you and for how long. The precautions you were given for sitting and bending, such as not crossing your legs and not bending the hip beyond a right angle, also apply when getting into and out of bed, so use the technique you were taught.

### Answers

**A.**

> Okay, let’s talk about your hip bending at one month after surgery. The discharge notes say you shouldn’t bend at the hip beyond 90 degrees – that’s a right angle – and it’s important to follow your surgeon’s specific instructions. While it’s great you’re working towards greater range of motion, it’s really key to stick with the precautions until your surgeon says it’s okay to increase your bending, so please check with them about your specific goals.

**B.**

> According to the discharge notes, at one month (Day 30) after Total Hip Arthroplasty (THA), it's recommended to avoid bending at the waist or hip beyond a right angle (90 degrees).

**C.**

> At one month (Day 30), your goal is to gradually increase your hip bending, but you should generally avoid bending beyond a right angle (90 degrees) unless your surgeon has specifically cleared you to do so. You can start moving more freely now that you are past the initial six-week precaution period for many movements, but always confirm with your physiotherapist which specific range of motion is safe for your surgical approach before trying new exercises.

**D.**

> Based on the discharge notes, the instructions mention bending the hip beyond 90 degrees, a right angle, for the first six weeks after surgery. The notes don't specify the exact maximum degrees for one month, only that you should avoid bending beyond 90 degrees. It's best to ask your surgeon or physiotherapist for specific guidance on your range of motion at one month.
