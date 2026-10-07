# 2026-09-29: judge summary (qwen2.5:7b)

Scope: read-only apart from this report (and the second-judge launch recorded at the end). Nothing staged or committed.

## Status

- The judge run finished at about 15:45, having started at 14:19:16 and averaged ~7 s per response. All 12 files have 60 ids each, **720 records in total**.
- **The `full` handling problem affected 191 of 468 `full` records (41%).** In these the judge answered `correct`/`invented` where the rubric requires `n/a`. The normalisation rule handles them: 21 written before the fix are normalised when read, and the rest were normalised when written. They count as valid, and the judge's raw value is kept in `judge_raw_handling`. It affects only that one field, but it shows how often the judge ignores the ANSWERABILITY line of its prompt.
- **7 records are still invalid, and every table excludes them.** All of them are `partial` questions where the judge answered `n/a`, the mirror image of the `full` problem. That one can't be normalised, because nothing tells us whether the answer should be `correct` or `invented`:

| results file | id | answerability |
|---|---|---|
| `results/gemma3-4b_minimal.jsonl` | q17 | partial |
| `results/llama3.2-latest_minimal.jsonl` | q14 | partial |
| `results/llama3.2-latest_project_abstain.jsonl` | c19 | partial |
| `results/qwen3.5-4b_minimal.jsonl` | c19 | partial |
| `results/qwen3.5-4b_project_abstain.jsonl` | r07 | partial |
| `results_medgemma_2048/medgemma1.5-4b-it-q4_K_M_project.jsonl` | c13 | partial |
| `results_medgemma_2048/medgemma1.5-4b-it-q4_K_M_project.jsonl` | c19 | partial |

  Four of the seven are **c19**. A clean retry isn't possible: the judge is deterministic, so a resume would get the same answer back. Scoring these seven by hand would fill the gap.

- MedGemma rows come from `results_medgemma_2048/` (num_predict 2048). The 600-token MedGemma files in `results/` were not judged. The 7 MedGemma answers that are still empty at 2048 were judged with `(no answer was given)`; how they were scored is shown in the grounded=0 section.

**Caveats:**

- The judge is qwen2.5:7b, from the same family as the qwen3.5:4b candidate.
- No calibration against manual scores yet: `calibration_set.md` is waiting to be scored by hand.
- Claim labels are the judge's own. The three label columns are never added together.

## Overall (performance + judge)

```
PERFORMANCE (from results/, results_medgemma_2048/; latest record per id, harness v2 only)
  results dir            model                     variant          num_predict  ok  err  no answer  trace  hit limit  p50 first visible s  p50 total s  p50 visible tok  p50 raw tok  p50 tok/s  peak GPU MiB  peak ollama MiB  min on GPU  cold start s (excluded)
  ---------------------  ------------------------  ---------------  -----------  --  ---  ---------  -----  ---------  -------------------  -----------  ---------------  -----------  ---------  ------------  ---------------  ----------  -----------------------
  results                gemma3:4b                 minimal          600          60  0    0          0      0          0.41                 1.58         63.5             64.5         52.92      3733          56.3             100%        4.793                  
  results                gemma3:4b                 project          600          60  0    0          0      0          0.47                 2.12         89.5             91.0         52.39      3733          85.9             100%        4.793                  
  results                gemma3:4b                 project_abstain  600          60  0    0          0      0          0.5                  2.28         91.5             94.0         52.45      3733          56.6             100%        4.793                  
  results                llama3.2:latest           minimal          600          60  0    0          0      0          0.27                 1.07         54.0             55.0         69.37      2537          55.9             100%        0.118                  
  results                llama3.2:latest           project          600          60  0    0          0      0          0.33                 1.53         83.0             86.0         68.94      2537          74.0             100%        0.118                  
  results                llama3.2:latest           project_abstain  600          60  0    0          0      0          0.14                 1.36         83.0             84.0         68.73      2537          55.9             100%        0.118                  
  results                medgemma1.5:4b-it-q4_K_M  minimal          600          60  0    0          5      2          0.41                 1.45         50.0             55.0         52.67      3733          56.0             100%        0.275                  
  results                medgemma1.5:4b-it-q4_K_M  project          600          60  0    38         60     41         9.59                 12.1         0.0              600.0        51.46      3733          86.4             100%        0.275                  
  results                medgemma1.5:4b-it-q4_K_M  project_abstain  600          60  0    31         54     36         8.26                 12.14        0.0              600.0        51.12      3733          55.6             100%        0.275                  
  results                qwen3.5:4b                minimal          600          60  0    0          0      0          0.58                 1.95         65.5             67.0         47.29      3827          57.2             100%        0.167                  
  results                qwen3.5:4b                project          600          60  0    0          0      0          0.64                 2.22         74.0             75.0         47.2       3827          73.1             100%        0.167                  
  results                qwen3.5:4b                project_abstain  600          60  0    0          0      0          0.66                 2.35         79.5             81.0         47.17      3827          56.6             100%        0.167                  
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  minimal          2048         60  0    0          5      0          0.44                 1.5          50.0             55.0         52.31      3733          32.6             100%        0.242                  
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project          2048         60  0    3          60     3          13.1                 14.52        54.5             745.5        51.34      3733          91.3             100%        0.242                  
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project_abstain  2048         60  0    4          54     4          12.09                13.55        57.5             668.0        51.27      3733          58.3             100%        0.242                  
  (GPU MiB is system-wide; 'min on GPU' is the lowest share of the model in VRAM per /api/ps;
   cold start = discarded warm-up request, from _runs.jsonl, not part of any latency column)

MANUAL SCORES  (score_source=manual)
  (none)

LLM-JUDGE SCORES  (score_source=llm_judge, judge=qwen2.5-7b)
  results dir            model                     variant          num_predict  n   grounded (0-2)  supported   embellished  unsupported  format ok  unanswerable correct  invented
  ---------------------  ------------------------  ---------------  -----------  --  --------------  ----------  -----------  -----------  ---------  --------------------  --------
  results                gemma3:4b                 minimal          600          59  1.47            129 (2.19)  31 (0.53)    3 (0.05)     97%        16/20                 4       
  results                gemma3:4b                 project          600          60  1.05            107 (1.78)  70 (1.17)    4 (0.07)     73%        8/21                  13      
  results                gemma3:4b                 project_abstain  600          60  1.17            112 (1.87)  61 (1.02)    3 (0.05)     83%        11/21                 10      
  results                llama3.2:latest           minimal          600          59  1.37            88 (1.49)   36 (0.61)    2 (0.03)     88%        12/20                 8       
  results                llama3.2:latest           project          600          60  1.08            110 (1.83)  82 (1.37)    5 (0.08)     78%        8/21                  13      
  results                llama3.2:latest           project_abstain  600          59  1.32            109 (1.85)  45 (0.76)    7 (0.12)     88%        19/20                 1       
  results                qwen3.5:4b                minimal          600          59  1.46            120 (2.03)  42 (0.71)    6 (0.10)     93%        16/20                 4       
  results                qwen3.5:4b                project          600          60  1.15            117 (1.95)  70 (1.17)    3 (0.05)     77%        5/21                  16      
  results                qwen3.5:4b                project_abstain  600          59  1.27            115 (1.95)  60 (1.02)    5 (0.08)     88%        11/20                 9       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  minimal          2048         60  1.53            125 (2.08)  21 (0.35)    1 (0.02)     93%        18/21                 3       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project          2048         58  1.21            101 (1.74)  42 (0.72)    3 (0.05)     88%        10/19                 9       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project_abstain  2048         60  1.3             107 (1.78)  32 (0.53)    2 (0.03)     87%        15/21                 6       
  (claim columns: total claims with that label (mean per response); the three are never summed)
  excluded: 0 stale (response changed or missing), 0 from an older rubric (score v2 is current; re-score them), 7 invalid
```

