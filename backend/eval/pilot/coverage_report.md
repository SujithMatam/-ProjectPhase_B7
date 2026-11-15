# Pilot retrieval coverage: old store vs eval corpus

Compares the frozen retrieval for the 10 pilot queries from two stores:

- **Old store:** `pilot/contexts.jsonl` (sha256 `ce1a54c4104fb6ed`), built from `rag/data/seed_knowledge.json` (8 documents).
- **Eval corpus:** `pilot/contexts_evalcorpus.jsonl` (sha256 `fbe3ca39d74fd601`), built from `eval_corpus.json` (36 documents, 88 chunks).

Both use all-MiniLM-L6-v2, top_k 4, a procedure filter and a 0.75 maximum distance. Distances are rounded to 3 places; lower is closer. Chunk IDs and distances are copied from the context files. The full / partial / none coverage judgements are a manual reading of the retrieved chunk text against the query. "Label" is the answerability written in `pilot_queries.jsonl`.

| Query | Label | Old store chunks (distance) | Old | Eval corpus chunks (distance) | Corpus | Notes |
|---|---|---|---|---|---|---|
| **p01** TKA day 3: my knee is paining a lot when I bend it, is that normal | full | TKA-01-c0 (0.501)<br>TKA-03-c0 (0.597) | none | EV-TKA-PAIN-04-c0 (0.322)<br>EV-TKA-PAIN-01-c1 (0.366)<br>EV-TKA-REC-05-c1 (0.387)<br>EV-TKA-PAIN-01-c0 (0.428) | **full** | Corpus top hit is the weeks 4-6 chunk (wrong window), but EV-TKA-PAIN-01 c0/c1 say bending pain in week 1 is expected and give red flags. |
| **p02** THA day 7: how long will the pain in my hip last after surgery | full | MED-01-c0 (0.627)<br>THA-01-c0 (0.652)<br>GEN-01-c0 (0.701)<br>NUT-01-c0 (0.727) | none | EV-THA-PAIN-05-c1 (0.204)<br>EV-THA-REC-04-c0 (0.254)<br>EV-THA-PAIN-04-c1 (0.293)<br>EV-THA-PAIN-05-c0 (0.295) | **partial** | All four corpus chunks are weeks 4-12; EV-THA-PAIN-01 (days 1-7, first-week hip pain) exists in the corpus but was not retrieved. Retrieval filters on procedure only, not post-op day. |
| **p03** TKA day 21: pain is fine in the day but at night it is worse, what can I do | partial | GEN-01-c0 (0.680)<br>MED-01-c0 (0.689)<br>MEN-01-c0 (0.715)<br>TKA-01-c0 (0.733) | none | EV-TKA-PAIN-03-c0 (0.420)<br>EV-TKA-PAIN-03-c1 (0.461)<br>EV-TKA-REC-02-c1 (0.566)<br>EV-TKA-PAIN-04-c2 (0.614) | **full** | EV-TKA-PAIN-03 c0/c1 cover night pain directly. |
| **p04** THA day 42: can I take ibuprofen along with my blood thinner | none | MED-01-c0 (0.470)<br>GEN-01-c0 (0.652) | partial | *(nothing within 0.75)* | **none** | Old MED-01 says no second NSAID / no extra blood thinners, which touches the question. Corpus retrieves nothing, as intended for an answerability-none medication question. |
| **p05** TKA day 7: which exercises should I do this week for my knee | full | TKA-03-c0 (0.548)<br>TKA-01-c0 (0.635) | none | EV-TKA-REHAB-01-c0 (0.322)<br>EV-TKA-REHAB-06-c1 (0.368)<br>EV-TKA-REHAB-06-c0 (0.387)<br>EV-TKA-REHAB-01-c1 (0.409) | **full** | EV-TKA-REHAB-01 c0/c1 list week-1 exercises. Ranks 2-3 are week 8-12 sport chunks (leg presses, squats) that a model could wrongly recommend at day 7. |
| **p06** THA day 21: when can I start walking without the walker | full | THA-01-c0 (0.585)<br>MEN-01-c0 (0.735) | none | EV-THA-REHAB-04-c1 (0.415)<br>EV-THA-REHAB-04-c0 (0.463)<br>EV-THA-REC-02-c1 (0.519)<br>EV-THA-REC-03-c0 (0.558) | **full** | EV-THA-REHAB-04: no fixed date; move to cane once standing/walking >10 min; physio decides. |
| **p07** TKA day 42: can I start cycling on a stationary bike now | partial | *(nothing within 0.75)* | none | EV-TKA-REHAB-05-c0 (0.476)<br>EV-TKA-REHAB-05-c1 (0.523)<br>EV-TKA-REHAB-01-c2 (0.626)<br>EV-TKA-REHAB-06-c1 (0.709) | **full** | EV-TKA-REHAB-05 says a stationary bike at ~6 weeks is normal. Labelled partial but fully covered. |
| **p08** THA day 84: is it ok to go back to playing cricket | none | *(nothing within 0.75)* | none | EV-THA-REHAB-06-c1 (0.679)<br>EV-THA-REHAB-06-c0 (0.741) | **partial** | General sport guidance (avoid running, jumping, sudden turns; agree with surgeon); cricket not named. Labelled none. |
| **p09** THA day 14: what should I be able to do by two weeks after hip replacement | full | THA-01-c0 (0.432)<br>NUT-01-c0 (0.636)<br>MEN-01-c0 (0.662)<br>MED-01-c0 (0.701) | none | EV-THA-REC-01-c0 (0.185)<br>EV-THA-REC-04-c0 (0.205)<br>EV-THA-REC-03-c0 (0.213)<br>EV-THA-REHAB-06-c0 (0.249) | **partial** | Got days 1-7, 22-42 and 56-84 chunks; EV-THA-REC-02 ("What you may be able to do two to three weeks after hip replacement") was not retrieved. |
| **p10** THA day 42: I still have swelling after 6 weeks, is my recovery slow | partial | NUT-01-c0 (0.663)<br>MED-01-c0 (0.681)<br>MEN-01-c0 (0.691)<br>THA-01-c0 (0.711) | none | EV-THA-REC-05-c0 (0.345)<br>EV-THA-PAIN-05-c1 (0.410)<br>EV-THA-REC-04-c0 (0.426)<br>EV-THA-PAIN-02-c0 (0.430) | **full** | EV-THA-REC-05 c0: ongoing swelling at six weeks is not by itself a sign of slow recovery. Labelled partial but fully covered. |

