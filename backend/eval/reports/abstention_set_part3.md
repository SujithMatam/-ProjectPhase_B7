# Blind abstention set, part 3 of 3: project_abstain, 7 partial/none queries × 4 models

Generated 2026-09-29T10:32:00+00:00. The full set is all 21 `partial`/`none` queries, split 7 per file in `eval_queries.jsonl` order. For each query, the four visible answers are labelled A-D in a random order that is different for every query across all three parts. The key is in `abstention_key.json` (base64). Don't decode it until all three parts are scored.

How to score: use the rubric in `score.py`. Judge each answer **only against the retrieved context below**. The reference answer shows what a good answer should cover, but it isn't evidence.

- `grounded` 0-2
- each claim labelled `supported` / `embellished` / `unsupported`
- `unanswerable_handling`: `correct` if the answer says the missing part isn't covered (or defers it to the care team) instead of supplying it, `invented` if it fills the gap with unsupported content. It is never `n/a` here, because every query is partial/none.
- `followed_format`: friendly, 2-3 sentences, plain language; a "not covered, check with your surgeon or physiotherapist" answer also counts

Answers are the visible text only, copied verbatim. Any reasoning trace was removed, exactly as `score.py` shows it to the judge. An answer shown as *(no answer was given)* produced no visible text; the judge sees the same placeholder.

---

## r20

| field | value |
|---|---|
| procedure | THA |
| postop_day | 100 |
| domain | rehab |
| answerability | **partial** |

**Query:** I want to play badminton again, is it a safe sport for the hip

**Reference answer** (from EV-THA-REC-06):

> The notes do not mention badminton specifically. They say lower-impact activities such as walking, swimming, golf, cycling and doubles tennis put less stress on the hip and are generally preferred over high-impact sports such as jogging, singles tennis, basketball and skiing, so ask your surgeon whether badminton suits your hip.

### Frozen context (4 chunk(s), as given to the models)

**[1] The longer term after hip replacement**  
`EV-THA-REC-06-c1` · THA · days 43-365 · in window · distance 0.550

> Lower-impact activities such as walking, swimming, golf, cycling and doubles tennis put less stress on the hip and are generally preferred over high-impact sports such as jogging, singles tennis, basketball and skiing. Infection can occur even long after surgery if bacteria enter the bloodstream, for example during dental procedures or from urinary tract or skin infections, so tell your dentist and doctors that you have a joint replacement; some people with certain risk factors are advised to take antibiotics before dental work. Keep attending your follow-up appointments. Contact your team if the hip becomes increasingly painful, if you develop a fever or redness around the scar, or if you have sudden severe pain with difficulty moving the leg.

**[2] Returning to sport and recreation after hip replacement**  
`EV-THA-REHAB-06-c0` · THA · days 43-84 · **outside the post-op window** · distance 0.473

> By two to three months after a hip replacement, many people are ready to add more activity, and your doctor will tell you when you can begin particular sports; timing depends on your surgical approach, your precautions and how your recovery is going. Walking is encouraged. Swimming is a good low-impact activity once the wound has fully healed and your doctor agrees. The American Academy of Orthopaedic Surgeons advises that lower-impact choices such as golf, cycling, and doubles tennis or pickleball load the hip less, so they are generally favoured over higher-impact sports such as jogging, basketball, singles tennis, racquetball or skiing.

**[3] Returning to sport and recreation after hip replacement**  
`EV-THA-REHAB-06-c1` · THA · days 43-84 · **outside the post-op window** · distance 0.534

> While the hip is still recovering, NHS guidance is to avoid exercises that involve jumping, sudden turns or a high risk of falling, and not to lift heavy objects until you are told it is safe. This means that sports involving running, jumping, quick changes of direction or a risk of falls should be discussed with your surgeon before you return, even if you feel well. When you do restart an activity, build up gradually, keep doing your strengthening exercises, and notice how the hip feels the next day. Pain that lasts after activity or new swelling are signs to ease back and seek advice. Most people can return to an active lifestyle, but the right sports and the right time are an individual decision to make with your surgeon.

**[4] Exercise bike and resistance exercises after hip replacement**  
`EV-THA-REHAB-05-c0` · THA · days 22-42 · **outside the post-op window** · distance 0.639