## By answerability

```
LLM-JUDGE SCORES  (score_source=llm_judge, judge=qwen2.5-7b)
  results dir            model                     variant          num_predict  answerability  n   grounded (0-2)  supported  embellished  unsupported  format ok  unanswerable correct  invented
  ---------------------  ------------------------  ---------------  -----------  -------------  --  --------------  ---------  -----------  -----------  ---------  --------------------  --------
  results                gemma3:4b                 minimal          600          full           39  1.49            92 (2.36)  22 (0.56)    1 (0.03)     97%        0/0                   0       
  results                gemma3:4b                 minimal          600          none           6   1.5             11 (1.83)  0 (0.00)     1 (0.17)     100%       6/6                   0       
  results                gemma3:4b                 minimal          600          partial        14  1.43            26 (1.86)  9 (0.64)     1 (0.07)     93%        10/14                 4       
  results                gemma3:4b                 project          600          full           39  1.1             69 (1.77)  44 (1.13)    3 (0.08)     82%        0/0                   0       
  results                gemma3:4b                 project          600          none           6   0.67            10 (1.67)  7 (1.17)     0 (0.00)     50%        3/6                   3       
  results                gemma3:4b                 project          600          partial        15  1.07            28 (1.87)  19 (1.27)    1 (0.07)     60%        5/15                  10      
  results                gemma3:4b                 project_abstain  600          full           39  1.23            78 (2.00)  36 (0.92)    0 (0.00)     87%        0/0                   0       
  results                gemma3:4b                 project_abstain  600          none           6   1               10 (1.67)  7 (1.17)     0 (0.00)     67%        4/6                   2       
  results                gemma3:4b                 project_abstain  600          partial        15  1.07            24 (1.60)  18 (1.20)    3 (0.20)     80%        7/15                  8       
  results                llama3.2:latest           minimal          600          full           39  1.38            66 (1.69)  23 (0.59)    0 (0.00)     95%        0/0                   0       
  results                llama3.2:latest           minimal          600          none           6   1.83            5 (0.83)   0 (0.00)     1 (0.17)     100%       6/6                   0       
  results                llama3.2:latest           minimal          600          partial        14  1.14            17 (1.21)  13 (0.93)    1 (0.07)     64%        6/14                  8       
  results                llama3.2:latest           project          600          full           39  1.21            81 (2.08)  45 (1.15)    5 (0.13)     87%        0/0                   0       
  results                llama3.2:latest           project          600          none           6   0.83            7 (1.17)   9 (1.50)     0 (0.00)     50%        2/6                   4       
  results                llama3.2:latest           project          600          partial        15  0.87            22 (1.47)  28 (1.87)    0 (0.00)     67%        6/15                  9       
  results                llama3.2:latest           project_abstain  600          full           39  1.28            80 (2.05)  32 (0.82)    4 (0.10)     85%        0/0                   0       
  results                llama3.2:latest           project_abstain  600          none           6   1.17            5 (0.83)   5 (0.83)     1 (0.17)     83%        5/6                   1       
  results                llama3.2:latest           project_abstain  600          partial        14  1.5             24 (1.71)  8 (0.57)     2 (0.14)     100%       14/14                 0       
  results                qwen3.5:4b                minimal          600          full           39  1.46            87 (2.23)  27 (0.69)    2 (0.05)     97%        0/0                   0       
  results                qwen3.5:4b                minimal          600          none           6   2               7 (1.17)   0 (0.00)     3 (0.50)     100%       6/6                   0       
  results                qwen3.5:4b                minimal          600          partial        14  1.21            26 (1.86)  15 (1.07)    1 (0.07)     79%        10/14                 4       
  results                qwen3.5:4b                project          600          full           39  1.31            88 (2.26)  37 (0.95)    1 (0.03)     92%        0/0                   0       
  results                qwen3.5:4b                project          600          none           6   0.67            7 (1.17)   8 (1.33)     0 (0.00)     33%        2/6                   4       
  results                qwen3.5:4b                project          600          partial        15  0.93            22 (1.47)  25 (1.67)    2 (0.13)     53%        3/15                  12      
  results                qwen3.5:4b                project_abstain  600          full           39  1.33            85 (2.18)  34 (0.87)    0 (0.00)     92%        0/0                   0       
  results                qwen3.5:4b                project_abstain  600          none           6   1.5             8 (1.33)   4 (0.67)     4 (0.67)     67%        4/6                   2       
  results                qwen3.5:4b                project_abstain  600          partial        14  1               22 (1.57)  22 (1.57)    1 (0.07)     86%        7/14                  7       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  minimal          2048         full           39  1.56            94 (2.41)  11 (0.28)    0 (0.00)     92%        0/0                   0       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  minimal          2048         none           6   1.5             6 (1.00)   1 (0.17)     1 (0.17)     83%        5/6                   1       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  minimal          2048         partial        15  1.47            25 (1.67)  9 (0.60)     0 (0.00)     100%       13/15                 2       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project          2048         full           39  1.26            72 (1.85)  28 (0.72)    2 (0.05)     92%        0/0                   0       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project          2048         none           6   1.5             8 (1.33)   2 (0.33)     0 (0.00)     83%        5/6                   1       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project          2048         partial        13  0.92            21 (1.62)  12 (0.92)    1 (0.08)     77%        5/13                  8       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project_abstain  2048         full           39  1.36            75 (1.92)  18 (0.46)    1 (0.03)     90%        0/0                   0       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project_abstain  2048         none           6   1.5             11 (1.83)  3 (0.50)     1 (0.17)     83%        5/6                   1       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project_abstain  2048         partial        15  1.07            21 (1.40)  11 (0.73)    0 (0.00)     80%        10/15                 5       
  (claim columns: total claims with that label (mean per response); the three are never summed)
  excluded: 0 stale (response changed or missing), 0 from an older rubric (score v2 is current; re-score them), 7 invalid
```