## Summary

- Full coverage: old store 0/10, eval corpus 6/10 (p01, p03, p05, p06, p07, p10). Partial: old 1 (p04), corpus 3 (p02, p08, p09).
- p02 and p09 are retrieval gaps, not corpus gaps: the chunk that answers each question is in the corpus, but retrieval ignores `postop_day` and ranks chunks from other recovery windows higher.
- Wrong-window chunks also appear in p01 (rank 1) and p05 (ranks 2-3).
- Labels to recheck against the corpus: p07 and p10 (partial, now fully covered), p08 (none, now partly covered).

## p01 qwen3.5:4b `project` response: icing and elevation

Record: `pilot/results/qwen3.5-4b_project.jsonl`, id p01 (harness v1, num_predict 300). Its `context_sha256` (`b4eb8a05866f8185…`) matches `pilot/contexts.jsonl`, so the model saw the **old store's** two chunks (TKA-01-c0, TKA-03-c0), not the eval corpus.

> Yes, feeling pain when bending your knee on Day 3 is completely normal as the surgery heals and you begin to move through your range of motion. To help manage this discomfort, try icing the area for 15–20 minutes after activity and keep your leg elevated above your heart level whenever possible.

| Claim in the response | In the frozen context? | Claim label |
|---|---|---|
| Keep the leg elevated above heart level | Yes: TKA-01-c0, "Normal swelling decreases with limb elevation (foot above heart level)". The context gives it for **swelling**; the response applies it to pain. | embellished (different purpose) |
| Ice the area | Yes: TKA-01-c0, "… and ice application", again for swelling. | embellished (different purpose) |
| For **15–20 minutes** and **after activity** | No. The context gives no duration or timing. Added by the model. | embellished (added specifics) |
| Pain when bending on Day 3 is completely normal | No. Neither chunk discusses pain on bending. | unsupported |

The project system prompt also contains "Mention Day 3 goals, icing, and limb elevation only when relevant", which steers the model toward giving icing and elevation advice whether or not the context supports the details.
