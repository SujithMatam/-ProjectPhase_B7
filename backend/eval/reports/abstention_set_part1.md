# Blind abstention set, part 1 of 3: project_abstain, 7 partial/none queries × 4 models

Generated 2026-09-29T10:32:00+00:00. The full set is all 21 `partial`/`none` queries, split 7 per file in `eval_queries.jsonl` order. For each query, the four visible answers are labelled A-D in a random order that is different for every query across all three parts. The key is in `abstention_key.json` (base64). Don't decode it until all three parts are scored.

How to score: use the rubric in `score.py`. Judge each answer **only against the retrieved context below**. The reference answer shows what a good answer should cover, but it isn't evidence.

- `grounded` 0-2
- each claim labelled `supported` / `embellished` / `unsupported`
- `unanswerable_handling`: `correct` if the answer says the missing part isn't covered (or defers it to the care team) instead of supplying it, `invented` if it fills the gap with unsupported content. It is never `n/a` here, because every query is partial/none.
- `followed_format`: friendly, 2-3 sentences, plain language; a "not covered, check with your surgeon or physiotherapist" answer also counts

Answers are the visible text only, copied verbatim. Any reasoning trace was removed, exactly as `score.py` shows it to the judge. An answer shown as *(no answer was given)* produced no visible text; the judge sees the same placeholder.

---

## q06

| field | value |
|---|---|
| procedure | TKA |
| postop_day | 35 |
| domain | pain |
| answerability | **partial** |

**Query:** my knee is still stiff in the mornings after 5 weeks, when will it go away

**Reference answer** (from EV-TKA-PAIN-04, EV-TKA-REC-05):

> Stiffness is still common four to six weeks after a knee replacement, particularly when you bend the knee a long way, and it is often noticeable after sitting for a while; a knee that is still stiff at this stage does not by itself mean recovery is slow. Keeping up your prescribed bending, straightening and strengthening exercises is the main way to reduce stiffness. The notes do not say when stiffness goes away. Mention it to your physiotherapist early if your range of motion stops improving or the end of the bend feels hard or painful.

### Frozen context (4 chunk(s), as given to the models)

**[1] Knee pain, stiffness and numbness in weeks 4-6**  
`EV-TKA-PAIN-04-c0` · TKA · days 22-42 · in window · distance 0.332

> Four to six weeks after a knee replacement, pain is usually less intense than in the first days, but aching after exercise, stiffness and some swelling are still common. Most people feel some stiffness, particularly when they bend the knee a long way, and it is often noticeable after sitting for a while. Keeping up the prescribed bending, straightening and strengthening exercises is the main way to reduce stiffness. Rehabilitation guidelines advise that if the range of motion stops improving and the end of the bend feels hard or painful, the physiotherapist should contact the surgeon, so mention this early rather than waiting.

**[2] Is my knee recovery on track? What steady progress looks like**  
`EV-TKA-REC-05-c1` · TKA · days 22-84 · in window · distance 0.345

> Useful markers from the HSS guideline are about 80 degrees of bending by the end of the first week, more than 110 degrees with a fully straight knee by around six weeks, and more than 120 degrees for people aiming to return to demanding activities, but your own team's targets take priority. A knee that is still swollen and stiff at four to six weeks is common and does not by itself mean recovery is slow, because mild to moderate swelling can last three to six months. Talk to your physiotherapist or surgeon if your range of motion stops improving or the end of the bend feels hard and painful, if you cannot straighten the knee fully, if pain is increasing rather than decreasing, or if you cannot progress your walking.

**[3] Two to three months after knee replacement: work and fuller activity**  
`EV-TKA-REC-04-c1` · TKA · days 43-84 · **outside the post-op window** · distance 0.367

> A useful sign of progress is being able to manage everyday lower-body tasks such as putting on socks and tying shoelaces, and climbing stairs step over step with little pain. Mild to moderate swelling may still come and go, and it can last for about three to six months. NHS guidance is still to avoid heavy lifting at home, such as vacuuming or carrying shopping, until about three months. Recovery continues well beyond this point; full recovery from a knee replacement can take several months or longer, and the pace varies with age and general health, so do not be discouraged if the knee is not yet as strong or flexible as you hoped. Keep attending your follow-up appointments and raise any concerns about your progress with your team.

**[4] Knee pain at night after knee replacement**  
`EV-TKA-PAIN-03-c0` · TKA · days 8-21 · **outside the post-op window** · distance 0.376