> As walking improves, many hip replacement programmes add an exercise bike and resistance exercises. Your doctor may recommend a stationary bicycle, usually at physical therapy, because it helps maintain muscle tone and flexibility. The American Academy of Orthopaedic Surgeons advises raising the seat until the sole of your foot only just reaches the pedal when the knee is nearly straight. Pedal backwards at first, and ride forwards only once a comfortable backward cycling motion is possible. At about four to six weeks the tension can be increased slowly. Sessions typically start at 10 to 15 minutes twice a day and build up to 20 to 30 minutes three or four times a week.

### Answers

**A.**

> Based on the discharge notes, it seems that high-impact sports like badminton might not be the best choice for you right now, especially since you've had a Total Hip Arthroplasty (THA). The notes mention that high-impact sports like jogging, singles tennis, basketball, and skiing are generally not recommended, as they can put too much stress on the hip. I would recommend checking with your surgeon or physiotherapist to get their specific advice on whether badminton is safe for you to play again.

**B.**

> Based on your discharge notes, badminton is generally considered a high-impact sport that puts significant stress on the hip, so it is usually not recommended unless you have specific clearance from your surgeon. While lower-impact activities like doubles tennis or cycling are preferred for most people after 2 to 3 months, playing singles badminton involves sudden stops and changes of direction that could be risky for your new joint. You should discuss returning to any sport with your surgical team before starting, as they will decide if it is safe for you based on your recovery progress.

**C.**

> Okay, let’s talk about badminton. Based on the discharge notes, it’s generally a good idea to stick with lower-impact activities like golf, cycling, or doubles tennis – these put less stress on your hip compared to sports like badminton. However, it’s really important to discuss this with your surgeon first, as they’ll consider your individual recovery and surgical approach to determine if it’s safe for you to return to badminton.

**D.**

> Based on the discharge notes, badminton is generally not recommended as it's considered a higher-impact sport involving jumping and quick movements which can put stress on the hip. The notes suggest sticking to lower-impact activities like doubles tennis or pickleball instead.

---

## c10

| field | value |
|---|---|
| procedure | THA |
| postop_day | 18 |
| domain | recovery |
| answerability | **partial** |

**Query:** can I cook standing in the kitchen at two and half weeks

**Reference answer** (from EV-THA-REC-02, EV-THA-REHAB-02):

> Two to three weeks after a hip replacement, many people still need help with tasks such as cooking, shopping and laundry. The notes do not say how long you can stand to cook, so ask your physiotherapist. While you are in the kitchen, keep to your hip precautions, such as not bending at the hip beyond 90 degrees and not reaching down to your feet or ankles.

### Frozen context (0 chunk(s), as given to the models)

*(no chunks were retrieved)*

### Answers

**A.**

> Based on the discharge reference for Day 18, it doesn't specifically mention cooking while standing. This type of activity usually requires more time to recover from. For guidance on when it's safe to return to cooking, especially standing, please check with your surgeon or physiotherapist.

**B.**

> Yes, by day 18 (two and a half weeks), many patients are able to stand and walk around the house, including cooking while standing, provided they have good balance and can move comfortably. However, since your specific surgery date isn't in our records, please confirm with your surgeon or physiotherapist that your healing is on track before starting new activities like cooking.

**C.**

> Okay, let’s talk about getting back to cooking. At this point, about two and a half weeks after your surgery, you should be able to stand in the kitchen for short periods, but it’s really important to take it easy and listen to your body. Continue to focus on icing your hip after any activity and elevating your leg – this will help manage any swelling and keep you comfortable as you gradually build up your strength and confidence. Please check with your surgeon or physiotherapist to ensure you’re progressing safely.

**D.**

> At 2.5 weeks after your Total Hip Arthroplasty (THA), it's generally recommended to avoid standing for long periods, especially in the kitchen, as it can put stress on your new hip joint. However, I don't have specific information on your individual progress or any previous conversations with your surgeon or physiotherapist. I would recommend checking with your surgeon or physiotherapist for personalized guidance on when it's safe to resume activities like cooking while standing. They can provide you with more tailored advice based on your specific recovery.

---

## c13

| field | value |
|---|---|
| procedure | THA |
| postop_day | 45 |
| domain | recovery |
| answerability | **partial** |

