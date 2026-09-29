# Corpus audit: eval_corpus.json

Date: 2026-09-28. Corpus: `eval_corpus.json`, 36 entries, sha256 `7fcb7bedbdfbc8af`. Report only; the corpus was not edited.

## 1. Source URLs

I fetched each entry's `metadata.source_url` once on 2026-09-28 (9 distinct URLs, GET with a browser user agent). The `additional_source_urls` (11 distinct) were not fetched, except where a note below says one was checked.

- **All 9 resolve** with HTTP 200.
- **All OrthoInfo URLs** redirect from `/en/...` to the same path without `/en/`.
- **The NHS knee URL** (`/conditions/knee-replacement/recovery/`) redirects to `/tests-and-treatments/knee-replacement/recovery/`. The corpus link is out of date but still works.
- **The HSS URL** is an 11-page PDF titled "Total Knee Arthroplasty Post-Operative Guidelines".

How to read the table:

- **Subject:** "direct" means the page is about the entry's topic. "general" means it is a procedure overview or recovery page that covers the topic in one section. Every entry's primary source is about the same procedure and recovery, so none is a mismatch.
- **Topic terms on page:** a keyword check of a few terms central to the topic against the page text. It is a sanity check that the page covers the topic, not a check of each claim.

| id | topic | source | resolves | page title | subject | topic terms on page |
|---|---|---|---|---|---|---|
| EV-TKA-PAIN-01 | Knee pain in the first week after knee replacement | <https://www.orthoinfo.org/en/treatment/total-knee-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/treatment/total-knee-replacement/> | Total Knee Replacement - OrthoInfo - AAOS | general | all found |
| EV-TKA-PAIN-02 | Easing knee pain and swelling after exercise: ice and elevation | <https://www.orthoinfo.org/en/recovery/total-knee-replacement-exercise-guide/> | HTTP 200, redirects to <https://www.orthoinfo.org/recovery/total-knee-replacement-exercise-guide/> | Total Knee Replacement Exercise Guide - OrthoInfo - AAOS | general | all found |
| EV-TKA-PAIN-03 | Knee pain at night after knee replacement | <https://www.orthoinfo.org/en/treatment/total-knee-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/treatment/total-knee-replacement/> | Total Knee Replacement - OrthoInfo - AAOS | general | all found |
| EV-TKA-PAIN-04 | Knee pain, stiffness and numbness in weeks 4-6 | <https://www.orthoinfo.org/en/treatment/total-knee-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/treatment/total-knee-replacement/> | Total Knee Replacement - OrthoInfo - AAOS | general | all found |
| EV-TKA-PAIN-05 | Aching and swelling two to three months after knee replacement | <https://www.orthoinfo.org/en/recovery/activities-after-knee-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/recovery/activities-after-knee-replacement/> | Activities After Total Knee Replacement - OrthoInfo - AAOS | general | missing: `kneel` ("kneel" is not on this page; it is on the NHS knee recovery page (an additional source), and the passage attributes it to the NHS.) |
| EV-TKA-PAIN-06 | Warning signs after knee replacement: when pain or swelling needs urgent attention | <https://www.orthoinfo.org/en/treatment/total-knee-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/treatment/total-knee-replacement/> | Total Knee Replacement - OrthoInfo - AAOS | direct | all found |
| EV-THA-PAIN-01 | Hip pain in the first week after hip replacement | <https://www.nhs.uk/tests-and-treatments/hip-replacement/recovering-from-a-hip-replacement/> | HTTP 200 | Recovering from a hip replacement - NHS | general | all found |
| EV-THA-PAIN-02 | Leg and foot swelling and discomfort after hip replacement | <https://www.nhs.uk/tests-and-treatments/hip-replacement/recovering-from-a-hip-replacement/> | HTTP 200 | Recovering from a hip replacement - NHS | direct | all found |
| EV-THA-PAIN-03 | Night discomfort and sleeping positions after hip replacement | <https://www.orthoinfo.org/en/treatment/total-hip-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/treatment/total-hip-replacement/> | Total Hip Replacement - OrthoInfo - AAOS | general | all found |
| EV-THA-PAIN-04 | Hip and thigh aching as activity increases (weeks 4-6) | <https://www.orthoinfo.org/en/recovery/total-hip-replacement-exercise-guide/> | HTTP 200, redirects to <https://www.orthoinfo.org/recovery/total-hip-replacement-exercise-guide/> | Total Hip Replacement Exercise Guide - OrthoInfo - AAOS | general | all found |
| EV-THA-PAIN-05 | Lingering discomfort and swelling two to three months after hip replacement | <https://www.orthoinfo.org/en/recovery/activities-after-hip-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/recovery/activities-after-hip-replacement/> | Activities After Total Hip Replacement - OrthoInfo - AAOS | general | missing: `shoe lift|leg length`, `fly|flight` (Leg length is not on this page; it is on the OrthoInfo total hip overview (an additional source). Flying: the page says "Talk to your doctor before you travel on an airplane" (the keyword pattern missed it).) |
| EV-THA-PAIN-06 | Warning signs after hip replacement: blood clot, infection and dislocation | <https://www.orthoinfo.org/en/treatment/total-hip-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/treatment/total-hip-replacement/> | Total Hip Replacement - OrthoInfo - AAOS | direct | all found |
| EV-TKA-REHAB-01 | Early exercises in the first week after knee replacement | <https://www.orthoinfo.org/en/recovery/total-knee-replacement-exercise-guide/> | HTTP 200, redirects to <https://www.orthoinfo.org/recovery/total-knee-replacement-exercise-guide/> | Total Knee Replacement Exercise Guide - OrthoInfo - AAOS | direct | all found |
| EV-TKA-REHAB-02 | Knee bend and straightening goals after knee replacement | <https://www.hss.edu/globalassets/files/rehab/guidelines/hssrehabilitationclinicalguidelines-knee-totalkneearthroplasty-post-operative.pdf> | HTTP 200 | TOTAL KNEE ARTHROPLASTY POST-OPERATIVE GUIDELINES (HSS, PDF) | direct | all found |
| EV-TKA-REHAB-03 | Walking aids and stairs after knee replacement | <https://www.orthoinfo.org/en/recovery/total-knee-replacement-exercise-guide/> | HTTP 200, redirects to <https://www.orthoinfo.org/recovery/total-knee-replacement-exercise-guide/> | Total Knee Replacement Exercise Guide - OrthoInfo - AAOS | direct | all found |
| EV-TKA-REHAB-04 | Building strength and function in weeks 2-6 after knee replacement | <https://www.hss.edu/globalassets/files/rehab/guidelines/hssrehabilitationclinicalguidelines-knee-totalkneearthroplasty-post-operative.pdf> | HTTP 200 | TOTAL KNEE ARTHROPLASTY POST-OPERATIVE GUIDELINES (HSS, PDF) | direct | all found |
| EV-TKA-REHAB-05 | Using a stationary exercise bike after knee replacement | <https://www.orthoinfo.org/en/recovery/total-knee-replacement-exercise-guide/> | HTTP 200, redirects to <https://www.orthoinfo.org/recovery/total-knee-replacement-exercise-guide/> | Total Knee Replacement Exercise Guide - OrthoInfo - AAOS | direct | all found |
| EV-TKA-REHAB-06 | Returning to exercise and sport after knee replacement | <https://www.orthoinfo.org/en/recovery/activities-after-knee-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/recovery/activities-after-knee-replacement/> | Activities After Total Knee Replacement - OrthoInfo - AAOS | direct | all found |
| EV-THA-REHAB-01 | Early exercises in bed after hip replacement | <https://www.orthoinfo.org/en/recovery/total-hip-replacement-exercise-guide/> | HTTP 200, redirects to <https://www.orthoinfo.org/recovery/total-hip-replacement-exercise-guide/> | Total Hip Replacement Exercise Guide - OrthoInfo - AAOS | direct | all found |
| EV-THA-REHAB-02 | Hip precautions during recovery | <https://www.orthoinfo.org/en/treatment/total-hip-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/treatment/total-hip-replacement/> | Total Hip Replacement - OrthoInfo - AAOS | general | missing: `90 degrees|right angle`, `cross` (This page only says precautions last "usually for the first 6 weeks" and vary by approach. The specific list (90 degrees, no leg crossing, etc.) is on the NHS hip recovery page and OrthoInfo "Activities after hip replacement" (both additional sources). The latter says "Don't cross your legs at the knees for at least 6 to 8 weeks".) |
| EV-THA-REHAB-03 | Standing exercises after hip replacement | <https://www.orthoinfo.org/en/recovery/total-hip-replacement-exercise-guide/> | HTTP 200, redirects to <https://www.orthoinfo.org/recovery/total-hip-replacement-exercise-guide/> | Total Hip Replacement Exercise Guide - OrthoInfo - AAOS | direct | all found |
| EV-THA-REHAB-04 | Walking aids, moving off the walker, and stairs after hip replacement | <https://www.orthoinfo.org/en/recovery/total-hip-replacement-exercise-guide/> | HTTP 200, redirects to <https://www.orthoinfo.org/recovery/total-hip-replacement-exercise-guide/> | Total Hip Replacement Exercise Guide - OrthoInfo - AAOS | direct | all found |
| EV-THA-REHAB-05 | Exercise bike and resistance exercises after hip replacement | <https://www.orthoinfo.org/en/recovery/total-hip-replacement-exercise-guide/> | HTTP 200, redirects to <https://www.orthoinfo.org/recovery/total-hip-replacement-exercise-guide/> | Total Hip Replacement Exercise Guide - OrthoInfo - AAOS | direct | all found |
| EV-THA-REHAB-06 | Returning to sport and recreation after hip replacement | <https://www.orthoinfo.org/en/recovery/activities-after-hip-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/recovery/activities-after-hip-replacement/> | Activities After Total Hip Replacement - OrthoInfo - AAOS | direct | all found |
| EV-TKA-REC-01 | Leaving hospital and the first week at home after knee replacement | <https://www.nhs.uk/conditions/knee-replacement/recovery/> | HTTP 200, redirects to <https://www.nhs.uk/tests-and-treatments/knee-replacement/recovery/> | Recovering from a knee replacement - NHS | direct | all found |
| EV-TKA-REC-02 | What to expect two to three weeks after knee replacement | <https://www.nhs.uk/conditions/knee-replacement/recovery/> | HTTP 200, redirects to <https://www.nhs.uk/tests-and-treatments/knee-replacement/recovery/> | Recovering from a knee replacement - NHS | direct | all found |
| EV-TKA-REC-03 | Recovery milestones around four to six weeks after knee replacement | <https://www.orthoinfo.org/en/treatment/total-knee-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/treatment/total-knee-replacement/> | Total Knee Replacement - OrthoInfo - AAOS | general | all found |
| EV-TKA-REC-04 | Two to three months after knee replacement: work and fuller activity | <https://www.nhs.uk/conditions/knee-replacement/recovery/> | HTTP 200, redirects to <https://www.nhs.uk/tests-and-treatments/knee-replacement/recovery/> | Recovering from a knee replacement - NHS | direct | all found |
| EV-TKA-REC-05 | Is my knee recovery on track? What steady progress looks like | <https://www.hss.edu/globalassets/files/rehab/guidelines/hssrehabilitationclinicalguidelines-knee-totalkneearthroplasty-post-operative.pdf> | HTTP 200 | TOTAL KNEE ARTHROPLASTY POST-OPERATIVE GUIDELINES (HSS, PDF) | direct | all found |
| EV-TKA-REC-06 | The months ahead after knee replacement | <https://www.nhs.uk/conditions/knee-replacement/recovery/> | HTTP 200, redirects to <https://www.nhs.uk/tests-and-treatments/knee-replacement/recovery/> | Recovering from a knee replacement - NHS | direct | all found |
| EV-THA-REC-01 | Leaving hospital and the first week at home after hip replacement | <https://www.nhs.uk/tests-and-treatments/hip-replacement/recovering-from-a-hip-replacement/> | HTTP 200 | Recovering from a hip replacement - NHS | direct | all found |
| EV-THA-REC-02 | What you may be able to do two to three weeks after hip replacement | <https://www.orthoinfo.org/en/treatment/total-hip-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/treatment/total-hip-replacement/> | Total Hip Replacement - OrthoInfo - AAOS | general | all found |
| EV-THA-REC-03 | Recovery around four to six weeks after hip replacement | <https://www.orthoinfo.org/en/treatment/total-hip-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/treatment/total-hip-replacement/> | Total Hip Replacement - OrthoInfo - AAOS | general | all found |
| EV-THA-REC-04 | Two to three months after hip replacement, including lingering swelling | <https://www.orthoinfo.org/en/recovery/activities-after-hip-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/recovery/activities-after-hip-replacement/> | Activities After Total Hip Replacement - OrthoInfo - AAOS | general | all found |
| EV-THA-REC-05 | Is my hip recovery slow? What normal progress looks like | <https://www.orthoinfo.org/en/treatment/total-hip-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/treatment/total-hip-replacement/> | Total Hip Replacement - OrthoInfo - AAOS | general | all found |
| EV-THA-REC-06 | The longer term after hip replacement | <https://www.orthoinfo.org/en/treatment/total-hip-replacement/> | HTTP 200, redirects to <https://www.orthoinfo.org/treatment/total-hip-replacement/> | Total Hip Replacement - OrthoInfo - AAOS | general | all found |

