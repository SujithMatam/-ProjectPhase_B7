# 2026-09-29: full eval run — summary

Scope: read-only apart from this report. Nothing staged or committed. The run is described in `2026-09-29_full-run-launch.md`, and the figures below come from `results/*.jsonl` and `results/_runs.jsonl`.

## Status: finished

The run process has exited. The first request started at 2026-09-29T03:40:56+00:00 and the last finished at 2026-09-29T04:22:48+00:00 (UTC), about 42 min in total. `run.log` has no errors, retries or restarts: each model loaded once, in the requested order.

### Completion per results file

| file | lines | ok / 60 | errors | truncated at num_predict 600 (`done_reason: length`) |
|---|---|---|---|---|
| `llama3.2-latest_project.jsonl` | 60 | 60 | 0 | 0 |
| `llama3.2-latest_project_abstain.jsonl` | 60 | 60 | 0 | 0 |
| `llama3.2-latest_minimal.jsonl` | 60 | 60 | 0 | 0 |
| `gemma3-4b_project.jsonl` | 60 | 60 | 0 | 0 |
| `gemma3-4b_project_abstain.jsonl` | 60 | 60 | 0 | 0 |
| `gemma3-4b_minimal.jsonl` | 60 | 60 | 0 | 0 |
| `medgemma1.5-4b-it-q4_K_M_project.jsonl` | 60 | 60 | 0 | **41**: q01, q06, q10, q11, q12, q13, q14, q16, q17, q18, q19, q20, r02, r03, r04, r05, r06, r07, r08, r09, r10, r11, r12, r14, r15, r17, r18, r19, r20, c01, c03, c04, c05, c07, c09, c10, c12, c13, c15, c18, c19 |
| `medgemma1.5-4b-it-q4_K_M_project_abstain.jsonl` | 60 | 60 | 0 | **36**: q01, q04, q05, q06, q08, q10, q11, q12, q13, q14, q16, q17, q18, q19, r01, r02, r03, r04, r05, r07, r10, r12, r14, r15, r16, r17, r19, c02, c03, c07, c09, c12, c13, c15, c19, c20 |
| `medgemma1.5-4b-it-q4_K_M_minimal.jsonl` | 60 | 60 | 0 | **2**: q07, q19 |
| `qwen3.5-4b_project.jsonl` | 60 | 60 | 0 | 0 |
| `qwen3.5-4b_project_abstain.jsonl` | 60 | 60 | 0 | 0 |
| `qwen3.5-4b_minimal.jsonl` | 60 | 60 | 0 | 0 |

All 720 requests finished `ok`, with no errors and no duplicate or torn lines. **Every truncation is MedGemma** (79 of its 180 requests). llama3.2, gemma3 and qwen3.5 never hit the limit.

## Main finding: MedGemma's reasoning trace eats the token budget under the project prompts

MedGemma 1.5 writes a reasoning block (`<unused94>…<unused95>`) before its answer. The harness separates this out as `reasoning_trace`. Ollama doesn't report a `thinking` capability for this model, so `think:false` does nothing to stop it. With the long project-style system prompt, the trace often uses up all 600 tokens before any answer appears:

| MedGemma variant | with trace | trace never closed → **empty answer** | trace closed, answer cut off mid-sentence | complete answers | mean raw tokens | mean visible tokens |
|---|---|---|---|---|---|---|
| project | 60 | 38 | 3 | 19 | 565 | 15.4 |
| project_abstain | 54 | 31 | 5 | 24 | 503 | 23.5 |
| minimal | 5 | 0 | 1 | 58 | 93 | 62.7 |