**Query:** can I sleep on my operated side now

**Reference answer** (from EV-THA-REHAB-02, EV-THA-REC-04):

> Your surgeon may restrict some sleeping positions for a period after a hip replacement, and the notes do not say specifically when you can sleep on the operated side. Most patients can do most of the movements restricted by their hip precautions after six to eight weeks, but only once their surgeon agrees, so check with your surgeon or physiotherapist first.

### Frozen context (4 chunk(s), as given to the models)

**[1] Hip precautions during recovery**  
`EV-THA-REHAB-02-c1` · THA · days 1-56 · in window · distance 0.574

> Low chairs, low toilet seats and chairs without arms make standing up difficult, so a raised toilet seat and a firm, higher chair with arms help, as do aids such as a grabber, a long-handled sponge and a long shoehorn, so you can avoid bending too far. Your surgeon may also restrict some sleeping positions or suggest a pillow between the knees at night for a period. AAOS guidance adds that, whichever approach was used, most patients can do most of these movements again after six to eight weeks without affecting the implant, but wait until your surgeon confirms that your own precautions have ended. While the hip is recovering, NHS guidance is also to avoid exercises that involve jumping, sudden turns or a high risk of falling, and not to lift heavy objects until you are told it is safe.

**[2] Hip precautions during recovery**  
`EV-THA-REHAB-02-c0` · THA · days 1-56 · in window · distance 0.607

> After a hip replacement you may be given extra precautions for how you sit, bend and sleep, typically for around six weeks, to help prevent the new joint from dislocating while the tissues heal. The exact precautions depend on the surgical approach your surgeon used, and not all surgeons recommend the same ones, so follow the instructions you were given and ask if you are unsure which apply to you. Common precautions include: do not bend at the waist or hip beyond 90 degrees, a right angle; do not bring the knee on the operated side up higher than the hip; do not cross your legs at the knees; do not lean forwards when seated or while lowering yourself into a chair; and do not reach down to your feet or ankles.

**[3] Night discomfort and sleeping positions after hip replacement**  
`EV-THA-PAIN-03-c0` · THA · days 8-21 · **outside the post-op window** · distance 0.526

> For several weeks after a hip replacement it is common to feel some discomfort at night and when you are active. Evenings can be harder because the hip may feel sore after the day's walking and exercises, and it takes time to find a comfortable position in bed while protecting the new joint. For a while your surgeon may want you to stay out of some sleeping positions or to keep a pillow between your knees in bed; these instructions vary with the surgical approach, so ask your own surgeon or physiotherapist which positions are safe for you and for how long. The precautions you were given for sitting and bending, such as not crossing your legs and not bending the hip beyond a right angle, also apply when getting into and out of bed, so use the technique you were taught.

**[4] Night discomfort and sleeping positions after hip replacement**  
`EV-THA-PAIN-03-c1` · THA · days 8-21 · **outside the post-op window** · distance 0.608

> Things that may help at night include spreading walking and exercise through the day rather than doing it all at once, raising the leg slightly and applying ice in the evening to settle swelling, and getting up briefly to move if you have been still for a long time. If pain is regularly stopping you from sleeping, tell your team; they can review when you take your prescribed pain relief or adjust your activity plan, but do not change your medicines on your own. Night-time discomfort should ease gradually over the weeks. Pain that is steadily increasing, pain at rest together with fever or redness at the wound, sudden severe hip pain with difficulty moving the leg, or new calf pain and swelling should be checked promptly.

### Answers

**A.**

> Based on the discharge notes, you should generally avoid sleeping on your operated (right) side for at least six weeks to prevent dislocation, as this position often requires bending the hip beyond 90 degrees or crossing the legs. Instead, it is common to sleep on your unaffected left side with a pillow between your knees to keep your right leg straight and slightly elevated. Since specific restrictions vary by surgical approach, please confirm with your surgeon or physiotherapist exactly how long you need to avoid this position before trying it again.

**B.**

> I don't have that information in the discharge notes. It's best to check with your surgeon or physiotherapist to see what sleeping positions are safe for you after a hip replacement. They can provide personalized guidance based on your specific surgery and recovery progress.

**C.**