**Attribution check:** each passage that names a source (NHS, AAOS/American Academy of Orthopaedic Surgeons, HSS/Hospital for Special Surgery) lists that source's domain in `source_url` or `additional_source_urls`. There are no mismatches.

**HSS spot check:** the "about 80 degrees" criterion in EV-TKA-REHAB-02 and EV-TKA-REC-05 matches the PDF's "Acute Care Phase (Week 1)" advancement criteria ("active knee flexion ROM ~80° in sitting and active extension ROM <10°"). The >110° criterion matches Phase 1 (Weeks 2-6), and >120° matches the return-to-sport criteria.

## 2. Drug names with doses or frequencies

**None found.** I scanned all 36 passages for common analgesic, anticoagulant and antibiotic names and classes, and for dose and frequency patterns (`N mg/mcg/g/ml/units`, `once/twice/N times a day`, `every N hours`, `daily`). No sentence contains both a drug and a dose or frequency.

Drug mentions are class-level only, with no dose, frequency or product:

| entries | mention |
|---|---|
| EV-THA-PAIN-01 | several kinds of pain medicine are combined "keeping the need for opioids as low as possible" |
| EV-TKA-REC-03, EV-THA-REC-03 | driving is generally safe "once you are no longer taking opioid pain medicine" |
| EV-TKA-PAIN-06 | "blood-thinning medicine" as one of the clot-prevention measures |
| EV-TKA-REC-06, EV-THA-REC-06 | "people with certain risk factors may be advised to take antibiotics before dental work" |
| EV-TKA-PAIN-01, -03, -04, -06, EV-THA-PAIN-01, -03 | generic "pain relief / pain medicines", always with "take as prescribed / don't change on your own" |

