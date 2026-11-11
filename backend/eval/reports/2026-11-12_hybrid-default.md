# Hybrid triage as the default (feature/triage-classifier, 2026-11-12)

Commits: `ab55940` (default + shipped model) and the follow-up that fixes the v1 restore hint
in the fallback warning and adds this report.

## 1. Shipped model in git
- `backend/triage/model/artifacts/setfit/m2_main_v2_it3_seed0`: 12 files, largest
  `model.safetensors` 90,864,192 bytes (86.7 MiB), so all are under 95 MB. **Plain git, no LFS.**
  GitHub printed its advisory "GH001: Large files detected" (> 50 MB) on push; the push succeeded.
- `.gitignore` un-ignores only that folder (`artifacts/setfit/*` + `!.../m2_main_v2_it3_seed0/`);
  other seeds, v1 weights, `artifacts/cache/` and `__pycache__/` stay ignored. New
  `.gitattributes` marks `artifacts/setfit/** -text` so `core.autocrlf=true` cannot rewrite
  tokenizer/config bytes.
- **Clone proof:** `git clone --branch feature/triage-classifier` of the pushed branch into a temp
  folder: HEAD `ab55940`; `setfit/` holds only `m2_main_v2_it3_seed0`; sha256 of all 12 files is
  identical to the local copy; `git lfs ls-files` is empty. With `HF_HUB_OFFLINE=1`, importing
  the clone's `main.py` and running its startup hooks printed
  `[TRIAGE][HYBRID] classifier loaded: M2:m2_main_v2_it3_seed0 (t_red=0.354 t_yel=0.363 t_alert=0.684)`;
  `model_info()`: no load error and no warning; a sample message scored RED with p(RED) 0.953.
  8.5 s in total, no training, and no new files in the clone.

## 2. Modes
- `TRIAGE_MODE` unset, empty or unknown: hybrid (unknown values log a warning).
- `TRIAGE_MODE=rules`: `SafetyTriageEngine.evaluate_rules`, the same code path as before.
- `TRIAGE_MODEL_VERSION=v1`: works. Locally it loads `M2:m2_main_it3_seed4` (t_red 0.217). In a
  fresh clone those weights do not exist, so it warns and uses v1's M1 (`m1_main.json`).

## 3. Fallback is never silent
- M2 folder missing or failing to load: one stderr `WARNING` that names the folder and says
  "Using the M1 fallback", then M1. Shown in the clone by moving the v2 folder away. If M1 also
  fails, an `ERROR` is printed and the rules engine fills the classifier component.
- `main.py` now loads the classifier in a startup hook (hybrid only), so the warning appears when
  the server starts rather than on the first patient message.
- New tests: the missing-folder and broken-folder cases each produce exactly one warning that
  names the folder.

## 4. requirements.txt
Pinned to the training versions recorded in the model card: `torch==2.14.0` (CPU; the comment
gives the CPU index URL), `sentence-transformers==6.0.1`, `setfit==1.2.0`, plus
`transformers==5.17.0` and `scikit-learn==1.9.1` (`model_head.pkl` is a pickled scikit-learn
model). Note: `sentence-transformers` was `>=2.7.0` and is also used by RAG.

## 5. Test suites (SMTP*/DOCTOR_ALERT* unset, temporary patient DB, run one after another)

| suite | hybrid (default) | rules |
|---|---|---|
| test_multi_agent_orchestration.py | 4/5 | 5/5 |
| test_nutrition_wellbeing_agents.py | 6/9 | 9/9 |
| test_doctor_alert.py | 2 check failures | all passed |
| test_phase4_agents.py | 3 check failures | all passed |
| test_fallback_procedure_isolation.py | 5/10 | 5/10 (same) |
| test_specialized_assigned.py | 1/4 | 1/4 (same) |
| test_phase3_rag.py | 4 check failures | same 4 |
| pain / recovery / rehab / symptom / medication_schedule | 79/79 | 79/79 |
| test_medication_proactive.py | 21/21 | 21/21 |
| test_phase2_intent.py | all passed | all passed |
| triage/test_overrides.py + test_classifier_triage.py | 153/153 | 153/153 |

**Hybrid over-triage causes every hybrid-only failure.** In each case the classifier says RED and
no override fired:

| message | test (author) | rules | p(RED) | doctor email |
|---|---|---|---|---|
| My knee is more swollen today and hurts. | test_phase4_agents.py (3 checks) | YELLOW | 0.809 | yes |
| I cannot keep fluids down and I am hardly urinating. | test_nutrition_wellbeing_agents.py | GREEN | 0.782 | yes |
| Since I didn't take my medicine yesterday, my knee wound is worse | test_multi_agent_orchestration.py (Finding V7) | GREEN | 0.756 | yes |
| I feel hopeless and cannot function. | test_nutrition_wellbeing_agents.py | GREEN | 0.753 | yes |
| I feel scared to move my leg. | test_nutrition_wellbeing_agents.py | GREEN | 0.601 | no |
| My wound looks a bit red today. | test_doctor_alert.py G (2 checks) | YELLOW | 0.477 | no* |

\* The email is suppressed by the t_alert gate, but test G counts any call to the notifier, and
the message is routed to emergency instead of wound care.

**Not caused by hybrid (the same failures in rules mode):** test_fallback_procedure_isolation.py
(5: `ChatAgent._generate_smart_reply()` does not accept `procedure` / `domain_instruction` on this
branch), test_specialized_assigned.py (3: `IndexError`, the mocked reply call is never reached,
the same signature drift), test_phase3_rag.py (4: `reindex()` returns `None`, plus one
keyword_fallback check).

**Tests I did not edit** (failing in hybrid, written by others or shared): test_phase4_agents.py,
test_nutrition_wellbeing_agents.py, test_multi_agent_orchestration.py, test_doctor_alert.py, and
the mode-independent test_fallback_procedure_isolation.py, test_specialized_assigned.py and
test_phase3_rag.py. The only test file changed is triage/test_classifier_triage.py (the default
flips to hybrid, plus the fallback-warning tests).

## 6. Docs
`backend/README.md` has a new "Triage" section. `triage/REPORT.md` and `model/report_template.md`
(REPORT.md is regenerated from the template) have a new "Default mode changed to hybrid" section
with the tables above, and the stale "default rules" lines are updated.