## By domain

```
LLM-JUDGE SCORES  (score_source=llm_judge, judge=qwen2.5-7b)
  results dir            model                     variant          num_predict  domain    n   grounded (0-2)  supported  embellished  unsupported  format ok  unanswerable correct  invented
  ---------------------  ------------------------  ---------------  -----------  --------  --  --------------  ---------  -----------  -----------  ---------  --------------------  --------
  results                gemma3:4b                 minimal          600          pain      19  1.47            42 (2.21)  12 (0.63)    0 (0.00)     95%        5/6                   1       
  results                gemma3:4b                 minimal          600          recovery  20  1.55            44 (2.20)  7 (0.35)     2 (0.10)     100%       6/6                   0       
  results                gemma3:4b                 minimal          600          rehab     20  1.4             43 (2.15)  12 (0.60)    1 (0.05)     95%        5/8                   3       
  results                gemma3:4b                 project          600          pain      20  1.1             39 (1.95)  22 (1.10)    1 (0.05)     90%        4/7                   3       
  results                gemma3:4b                 project          600          recovery  20  1.05            35 (1.75)  20 (1.00)    1 (0.05)     70%        1/6                   5       
  results                gemma3:4b                 project          600          rehab     20  1               33 (1.65)  28 (1.40)    2 (0.10)     60%        3/8                   5       
  results                gemma3:4b                 project_abstain  600          pain      20  1.25            39 (1.95)  18 (0.90)    1 (0.05)     95%        4/7                   3       
  results                gemma3:4b                 project_abstain  600          recovery  20  1.1             38 (1.90)  18 (0.90)    0 (0.00)     85%        3/6                   3       
  results                gemma3:4b                 project_abstain  600          rehab     20  1.15            35 (1.75)  25 (1.25)    2 (0.10)     70%        4/8                   4       
  results                llama3.2:latest           minimal          600          pain      19  1.32            31 (1.63)  17 (0.89)    0 (0.00)     84%        2/6                   4       
  results                llama3.2:latest           minimal          600          recovery  20  1.45            31 (1.55)  6 (0.30)     1 (0.05)     95%        5/6                   1       
  results                llama3.2:latest           minimal          600          rehab     20  1.35            26 (1.30)  13 (0.65)    1 (0.05)     85%        5/8                   3       
  results                llama3.2:latest           project          600          pain      20  1.15            38 (1.90)  28 (1.40)    0 (0.00)     85%        2/7                   5       
  results                llama3.2:latest           project          600          recovery  20  1.1             37 (1.85)  24 (1.20)    2 (0.10)     85%        3/6                   3       
  results                llama3.2:latest           project          600          rehab     20  1               35 (1.75)  30 (1.50)    3 (0.15)     65%        3/8                   5       
  results                llama3.2:latest           project_abstain  600          pain      20  1.25            42 (2.10)  16 (0.80)    5 (0.25)     85%        7/7                   0       
  results                llama3.2:latest           project_abstain  600          recovery  19  1.37            38 (2.00)  16 (0.84)    1 (0.05)     89%        5/5                   0       
  results                llama3.2:latest           project_abstain  600          rehab     20  1.35            29 (1.45)  13 (0.65)    1 (0.05)     90%        7/8                   1       
  results                qwen3.5:4b                minimal          600          pain      20  1.4             41 (2.05)  15 (0.75)    1 (0.05)     90%        5/7                   2       
  results                qwen3.5:4b                minimal          600          recovery  19  1.47            37 (1.95)  9 (0.47)     3 (0.16)     100%       5/5                   0       
  results                qwen3.5:4b                minimal          600          rehab     20  1.5             42 (2.10)  18 (0.90)    2 (0.10)     90%        6/8                   2       
  results                qwen3.5:4b                project          600          pain      20  1.15            38 (1.90)  24 (1.20)    1 (0.05)     85%        3/7                   4       
  results                qwen3.5:4b                project          600          recovery  20  1.15            37 (1.85)  23 (1.15)    1 (0.05)     65%        0/6                   6       
  results                qwen3.5:4b                project          600          rehab     20  1.15            42 (2.10)  23 (1.15)    1 (0.05)     80%        2/8                   6       
  results                qwen3.5:4b                project_abstain  600          pain      20  1.05            39 (1.95)  23 (1.15)    3 (0.15)     95%        4/7                   3       
  results                qwen3.5:4b                project_abstain  600          recovery  20  1.3             37 (1.85)  19 (0.95)    0 (0.00)     85%        2/6                   4       
  results                qwen3.5:4b                project_abstain  600          rehab     19  1.47            39 (2.05)  18 (0.95)    2 (0.11)     84%        5/7                   2       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  minimal          2048         pain      20  1.6             50 (2.50)  8 (0.40)     0 (0.00)     95%        7/7                   0       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  minimal          2048         recovery  20  1.6             36 (1.80)  4 (0.20)     0 (0.00)     95%        5/6                   1       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  minimal          2048         rehab     20  1.4             39 (1.95)  9 (0.45)     1 (0.05)     90%        6/8                   2       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project          2048         pain      20  1.25            31 (1.55)  16 (0.80)    1 (0.05)     90%        3/7                   4       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project          2048         recovery  18  1.28            32 (1.78)  11 (0.61)    2 (0.11)     83%        3/4                   1       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project          2048         rehab     20  1.1             38 (1.90)  15 (0.75)    0 (0.00)     90%        4/8                   4       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project_abstain  2048         pain      20  1.45            40 (2.00)  7 (0.35)     0 (0.00)     85%        4/7                   3       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project_abstain  2048         recovery  20  1.35            34 (1.70)  8 (0.40)     1 (0.05)     85%        6/6                   0       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project_abstain  2048         rehab     20  1.1             33 (1.65)  17 (0.85)    1 (0.05)     90%        5/8                   3       
  (claim columns: total claims with that label (mean per response); the three are never summed)
  excluded: 0 stale (response changed or missing), 0 from an older rubric (score v2 is current; re-score them), 7 invalid
```