The dose and frequency patterns matched only exercise, cycling and walking schedules (for example "10 to 15 minutes twice a day" in EV-TKA-REHAB-05 and EV-THA-REHAB-05, and "walk daily").

## 3. Conflicting numbers or timelines for the same milestone

No two passages flatly contradict each other for the same procedure. The table lists places where different numbers are given for the same milestone, most serious first. The first two are divergences within a single passage, where two sources are quoted with different figures.

| # | milestone | passages | what they say | severity |
|---|---|---|---|---|
| 1 | Return to work (TKA) | EV-TKA-REC-04 | NHS "about six to twelve weeks" and AAOS "anywhere from several days to several weeks", in the same passage | medium: a model quoting either figure is supported, but the two ranges barely overlap |
| 2 | Return to work (THA) | EV-THA-REC-03 | NHS "about six weeks" and AAOS "from several weeks to several months", in the same passage | medium |
| 3 | Driving (TKA) | EV-TKA-REC-03 | AAOS "about four to six weeks" and NHS "at least six weeks", in the same passage | low-medium: a 4-week answer is supported by one source and ruled out by the other |
| 4 | Knee bend of about 80° | EV-TKA-REHAB-02 vs EV-TKA-REC-05 | REHAB-02: about 80° *before moving on from* the first-week phase (an advancement criterion). REC-05: about 80° *by the end of the first week* (a deadline) | low: same number, different framing. HSS presents it as a criterion |
| 5 | Stopping hip precautions / crossing legs | EV-THA-REHAB-02, EV-THA-REC-02, EV-THA-PAIN-04 | precautions "typically for around six weeks" / "about the first six weeks", and most movements are fine "after six to eight weeks" | low: internally consistent, but OrthoInfo "Activities after hip replacement" says not to cross the legs "for at least 6 to 8 weeks" |
| 6 | Ankle pumps | EV-TKA-REHAB-01 vs EV-THA-REHAB-01 | knee: "a couple of minutes, several times an hour". Hip: "as often as every five or ten minutes" | low: different procedures, both from AAOS |

