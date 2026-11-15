# Pain test set q01-q20: final

Date: 2026-09-28. Corpus `eval_corpus.json` sha256 `5b708a30e85bc715`. Queries `eval_queries.jsonl` sha256 `c2610a3ef2af6143`. Frozen contexts `contexts_pain_wf.jsonl` sha256 `cd46cf5fa13e6f35` (`--window-filter`). No model generation was run.

## Final rows

The full reference answers are in `eval_queries.jsonl`.

| id | procedure | day | label | query | reference_passages |
|---|---|---|---|---|---|
| q01 | TKA | 2 | full | its only day 2 and my knee is very sore and stiff, did something go wrong | EV-TKA-PAIN-01 |
| q02 | TKA | 5 | full | how long should I keep the ice on my knee after doing my exercises | EV-TKA-PAIN-02 |
| q03 | TKA | 10 | full | my knee pains more in the night than daytime, is that normal | EV-TKA-PAIN-03 |
| q04 | TKA | 12 | full | can I sleep with a pillow under my knee, it feels better like that | EV-TKA-PAIN-03, EV-TKA-REHAB-02 |
| q05 | TKA | 30 | full | there is numbness on the outer side of my knee near the scar, is this a problem | EV-TKA-PAIN-04 |
| q06 | TKA | 35 | partial | my knee is still stiff in the mornings after 5 weeks, when will it go away | EV-TKA-PAIN-04, EV-TKA-REC-05 |
| q07 | TKA | 60 | full | even after 2 months the knee swells up when I walk a lot, is that ok | EV-TKA-PAIN-05 |
| q08 | TKA | 70 | full | is it ok to kneel on my new knee, it hurts when I try | EV-TKA-PAIN-05, EV-TKA-REC-06, EV-TKA-REHAB-06 |
| q09 | TKA | 8 | none | which painkiller is stronger for knee pain, tramadol or paracetamol | EV-TKA-PAIN-01 |
| q10 | TKA | 4 | full | my calf is swollen and paining, is that part of the knee pain | EV-TKA-PAIN-06, EV-TKA-PAIN-01, EV-TKA-PAIN-02 |
| q11 | THA | 3 | full | hip hurts a lot when the nurse makes me walk, should I stop walking till it heals | EV-THA-PAIN-01 |
| q12 | THA | 6 | full | should I wait for the pain to fully go before doing the bed exercises | EV-THA-REHAB-01 |
| q13 | THA | 12 | full | my foot and ankle on the operated side are swollen, is this because of the hip surgery | EV-THA-PAIN-02 |
| q14 | THA | 15 | partial | how should I sleep, I keep waking up with hip pain in the night | EV-THA-PAIN-03 |
| q15 | THA | 28 | full | my thigh aches after I walk longer, is that normal at 4 weeks | EV-THA-PAIN-04 |
| q16 | THA | 30 | partial | the pain has shifted from the hip to the front of the thigh and knee, why | EV-THA-PAIN-04, EV-THA-PAIN-06 |
| q17 | THA | 65 | partial | my operated leg feels longer than the other one, will it stay like that | EV-THA-PAIN-05 |
| q18 | THA | 75 | partial | I want to fly to Dubai next week for work, is that ok with my hip | EV-THA-PAIN-05, EV-THA-REC-04 |
| q19 | THA | 20 | none | can I use a heating pad and Volini spray on the hip | EV-THA-PAIN-01 |
| q20 | THA | 9 | full | I have fever and the hip wound is red and leaking, is this normal pain from surgery | EV-THA-PAIN-06 |

**Labels:** full 13, partial 5, none 2. **By procedure:** TKA 10, THA 10.

## Changes this turn

- **`eval_queries.jsonl`:**
  - q08 relabelled `full`; q14 relabelled `partial`.
  - The 20 draft reference answers are written in, with your three edits: the q06 "two to three months" clause removed, the q18 return-to-work sentence removed, and the q13 compression-stockings / move-regularly sentence removed.
  - Each row now has `reference_passages`. The template row has `"reference_passages": []` and is still ignored.
- **`common.py`:** `reference_passages` is added to `OPTIONAL_QUERY_FIELDS`. `load_queries` checks that, when present, it is a list of non-empty strings, and rejects anything else (tested). Retrieval and scoring don't read it, and it isn't part of `query_fingerprint`.
- **`eval_corpus.json`:** in EV-TKA-PAIN-01, "…cool it with an ice pack wrapped in a towel; a separate passage covers how long to apply ice." now reads "…cool it with an ice pack wrapped in a towel." The diff is 1 line and nothing else changed. `corpus_review.md` was regenerated.
- **Contexts rebuilt** against corpus `5b708a30e85bc715`: `pilot/contexts_evalcorpus.jsonl`, `pilot/contexts_evalcorpus_wf.jsonl` and `contexts_pain_wf.jsonl`. `backend/rag/data` was unchanged; each build verified its fingerprint.
- **README:** a new "Test-set notes" section, and `reference_passages` added to the query-field list.

## Things to check

1. **q09 and q19 break the in-window rule you set.** Each second sentence draws on a days 1-7 passage, but q09 is day 8 and q19 is day 20. I kept them as drafted, as you asked. In-window rewordings:
   - **q09:** replace "take the pain relief you were prescribed exactly as directed without changing anything on your own" with "do not change your medicines on your own" (EV-TKA-PAIN-03, days 8-21).
   - **q19:** replace the ice sentence with "For pain and swelling, the notes mention raising the leg slightly and applying ice for short periods" (EV-THA-PAIN-02, days 8-21).

   Every other reference passes the rule.
2. **q13 now has 3 sentences, not 4.** The draft already had four, so dropping one left three, which is still within the 2-4 limit.
3. **`reference_passages` lists only the passages each final reference actually uses.** That is narrower than the "passage IDs" column in the review report, which listed every passage covering the question. Removed from the lists:
   - q03: EV-TKA-REC-02
   - q05: EV-TKA-REC-06
   - q06: EV-TKA-PAIN-05, EV-TKA-REC-06 (their clause was dropped)
   - q07: EV-TKA-REC-04
   - q08: EV-TKA-REC-02
   - q12, q20: EV-THA-PAIN-01
   - q13: EV-THA-PAIN-06 (the kept sentences come from EV-THA-PAIN-02)
   - q14: EV-THA-REC-02
   - q17: EV-THA-REC-06
   - q18: EV-THA-REC-03 (its sentence was dropped)

   q09 and q19 list the passage behind their safety sentence, not coverage of the question.
4. **EV-TKA-PAIN-01's stored `metadata.word_count` is now out of date:** 269, but the text is 260 words. Left because you said to change nothing else.
5. **The edit changed retrieval for three pain queries.** Wrong-window chunks are now 17 of 80, up from 16. Coverage judgements are unchanged.
   - **q02:** EV-TKA-PAIN-01-c1 dropped out, since it no longer mentions ice timing, and a wrong-window EV-TKA-REC-05-c1 came in (2 wrong-window). It is still fully covered: both EV-TKA-PAIN-02 chunks are retrieved.
   - **q05:** one wrong-window chunk swapped for another (EV-TKA-PAIN-02-c2 → EV-TKA-PAIN-01-c1).
   - **q10:** same chunks, reordered.

   The pilot contexts retrieve the same chunk IDs as before (wrong-window: default 19, window filter 12). One p01 distance moved slightly (0.366 → 0.364).
6. **The review report is superseded:** `reports/2026-09-28_pain-queries-review.md` still shows the old labels and the unedited drafts, and its coverage table predates this rebuild.
