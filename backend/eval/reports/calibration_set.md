# Blind calibration set: project_abstain, 5 queries × 4 models

Generated 2026-09-29T08:56:04+00:00. For each query, the four visible answers are labelled A-D in a random order that is different for every query. The key is in `calibration_key.json`; don't open it until you have scored everything here.

How to score: use the rubric in `score.py` (the same one the judge gets). Judge each answer **only against the retrieved context below**. The reference answer shows what a good answer should cover, but it isn't evidence.

- `grounded` 0-2
- each claim labelled `supported` / `embellished` / `unsupported`
- `unanswerable_handling`: `correct` / `invented`, or `n/a` when answerability is `full`
- `followed_format`: friendly, 2-3 sentences, plain language; for partial/none questions, a "not covered, check with your surgeon or physiotherapist" answer also counts

Answers are the visible text only, copied verbatim. Any reasoning trace was removed, exactly as `score.py` shows it to the judge. All 20 answers finished normally (`done_reason: stop`); none were truncated.

---

## q04

| field | value |
|---|---|
| procedure | TKA |
| postop_day | 12 |
| domain | pain |
| answerability | **full** |

**Query:** can I sleep with a pillow under my knee, it feels better like that

**Reference answer** (from EV-TKA-PAIN-03, EV-TKA-REHAB-02):

> No: do not sleep with a pillow under the knee, because a knee that rests bent for long periods can lose its ability to fully straighten, and getting the knee fully straight is especially important for walking well. Keep the knee straight when lying down; propping the heel on a small rolled towel is one way to support the leg. NHS guidance says no particular sleeping position is required, so choose whatever is comfortable while keeping the knee straight.

### Frozen context (4 chunk(s), as given to the models)

**[1] Knee pain at night after knee replacement**  
`EV-TKA-PAIN-03-c0` · TKA · days 8-21 · in window · distance 0.361

> Many people find that the knee aches more in the evening and at night, and the American Academy of Orthopaedic Surgeons notes that it is common for the knee to hurt at night and with activity for several weeks after surgery. By the end of the day the knee can feel sore and swollen from walking and exercise, so a few habits can make nights easier. Spread your walks and exercise sessions through the day instead of doing everything at once. In the evening, rest with the leg raised and use ice for a while to settle swelling. When lying down, keep the knee straight: do not sleep with a pillow under the knee, because a knee that rests bent for long periods can lose its ability to fully straighten.

**[2] Knee pain at night after knee replacement**  
`EV-TKA-PAIN-03-c1` · TKA · days 8-21 · in window · distance 0.391

> NHS guidance says no particular sleeping position is required after a knee replacement, so choose whatever is comfortable while keeping the knee straight; propping the heel on a small rolled towel, as in your straightening exercise, is one way to support the leg. If night pain is regularly stopping you from sleeping, tell your surgical team or physiotherapist. They may suggest changing when you take your prescribed pain relief or adjusting your activity plan, but do not change your medicines on your own. Night pain should slowly become less of a problem over the weeks. Pain that is steadily getting worse instead of easing, pain at rest together with fever or redness around the wound, or new calf pain and swelling should be checked promptly rather than waiting for your next appointment.

**[3] What to expect two to three weeks after knee replacement**  
`EV-TKA-REC-02-c1` · TKA · days 8-21 · in window · distance 0.510

> Swelling, stiffness, and some pain with activity and at night are still common at this stage, and some days will feel worse than others. You may still need help with some household tasks. Keep wearing compression stockings if advised, raise the leg when resting, avoid standing still for long periods, and avoid twisting the knee, bending down and reaching up where you can. Hold off kneeling on the new knee until your doctor approves it, and avoid crossing your legs when sitting for the first six weeks. Keep the wound clean and dry and follow your team's advice about showering. Contact your team if the wound becomes red, hot or starts to drain, if you have a fever, or if calf pain or new swelling develops.

**[4] Knee bend and straightening goals after knee replacement**  
`EV-TKA-REHAB-02-c2` · TKA · days 1-42 · in window · distance 0.543

> Swelling makes the knee harder to bend, so controlling it with ice, raising the leg and sensible pacing also helps you regain movement.

### Answers

**A.**