- **project:** 38/60 answers are empty and 3 more (q06, r12, c15) are cut off mid-sentence. **project_abstain:** 31/60 are empty and 5 more (q08, q10, r01, r05, r16) are cut off. The empties are spread across every answerability label and domain (project: full 21, partial 13, none 4), so this isn't limited to hard questions.
- **minimal:** only 5/60 have a trace (q19, r09, c07, c10, c12). In all five, the frozen context doesn't answer the question: q19 and r09 are labelled `none`, and c07, c10 and c12 are known retrieval misses (README "Test-set notes"). So under the short prompt, MedGemma reasons only when the context falls short. There are 2 truncations. q19 is a trace plus a cut-off answer. q07 has **no** trace: MedGemma copied the context back verbatim, starting with `[1] Aching and swelling…`, until it hit the limit (594 visible tokens).
- **Effect on scoring:** as things stand, MedGemma's project and project_abstain scores would mostly measure whether it finishes reasoning within 600 tokens, not how good its answers are. Scoring an empty answer as "invented" or "not grounded" would unfairly penalise medical tuning in the gemma3 vs medgemma comparison. Before scoring, decide whether to (a) re-run MedGemma with a larger `num_predict` (the traces are about 2,000-2,700 characters), (b) score only the completed answers and report the completion rate separately, or (c) treat budget exhaustion as a failure, which is also valid because production uses `num_predict` 150. That is a methodology choice for you; I haven't re-run anything.
- The MedGemma latency figures reflect this. Most project requests take the full ~12 s (600 tokens at ~51 tok/s). Time to first visible token is averaged **only over non-empty answers**, because empty answers have no first visible token.

## Per model and variant

- **Latency:** `latency_s.total`, wall-clock time per request.
- **TTFVT:** `time_to_first_visible_token`, the mean and median over requests that produced visible text. `n` is shown where some requests produced none.
- **Cold start:** measured **once per model**, as the discarded warm-up request after loading, so all three variants show the same value. Load time is shown next to it.
- **Peak VRAM:** the maximum `gpu_used_peak_mib` in the file. `nvidia-smi` measures this system-wide, and GPU use was 0 MiB before each model loaded. Every model was **100% in VRAM** (`/api/ps` `size_vram == size`), with no CPU spill.