> Many people find that the knee aches more in the evening and at night, and the American Academy of Orthopaedic Surgeons notes that it is common for the knee to hurt at night and with activity for several weeks after surgery. By the end of the day the knee can feel sore and swollen from walking and exercise, so a few habits can make nights easier. Spread your walks and exercise sessions through the day instead of doing everything at once. In the evening, rest with the leg raised and use ice for a while to settle swelling. When lying down, keep the knee straight: do not sleep with a pillow under the knee, because a knee that rests bent for long periods can lose its ability to fully straighten.

### Answers

**A.**

> It's common to feel stiffness in the mornings after 5 weeks, especially after sitting. This is part of the healing process as your knee continues to strengthen. Keep up with your prescribed exercises to help manage stiffness and swelling.

**B.**

> It's not uncommon for stiffness to persist for a bit after surgery. Typically, stiffness should start to improve around 4-6 weeks after surgery, but it can take a few more weeks for it to fully resolve. Since you're already at 5 weeks, it's likely that your stiffness will continue to improve, but it may take a bit longer to feel completely normal again. I would recommend talking to your physiotherapist or surgeon to get a better idea of when you can expect your stiffness to improve.

**C.**

> It is very common for your knee to feel stiffer in the mornings around five weeks post-surgery, and this usually improves gradually as you continue your daily bending and strengthening exercises. While mild stiffness can persist for several months, if your range of motion stops improving or the end of the bend feels hard and painful, please contact your physiotherapist or surgeon rather than waiting.

**D.**

> It’s common to still experience some stiffness in the mornings after a TKA, and it’s great you’re proactively addressing it! While stiffness usually decreases significantly within four to six weeks, it can linger for up to three months, so continuing with your prescribed exercises is key. To help manage this, try elevating your leg and icing it in the mornings – and please discuss this with your physiotherapist or surgeon to ensure you’re on track with your recovery.

---

## q09

| field | value |
|---|---|
| procedure | TKA |
| postop_day | 8 |
| domain | pain |
| answerability | **none** |

**Query:** which painkiller is stronger for knee pain, tramadol or paracetamol

**Reference answer** (from EV-TKA-PAIN-03):

> The information I have does not compare pain medicines, so I can't say which is stronger. Please ask your surgical team, and do not change your medicines on your own.

### Frozen context (4 chunk(s), as given to the models)

**[1] Knee pain at night after knee replacement**  
`EV-TKA-PAIN-03-c1` · TKA · days 8-21 · in window · distance 0.678

> NHS guidance says no particular sleeping position is required after a knee replacement, so choose whatever is comfortable while keeping the knee straight; propping the heel on a small rolled towel, as in your straightening exercise, is one way to support the leg. If night pain is regularly stopping you from sleeping, tell your surgical team or physiotherapist. They may suggest changing when you take your prescribed pain relief or adjusting your activity plan, but do not change your medicines on your own. Night pain should slowly become less of a problem over the weeks. Pain that is steadily getting worse instead of easing, pain at rest together with fever or redness around the wound, or new calf pain and swelling should be checked promptly rather than waiting for your next appointment.

**[2] Knee bend and straightening goals after knee replacement**  
`EV-TKA-REHAB-02-c2` · TKA · days 1-42 · in window · distance 0.688

> Swelling makes the knee harder to bend, so controlling it with ice, raising the leg and sensible pacing also helps you regain movement.

**[3] Building strength and function in weeks 2-6 after knee replacement**  
`EV-TKA-REHAB-04-c2` · TKA · days 8-42 · in window · distance 0.699

> By the end of this stage the usual aims are controlled swelling and pain, good bend with a fully straight knee, no lag when lifting the straight leg, a normal walking pattern with or without an aid, climbing a standard step with control, and independence in daily activities. Your physiotherapist will adapt the programme to your progress.

**[4] Knee pain, stiffness and numbness in weeks 4-6**  
`EV-TKA-PAIN-04-c0` · TKA · days 22-42 · **outside the post-op window** · distance 0.663

> Four to six weeks after a knee replacement, pain is usually less intense than in the first days, but aching after exercise, stiffness and some swelling are still common. Most people feel some stiffness, particularly when they bend the knee a long way, and it is often noticeable after sitting for a while. Keeping up the prescribed bending, straightening and strengthening exercises is the main way to reduce stiffness. Rehabilitation guidelines advise that if the range of motion stops improving and the end of the bend feels hard or painful, the physiotherapist should contact the surgeon, so mention this early rather than waiting.