> No, you should not sleep with a pillow directly under your knee because keeping it bent for long periods can prevent your leg from fully straightening out. Instead, if the position feels more comfortable, try propping your heel up on a small rolled towel to keep your knee straight while resting.

**B.**

> It’s understandable that you’re finding comfort with a pillow under your knee – many people do! However, the discharge notes advise against sleeping with a pillow there, as it can prevent your knee from straightening fully and potentially impact its ability to move correctly. Instead, try keeping your knee straight while lying down and use ice to help manage any swelling and pain, especially in the evenings.

**C.**

> According to the discharge notes, it's actually recommended to keep your knee straight when lying down, and not to sleep with a pillow under the knee. This is because a knee that rests bent for long periods can lose its ability to fully straighten. Instead, you can try propping your heel on a small rolled towel to support your leg while sleeping.

**D.**

> Based on the discharge notes, it's best not to sleep with a pillow under your knee. The notes explain that keeping your knee straight while resting helps prevent it from losing its ability to fully straighten.

---

## q10

| field | value |
|---|---|
| procedure | TKA |
| postop_day | 4 |
| domain | pain |
| answerability | **full** |

**Query:** my calf is swollen and paining, is that part of the knee pain

**Reference answer** (from EV-TKA-PAIN-06, EV-TKA-PAIN-01, EV-TKA-PAIN-02):

> Calf pain and swelling should not be assumed to be part of the knee pain: pain in the calf that is not related to the incision, with new or increasing swelling of the calf, ankle or foot, can be a sign of a blood clot in the leg. Report it to your surgical team promptly, the same day, rather than waiting. Sudden shortness of breath or chest pain needs emergency help straight away, because it can mean a blood clot has reached the lungs.

### Frozen context (4 chunk(s), as given to the models)

**[1] Easing knee pain and swelling after exercise: ice and elevation**  
`EV-TKA-PAIN-02-c2` · TKA · days 1-21 · in window · distance 0.283

> Swelling that is severe, keeps increasing, or does not go down when the leg is raised, especially with calf pain, tenderness or redness above or below the knee, can be a sign of a blood clot and should be reported to your surgical team the same day.

**[2] Knee pain in the first week after knee replacement**  
`EV-TKA-PAIN-01-c1` · TKA · days 1-7 · in window · distance 0.303

> It helps to plan exercise sessions for times when your pain relief is working well and to rest with the leg supported in between. If the knee aches or swells after activity, raise the leg and cool it with an ice pack wrapped in a towel. Pain when bending the knee in this first week is expected, but overall it should be slowly settling rather than steadily getting worse. Contact your surgical team promptly if pain keeps increasing both at rest and with movement, if it is not controlled by the pain relief you were given, or if it comes with fever, shaking chills, increasing redness or drainage at the wound, or new pain and swelling in the calf. Sudden shortness of breath or chest pain needs emergency help straight away, because it can mean a blood clot has reached the lungs.

**[3] Warning signs after knee replacement: when pain or swelling needs urgent attention**  
`EV-TKA-PAIN-06-c1` · TKA · days 1-84 · in window · distance 0.400

> Possible blood clot in the leg: pain in the calf or leg that is not related to the incision, tenderness or redness above or below the knee, and new or increasing swelling of the calf, ankle or foot, particularly swelling that does not settle when the leg is raised. Blood clots in the leg veins are among the more frequent complications after knee replacement, which is why you may be given compression stockings or boots, blood-thinning medicine, and exercises such as ankle pumps to keep blood moving; report possible clot symptoms promptly, because some people have few symptoms at first. A clot that travels to the lungs is an emergency.

**[4] Easing knee pain and swelling after exercise: ice and elevation**  
`EV-TKA-PAIN-02-c0` · TKA · days 1-21 · in window · distance 0.407

> Pain and swelling that flare up after exercise or a walk are common in the first weeks after a knee replacement, and two simple measures help. The first is elevation: rest with the leg raised and supported, ideally with the foot above the level of the heart. NHS advice is to keep the leg up whenever you can, because this helps the swelling go down, and a firm chair with a footstool makes this easier at home. The second is cold. The American Academy of Orthopaedic Surgeons suggests cooling the knee with an ice pack or towel-wrapped ice for 20 minutes, then taking it off for 20 minutes, repeating that on-off cycle for about two hours after exercise or activity.