## By procedure

```
LLM-JUDGE SCORES  (score_source=llm_judge, judge=qwen2.5-7b)
  results dir            model                     variant          num_predict  procedure  n   grounded (0-2)  supported  embellished  unsupported  format ok  unanswerable correct  invented
  ---------------------  ------------------------  ---------------  -----------  ---------  --  --------------  ---------  -----------  -----------  ---------  --------------------  --------
  results                gemma3:4b                 minimal          600          THA        34  1.56            77 (2.26)  14 (0.41)    2 (0.06)     97%        12/14                 2       
  results                gemma3:4b                 minimal          600          TKA        25  1.36            52 (2.08)  17 (0.68)    1 (0.04)     96%        4/6                   2       
  results                gemma3:4b                 project          600          THA        35  1.06            63 (1.80)  40 (1.14)    3 (0.09)     77%        5/15                  10      
  results                gemma3:4b                 project          600          TKA        25  1.04            44 (1.76)  30 (1.20)    1 (0.04)     68%        3/6                   3       
  results                gemma3:4b                 project_abstain  600          THA        35  1.17            70 (2.00)  35 (1.00)    3 (0.09)     80%        8/15                  7       
  results                gemma3:4b                 project_abstain  600          TKA        25  1.16            42 (1.68)  26 (1.04)    0 (0.00)     88%        3/6                   3       
  results                llama3.2:latest           minimal          600          THA        34  1.44            55 (1.62)  18 (0.53)    1 (0.03)     85%        8/14                  6       
  results                llama3.2:latest           minimal          600          TKA        25  1.28            33 (1.32)  18 (0.72)    1 (0.04)     92%        4/6                   2       
  results                llama3.2:latest           project          600          THA        35  1.14            65 (1.86)  52 (1.49)    1 (0.03)     80%        6/15                  9       
  results                llama3.2:latest           project          600          TKA        25  1               45 (1.80)  30 (1.20)    4 (0.16)     76%        2/6                   4       
  results                llama3.2:latest           project_abstain  600          THA        34  1.29            66 (1.94)  25 (0.74)    5 (0.15)     91%        13/14                 1       
  results                llama3.2:latest           project_abstain  600          TKA        25  1.36            43 (1.72)  20 (0.80)    2 (0.08)     84%        6/6                   0       
  results                qwen3.5:4b                minimal          600          THA        34  1.41            75 (2.21)  22 (0.65)    3 (0.09)     94%        11/14                 3       
  results                qwen3.5:4b                minimal          600          TKA        25  1.52            45 (1.80)  20 (0.80)    3 (0.12)     92%        5/6                   1       
  results                qwen3.5:4b                project          600          THA        35  1.03            67 (1.91)  45 (1.29)    2 (0.06)     69%        3/15                  12      
  results                qwen3.5:4b                project          600          TKA        25  1.32            50 (2.00)  25 (1.00)    1 (0.04)     88%        2/6                   4       
  results                qwen3.5:4b                project_abstain  600          THA        35  1.23            68 (1.94)  41 (1.17)    2 (0.06)     83%        6/15                  9       
  results                qwen3.5:4b                project_abstain  600          TKA        24  1.33            47 (1.96)  19 (0.79)    3 (0.12)     96%        5/5                   0       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  minimal          2048         THA        35  1.63            72 (2.06)  11 (0.31)    0 (0.00)     97%        14/15                 1       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  minimal          2048         TKA        25  1.4             53 (2.12)  10 (0.40)    1 (0.04)     88%        4/6                   2       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project          2048         THA        33  1.21            63 (1.91)  24 (0.73)    2 (0.06)     91%        8/13                  5       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project          2048         TKA        25  1.2             38 (1.52)  18 (0.72)    1 (0.04)     84%        2/6                   4       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project_abstain  2048         THA        35  1.4             64 (1.83)  17 (0.49)    0 (0.00)     89%        11/15                 4       
  results_medgemma_2048  medgemma1.5:4b-it-q4_K_M  project_abstain  2048         TKA        25  1.16            43 (1.72)  15 (0.60)    2 (0.08)     84%        4/6                   2       
  (claim columns: total claims with that label (mean per response); the three are never summed)
  excluded: 0 stale (response changed or missing), 0 from an older rubric (score v2 is current; re-score them), 7 invalid
```