### Answers

**A.**

> I'm not sure which painkiller is stronger for knee pain between tramadol and paracetamol. I would recommend checking with your surgeon or physiotherapist for guidance on the best pain management options for your specific situation. They can provide personalized advice based on your individual needs and medical history.

**B.**

> The discharge notes don't mention tramadol or paracetamol, so they can't tell you which one is stronger for your knee pain. For the best advice on pain relief, please ask your surgeon or physiotherapist.

**C.**

> Okay, let’s talk about pain relief after your knee replacement. The discharge notes don’t specifically say which painkiller is stronger, but they do advise against changing your medication on your own – it’s really important to stick with what your surgical team has prescribed. Night pain can often ease up over the weeks, and if it’s still a problem, let your team know so they can adjust your plan.

**D.**

> I do not have information about which specific painkiller is stronger between tramadol and paracetamol in this context. Please check with your surgeon or physiotherapist before changing your medicines or deciding which one to take. Your surgical team knows exactly what you are prescribed and can advise you on the best option for your current pain levels.

---

## q14

| field | value |
|---|---|
| procedure | THA |
| postop_day | 15 |
| domain | pain |
| answerability | **partial** |

**Query:** how should I sleep, I keep waking up with hip pain in the night

**Reference answer** (from EV-THA-PAIN-03):

> For several weeks after a hip replacement it is common to feel some discomfort at night, and it should ease gradually over the weeks. Which sleeping positions are safe depends on your surgical approach: your surgeon may want you to avoid some positions or keep a pillow between your knees, so ask your surgeon or physiotherapist which positions are safe for you and for how long. Spreading walking and exercise through the day, raising the leg slightly and applying ice in the evening, and getting up briefly to move if you have been still can help. If pain is regularly stopping you from sleeping, tell your team; they can review when you take your prescribed pain relief, but do not change your medicines on your own.

### Frozen context (4 chunk(s), as given to the models)

**[1] Night discomfort and sleeping positions after hip replacement**  
`EV-THA-PAIN-03-c1` · THA · days 8-21 · in window · distance 0.300

> Things that may help at night include spreading walking and exercise through the day rather than doing it all at once, raising the leg slightly and applying ice in the evening to settle swelling, and getting up briefly to move if you have been still for a long time. If pain is regularly stopping you from sleeping, tell your team; they can review when you take your prescribed pain relief or adjust your activity plan, but do not change your medicines on your own. Night-time discomfort should ease gradually over the weeks. Pain that is steadily increasing, pain at rest together with fever or redness at the wound, sudden severe hip pain with difficulty moving the leg, or new calf pain and swelling should be checked promptly.

**[2] Night discomfort and sleeping positions after hip replacement**  
`EV-THA-PAIN-03-c0` · THA · days 8-21 · in window · distance 0.338

> For several weeks after a hip replacement it is common to feel some discomfort at night and when you are active. Evenings can be harder because the hip may feel sore after the day's walking and exercises, and it takes time to find a comfortable position in bed while protecting the new joint. For a while your surgeon may want you to stay out of some sleeping positions or to keep a pillow between your knees in bed; these instructions vary with the surgical approach, so ask your own surgeon or physiotherapist which positions are safe for you and for how long. The precautions you were given for sitting and bending, such as not crossing your legs and not bending the hip beyond a right angle, also apply when getting into and out of bed, so use the technique you were taught.

**[3] What you may be able to do two to three weeks after hip replacement**  
`EV-THA-REC-02-c1` · THA · days 8-21 · in window · distance 0.458

> Your exercise programme will usually include bed exercises and standing exercises such as knee raises, hip abduction and hip extension several times a day. You should be able to get in and out of bed using the technique you were taught and manage stairs one step at a time with a handrail. At this stage you are still following your hip precautions, which usually last for about the first six weeks, such as not bending the hip beyond a right angle, not crossing your legs and avoiding low chairs. Some discomfort with activity and at night, and swelling in the leg and foot, are still common. It is too early to drive: NHS guidance is to wait at least six weeks. Most people resume light everyday activities within three to six weeks, so there is still steady progress to come.