**Checked and consistent across passages:**

- Swelling lasting 3-6 months: 5 TKA and 5 THA passages.
- Compression stockings for at least 6 weeks (EV-TKA-PAIN-02, EV-TKA-REC-01).
- No leg crossing for 6 weeks after TKA (EV-TKA-REC-01, EV-TKA-REC-02).
- Avoiding heavy household jobs for 3 months (EV-TKA-REC-03, EV-TKA-REC-04).
- Continuing the exercises for at least 2 months (EV-TKA-PAIN-05, EV-TKA-REHAB-06, EV-TKA-REC-06).
- More than 110° of bending by week 6 (EV-TKA-REHAB-02, EV-TKA-REC-02, EV-TKA-REC-03, EV-TKA-REC-05).
- Cane after about 2-3 weeks for TKA (EV-TKA-REHAB-03, EV-TKA-REC-02).
- Walking without an aid at about 6 weeks for TKA (EV-TKA-REHAB-03, EV-TKA-REC-03).
- The same bike schedule in EV-TKA-REHAB-05 and EV-THA-REHAB-05.
- Light daily activities at 3-6 weeks (EV-THA-REC-02, EV-THA-REC-03, EV-THA-REC-05, EV-TKA-REC-03).
- A fever threshold of 100 °F / 37.8 °C (EV-TKA-PAIN-06, EV-THA-PAIN-06).
- Follow-up at 6-12 weeks for THA (EV-THA-PAIN-05, EV-THA-REC-03, EV-THA-REC-04).