## Responses with grounded = 0, per model and variant

| model | variant | num_predict | n valid | grounded = 0 | ids |
|---|---|---|---|---|---|
| llama3.2:latest | project | 600 | 60 | 5 | c17, c20, r02, r04, r09 |
| llama3.2:latest | project_abstain | 600 | 59 | 1 | r19 |
| llama3.2:latest | minimal | 600 | 59 | 1 | q16 |
| gemma3:4b | project | 600 | 60 | 4 | c10, c12, c20, r09 |
| gemma3:4b | project_abstain | 600 | 60 | 1 | c10 |
| gemma3:4b | minimal | 600 | 59 | 1 | r08 |
| medgemma1.5:4b-it-q4_K_M | project | 2048 | 58 | 5 | c10, c12, q18, r09, r10 |
| medgemma1.5:4b-it-q4_K_M | project_abstain | 2048 | 60 | 6 | c12, c15, q14, q16, r09, r10 |
| medgemma1.5:4b-it-q4_K_M | minimal | 2048 | 60 | 3 | c07, c12, r09 |
| qwen3.5:4b | project | 600 | 60 | 5 | c17, c20, q19, r09, r19 |
| qwen3.5:4b | project_abstain | 600 | 59 | 2 | c12, q16 |
| qwen3.5:4b | minimal | 600 | 59 | 2 | c12, q16 |

Empty answers judged: 7, all MedGemma. For each: project c13: grounded=0, valid=False; project q18: grounded=0, valid=True; project r10: grounded=0, valid=True; project_abstain c12: grounded=0, valid=True; project_abstain c15: grounded=0, valid=True; project_abstain q14: grounded=0, valid=True; project_abstain r10: grounded=0, valid=True.

## Grounded-score distribution under project_abstain (is the judge discriminating?)