| model | variant | latency mean (s) | latency median (s) | TTFVT mean (s) | TTFVT median (s) | cold start (s) [load] | mean visible tokens | with reasoning trace | empty | peak VRAM (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| llama3.2:latest | project | 1.54 | 1.53 | 0.31 | 0.33 | 0.12 [6.7] | 82.9 | 0 | 0 | 2537 |
| llama3.2:latest | project_abstain | 1.38 | 1.36 | 0.14 | 0.14 | 0.12 [6.7] | 84.0 | 0 | 0 | 2537 |
| llama3.2:latest | minimal | 1.15 | 1.07 | 0.35 | 0.27 | 0.12 [6.7] | 53.9 | 0 | 0 | 2537 |
| gemma3:4b | project | 2.14 | 2.12 | 0.44 | 0.47 | 4.79 [5.8] | 88.0 | 0 | 0 | 3733 |
| gemma3:4b | project_abstain | 2.26 | 2.28 | 0.47 | 0.50 | 4.79 [5.8] | 92.7 | 0 | 0 | 3733 |
| gemma3:4b | minimal | 1.64 | 1.58 | 0.46 | 0.41 | 4.79 [5.8] | 60.8 | 0 | 0 | 3733 |
| medgemma1.5:4b-it-q4_K_M | project | 11.39 | 12.10 | 9.39 (n=22) | 9.59 (n=22) | 0.28 [6.2] | 15.4 | 60 | 38 | 3733 |
| medgemma1.5:4b-it-q4_K_M | project_abstain | 10.29 | 12.14 | 7.27 (n=29) | 8.26 (n=29) | 0.28 [6.2] | 23.5 | 54 | 31 | 3733 |
| medgemma1.5:4b-it-q4_K_M | minimal | 2.16 | 1.45 | 0.93 | 0.41 | 0.28 [6.2] | 62.7 | 5 | 0 | 3733 |
| qwen3.5:4b | project | 2.25 | 2.22 | 0.58 | 0.64 | 0.17 [5.8] | 76.8 | 0 | 0 | 3827 |
| qwen3.5:4b | project_abstain | 2.36 | 2.35 | 0.61 | 0.66 | 0.17 [5.8] | 81.1 | 0 | 0 | 3827 |
| qwen3.5:4b | minimal | 1.93 | 1.95 | 0.52 | 0.58 | 0.17 [5.8] | 65.6 | 0 | 0 | 3827 |

Notes:
- Latency outliers over 5 s that weren't truncated: llama3.2:latest minimal q02 7.4 s (34 tokens); gemma3:4b minimal r20 6.8 s (67 tokens); medgemma1.5:4b-it-q4_K_M project q02 8.2 s (37 tokens); medgemma1.5:4b-it-q4_K_M project q03 11.2 s (50 tokens); medgemma1.5:4b-it-q4_K_M project q04 6.2 s (45 tokens); medgemma1.5:4b-it-q4_K_M project q05 10.8 s (63 tokens); medgemma1.5:4b-it-q4_K_M project q07 7.5 s (62 tokens); medgemma1.5:4b-it-q4_K_M project q08 10.8 s (37 tokens); medgemma1.5:4b-it-q4_K_M project q09 9.2 s (57 tokens); medgemma1.5:4b-it-q4_K_M project q15 12.2 s (47 tokens); medgemma1.5:4b-it-q4_K_M project r01 11.7 s (40 tokens); medgemma1.5:4b-it-q4_K_M project r13 10.7 s (43 tokens); medgemma1.5:4b-it-q4_K_M project r16 9.8 s (36 tokens); medgemma1.5:4b-it-q4_K_M project c02 10.8 s (63 tokens); medgemma1.5:4b-it-q4_K_M project c06 9.7 s (39 tokens); medgemma1.5:4b-it-q4_K_M project c08 7.3 s (24 tokens); medgemma1.5:4b-it-q4_K_M project c11 11.3 s (53 tokens); medgemma1.5:4b-it-q4_K_M project c14 10.0 s (40 tokens); medgemma1.5:4b-it-q4_K_M project c16 9.4 s (50 tokens); medgemma1.5:4b-it-q4_K_M project c17 9.6 s (26 tokens); medgemma1.5:4b-it-q4_K_M project c20 11.7 s (34 tokens); medgemma1.5:4b-it-q4_K_M project_abstain q02 8.6 s (36 tokens); medgemma1.5:4b-it-q4_K_M project_abstain q07 7.0 s (64 tokens); medgemma1.5:4b-it-q4_K_M project_abstain q09 7.7 s (45 tokens); medgemma1.5:4b-it-q4_K_M project_abstain q20 8.6 s (66 tokens); medgemma1.5:4b-it-q4_K_M project_abstain r08 5.8 s (81 tokens); medgemma1.5:4b-it-q4_K_M project_abstain r09 10.4 s (57 tokens); medgemma1.5:4b-it-q4_K_M project_abstain r13 8.8 s (43 tokens); medgemma1.5:4b-it-q4_K_M project_abstain r18 9.8 s (38 tokens); medgemma1.5:4b-it-q4_K_M project_abstain r20 12.0 s (51 tokens); medgemma1.5:4b-it-q4_K_M project_abstain c01 6.8 s (53 tokens); medgemma1.5:4b-it-q4_K_M project_abstain c05 10.7 s (42 tokens); medgemma1.5:4b-it-q4_K_M project_abstain c06 11.2 s (42 tokens); medgemma1.5:4b-it-q4_K_M project_abstain c08 7.4 s (21 tokens); medgemma1.5:4b-it-q4_K_M project_abstain c10 11.0 s (57 tokens); medgemma1.5:4b-it-q4_K_M project_abstain c14 10.1 s (41 tokens); medgemma1.5:4b-it-q4_K_M project_abstain c16 9.9 s (72 tokens); medgemma1.5:4b-it-q4_K_M project_abstain c17 9.8 s (26 tokens); medgemma1.5:4b-it-q4_K_M project_abstain c18 10.7 s (58 tokens); medgemma1.5:4b-it-q4_K_M minimal c07 9.8 s (49 tokens); medgemma1.5:4b-it-q4_K_M minimal c10 5.5 s (31 tokens); medgemma1.5:4b-it-q4_K_M minimal c12 6.4 s (41 tokens).
- gemma3:4b's 4.8 s cold start is almost all prompt evaluation of the warm-up request (4.73 s for 17 tokens), which looks like a one-off first-run cost. The other models took 0.1-0.3 s.
- Decode speed (`eval_tokens_per_s`, mean over all variants): llama3.2:latest 69, gemma3:4b 53, medgemma1.5:4b-it-q4_K_M 52, qwen3.5:4b 47 tok/s.
- Wall time per model: llama3.2 ≈ 4 min, gemma3 ≈ 6 min, medgemma ≈ 24 min (the reasoning traces), qwen3.5 ≈ 7 min.
- No record has `context_may_be_truncated` set, so every prompt fitted in `num_ctx` 4096.

## Responses under project_abstain: q04, q10, r04, c12, r09

These are the full visible responses (the `response` field), copied verbatim. MedGemma's reasoning traces aren't shown; they are in each record's `reasoning_trace` field.

### q04: TKA, day 12, `pain`, answerability `full`

> **Q:** can I sleep with a pillow under my knee, it feels better like that

**llama3.2:latest** (`done_reason: stop`, 71 visible / 72 raw tokens)

> According to the discharge notes, it's actually recommended to keep your knee straight when lying down, and not to sleep with a pillow under the knee. This is because a knee that rests bent for long periods can lose its ability to fully straighten. Instead, you can try propping your heel on a small rolled towel to support your leg while sleeping.

**gemma3:4b** (`done_reason: stop`, 78 visible / 79 raw tokens)

> It’s understandable that you’re finding comfort with a pillow under your knee – many people do! However, the discharge notes advise against sleeping with a pillow there, as it can prevent your knee from straightening fully and potentially impact its ability to move correctly. Instead, try keeping your knee straight while lying down and use ice to help manage any swelling and pain, especially in the evenings.

**medgemma1.5:4b-it-q4_K_M** (`done_reason: length`, 0 visible / 600 raw tokens, reasoning trace 2679 chars (**never closed**))

> *(empty: all 600 tokens went on the reasoning trace, and no answer was produced)*

**qwen3.5:4b** (`done_reason: stop`, 58 visible / 59 raw tokens)

> No, you should not sleep with a pillow directly under your knee because keeping it bent for long periods can prevent your leg from fully straightening out. Instead, if the position feels more comfortable, try propping your heel up on a small rolled towel to keep your knee straight while resting.

### q10: TKA, day 4, `pain`, answerability `full`

> **Q:** my calf is swollen and paining, is that part of the knee pain

**llama3.2:latest** (`done_reason: stop`, 105 visible / 106 raw tokens)

> It sounds like you're experiencing some discomfort and swelling in your calf. According to the discharge notes, swelling that's severe, keeps increasing, or doesn't go down when you raise your leg, especially with calf pain, tenderness, or redness above or below the knee, could be a sign of a blood clot. I would recommend checking with your surgeon or physiotherapist to get a better understanding of what's going on with your calf. They can assess the situation and provide guidance on what to do next.

**gemma3:4b** (`done_reason: stop`, 81 visible / 82 raw tokens)

> It’s understandable to be concerned about the swelling and pain in your calf – it’s a common issue after a knee replacement. However, it’s really important to pay close attention to the details, as this swelling could be a sign of a blood clot, which needs immediate attention. Please report this to your surgical team right away, as they can investigate and ensure you receive the appropriate care.

**medgemma1.5:4b-it-q4_K_M** (`done_reason: length`, 50 visible / 600 raw tokens, reasoning trace 2538 chars (closed))

> Calf swelling and pain can sometimes happen after knee replacement surgery, but it's important to know that if the swelling doesn't go down when you raise your leg, or if you feel pain or tenderness in your calf, it could be a sign *[cut off at num_predict 600]*

**qwen3.5:4b** (`done_reason: stop`, 80 visible / 82 raw tokens)

> No, calf pain and swelling are not part of normal knee pain after surgery and should be reported to your surgical team immediately. While some discomfort around the incision is expected on Day 4, new or worsening pain specifically in the calf can be a sign of a blood clot, which requires urgent medical attention. Please contact your surgeon right away rather than waiting for it to go down with ice or elevation.

### r04: TKA, day 10, `rehab`, answerability `partial`

> **Q:** the leg raises are too painful, can I skip them and just walk more instead

**llama3.2:latest** (`done_reason: stop`, 60 visible / 61 raw tokens)

> I don't have that information in the discharge notes. It's best to check with your surgeon or physiotherapist to see what exercises are recommended for you at this stage. They can advise on the best way to progress your exercises and ensure you're not putting too much strain on your knee.

**gemma3:4b** (`done_reason: stop`, 85 visible / 86 raw tokens)

> Okay, it sounds like those straight leg raises are causing you some pain – that’s really common after a knee replacement. You can definitely focus on increasing your walking as you feel able, and your physiotherapist will be monitoring your progress closely. Remember to continue icing your leg and elevating it when you’re resting to help manage any swelling, and please check with your physiotherapist about adjusting your exercises if the pain persists.

**medgemma1.5:4b-it-q4_K_M** (`done_reason: length`, 0 visible / 600 raw tokens, reasoning trace 2723 chars (**never closed**))

> *(empty: all 600 tokens went on the reasoning trace, and no answer was produced)*

**qwen3.5:4b** (`done_reason: stop`, 84 visible / 86 raw tokens)

> It is understandable that the leg raises feel painful right now, but skipping them entirely might slow down your recovery because these exercises help build the specific strength needed for walking without limping. Since you are on Day 10, please check with your physiotherapist before changing your routine, as they can advise whether to modify the leg raises or focus more on gentle walking and other safe movements that match your current pain level.

### c12: THA, day 40, `recovery`, answerability `full`

> **Q:** is it normal to still need the stick at 6 weeks, my son says I should stop using it

**llama3.2:latest** (`done_reason: stop`, 120 visible / 123 raw tokens)

> It's not uncommon for people to still need some assistance with mobility and balance at 6 weeks after surgery. Your son might be right that you should be able to walk without the stick by now, but everyone's recovery is different. Typically, people can start to reduce their reliance on a walking stick around 4-6 weeks after surgery, but it's great that you're listening to your body and not pushing yourself too hard. Let's talk to your surgeon or physiotherapist to get a better idea of what's normal for you and when it's okay to start weaning off the stick.

**gemma3:4b** (`done_reason: stop`, 111 visible / 113 raw tokens)

> Okay, it’s definitely understandable to be wondering about this! At 6 weeks after your THA, it’s still quite common for people to still rely on a walker or stick for support – many patients continue to use them for a few more weeks. Focus on continuing to gradually increase your weight-bearing as your physical therapist has instructed, and remember to ice your hip and elevate your leg as often as possible to help with swelling and pain. Please check with your surgeon or physiotherapist to discuss your specific progress and what’s right for you.

**medgemma1.5:4b-it-q4_K_M** (`done_reason: length`, 0 visible / 600 raw tokens, reasoning trace 2187 chars (**never closed**))

> *(empty: all 600 tokens went on the reasoning trace, and no answer was produced)*

**qwen3.5:4b** (`done_reason: stop`, 85 visible / 87 raw tokens)

> It is actually quite common for patients to still need a walking aid like a walker or crutches around the 6-week mark after hip surgery, as your hip may not be strong enough yet to walk safely without support. Since your son suggests stopping, please double-check with your surgeon or physiotherapist before removing the stick, as they know exactly how much weight-bearing you are allowed based on your specific surgery and healing progress.

### r09: TKA, day 6, `rehab`, answerability `none`

> **Q:** the hospital is asking me to rent a CPM machine, is it really necessary

**llama3.2:latest** (`done_reason: stop`, 71 visible / 72 raw tokens)

> I don't have information on the specific needs of your recovery after Total Knee Arthroplasty (TKA). I recommend checking with your surgeon or physiotherapist for guidance on whether a Continuous Passive Motion (CPM) machine is necessary for your recovery. They can assess your progress and provide personalized advice on the best course of treatment for you.

**gemma3:4b** (`done_reason: stop`, 86 visible / 87 raw tokens)

> Okay, let’s talk about that CPM machine. The discharge notes say you should continue with the exercises we’ve been doing, and icing your knee after each session – that’s really important for reducing swelling. While the hospital suggests a CPM machine, it’s not always necessary, and it’s best to discuss this with your surgeon or physiotherapist to see if it’s the right fit for your recovery.

**medgemma1.5:4b-it-q4_K_M** (`done_reason: stop`, 57 visible / 534 raw tokens, reasoning trace 2071 chars (closed))

> Based on the discharge notes, the goal is to use the CPM machine to help maintain your knee's extension and prevent stiffness. The notes also say to continue it "as prescribed" by your physiotherapist. So, according to the plan, it seems necessary for achieving those goals.

**qwen3.5:4b** (`done_reason: stop`, 80 visible / 82 raw tokens)

> Based on your discharge notes for Day 6 after Total Knee Arthroplasty, there is no specific information about renting a Continuous Passive Motion (CPM) machine or whether it is required for your recovery. Since the hospital's recommendation might depend on your specific surgery details and surgeon's preference, you should check directly with your surgeon or physiotherapist to confirm if this device is necessary for you.