### Answers

**A.**

> It sounds like you're experiencing some discomfort and swelling in your calf. According to the discharge notes, swelling that's severe, keeps increasing, or doesn't go down when you raise your leg, especially with calf pain, tenderness, or redness above or below the knee, could be a sign of a blood clot. I would recommend checking with your surgeon or physiotherapist to get a better understanding of what's going on with your calf. They can assess the situation and provide guidance on what to do next.

**B.**

> It’s understandable to be concerned about the swelling and pain in your calf – it’s a common issue after a knee replacement. However, it’s really important to pay close attention to the details, as this swelling could be a sign of a blood clot, which needs immediate attention. Please report this to your surgical team right away, as they can investigate and ensure you receive the appropriate care.

**C.**

> No, calf pain and swelling are not part of normal knee pain after surgery and should be reported to your surgical team immediately. While some discomfort around the incision is expected on Day 4, new or worsening pain specifically in the calf can be a sign of a blood clot, which requires urgent medical attention. Please contact your surgeon right away rather than waiting for it to go down with ice or elevation.

**D.**

> Calf swelling and pain can sometimes happen after knee replacement surgery, but it's important to know that if the swelling doesn't go down when you raise your leg, or if you feel pain or tenderness in your calf, it could be a sign of a blood clot. You should report this to your surgical team right away.

---

## q16

| field | value |
|---|---|
| procedure | THA |
| postop_day | 30 |
| domain | pain |
| answerability | **partial** |

**Query:** the pain has shifted from the hip to the front of the thigh and knee, why

**Reference answer** (from EV-THA-PAIN-04, EV-THA-PAIN-06):

> The notes do not explain why pain might move from the hip to the front of the thigh and knee, so please mention this to your physiotherapist or surgeon. They do say that at four to six weeks the muscles around the hip, thigh and buttock can feel tired and achy as they work harder again, and that aching which eases with rest is common. Contact your surgical team if pain that had been improving starts to increase both at rest and with activity, and get emergency help for sudden, severe pain in the hip or groin with difficulty moving the leg.

### Frozen context (4 chunk(s), as given to the models)

**[1] Warning signs after hip replacement: blood clot, infection and dislocation**  
`EV-THA-PAIN-06-c1` · THA · days 1-84 · in window · distance 0.382

> Possible infection: a fever over 100 degrees Fahrenheit (about 37.8 degrees Celsius) that persists, shaking chills, a hip wound that is getting redder, more tender or more swollen, fluid leaking from the wound, or hip pain that keeps increasing both at rest and with activity. Contact your surgeon's office the same day. Possible dislocation: this happens when the ball of the new joint comes out of its socket. It is uncommon, and the risk is highest in the first few months while the tissues heal. Warning signs include sudden, severe pain in the hip or groin, muscle spasm, being unable to move the leg, and the leg suddenly looking turned inward or outward or appearing shorter. Do not try to move or straighten the leg yourself; call an ambulance or go to an emergency department.

**[2] Warning signs after hip replacement: blood clot, infection and dislocation**  
`EV-THA-PAIN-06-c0` · THA · days 1-84 · in window · distance 0.434

> Most discomfort after a hip replacement is part of normal healing, but some symptoms need prompt attention. Possible blood clot in the leg: pain in the calf or leg that is unrelated to the incision, tenderness or redness of the calf, or new or increasing swelling of the thigh, calf, ankle or foot, particularly severe swelling that does not go down when the leg is raised. Report these straight away. Possible clot in the lungs, which is an emergency: sudden shortness of breath, sudden chest pain, or chest pain in one place that comes on with coughing; call emergency services immediately.

**[3] Hip and thigh aching as activity increases (weeks 4-6)**  
`EV-THA-PAIN-04-c1` · THA · days 22-42 · in window · distance 0.492

> Keep following any hip precautions you have been given. The AAOS notes they usually apply for about the first six weeks and that most patients can do most of the restricted movements after six to eight weeks without any effect on the implant, but your own surgeon will tell you when your precautions end. Speak to your physiotherapist if a particular exercise causes sharp pain rather than muscle ache, or if soreness is still getting worse the next day, as the programme may need adjusting. Contact your surgical team if pain that had been improving starts to increase both at rest and with activity, or if you notice a persistent fever, wound redness or drainage, new calf pain, or new or severe swelling of the leg.