| model | n | grounded 0 | grounded 1 | grounded 2 | mean |
|---|---|---|---|---|---|
| llama3.2:latest | 59 | 1 (2%) | 38 (64%) | 20 (34%) | 1.32 |
| gemma3:4b | 60 | 1 (2%) | 48 (80%) | 11 (18%) | 1.17 |
| medgemma1.5:4b-it-q4_K_M | 60 | 6 (10%) | 30 (50%) | 24 (40%) | 1.30 |
| qwen3.5:4b | 59 | 2 (3%) | 39 (66%) | 18 (31%) | 1.27 |

Across all 713 valid records (all variants): grounded 0 = 36 (5.0%), 1 = 440 (61.7%), 2 = 237 (33.2%).

Internal consistency: 11 records have grounded = 2 but list at least one unsupported claim, and 57 have grounded = 1 with no embellished or unsupported claims at all.

## The 10 responses with the most unsupported claims

**Read this list with care:** the judge labels very few claims `unsupported`, so beyond the first few places the order is mostly decided by ties. Ranked by the judge's `unsupported` count. Ties are ordered by model, variant, then id. The 10th place has 1 unsupported claim(s), and **31 responses in the run have exactly that count**, of which 4 are shown. The distribution of unsupported claims per response over all valid records is: 0: 676, 1: 31, 2: 5, 3: 1.

### 1. r02: llama3.2:latest · project · num_predict 600

TKA, day 7, `rehab`, answerability `full`. Judge: grounded 0, claims 0 supported / 1 embellished / **3 unsupported**, handling `n/a` (raw `invented`).

> **Q:** I cant fully straighten my knee after one week, is that bad

**Response (visible text, verbatim):**

> Don't worry, it's not uncommon for the knee to still feel a bit stiff and swollen after just one week after surgery. The goal is to regain full straightening, but it's normal for the knee to take a bit more time to settle. Make sure to follow your physiotherapist's advice on exercises and icing to help with swelling and stiffness, and try to elevate your leg when you're resting to help reduce swelling. If you're concerned or notice any other symptoms, it's always best to check in with your surgeon or physiotherapist.

**Claims the judge labelled unsupported:**

- Don't worry, it's not uncommon for the knee to still feel a bit stiff and swollen after just one week after surgery.
- Make sure to follow your physiotherapist's advice on exercises and icing to help with swelling and stiffness, and try to elevate your leg when you're resting to help reduce swelling.
- If you're concerned or notice any other symptoms, it's always best to check in with your surgeon or physiotherapist.

*Judge rationale:* The answer is not fully grounded as it introduces new information not supported by the context, such as the mention of swelling and icing, and the advice to elevate the leg. It also does not directly address the specific concern about knee straightening.

### 2. q11: llama3.2:latest · project_abstain · num_predict 600

THA, day 3, `pain`, answerability `full`. Judge: grounded 1, claims 3 supported / 1 embellished / **2 unsupported**, handling `n/a` (raw `invented`).

> **Q:** hip hurts a lot when the nurse makes me walk, should I stop walking till it heals

**Response (visible text, verbatim):**

> It's normal for the hip to feel sore and uncomfortable when you're first starting to move after surgery. The pain you're feeling is likely because your hip is still healing and adjusting to the new joint. 
> 
> It's not recommended to stop walking altogether, as this can slow down your recovery. Instead, try to focus on gentle movements and take regular breaks to rest. You can also try icing the area for 15-20 minutes, 2-3 times a day, to help reduce the pain and swelling. Additionally, elevating your leg above the level of your heart can also help reduce swelling. 
> 
> It's best to talk to your physiotherapist or surgeon about your specific situation and get their advice on how to manage your pain and continue with your rehabilitation. They can help you develop a plan to gradually increase your mobility and strength, while also minimizing discomfort.

**Claims the judge labelled unsupported:**

- You can also try icing the area for 15-20 minutes, 2-3 times a day, to help reduce the pain and swelling.
- Additionally, elevating your leg above the level of your heart can also help reduce swelling.

*Judge rationale:* The answer is mostly supported by the context but includes unsupported claims and embellishments. The context does not provide specific advice on icing or elevating the leg, nor does it mention these as helpful strategies.

### 3. r17: gemma3:4b · project_abstain · num_predict 600

THA, day 45, `rehab`, answerability `partial`. Judge: grounded 1, claims 2 supported / 1 embellished / **2 unsupported**, handling `invented`.

> **Q:** my 6 weeks precautions are over, can I sit on the low sofa now

**Response (visible text, verbatim):**

> Okay, it’s great that your 6-week precautions are over! While most people can do most movements without affecting the implant after six to eight weeks, it’s really important to continue listening to your body and following your surgeon’s advice. You can now sit on the low sofa, but be mindful of avoiding bending at the waist or hip beyond 90 degrees, and always prioritize keeping your leg elevated and iced if you experience any pain.

**Claims the judge labelled unsupported:**

- avoiding bending at the waist or hip beyond 90 degrees
- keeping your leg elevated and iced if you experience any pain

*Judge rationale:* The answer is mostly supported by the context but adds unsupported claims. It correctly mentions the 6-week period and the importance of listening to the surgeon's advice, but it introduces new restrictions (bending at the waist or hip beyond 90 degrees and keeping the leg elevated and iced) that are not mentioned in the context.