> Based on the discharge notes, it's best to check with your surgeon or physiotherapist about sleeping positions. The notes mention that for a while after surgery, surgeons might advise against certain sleeping positions, like keeping a pillow between your knees. They also state that the specific instructions depend on your surgical approach, so ask them which positions are safe for you and for how long.

**D.**

> Okay, let’s talk about sleeping after your hip replacement. Generally, after about six to eight weeks, most people can start sleeping on their operated side again, but it’s really important to check with your surgeon first to make sure it’s okay for you. For now, your surgeon may have advised you to avoid certain sleeping positions, like sleeping on your side, so it’s best to confirm with them before you try it.

---

## c17

| field | value |
|---|---|
| procedure | THA |
| postop_day | 95 |
| domain | recovery |
| answerability | **partial** |

**Query:** how many years will the hip implant last

**Reference answer** (from EV-THA-REC-06):

> The notes do not say how many years a hip implant lasts. They explain that over a period of years an implant can wear or loosen, most often as a result of everyday activity, and that lower-impact activities such as walking, swimming, golf, cycling and doubles tennis put less stress on the hip than high-impact sports.

### Frozen context (4 chunk(s), as given to the models)

**[1] The longer term after hip replacement**  
`EV-THA-REC-06-c0` · THA · days 43-365 · in window · distance 0.317

> Recovery from a hip replacement takes several months, and a few things continue to matter in the months and years afterwards. Dislocation, where the ball of the new joint comes out of the socket, is uncommon; the risk is greatest in the first few months while the tissues heal, and most people can do most previously restricted movements after six to eight weeks, but follow your surgeon's advice about when your precautions end. Some people feel that one leg is slightly longer or shorter than the other after surgery. Surgeons aim to make leg lengths equal but sometimes adjust length slightly for stability, and a shoe lift can help if the difference is noticeable. Over a period of years, a hip implant can wear or loosen, most often as a result of everyday activity.

**[2] Recovery around four to six weeks after hip replacement**  
`EV-THA-REC-03-c0` · THA · days 22-42 · **outside the post-op window** · distance 0.402

> Around four to six weeks after a hip replacement, many people are noticeably more independent. The American Academy of Orthopaedic Surgeons says most people are managing most light everyday activities again between three and six weeks after surgery. Walking distance is usually increasing, and your physical therapist will advise when you can safely reduce or stop using your walking aid. Exercise programmes often add an exercise bike and resistance work around this time, with bike tension increased gradually from about four to six weeks. Hip precautions commonly apply for about the first six weeks, and most patients can do most of the restricted movements after six to eight weeks, but wait for your surgeon to confirm that yours have ended.

**[3] Two to three months after hip replacement, including lingering swelling**  
`EV-THA-REC-04-c0` · THA · days 43-84 · **outside the post-op window** · distance 0.444

> By two to three months after a hip replacement, most people are walking further, doing most everyday activities, and returning to work and hobbies. Most patients can do the movements restricted by their hip precautions after six to eight weeks, once their surgeon agrees. Your follow-up appointment, often between six and twelve weeks after surgery, is the time to check your progress and ask about further activities, including sport. Swelling can still be present. The American Academy of Orthopaedic Surgeons notes that mild to moderate swelling may last for three to six months after surgery, so some leg or ankle swelling at six to twelve weeks, particularly at the end of the day or after sitting still or travelling, is not unusual and does not by itself mean that your recovery is slow.

**[4] Hip and thigh aching as activity increases (weeks 4-6)**  
`EV-THA-PAIN-04-c1` · THA · days 22-42 · **outside the post-op window** · distance 0.447

> Keep following any hip precautions you have been given. The AAOS notes they usually apply for about the first six weeks and that most patients can do most of the restricted movements after six to eight weeks without any effect on the implant, but your own surgeon will tell you when your precautions end. Speak to your physiotherapist if a particular exercise causes sharp pain rather than muscle ache, or if soreness is still getting worse the next day, as the programme may need adjusting. Contact your surgical team if pain that had been improving starts to increase both at rest and with activity, or if you notice a persistent fever, wound redness or drainage, new calf pain, or new or severe swelling of the leg.

### Answers

**A.**