**[4] Standing exercises after hip replacement**  
`EV-THA-REHAB-03-c1` · THA · days 8-21 · in window · distance 0.473

> Standing hip extension: slowly lift the operated leg backwards while keeping your back straight, hold for two or three counts, and return. Keep every movement slow and controlled rather than swinging the leg. These exercises help your balance and walking and work alongside the bed exercises and daily walks. Continue to follow your hip precautions while exercising; in particular, keep the knee below waist height during knee raises so the hip does not bend too far. As strength improves, your physiotherapist may add resistance using elastic tubing, bringing the leg forward, out to the side and backwards against the band. Muscle tiredness afterwards is expected. Stop and tell your physiotherapist if an exercise causes sharp pain in the hip or groin, or if you feel unsteady doing it.

### Answers

**A.**

> *(no answer was given)*

**B.**

> It’s really common to experience some discomfort and pain when you’re sleeping after a hip replacement, and it’s great you’re taking steps to manage it! Try elevating your leg slightly and applying ice to the area in the evening to help reduce swelling, and you might also find it helpful to get up briefly to move around if you’ve been lying still for a while. Remember, this nighttime discomfort should ease up gradually over the coming weeks, and if it’s not improving, please let your physical therapy team know – they can help you adjust your routine or explore other options.

**C.**

> Based on the discharge notes, it's common to feel some discomfort at night and when you're active after a hip replacement. To help with hip pain at night, try raising the leg slightly and applying ice in the evening to settle swelling. You can also try getting up briefly to move if you've been still for a while. Remember to check with your surgeon or physiotherapist for specific guidance on safe sleeping positions, as they may have recommendations for you.

**D.**

> It is very common to feel some discomfort at night after your hip replacement, but since you are on Day 15, try sleeping with a pillow between your knees if your surgeon has approved this position for your specific surgery. You can also help reduce that pain by spreading your walking and exercise throughout the day rather than doing it all at once, and applying ice in the evening to settle any swelling. If the pain is steadily increasing or you notice redness, fever, or sudden severe pain, please tell your team immediately so they can review your pain relief plan.

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

> Okay, it’s understandable that you’re noticing a change in where you’re feeling pain after your hip replacement. It’s common for pain to shift as your body continues to heal and the muscles around the hip start to adjust – this can sometimes radiate down your thigh and even into your knee. Please contact your physiotherapist or surgeon’s office to discuss this, as they can help you understand exactly what’s happening and adjust your exercises accordingly.

**B.**

> It is common for pain to shift from the hip to the front of your thigh and knee around Day 30 as your healing tissues settle and muscles adjust to the new joint. This pattern often indicates that your exercises are working to strengthen those areas, but if the soreness feels sharp or is getting worse each day, it may be time to speak with your physiotherapist to see if your program needs a small tweak.

**C.**

> It's common for hip pain to shift to the thigh and knee area as you recover. This often happens because your body is adapting to the new joint and the muscles around it are working differently.

**D.**

> I'm not sure why the pain has shifted from the hip to the front of the thigh and knee. I don't have that information in the discharge notes. I would recommend checking with your surgeon or physiotherapist to see if they can provide any insight or guidance on this. They may be able to offer some suggestions or adjustments to your exercise program to help manage the pain.

---

## q17

| field | value |
|---|---|
| procedure | THA |
| postop_day | 65 |
| domain | pain |
| answerability | **partial** |

**Query:** my operated leg feels longer than the other one, will it stay like that

**Reference answer** (from EV-THA-PAIN-05):

> Some people notice that one leg feels slightly longer or shorter than the other after a hip replacement: surgeons aim to make leg lengths even, but sometimes lengthen or shorten the leg slightly to keep the hip stable. The notes do not say whether this feeling changes over time. Some patients find a shoe lift more comfortable, so mention it to your surgeon if it bothers you.

### Frozen context (4 chunk(s), as given to the models)

**[1] Two to three months after hip replacement, including lingering swelling**  
`EV-THA-REC-04-c1` · THA · days 43-84 · in window · distance 0.478

> Keep reducing it by raising the leg slightly, applying ice, wearing compression stockings if advised, and avoiding sitting still for long periods. Report new or severe swelling to your doctor, because it may be a warning sign of a blood clot, particularly if it does not go down when the leg is raised above the level of the heart or comes with calf pain, tenderness or redness. Continue your exercises and daily walking, building activity gradually. Talk to your doctor before long flights or car journeys, because pressure changes and long periods without moving can make the operated leg swell. Recovery from a hip replacement continues for several months, so it is normal to still be improving at this stage.