**[4] Hip pain in the first week after hip replacement**  
`EV-THA-PAIN-01-c0` · THA · days 1-7 · **outside the post-op window** · distance 0.445

> It is normal for the hip to be sore after a total hip replacement, and you will usually be given pain relief in the days after the operation. Doctors often combine several kinds of pain medicine, which improves relief while keeping the need for opioids as low as possible; take what you are prescribed as directed and speak to your team before changing anything. Getting moving early is part of recovery. Nurses and physiotherapists usually help you start walking as soon as possible after surgery, using crutches or a walking frame at first, and simple exercises in bed such as ankle pumps, buttock squeezes and gentle knee bends begin early. These exercises may feel uncomfortable at first, but AAOS guidance explains that they help recovery and actually reduce pain after the operation.

### Answers

**A.**

> I'm not sure why the pain has shifted from the hip to the front of the thigh and knee. I don't have that information in the discharge notes. I would recommend checking with your surgeon or physiotherapist to see if they can provide any insight or guidance on this. They may be able to offer some suggestions or adjustments to your exercise program to help manage the pain.

**B.**

> Okay, it’s understandable that you’re noticing a change in where you’re feeling pain after your hip replacement. It’s common for pain to shift as your body continues to heal and the muscles around the hip start to adjust – this can sometimes radiate down your thigh and even into your knee. Please contact your physiotherapist or surgeon’s office to discuss this, as they can help you understand exactly what’s happening and adjust your exercises accordingly.

**C.**

> It's common for hip pain to shift to the thigh and knee area as you recover. This often happens because your body is adapting to the new joint and the muscles around it are working differently.

**D.**

> It is common for pain to shift from the hip to the front of your thigh and knee around Day 30 as your healing tissues settle and muscles adjust to the new joint. This pattern often indicates that your exercises are working to strengthen those areas, but if the soreness feels sharp or is getting worse each day, it may be time to speak with your physiotherapist to see if your program needs a small tweak.

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

> Okay, let’s talk about that CPM machine. The discharge notes say you should continue with the exercises we’ve been doing, and icing your knee after each session – that’s really important for reducing swelling. While the hospital suggests a CPM machine, it’s not always necessary, and it’s best to discuss this with your surgeon or physiotherapist to see if it’s the right fit for your recovery.

**B.**

> Based on the discharge notes, the goal is to use the CPM machine to help maintain your knee's extension and prevent stiffness. The notes also say to continue it "as prescribed" by your physiotherapist. So, according to the plan, it seems necessary for achieving those goals.

**C.**

> I don't have information on the specific needs of your recovery after Total Knee Arthroplasty (TKA). I recommend checking with your surgeon or physiotherapist for guidance on whether a Continuous Passive Motion (CPM) machine is necessary for your recovery. They can assess your progress and provide personalized advice on the best course of treatment for you.

**D.**

> Based on your discharge notes for Day 6 after Total Knee Arthroplasty, there is no specific information about renting a Continuous Passive Motion (CPM) machine or whether it is required for your recovery. Since the hospital's recommendation might depend on your specific surgery details and surgeon's preference, you should check directly with your surgeon or physiotherapist to confirm if this device is necessary for you.

---

## c19

| field | value |
|---|---|
| procedure | THA |
| postop_day | 30 |
| domain | recovery |
| answerability | **partial** |

**Query:** my surgeon said 6 weeks precautions but physio says 8 weeks, who is right

**Reference answer** (from EV-THA-REC-03, EV-THA-REHAB-02):

> The notes cannot say which is right for you: hip precautions commonly apply for about the first six weeks, and AAOS guidance notes that most patients can do most of the restricted movements after six to eight weeks. The exact precautions depend on your surgical approach, and the notes say to wait for your surgeon to confirm that yours have ended.

### Frozen context (4 chunk(s), as given to the models)

**[1] Recovery around four to six weeks after hip replacement**  
`EV-THA-REC-03-c1` · THA · days 22-42 · in window · distance 0.516