Different procedures give different values for discharge (TKA 1-4 days, THA 1-3 days), stitch removal (TKA about 10 days, THA 10 days to 2 weeks) and follow-up (TKA about 6 weeks, THA 6-12 weeks). These are not conflicts.

**Across stores:** the old app store's TKA-01 says TKA swelling is expected "up to 3 months", while the eval corpus says 3-6 months. This only matters if the two stores are ever mixed.

## 4. `days` range vs the stated window

The other entries convert week labels to days as week N = days 7N-6 to 7N: "weeks 2-3" is days 8-21 and "weeks 4-6" is days 22-42. By that rule, 8 entries do not match their `days`:

| id | metadata.postop_window | implied days | `days` |
|---|---|---|---|
| EV-TKA-PAIN-05 | weeks 8-12 | 50-84 | 56-84 |
| EV-THA-PAIN-05 | weeks 8-12 | 50-84 | 56-84 |
| EV-TKA-REHAB-06 | weeks 8-12 | 50-84 | 56-84 |
| EV-THA-REHAB-06 | weeks 8-12 | 50-84 | 56-84 |
| EV-TKA-REC-04 | weeks 8-12 | 50-84 | 56-84 |
| EV-THA-REC-04 | weeks 8-12 | 50-84 | 56-84 |
| EV-TKA-REC-06 | week 8 onwards | 50 onwards | 56-365 |
| EV-THA-REC-06 | week 8 onwards | 50 onwards | 56-365 |

The "weeks 8-12" entries start at day 56 (the end of week 8, i.e. "after 8 weeks"), while the rest start at the first day of the week. The other 28 entries match their window text.

**Consequence:** days 43-55 (week 7 and most of week 8) have no stage-specific entry for any procedure and domain. Only the broad entries cover them: EV-TKA-PAIN-06 and EV-THA-PAIN-06 (1-84), EV-TKA-REHAB-05 (8-84), EV-THA-REHAB-02 (1-56), and EV-TKA-REC-05 and EV-THA-REC-05 (22-84). This matters for `--window-filter` queries in that range.

**Minor:** topics and first sentences say "two to three months", which runs to about day 91, but `days` ends at 84 (12 weeks).