**[2] Lingering discomfort and swelling two to three months after hip replacement**  
`EV-THA-PAIN-05-c0` · THA · days 43-84 · in window · distance 0.497

> By two to three months after a hip replacement, most people are walking with more confidence and doing most everyday activities, but some symptoms can linger. Mild to moderate swelling of the leg can continue for three to six months after surgery, and it tends to be more noticeable after a long, active day or after sitting still for a long time. It usually improves with rest, raising the leg slightly and applying ice. Some people notice that one leg feels slightly longer or shorter than the other; surgeons aim to make leg lengths even but sometimes lengthen or shorten the leg slightly to keep the hip stable, and some patients find a shoe lift more comfortable, so mention it if it bothers you.

**[3] Lingering discomfort and swelling two to three months after hip replacement**  
`EV-THA-PAIN-05-c1` · THA · days 43-84 · in window · distance 0.501

> Aching after a long walk or exercise can still happen, but it should be becoming less frequent and less intense. Your follow-up appointment is often between six and twelve weeks after surgery, which is a good time to raise ongoing pain, swelling or questions about your progress. Full recovery from a hip replacement takes several months, so slow, continued improvement at this stage is normal. Long journeys matter too: pressure changes and long periods without moving can make the operated leg swell, so talk to your doctor before flying or taking a long trip. Contact your surgical team sooner if swelling is new or severe, if pain increases at rest as well as with activity, or if you have a fever, shaking chills, or redness or drainage from the wound.

**[4] The longer term after hip replacement**  
`EV-THA-REC-06-c0` · THA · days 43-365 · in window · distance 0.545

> Recovery from a hip replacement takes several months, and a few things continue to matter in the months and years afterwards. Dislocation, where the ball of the new joint comes out of the socket, is uncommon; the risk is greatest in the first few months while the tissues heal, and most people can do most previously restricted movements after six to eight weeks, but follow your surgeon's advice about when your precautions end. Some people feel that one leg is slightly longer or shorter than the other after surgery. Surgeons aim to make leg lengths equal but sometimes adjust length slightly for stability, and a shoe lift can help if the difference is noticeable. Over a period of years, a hip implant can wear or loosen, most often as a result of everyday activity.

### Answers

**A.**

> It's not uncommon for one leg to feel slightly longer or shorter than the other after a hip replacement, as the surgeon aims to make leg lengths even. However, this difference is usually temporary and can be adjusted with a shoe lift if needed. It's unlikely to be a permanent issue, but it's always best to check with your surgeon to confirm.

**B.**

> It’s common to notice a slight difference in leg length after a hip replacement, and it can sometimes feel like one leg is longer than the other. Surgeons often make small adjustments to leg length during surgery, and while it might feel persistent now, it’s usually a gradual improvement over the next few months. Please discuss this with your surgeon or physiotherapist to ensure you’re getting the best support and guidance for your recovery.

**C.**

> It is common for your operated leg to feel slightly longer or shorter a few months after surgery, as surgeons sometimes adjust the implant length intentionally for stability. While this difference might seem permanent, many people find that wearing a small shoe lift on the affected side makes walking much more comfortable and balanced.

**D.**

> It's common for people to notice a slight difference in leg length after hip replacement, even if the surgeon tried to make them even. This difference might persist after recovery, especially if the surgeon made a small adjustment for stability. It's best to discuss this with your surgeon or physiotherapist for personalized advice.

---

## q18

| field | value |
|---|---|
| procedure | THA |
| postop_day | 75 |
| domain | pain |
| answerability | **partial** |

**Query:** I want to fly to Dubai next week for work, is that ok with my hip

**Reference answer** (from EV-THA-PAIN-05, EV-THA-REC-04):

> The notes do not say whether flying is safe for you; they advise talking to your doctor before flying or taking a long trip, because pressure changes and long periods without moving can make the operated leg swell. Report new or severe swelling to your doctor, especially if it does not go down when the leg is raised or comes with calf pain, tenderness or redness.

### Frozen context (4 chunk(s), as given to the models)

**[1] Returning to sport and recreation after hip replacement**  
`EV-THA-REHAB-06-c1` · THA · days 43-84 · in window · distance 0.568