> For driving, NHS guidance is to wait at least six weeks and check with your doctor that you are fit to drive, and the AAOS notes it is generally safe once you are no longer taking opioid pain medicine and your reflexes have returned to normal. Returning to work usually takes about six weeks according to the NHS, although the AAOS notes it can range from several weeks to several months depending on the demands of your job and the speed of your recovery. NHS guidance also suggests avoiding sex for six to eight weeks after the operation. Some swelling, tiredness and aching after activity are still common at this stage. Your follow-up appointment is often around six to twelve weeks after surgery and is a good time to review your progress and plans.

**[2] Hip and thigh aching as activity increases (weeks 4-6)**  
`EV-THA-PAIN-04-c1` · THA · days 22-42 · in window · distance 0.518

> Keep following any hip precautions you have been given. The AAOS notes they usually apply for about the first six weeks and that most patients can do most of the restricted movements after six to eight weeks without any effect on the implant, but your own surgeon will tell you when your precautions end. Speak to your physiotherapist if a particular exercise causes sharp pain rather than muscle ache, or if soreness is still getting worse the next day, as the programme may need adjusting. Contact your surgical team if pain that had been improving starts to increase both at rest and with activity, or if you notice a persistent fever, wound redness or drainage, new calf pain, or new or severe swelling of the leg.

**[3] Hip precautions during recovery**  
`EV-THA-REHAB-02-c0` · THA · days 1-56 · in window · distance 0.557

> After a hip replacement you may be given extra precautions for how you sit, bend and sleep, typically for around six weeks, to help prevent the new joint from dislocating while the tissues heal. The exact precautions depend on the surgical approach your surgeon used, and not all surgeons recommend the same ones, so follow the instructions you were given and ask if you are unsure which apply to you. Common precautions include: do not bend at the waist or hip beyond 90 degrees, a right angle; do not bring the knee on the operated side up higher than the hip; do not cross your legs at the knees; do not lean forwards when seated or while lowering yourself into a chair; and do not reach down to your feet or ankles.

**[4] Recovery around four to six weeks after hip replacement**  
`EV-THA-REC-03-c0` · THA · days 22-42 · in window · distance 0.584

> Around four to six weeks after a hip replacement, many people are noticeably more independent. The American Academy of Orthopaedic Surgeons says most people are managing most light everyday activities again between three and six weeks after surgery. Walking distance is usually increasing, and your physical therapist will advise when you can safely reduce or stop using your walking aid. Exercise programmes often add an exercise bike and resistance work around this time, with bike tension increased gradually from about four to six weeks. Hip precautions commonly apply for about the first six weeks, and most patients can do most of the restricted movements after six to eight weeks, but wait for your surgeon to confirm that yours have ended.

### Answers

**A.**

> It’s understandable to feel a little confused when you hear different timelines – both six and eight weeks are common after your hip replacement. Generally, the first six weeks of precautions are pretty standard to protect your new joint as it heals, but your surgeon will be the best person to tell you exactly when those restrictions are safe to lift based on your individual progress. Please check with your surgeon or physiotherapist to get a clear understanding of when you can safely move beyond the precautions you’ve been given.

**B.**

> It sounds like you're getting conflicting advice from your surgeon and physiotherapist. Typically, hip precautions are recommended for around 6 weeks after surgery, but it's not uncommon for the exact timeline to vary depending on the individual's progress and the surgeon's specific recommendations. I would recommend checking with your surgeon or physiotherapist to clarify their advice and get a more personalized understanding of what to expect. They can provide you with the most up-to-date and accurate information based on your specific situation.

**C.**

> It is common for there to be a slight difference between your surgeon's advice on hip precautions and your physiotherapist's guidance, as they may have different perspectives based on your specific surgery or recovery progress. Since the discharge notes state that most patients can resume restricted movements after six to eight weeks but emphasize waiting for your surgeon to confirm when their specific precautions end, you should prioritize your surgeon's 6-week timeline while staying alert to any sharp pain or worsening soreness that might suggest you need to hold off slightly longer.

**D.**

> The discharge notes suggest hip precautions are typically given for around six weeks. However, most people can usually do most of the restricted movements after six to eight weeks. It's best to follow the specific precautions recommended by your surgeon and ask them if you have any questions.