> Okay, let’s talk about the long-term outlook for your hip implant. Generally, hip implants can last for several years, but they can wear down or loosen over time due to everyday activity. While most people can continue to do most things for six to eight weeks after surgery, it’s important to remember that surgeons aim to make leg lengths equal, and a shoe lift can help if there’s a slight difference.  I don’t have an exact timeframe for how long your implant will last, so please discuss this with your surgeon to get the most accurate information for your specific situation.

**B.**

> Based on the discharge notes provided, there is no specific information about how many years a hip implant will last. While the text mentions that implants can wear or loosen over time due to everyday activity, it does not give a guaranteed lifespan for your specific device. For an accurate estimate of your implant's longevity and any potential future risks, please check with your surgeon or physiotherapist.

**C.**

> Unfortunately, I don't have that information in the discharge notes. The notes mention that a hip implant can wear or loosen over time, but they don't provide a specific estimate for how long the implant is likely to last. I would recommend checking with your surgeon or physiotherapist for more information on the expected lifespan of your hip implant.

**D.**

> Based on the provided reference, hip implants can wear or loosen over a period of years, often as a result of everyday activity.

---

## c18

| field | value |
|---|---|
| procedure | THA |
| postop_day | 150 |
| domain | recovery |
| answerability | **partial** |

**Query:** my dentist wants to do a root canal, do I need antibiotics before it

**Reference answer** (from EV-THA-REC-06):

> Tell your dentist that you have a hip replacement, because infection can occur even long after surgery if bacteria enter the bloodstream, for example during dental procedures. Some people with certain risk factors are advised to take antibiotics before dental work; the notes do not list those factors, so ask your dentist or doctor whether this applies to you.

### Frozen context (2 chunk(s), as given to the models)

**[1] The longer term after hip replacement**  
`EV-THA-REC-06-c1` · THA · days 43-365 · in window · distance 0.722

> Lower-impact activities such as walking, swimming, golf, cycling and doubles tennis put less stress on the hip and are generally preferred over high-impact sports such as jogging, singles tennis, basketball and skiing. Infection can occur even long after surgery if bacteria enter the bloodstream, for example during dental procedures or from urinary tract or skin infections, so tell your dentist and doctors that you have a joint replacement; some people with certain risk factors are advised to take antibiotics before dental work. Keep attending your follow-up appointments. Contact your team if the hip becomes increasingly painful, if you develop a fever or redness around the scar, or if you have sudden severe pain with difficulty moving the leg.

**[2] Hip pain in the first week after hip replacement**  
`EV-THA-PAIN-01-c0` · THA · days 1-7 · **outside the post-op window** · distance 0.739

> It is normal for the hip to be sore after a total hip replacement, and you will usually be given pain relief in the days after the operation. Doctors often combine several kinds of pain medicine, which improves relief while keeping the need for opioids as low as possible; take what you are prescribed as directed and speak to your team before changing anything. Getting moving early is part of recovery. Nurses and physiotherapists usually help you start walking as soon as possible after surgery, using crutches or a walking frame at first, and simple exercises in bed such as ankle pumps, buttock squeezes and gentle knee bends begin early. These exercises may feel uncomfortable at first, but AAOS guidance explains that they help recovery and actually reduce pain after the operation.

### Answers

**A.**

> I don't have information about your specific situation, but I can suggest that you check with your surgeon or physiotherapist for guidance on this. They can assess your individual risk factors and provide personalized advice on whether antibiotics are necessary before your dentist procedure.

**B.**

> Okay, that’s a really important question to ask! Based on the discharge notes, it’s absolutely crucial that you let your dentist and all your doctors know you’ve had a hip replacement. Because bacteria can travel through your bloodstream and potentially cause an infection around your new hip, even long after surgery, it’s standard practice for some people to take antibiotics beforehand, especially before procedures like a root canal. Please discuss this with your dentist to determine the best course of action for you.

**C.**

> Based on the discharge notes, it mentions that infection can happen during dental procedures, and some people with certain risk factors might need antibiotics before dental work like a root canal. So, it's possible you might need antibiotics, but whether you specifically need them depends on your individual risk factors.

**D.**

> Yes, you should tell your dentist that you have a hip replacement so they can decide if you need antibiotics before the root canal. While not everyone requires them, some people with specific risk factors are advised to take them to prevent infection in your new joint. Please confirm this plan with your dental team and let them know about your surgery date.

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