> While the hip is still recovering, NHS guidance is to avoid exercises that involve jumping, sudden turns or a high risk of falling, and not to lift heavy objects until you are told it is safe. This means that sports involving running, jumping, quick changes of direction or a risk of falls should be discussed with your surgeon before you return, even if you feel well. When you do restart an activity, build up gradually, keep doing your strengthening exercises, and notice how the hip feels the next day. Pain that lasts after activity or new swelling are signs to ease back and seek advice. Most people can return to an active lifestyle, but the right sports and the right time are an individual decision to make with your surgeon.

**[2] Returning to sport and recreation after hip replacement**  
`EV-THA-REHAB-06-c0` · THA · days 43-84 · in window · distance 0.568

> By two to three months after a hip replacement, many people are ready to add more activity, and your doctor will tell you when you can begin particular sports; timing depends on your surgical approach, your precautions and how your recovery is going. Walking is encouraged. Swimming is a good low-impact activity once the wound has fully healed and your doctor agrees. The American Academy of Orthopaedic Surgeons advises that lower-impact choices such as golf, cycling, and doubles tennis or pickleball load the hip less, so they are generally favoured over higher-impact sports such as jogging, basketball, singles tennis, racquetball or skiing.

**[3] The longer term after hip replacement**  
`EV-THA-REC-06-c1` · THA · days 43-365 · in window · distance 0.604

> Lower-impact activities such as walking, swimming, golf, cycling and doubles tennis put less stress on the hip and are generally preferred over high-impact sports such as jogging, singles tennis, basketball and skiing. Infection can occur even long after surgery if bacteria enter the bloodstream, for example during dental procedures or from urinary tract or skin infections, so tell your dentist and doctors that you have a joint replacement; some people with certain risk factors are advised to take antibiotics before dental work. Keep attending your follow-up appointments. Contact your team if the hip becomes increasingly painful, if you develop a fever or redness around the scar, or if you have sudden severe pain with difficulty moving the leg.

**[4] Leaving hospital and the first week at home after hip replacement**  
`EV-THA-REC-01-c0` · THA · days 1-7 · **outside the post-op window** · distance 0.555

> After a hip replacement, many people go home within one to three days, and some have the operation as a day case and go home the same day. Staff will help you get up and walking early after the operation, using crutches or a walking frame at first. Before discharge you will usually need to get in and out of bed by yourself, have acceptable pain control, manage eating, drinking and using the toilet, walk with your aid on a level surface, manage two or three steps up and down, do your exercises, and understand the hip precautions you have been given. A physiotherapist or occupational therapist will go through daily tasks and your home exercises with you, and following the exercises early on helps the long-term strength and movement of the hip.

### Answers

**A.**

> Flying in just one week after your surgery is generally not recommended because the swelling and stiffness from long flights can delay your recovery and increase pain. You should check with your surgeon or physiotherapist before booking, as they need to confirm that your incision has fully healed and that you have enough strength to travel safely without risking a fall.

**B.**

> Okay, let’s talk about flying with your hip after your THA. It’s great you’re thinking ahead! While many people can travel after this surgery, it’s really important to discuss your trip to Dubai with your surgeon first, as long-term recovery varies. They can assess your specific situation and advise you on any precautions you might need to take during the flight.

**C.**

> Based on the discharge notes, there isn't specific advice on whether flying is okay after your hip replacement. The notes focus more on returning to activity levels and precautions.
> 
> To get the best advice for your specific situation, it's best to discuss flying with your surgeon. They can consider your recovery progress and the precautions you've been given.
> 
> The notes do mention avoiding high-risk activities like jumping, sudden turns, or high-risk falls, and building up your activity gradually, which is generally good advice.

**D.**

> I don't have information about your specific hip replacement surgery or recovery progress. I would recommend checking with your surgeon or physiotherapist to get personalized advice on traveling after a hip replacement. They can assess your current condition and provide guidance on whether flying to Dubai is safe for you.

---

## q19

| field | value |
|---|---|
| procedure | THA |
| postop_day | 20 |
| domain | pain |
| answerability | **none** |

**Query:** can I use a heating pad and Volini spray on the hip

**Reference answer** (from EV-THA-PAIN-02):

> The information I have does not cover heating pads or medicated sprays such as Volini, so please check with your surgeon or physiotherapist before using them on your hip. For pain and swelling, the notes mention raising the leg slightly and applying ice for short periods.

