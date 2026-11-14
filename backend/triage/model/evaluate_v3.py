"""v2 vs v3 SHIPPED pipeline (hybrid: overrides + thresholded classifier + doctor-alert gate) on
main test, challenge, challenge_v2, challenge_v3, the integration set and the unseen-scenario
test, and the shipping rule stated in REPORT.md before training.

* Every row goes through ``classifier_triage.combine`` with that version's val-chosen thresholds;
  probabilities come from train.py's cached predictions (v2 on challenge_v3 / integration is
  predicted here from the saved v2 weights and cached).
* unseen-scenario test: the unseen-split models of each version (v2: selection_v2 seed and
  thresholds; v3: selection_v3 seed and thresholds), as in evaluate_v2.py.
* Live check: when ``classifier_triage`` loads the v3 weights (v3 is the default), the real code
  path ``classifier_triage.evaluate`` is run on every main-model row and must give the same level
  and email as the cached path; otherwise the check is recorded as skipped.
* Prevalence-adjusted rows: per-class rates re-weighted to 5% RED, 25% YELLOW, 70% GREEN.

No temperature field; SMTP / DOCTOR_ALERT variables are removed. Writes artifacts/v3_results.json
and model/v3_report.md.

  set HF_HUB_OFFLINE=1
  backend/.venv/Scripts/python backend/triage/model/evaluate_v3.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
for _k in [k for k in os.environ if "SMTP" in k.upper() or "DOCTOR_ALERT" in k.upper()]:
    del os.environ[_k]                                    # never send mail from an evaluation
os.environ.pop("TRIAGE_MODEL_VERSION", None)

from common import (ART, CACHE, LABELS, SETFIT_SEEDS, load_challenge, load_challenge_v2,  # noqa: E402
                    load_challenge_v3, load_integration, load_split)
from evaluate_v2 import cached, pipeline, setfit_proba, summarise, thr  # noqa: E402
from triage import classifier_triage as ct  # noqa: E402
from triage.safety_triage import SafetyTriageEngine  # noqa: E402

PREDS = CACHE / "preds"
MAIN_SETS = ("test", "challenge", "challenge_v2", "challenge_v3", "integration")
ALL_SETS = MAIN_SETS + ("unseen_test",)
SET_NAMES = {"test": "main test", "challenge": "challenge", "challenge_v2": "challenge_v2",
             "challenge_v3": "challenge_v3", "integration": "integration set",
             "unseen_test": "unseen-scenario test"}
CALF = "I have severe calf pain and swelling, can I still do my exercises?"
SHORT_EXAMPLES = [   # from backend/eval/reports/2026-11-14_main-post-merge-tests.md and REPORT.md
    "My knee is swollen.", "My knee pain suddenly got much worse today.",
    "My pain suddenly got much worse today.", "My knee is more swollen today and hurts.",
    "My knee is swollen and sore.", "My hip is swollen and sore.", "My ankle is swollen and sore.",
    "My hip has started aching today.", "My knee is sore.", "My knee hurts.",
    "My pain suddenly got worse today, and it's mostly behind the knee.",
    "My knee is sore and a bit tender. It started suddenly, I feel it mostly behind the knee, it's been getting worse, and the knee feels stiff.",
    "My knee pain is 6 out of 10, it started suddenly behind the knee and it is swollen.",
    "My incision hurts and there is yellow fluid coming out.",
    "My wound looks more red today and it's leaking some fluid.", "My wound looks a bit red today.",
    "Since I didn't take my medicine yesterday, my knee wound is worse",
    "I am anxious, my knee hurts, and I need help with exercises",
    "I cannot keep fluids down and I am hardly urinating.", "I feel hopeless and cannot function.",
    "I feel scared to move my leg.",
    "I have severe calf pain and swelling in my calf.", "My calf is swollen.",
    "I have severe chest pain and can't breathe.",
]


def over(x: dict) -> int:
    return x["yellow_to_red"] + x["green_to_red"]


def main() -> None:
    v2sel = json.loads((ART / "selection_v2.json").read_text(encoding="utf-8"))["splits"]
    v3sel = json.loads((ART / "selection_v3.json").read_text(encoding="utf-8"))["splits"]
    sets = {"test": load_split("main", "test"), "challenge": load_challenge(),
            "challenge_v2": load_challenge_v2(), "challenge_v3": load_challenge_v3(),
            "integration": load_integration()}

    s2 = v2sel["main"]["M2"]["best_seed"]
    v2name = f"m2_main_v2_it3_seed{s2}"
    p_v2 = cached(f"{v2name}.npz")
    extra = PREDS / f"{v2name}_v3sets.npz"
    if not extra.exists():
        arrs = {}
        for k in ("challenge_v3", "integration"):
            arrs[f"{k}_ids"] = np.array([r["id"] for r in sets[k]])
            arrs[f"{k}_p"] = setfit_proba(v2name, [r["text"] for r in sets[k]])
        np.savez(extra, **arrs)
    p_v2.update(cached(extra.name))
    t_v2 = thr(v2sel["main"]["M2"]["seeds"][str(s2)])

    s3 = v3sel["main"]["M2"]["best_seed"]
    v3name = v3sel["main"]["M2"]["weights_dir"]
    p_v3 = {sd: cached(f"m2_main_v3_it3_seed{sd}.npz") for sd in SETFIT_SEEDS["main"]}
    t_v3 = {sd: thr(v3sel["main"]["M2"]["seeds"][str(sd)]) for sd in SETFIT_SEEDS["main"]}

    info = ct.model_info()
    live_ok = info["model_used"] == f"M2:{v3name}"
    res: dict = {"seeds": {"v2": s2, "v3": s3}, "weights": {"v2": v2name, "v3": v3name},
                 "thresholds": {"v2": t_v2, "v3": t_v3[s3]}, "sets": {}, "model_info": info}
    per_row: dict = {}
    for name, rows in sets.items():
        rules = [SafetyTriageEngine.evaluate_rules(r["text"])["triage_level"] for r in rows]
        a = pipeline(rows, p_v2, t_v2, f"M2:{v2name}")
        b = {sd: pipeline(rows, p_v3[sd], t_v3[sd], f"M2:m2_main_v3_it3_seed{sd}")
             for sd in SETFIT_SEEDS["main"]}
        seed_stats = [summarise(rows, [h["triage_level"] for h in b[sd]], [h["doctor_alert"] for h in b[sd]])
                      for sd in SETFIT_SEEDS["main"]]
        for st in seed_stats:
            st["over_triage"] = over(st)
        entry = {
            "rules": summarise(rows, rules, [x == "RED" for x in rules]),
            "v2": summarise(rows, [h["triage_level"] for h in a], [h["doctor_alert"] for h in a]),
            "v3": summarise(rows, [h["triage_level"] for h in b[s3]], [h["doctor_alert"] for h in b[s3]]),
            "v3_seeds": {k: [float(np.mean([s[k] for s in seed_stats])), float(np.std([s[k] for s in seed_stats]))]
                         for k in ("red_recall", "red_tp", "red_to_green", "yellow_to_red", "green_to_red",
                                   "over_triage", "emails_per_100", "macro_f1")},
        }
        if live_ok:
            live = [ct.evaluate(r["text"]) for r in rows]
            mism = [(r["id"], x["triage_level"], y["triage_level"]) for r, x, y in zip(rows, live, b[s3])
                    if x["triage_level"] != y["triage_level"] or x["doctor_alert"] != y["doctor_alert"]]
            dp = max(abs(x["probabilities"]["RED"] - y["probabilities"]["RED"]) for x, y in zip(live, b[s3]))
            entry["live_check"] = {"model_used": info["model_used"], "mismatches": mism, "max_abs_p_red_diff": dp}
        else:
            entry["live_check"] = {"skipped": f"default loads {info['model_used']}, not M2:{v3name}"}
        res["sets"][name] = entry
        per_row[name] = {r["id"]: (r, rr, x, y) for r, rr, x, y in zip(rows, rules, a, b[s3])}

    rows = load_split("unseen", "test")
    rules = [SafetyTriageEngine.evaluate_rules(r["text"])["triage_level"] for r in rows]
    u2, u3 = v2sel["unseen"]["M2"]["best_seed"], v3sel["unseen"]["M2"]["best_seed"]
    h2 = pipeline(rows, cached(f"m2_unseen_v2_it3_seed{u2}.npz"), thr(v2sel["unseen"]["M2"]["seeds"][str(u2)]), "unseen v2")
    h3 = pipeline(rows, cached(f"m2_unseen_v3_it3_seed{u3}.npz"), thr(v3sel["unseen"]["M2"]["seeds"][str(u3)]), "unseen v3")
    res["sets"]["unseen_test"] = {
        "rules": summarise(rows, rules, [x == "RED" for x in rules]),
        "v2": summarise(rows, [h["triage_level"] for h in h2], [h["doctor_alert"] for h in h2]),
        "v3": summarise(rows, [h["triage_level"] for h in h3], [h["doctor_alert"] for h in h3])}
    res["unseen_seeds"] = {"v2": u2, "v3": u3}
    per_row["unseen_test"] = {r["id"]: (r, rr, x, y) for r, rr, x, y in zip(rows, rules, h2, h3)}
    for s in ALL_SETS:
        for m in ("rules", "v2", "v3"):
            res["sets"][s][m]["over_triage"] = over(res["sets"][s][m])

    # ---- shipping rule (REPORT.md, committed before training)
    t2, t3 = res["sets"]["test"]["v2"], res["sets"]["test"]["v3"]
    c1 = t3["red_tp"] >= t2["red_tp"] - 2
    c2 = {s: res["sets"][s]["v3"]["red_to_green"] <= res["sets"][s]["v2"]["red_to_green"] for s in ALL_SETS}
    c3 = {s: res["sets"][s]["v3"]["over_triage"] < res["sets"][s]["v2"]["over_triage"]
          for s in ("challenge_v3", "integration")}
    res["rule"] = {"c1_test_red_recall": {"pass": c1, "v2_red_tp": t2["red_tp"], "v3_red_tp": t3["red_tp"],
                                          "n_red": t2["n_red"]},
                   "c2_red_to_green": {"pass": all(c2.values()), "per_set": c2},
                   "c3_over_triage": {"pass": all(c3.values()), "per_set": c3},
                   "ship_v3": bool(c1 and all(c2.values()) and all(c3.values()))}

    # ---- per category, examples, misses, changes
    cats = {}
    for name in ("challenge_v3", "challenge_v2", "challenge"):
        for rid, (r, rr, a, b) in per_row[name].items():
            c = cats.setdefault(f"{name}:{r['category']}", {"n": 0, "R": 0, "Y": 0, "G": 0, "v2_red_tp": 0,
                                                             "v3_red_tp": 0, "v2_over": 0, "v3_over": 0,
                                                             "v2_r2g": 0, "v3_r2g": 0})
            c["n"] += 1
            c[r["label"][0]] += 1
            for v, h in (("v2", a), ("v3", b)):
                lv = h["triage_level"]
                c[f"{v}_red_tp"] += r["label"] == "RED" and lv == "RED"
                c[f"{v}_over"] += r["label"] != "RED" and lv == "RED"
                c[f"{v}_r2g"] += r["label"] == "RED" and lv == "GREEN"
    res["categories"] = cats

    def ex(r, a, b, setname):
        return {"set": setname, "id": r["id"], "text": r["text"], "label": r["label"],
                "v2": a["triage_level"], "v2_p_red": a["probabilities"]["RED"], "v2_email": a["doctor_alert"],
                "v3": b["triage_level"], "v3_p_red": b["probabilities"]["RED"], "v3_email": b["doctor_alert"],
                "v3_reason_codes": b["reason_codes"]}
    by_text = {r["text"]: (r, a, b) for rid, (r, rr, a, b) in per_row["integration"].items()}
    res["examples"] = [ex(*by_text[t], "integration") for t in [CALF] + SHORT_EXAMPLES]
    res["challenge_v3_short"] = [ex(r, a, b, "challenge_v3") for rid, (r, rr, a, b) in per_row["challenge_v3"].items()
                                 if r["category"] == "short_single_symptom"]
    res["red_misses"] = [ex(r, a, b, n) for n in per_row for rid, (r, rr, a, b) in per_row[n].items()
                         if r["label"] == "RED" and (a["triage_level"] != "RED" or b["triage_level"] != "RED")]
    res["integration_changed"] = [ex(r, a, b, "integration") for rid, (r, rr, a, b) in per_row["integration"].items()
                                  if a["triage_level"] != b["triage_level"] or a["doctor_alert"] != b["doctor_alert"]]
    res["integration_over_red"] = [ex(r, a, b, "integration") for rid, (r, rr, a, b) in per_row["integration"].items()
                                   if r["label"] != "RED" and "RED" in (a["triage_level"], b["triage_level"])]

    (ART / "v3_results.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    md = render(res)
    (HERE / "v3_report.md").write_text(md, encoding="utf-8")
    print(md)


def _f(x, d=3):
    return f"{x:.{d}f}"


def _e(b):
    return "yes" if b else "no"


def render(res) -> str:
    L = []
    rule = res["rule"]
    L += ["### Shipping rule (stated before training)", "",
          "| condition | v2 | v3 | pass |", "|---|---|---|---|",
          f"| 1. main test RED rows called RED (v3 >= v2 - 2) | {rule['c1_test_red_recall']['v2_red_tp']}/"
          f"{rule['c1_test_red_recall']['n_red']} | {rule['c1_test_red_recall']['v3_red_tp']}/"
          f"{rule['c1_test_red_recall']['n_red']} | {_e(rule['c1_test_red_recall']['pass'])} |"]
    for s in ALL_SETS:
        L.append(f"| 2. RED->GREEN not higher: {SET_NAMES[s]} | {res['sets'][s]['v2']['red_to_green']} | "
                 f"{res['sets'][s]['v3']['red_to_green']} | {_e(rule['c2_red_to_green']['per_set'][s])} |")
    for s in ("challenge_v3", "integration"):
        L.append(f"| 3. over-triage (Y->R + G->R) lower: {SET_NAMES[s]} | {res['sets'][s]['v2']['over_triage']} | "
                 f"{res['sets'][s]['v3']['over_triage']} | {_e(rule['c3_over_triage']['per_set'][s])} |")
    L += ["", f"**Ship v3: {'YES' if rule['ship_v3'] else 'NO'}.**", ""]

    modes = {"rules": "rules (TRIAGE_MODE=rules)", "v2": "v2 hybrid (current default)", "v3": "**v3 hybrid**"}
    L += ["### v2 vs v3 shipped pipeline", "",
          "| set | pipeline | RED recall | 95% CI | RED->GREEN | RED->YELLOW | YELLOW->RED | GREEN->RED | "
          "over-triage | RED prec. | macro F1 | RED calls / 100 | emails / 100 | RED rows emailed |",
          "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in ALL_SETS:
        for m in modes:
            x = res["sets"][s][m]
            L.append(f"| {SET_NAMES[s]} (n={x['n']}: R {x['n_red']} / Y {x['n_yellow']} / G {x['n_green']}) | "
                     f"{modes[m]} | {_f(x['red_recall'])} | {_f(x['red_recall_ci'][0])}-{_f(x['red_recall_ci'][1])} | "
                     f"{x['red_to_green']} | {x['red_to_yellow']} | {x['yellow_to_red']} | {x['green_to_red']} | "
                     f"{x['over_triage']} | {_f(x['red_precision'])} | {_f(x['macro_f1'])} | "
                     f"{x['red_calls_per_100']:.1f} | {x['emails_per_100']:.1f} | {x['red_rows_emailed']}/{x['n_red']} |")
    L += ["", "v3 seed spread (all 5 main-split v3 seeds, each with its own val-chosen thresholds; mean ± sd):", "",
          "| set | RED recall | RED rows called RED | RED->GREEN | YELLOW->RED | GREEN->RED | over-triage | emails / 100 | macro F1 |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in MAIN_SETS:
        v = res["sets"][s]["v3_seeds"]

        def ms(k, d=3):
            return f"{v[k][0]:.{d}f} ± {v[k][1]:.{d}f}"
        L.append(f"| {SET_NAMES[s]} | {ms('red_recall')} | {ms('red_tp', 1)} | {ms('red_to_green', 1)} | "
                 f"{ms('yellow_to_red', 1)} | {ms('green_to_red', 1)} | {ms('over_triage', 1)} | "
                 f"{ms('emails_per_100', 1)} | {ms('macro_f1')} |")
    L += ["", "### Prevalence-adjusted (5% RED, 25% YELLOW, 70% GREEN)", "",
          "Per-class rates from each set (share of RED / YELLOW / GREEN rows called RED, and emailed), "
          "re-weighted to the mix. Email precision = share of emails that are about a RED message at that mix.", "",
          "| set | pipeline | RED-call rate R / Y / G | email rate R / Y / G | RED calls / 100 | emails / 100 | email precision |",
          "|---|---|---|---|---:|---:|---:|"]
    for s in ALL_SETS:
        for m in modes:
            x = res["sets"][s][m]
            pr = x["per_class_rates"]
            rr = " / ".join(f"{pr[c]['red']:.2f}" if c in pr else "-" for c in LABELS[::-1])
            er = " / ".join(f"{pr[c]['email']:.2f}" if c in pr else "-" for c in LABELS[::-1])
            L.append(f"| {SET_NAMES[s]} | {modes[m]} | {rr} | {er} | {x['adj_red_calls_per_100']:.1f} | "
                     f"{x['adj_emails_per_100']:.1f} | {_f(x['adj_email_precision'], 2)} |")
    L += ["", "### Per category", "",
          "| set:category | n (R/Y/G) | v2 RED caught | v3 RED caught | v2 RED->GREEN | v3 RED->GREEN | "
          "v2 non-RED called RED | v3 non-RED called RED |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for k, c in res["categories"].items():
        rr2 = f"{c['v2_red_tp']}/{c['R']}" if c["R"] else ""
        rr3 = f"{c['v3_red_tp']}/{c['R']}" if c["R"] else ""
        L.append(f"| {k} | {c['n']} ({c['R']}/{c['Y']}/{c['G']}) | {rr2} | {rr3} | {c['v2_r2g']} | {c['v3_r2g']} | "
                 f"{c['v2_over']} | {c['v3_over']} |")

    def table(title, items):
        out = ["", f"### {title}", "",
               "| set | text | label | v2 | v2 p(RED) | v2 email | v3 | v3 p(RED) | v3 email |",
               "|---|---|---|---|---:|---|---|---:|---|"]
        for e in items:
            def b(l):
                return l if l == e["label"] else f"**{l}**"
            out.append(f"| {e['set']} | {e['text']} | {e['label']} | {b(e['v2'])} | {_f(e['v2_p_red'])} | "
                       f"{_e(e['v2_email'])} | {b(e['v3'])} | {_f(e['v3_p_red'])} | {_e(e['v3_email'])} |")
        return out
    L += table("The calf message and short-message examples (integration set)", res["examples"])
    L += ["", "Bold = differs from the guideline label."]
    L += table("challenge_v3 short single-symptom rows", res["challenge_v3_short"])
    L += table("RED rows missed by v2 or v3 (every set)", res["red_misses"])
    L += table("Integration rows whose level or email changed v2 -> v3", res["integration_changed"])
    L += table("Integration rows labelled non-RED that v2 or v3 calls RED", res["integration_over_red"])
    L += ["", "Live code path (`classifier_triage.evaluate`) vs cached probabilities, v3:"]
    for s in MAIN_SETS:
        lc = res["sets"][s]["live_check"]
        if "skipped" in lc:
            L.append(f"- {s}: skipped ({lc['skipped']})")
        else:
            L.append(f"- {s}: model `{lc['model_used']}`, {len(lc['mismatches'])} level/email mismatches, "
                     f"max |p(RED) diff| {lc['max_abs_p_red_diff']:.2e}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