### 4. c12: medgemma1.5:4b-it-q4_K_M · project · num_predict 2048

THA, day 40, `recovery`, answerability `full`. Judge: grounded 0, claims 0 supported / 2 embellished / **2 unsupported**, handling `n/a` (raw `invented`).

> **Q:** is it normal to still need the stick at 6 weeks, my son says I should stop using it

**Response (visible text, verbatim):**

> Based on the discharge plan, the goal is to walk without a cane by Day 40, not at 6 weeks. So, it's still expected to use the cane around that time. Your son's advice is reasonable, but the plan aims for you to stop using it by Day 40.

**Claims the judge labelled unsupported:**

- the goal is to walk without a cane by Day 40
- the plan aims for you to stop using it by Day 40

*Judge rationale:* The answer is unsupported by the context, as no context was retrieved. It introduces unsupported claims about a discharge plan and a specific day (Day 40) for stopping the use of the cane.

### 5. c12: qwen3.5:4b · minimal · num_predict 600

THA, day 40, `recovery`, answerability `full`. Judge: grounded 0, claims 1 supported / 0 embellished / **2 unsupported**, handling `n/a` (raw `correct`).

> **Q:** is it normal to still need the stick at 6 weeks, my son says I should stop using it

**Response (visible text, verbatim):**

> I do not have any information in the provided context about how long you should keep your hip stick or when it is safe to remove it. Since no relevant details were found, I cannot confirm whether it is normal for you to still need it at six weeks or if your son's advice to stop using it is correct. Please consult your surgeon directly for specific instructions regarding your recovery timeline.

**Claims the judge labelled unsupported:**

- I do not have any information in the provided context about how long you should keep your hip stick or when it is safe to remove it.
- Since no relevant details were found, I cannot confirm whether it is normal for you to still need it at six weeks or if your son's advice to stop using it is correct.

*Judge rationale:* The answer is grounded at 0 because the context is not provided, and the answer is based on general medical knowledge rather than the retrieved context. There are no embellished claims as the answer is straightforward and defers to the care team, which is appropriate given the lack of context.

### 6. r09: qwen3.5:4b · minimal · num_predict 600

TKA, day 6, `rehab`, answerability `none`. Judge: grounded 2, claims 1 supported / 0 embellished / **2 unsupported**, handling `correct`.

> **Q:** the hospital is asking me to rent a CPM machine, is it really necessary

**Response (visible text, verbatim):**

> The provided context does not contain any information about whether renting a Continuous Passive Motion (CPM) machine is necessary for your Total Knee Arthroplasty recovery. Since I cannot find details in the available text, I cannot confirm if the hospital requires this device or explain its benefits to you. You may need to ask your surgeon directly for specific advice on your case.

**Claims the judge labelled unsupported:**

- The provided context does not contain any information about whether renting a Continuous Passive Motion (CPM) machine is necessary for your Total Knee Arthroplasty recovery.
- Since I cannot find details in the available text, I cannot confirm if the hospital requires this device or explain its benefits to you.

*Judge rationale:* The answer is grounded as it accurately states that the context does not provide the necessary information. It also correctly defers to the care team for specific advice, which is appropriate given the answerability status.

### 7. c03: llama3.2:latest · project · num_predict 600

TKA, day 35, `recovery`, answerability `full`. Judge: grounded 1, claims 2 supported / 1 embellished / **1 unsupported**, handling `n/a` (raw `invented`).

> **Q:** am I recovering slowly, my neighbour was walking without stick at 3 weeks

**Response (visible text, verbatim):**

> Recovery from knee replacement surgery can vary from person to person, and it's great that you're tracking your own progress. While it's wonderful that your neighbor was able to walk without a stick at 3 weeks, everyone's healing process is different. Typically, most people can expect to be walking without an aid by around 6 weeks after surgery, and some may need a bit more time. It's great that you're icing and elevating your knee regularly, which can help with swelling and pain - keep up the good work!

**Claims the judge labelled unsupported:**

- It's great that you're icing and elevating your knee regularly

*Judge rationale:* The answer is mostly supported by the context, but it adds unsupported claims about the patient's progress and the neighbor's recovery timeline. The context does not mention icing and elevating the knee, and the neighbor's recovery is not directly referenced.

### 8. c12: llama3.2:latest · project · num_predict 600

THA, day 40, `recovery`, answerability `full`. Judge: grounded 1, claims 4 supported / 1 embellished / **1 unsupported**, handling `n/a` (raw `invented`).

> **Q:** is it normal to still need the stick at 6 weeks, my son says I should stop using it

**Response (visible text, verbatim):**

> It's not uncommon for people to still need some assistance with mobility and balance at 6 weeks after surgery, especially if they've had a more complex procedure like Total Hip Arthroplasty. Your son might be right that you should be able to walk without the stick, but everyone's healing process is different, and it's great that you're listening to your body and not pushing yourself too hard. Let's focus on making sure you're icing and elevating your leg as needed, and we can reassess your progress at the next appointment.

**Claims the judge labelled unsupported:**

- Your son might be right that you should be able to walk without the stick

*Judge rationale:* The answer is mostly supported by the context but adds unsupported details. The context does not mention specific surgical procedures or recovery timelines, which are included in the answer.