### Frozen context (4 chunk(s), as given to the models)

**[1] Night discomfort and sleeping positions after hip replacement**  
`EV-THA-PAIN-03-c0` · THA · days 8-21 · in window · distance 0.588

> For several weeks after a hip replacement it is common to feel some discomfort at night and when you are active. Evenings can be harder because the hip may feel sore after the day's walking and exercises, and it takes time to find a comfortable position in bed while protecting the new joint. For a while your surgeon may want you to stay out of some sleeping positions or to keep a pillow between your knees in bed; these instructions vary with the surgical approach, so ask your own surgeon or physiotherapist which positions are safe for you and for how long. The precautions you were given for sitting and bending, such as not crossing your legs and not bending the hip beyond a right angle, also apply when getting into and out of bed, so use the technique you were taught.

**[2] Hip precautions during recovery**  
`EV-THA-REHAB-02-c0` · THA · days 1-56 · in window · distance 0.628

> After a hip replacement you may be given extra precautions for how you sit, bend and sleep, typically for around six weeks, to help prevent the new joint from dislocating while the tissues heal. The exact precautions depend on the surgical approach your surgeon used, and not all surgeons recommend the same ones, so follow the instructions you were given and ask if you are unsure which apply to you. Common precautions include: do not bend at the waist or hip beyond 90 degrees, a right angle; do not bring the knee on the operated side up higher than the hip; do not cross your legs at the knees; do not lean forwards when seated or while lowering yourself into a chair; and do not reach down to your feet or ankles.

**[3] Hip and thigh aching as activity increases (weeks 4-6)**  
`EV-THA-PAIN-04-c1` · THA · days 22-42 · **outside the post-op window** · distance 0.598

> Keep following any hip precautions you have been given. The AAOS notes they usually apply for about the first six weeks and that most patients can do most of the restricted movements after six to eight weeks without any effect on the implant, but your own surgeon will tell you when your precautions end. Speak to your physiotherapist if a particular exercise causes sharp pain rather than muscle ache, or if soreness is still getting worse the next day, as the programme may need adjusting. Contact your surgical team if pain that had been improving starts to increase both at rest and with activity, or if you notice a persistent fever, wound redness or drainage, new calf pain, or new or severe swelling of the leg.

**[4] Leaving hospital and the first week at home after hip replacement**  
`EV-THA-REC-01-c0` · THA · days 1-7 · **outside the post-op window** · distance 0.603

> After a hip replacement, many people go home within one to three days, and some have the operation as a day case and go home the same day. Staff will help you get up and walking early after the operation, using crutches or a walking frame at first. Before discharge you will usually need to get in and out of bed by yourself, have acceptable pain control, manage eating, drinking and using the toilet, walk with your aid on a level surface, manage two or three steps up and down, do your exercises, and understand the hip precautions you have been given. A physiotherapist or occupational therapist will go through daily tasks and your home exercises with you, and following the exercises early on helps the long-term strength and movement of the hip.

### Answers

**A.**

> Okay, let’s talk about managing your hip pain. You can definitely use a heating pad to help soothe any discomfort you’re feeling, and Volini spray can be used to help with some of the stiffness. However, it’s really important to follow the instructions your surgeon or physiotherapist gave you regarding hip precautions – things like not bending your hip too far – while you’re using these, and always check with them first to make sure it’s okay for you.

**B.**

> Based on the discharge notes, while ice and heat therapy are mentioned as part of the hip precautions, the notes don't specify exactly how to use a heating pad or Volini spray. It's best to ask your surgeon or physiotherapist for specific instructions on how to apply heat or cold therapy to your hip.

**C.**

> Based on the discharge notes, it doesn't seem that heating pads or Volini spray are recommended for use on the hip after a hip replacement. In fact, the notes mention that you should follow the precautions given by your surgeon and physiotherapist, which may include avoiding certain activities or positions to help the new joint heal. It's best to check with your surgeon or physiotherapist for specific guidance on using heat or other treatments on your hip.

**D.**

> Based on your discharge notes for Day 20, there is no specific mention of using heating pads or Volini spray, so please check with your surgeon or physiotherapist before trying them. While you may feel some soreness as activity increases around this time, the text advises speaking to your physio if an exercise causes sharp pain rather than a dull muscle ache, and they can guide you on whether heat or topical sprays are safe for your specific surgical approach.