> It is common for there to be a slight difference between your surgeon's advice on hip precautions and your physiotherapist's guidance, as they may have different perspectives based on your specific surgery or recovery progress. Since the discharge notes state that most patients can resume restricted movements after six to eight weeks but emphasize waiting for your surgeon to confirm when their specific precautions end, you should prioritize your surgeon's 6-week timeline while staying alert to any sharp pain or worsening soreness that might suggest you need to hold off slightly longer.

**B.**

> The discharge notes suggest hip precautions are typically given for around six weeks. However, most people can usually do most of the restricted movements after six to eight weeks. It's best to follow the specific precautions recommended by your surgeon and ask them if you have any questions.

**C.**

> It’s understandable to feel a little confused when you hear different timelines – both six and eight weeks are common after your hip replacement. Generally, the first six weeks of precautions are pretty standard to protect your new joint as it heals, but your surgeon will be the best person to tell you exactly when those restrictions are safe to lift based on your individual progress. Please check with your surgeon or physiotherapist to get a clear understanding of when you can safely move beyond the precautions you’ve been given.

**D.**

> It sounds like you're getting conflicting advice from your surgeon and physiotherapist. Typically, hip precautions are recommended for around 6 weeks after surgery, but it's not uncommon for the exact timeline to vary depending on the individual's progress and the surgeon's specific recommendations. I would recommend checking with your surgeon or physiotherapist to clarify their advice and get a more personalized understanding of what to expect. They can provide you with the most up-to-date and accurate information based on your specific situation.

---

## c20

| field | value |
|---|---|
| procedure | THA |
| postop_day | 8 |
| domain | recovery |
| answerability | **none** |

**Query:** which walker is better, the folding one or the one with wheels

**Reference answer** (from EV-THA-REHAB-04):

> The information I have does not compare types of walking frame, so please ask your physiotherapist which one suits you. Your physical therapist will help you decide which aids you need.

### Frozen context (1 chunk(s), as given to the models)

**[1] Walking aids, moving off the walker, and stairs after hip replacement**  
`EV-THA-REHAB-04-c0` · THA · days 8-42 · in window · distance 0.724

> Walking is central to recovery after a hip replacement, and you will need a walking frame or crutches at first. Move the frame or crutches forward a short distance, then step forward with the operated leg, knee straight, so the heel touches the floor first, and bring the other leg through. NHS guidance is to walk every day as far as is comfortable and to tell your physiotherapist about any problems. The American Academy of Orthopaedic Surgeons suggests changing to one crutch or a cane once you are able to stand and walk for over ten minutes and the leg is strong enough that you no longer rely on the frame or crutches to take its weight; hold the cane in the hand opposite the operated hip.

### Answers

**A.**

> I don't have information on specific walker models, but I can tell you that the type of walker you need will depend on your individual needs and mobility. Typically, walkers with wheels are easier to maneuver, especially on uneven surfaces, but folding walkers can be more convenient for traveling or storing. I recommend checking with your surgeon or physiotherapist for their recommendation on the best type of walker for your specific situation. They can assess your progress and provide guidance on the most suitable option for you.

**B.**

> Based on your discharge notes for Day 8 after a hip replacement, there isn't a specific recommendation between a folding walker and a wheeled walker; instead, the guidance focuses on choosing whichever device you can use comfortably for over ten minutes without relying on it to take your leg's weight. Many patients find that once they are strong enough, switching to a single crutch or cane is often easier than managing a standard walker with wheels. Since your specific recovery pace depends on how your right hip feels today, please check with your surgeon or physiotherapist to see which type of frame best suits your current strength and mobility goals.

**C.**

> Based on the discharge reference, the note doesn't specify whether a folding walker or a wheeled walker is better. It only mentions that you will need a walking frame or crutches initially. For a specific recommendation on which type is best for you, it's best to ask your physiotherapist or surgeon.

**D.**

> Okay, let’s talk about walkers! Based on the notes, it looks like you’ll likely start with a walking frame initially, and eventually you might switch to a single crutch or cane. Both folding and wheeled walkers can be helpful, but the best choice depends on what feels most comfortable and stable for you – it’s great to discuss this with your physiotherapist to see which one will best support you as you start moving around again.