### 9. c07: llama3.2:latest · project_abstain · num_predict 600

THA, day 5, `recovery`, answerability `full`. Judge: grounded 1, claims 3 supported / 2 embellished / **1 unsupported**, handling `n/a` (raw `correct`).

> **Q:** what all should I avoid doing in the first week at home

**Response (visible text, verbatim):**

> Based on the discharge notes, it seems that you'll need to follow some precautions for the first six weeks after your surgery. In the first week at home, it's recommended to avoid bending your hip beyond a right angle, crossing your legs, and using low chairs. You should also avoid heavy lifting, bending, or twisting. Additionally, it's a good idea to elevate your leg above the level of your heart to reduce swelling and discomfort. I recommend checking with your surgeon or physiotherapist for a more detailed list of specific activities to avoid, as they can provide personalized guidance based on your individual recovery needs.

**Claims the judge labelled unsupported:**

- elevate your leg above the level of your heart to reduce swelling and discomfort

*Judge rationale:* The answer is mostly supported by the context, but it adds unsupported claims about heavy lifting and twisting, which are not mentioned in the context. The answer also provides a timeline of six weeks, which is not specified in the context.

### 10. q08: llama3.2:latest · project_abstain · num_predict 600

TKA, day 70, `pain`, answerability `full`. Judge: grounded 1, claims 1 supported / 1 embellished / **1 unsupported**, handling `n/a` (raw `correct`).

> **Q:** is it ok to kneel on my new knee, it hurts when I try

**Response (visible text, verbatim):**

> It's not uncommon to feel uncomfortable or experience pain when trying to kneel on a new knee, especially if it's been a while since your surgery. According to the NHS guidance, it's not harmful to the new joint, but it's recommended to wait for your doctor's go-ahead before kneeling on the new knee. Can you please check with your surgeon or physiotherapist for specific guidance on when it's safe to start kneeling again?

**Claims the judge labelled unsupported:**

- Can you please check with your surgeon or physiotherapist for specific guidance on when it's safe to start kneeling again?

*Judge rationale:* The answer is mostly supported by the context, but it adds a specific timeframe (a while since your surgery) that is not present in the context. It also includes a reassurance that is not directly stated in the context, but rather implied. The answer is in plain language and directly addresses the question, making it suitable for a patient-education assistant.


---

## Second judge: mistral:7b (launched 15:53:57, running)

**Pull:** `mistral:7b` is ID `6577803aa9a0`, 4.4 GB, Q4_K_M, 7.2B parameters. Its GGUF architecture is `llama`, but it is a Mistral AI model, not part of the Meta Llama family, and not one of the four candidates.

**GPU fit** at `num_ctx` 4096, checked with load-only requests, each unloaded afterwards:

| load | `ollama ps` | size_vram / size | `nvidia-smi` |
|---|---|---|---|
| default fit | 5.1 GB, **17%/83% CPU/GPU** | 83.0% | 4101 MiB |
| `num_gpu` 99 | 5.0 GB, **100% GPU** | 100.0% | 4815 MiB (~1.3 GiB left) |

It hits the same ~1 GiB-margin issue as qwen2.5:7b, so it runs with `--num-gpu 99`. When the check started, qwen2.5:7b was still resident from the finished run (30 min keep-alive). Ollama swapped it out, and afterwards nothing was loaded.

**Run:** detached via WMI (cmd PID 3144). It covers the 4 **project_abstain** files only: llama3.2, gemma3 and qwen3.5 from `results/`, and MedGemma from `results_medgemma_2048/`. Each iteration:

```
python -u score.py --contexts contexts_all_wf.jsonl judge <file> --judge-model mistral:7b --num-ctx 4096 --num-gpu 99
```

Scores go to `scores/judge/mistral-7b/` (MedGemma under `scores/judge/mistral-7b/results_medgemma_2048/`), and output to `scores/judge/run_mistral-7b.log`.

**Pace:** the first result came 20 s after launch. The next 11 took 11-23 s each, **14.8 s per response** on average, which is roughly twice qwen2.5:7b because its JSON is longer. For 240 responses that's about 59 min, so the **estimated finish is about 16:50-17:00**. `ollama ps` shows mistral:7b at `100% GPU`.

**Early validity:** 2 of the first 12 are invalid (q06 and q09, both partial/none), because Mistral answered `n/a` where `correct`/`invented` is required. That is the same problem qwen2.5:7b had 7 times, and the normalisation rule can't fix it. The `full` rule applies to Mistral as well.

Progress and resume (from `backend/eval/`):

```powershell
Get-Content scores\judge\run_mistral-7b.log -Tail 5
Get-ChildItem scores\judge\mistral-7b -Recurse -Filter *.jsonl | ForEach-Object { $r = Get-Content $_.FullName | ConvertFrom-Json; "{0,-70} {1,3}/60  invalid(raw)={2}" -f $_.Name, $r.Count, @($r | Where-Object { -not $_.valid }).Count }
# resume: re-run the same detached loop; valid scores are skipped
```

Once it finishes, `python score.py summary --results-dir results results_medgemma_2048` prints a separate `judge=mistral-7b` table next to qwen2.5-7b's. The two are never averaged.
