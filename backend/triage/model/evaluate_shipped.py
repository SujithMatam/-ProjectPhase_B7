"""Evaluate the SHIPPED triage pipeline (TRIAGE_MODE=hybrid) against rules mode.

Shipped pipeline = overrides.py + the classifier that classifier_triage.py loads (M2 seed 4 if
its weights are present, else M1) + the doctor-alert gate (t_alert from selection.json).

* main test and challenge: the real code path, ``classifier_triage.evaluate(text)`` per message.
* unseen-scenario test: 191 of its 275 rows are in the MAIN train split, so the shipped model
  cannot be scored on it. Instead the same decision code (``classifier_triage.combine``) is fed
  the unseen-split M2 (seed 0) probabilities cached by train.py, with that split's own
  val-chosen t_red / t_yel / t_alert. This measures the pipeline design on new scenarios, not
  the shipped weights.
* rules mode: ``SafetyTriageEngine.evaluate_rules(text)`` (today's default engine), every RED
  emails.

No temperature field is supplied (the datasets are text only). Writes
artifacts/shipped_results.json and shipped_report.md (pasted into REPORT.md).

  set HF_HUB_OFFLINE=1
  backend/.venv/Scripts/python backend/triage/model/evaluate_shipped.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BACKEND))

from common import ART, CACHE, L2I, LABELS, R, Y, G, load_challenge, load_split, wilson, macro_f1  # noqa: E402

for _k in [k for k in os.environ if "SMTP" in k.upper() or "DOCTOR_ALERT" in k.upper()]:
    del os.environ[_k]                                    # never send mail from an evaluation

from triage import classifier_triage as ct  # noqa: E402
from triage.safety_triage import SafetyTriageEngine  # noqa: E402

AUDIT_IDS = [f"CH-{i}" for i in range(144, 151)]


def summarise(rows, preds, emails, suppressed=None):
    y = np.array([L2I[r["label"]] for r in rows])
    p = np.array([L2I[x] for x in preds])
    e = np.array(emails, dtype=bool)
    n, n_red = len(y), int((y == R).sum())
    k = int(((y == R) & (p == R)).sum())
    lo, hi = wilson(k, n_red)
    pp = int((p == R).sum())
    return {
        "n": n, "n_red": n_red, "red_tp": k,
        "red_recall": k / n_red, "red_recall_ci": [lo, hi],
        "red_precision": k / pp if pp else float("nan"),
        "macro_f1": macro_f1(y, p),
        "red_to_green": int(((y == R) & (p == G)).sum()),
        "red_to_yellow": int(((y == R) & (p == Y)).sum()),
        "green_to_red": int(((y == G) & (p == R)).sum()),
        "yellow_to_red": int(((y == Y) & (p == R)).sum()),
        "red_calls_per_100": 100 * pp / n,
        "emails": int(e.sum()),
        "emails_per_100": 100 * e.sum() / n,
        "red_rows_emailed": int((e & (y == R)).sum()),
        "email_recall": float((e & (y == R)).sum() / n_red),
        "email_precision": float((e & (y == R)).sum() / e.sum()) if e.sum() else float("nan"),
        "non_red_emails": int((e & (y != R)).sum()),
        "suppressed": int(sum(suppressed)) if suppressed is not None else 0,
        "suppressed_true_red": int(sum(1 for s, yy in zip(suppressed or [], y) if s and yy == R)),
    }


def run_rules(rows):
    preds = [SafetyTriageEngine.evaluate_rules(r["text"])["triage_level"] for r in rows]
    return preds, [x == "RED" for x in preds]


def run_live(rows):
    out = [ct.evaluate(r["text"]) for r in rows]
    return out


def run_cached(rows, npz, t):
    d = np.load(CACHE / "preds" / npz, allow_pickle=True)
    pmap = {str(i): p for i, p in zip(d["test_ids"], d["test_p"])}
    out = []
    for r in rows:
        p = pmap[r["id"]]
        probs = {l: float(v) for l, v in zip(LABELS, p)}
        out.append(ct.combine(r["text"], probs, t["t_red"], t["t_yel"], t["t_alert"],
                              f"M2:{npz[:-4]} (cached)"))
    return out


def classifier_only(results):
    return [r["classifier_level"] for r in results]


def main() -> None:
    sel = json.loads((ART / "selection.json").read_text(encoding="utf-8"))["splits"]
    info = ct.model_info()
    sets = {"test": load_split("main", "test"), "challenge": load_challenge()}
    results, per_row = {}, {}

    for name, rows in sets.items():
        rp, re_ = run_rules(rows)
        hy = run_live(rows)
        results[name] = {
            "rules": summarise(rows, rp, re_),
            "classifier_only": summarise(rows, classifier_only(hy),
                                         [h["classifier_level"] == "RED" for h in hy]),
            "hybrid": summarise(rows, [h["triage_level"] for h in hy],
                                [h["doctor_alert"] for h in hy],
                                [ct.SUPPRESSED_FLAG in h["flags"] for h in hy]),
        }
        per_row[name] = {r["id"]: (r, rr, h) for r, rr, h in zip(rows, rp, hy)}

    useen_rows = load_split("unseen", "test")
    s_un = sel["unseen"]["M2"]
    seed = s_un["best_seed"]
    t_un = s_un["seeds"][str(seed)]
    rp, re_ = run_rules(useen_rows)
    hy = run_cached(useen_rows, f"m2_unseen_it{s_un['num_iterations']}_seed{seed}.npz", t_un)
    results["unseen_test"] = {
        "rules": summarise(useen_rows, rp, re_),
        "classifier_only": summarise(useen_rows, classifier_only(hy),
                                     [h["classifier_level"] == "RED" for h in hy]),
        "hybrid": summarise(useen_rows, [h["triage_level"] for h in hy],
                            [h["doctor_alert"] for h in hy],
                            [ct.SUPPRESSED_FLAG in h["flags"] for h in hy]),
    }
    per_row["unseen_test"] = {r["id"]: (r, rr, h) for r, rr, h in zip(useen_rows, rp, hy)}

    # per-scenario RED recall on the unseen test
    scen = {}
    for rid, (r, rr, h) in per_row["unseen_test"].items():
        if r["label"] != "RED":
            continue
        s = scen.setdefault(r["scenario_id"], {"n": 0, "rules": 0, "clf": 0, "hybrid": 0})
        s["n"] += 1
        s["rules"] += rr == "RED"
        s["clf"] += h["classifier_level"] == "RED"
        s["hybrid"] += h["triage_level"] == "RED"
    results["unseen_test_per_scenario_red"] = scen

    audit = []
    for rid in AUDIT_IDS:
        r, rr, h = per_row["challenge"][rid]
        audit.append({"id": rid, "text": r["text"], "label": r["label"], "rules": rr,
                      "rules_email": rr == "RED", "hybrid": h["triage_level"],
                      "reasons": h["reasons"], "p_red": h["probabilities"]["RED"],
                      "email": h["doctor_alert"], "flags": h["flags"]})
    results["audit_rows"] = audit

    # every remaining hybrid RED->GREEN / RED->YELLOW, for the report
    misses = []
    for name in ("test", "challenge", "unseen_test"):
        for rid, (r, rr, h) in per_row[name].items():
            if r["label"] == "RED" and h["triage_level"] != "RED":
                misses.append({"set": name, "id": rid, "text": r["text"],
                               "hybrid": h["triage_level"],
                               "p_red": round(h["probabilities"]["RED"], 3)})
    results["hybrid_red_misses"] = misses
    results["model_info"] = info
    results["unseen_thresholds"] = {k: t_un[k] for k in ("t_red", "t_yel", "t_alert")}

    (ART / "shipped_results.json").write_text(json.dumps(results, indent=1) + "\n",
                                              encoding="utf-8")
    (HERE / "shipped_report.md").write_text(render(results), encoding="utf-8")
    print(render(results))


def _f(x, d=3):
    return f"{x:.{d}f}"


def render(res) -> str:
    mi = res["model_info"]
    L = []
    L.append("| set | mode | RED recall | 95% CI | RED prec. | macro F1 | RED->GREEN | "
             "RED->YELLOW | GREEN->RED | YELLOW->RED | RED calls / 100 | emails / 100 | "
             "RED rows emailed | non-RED emails | suppressed (of which RED) |")
    L.append("|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    names = {"test": "main test", "challenge": "challenge", "unseen_test": "unseen-scenario test"}
    modes = {"rules": "rules (default)", "classifier_only": "classifier only (thresholded)",
             "hybrid": "**hybrid (shipped)**"}
    for s in ("test", "challenge", "unseen_test"):
        for m in ("rules", "classifier_only", "hybrid"):
            x = res[s][m]
            ci = f"{_f(x['red_recall_ci'][0])}-{_f(x['red_recall_ci'][1])}"
            em = (f"{x['emails_per_100']:.1f}" if m != "classifier_only" else "")
            emailed = (f"{x['red_rows_emailed']}/{x['n_red']}" if m != "classifier_only" else "")
            nonred = (str(x["non_red_emails"]) if m != "classifier_only" else "")
            sup = (f"{x['suppressed']} ({x['suppressed_true_red']})" if m == "hybrid" else "")
            L.append(f"| {names[s]} (n={x['n']}, RED {x['n_red']}) | {modes[m]} | "
                     f"{_f(x['red_recall'])} | {ci} | {_f(x['red_precision'])} | "
                     f"{_f(x['macro_f1'])} | {x['red_to_green']} | {x['red_to_yellow']} | "
                     f"{x['green_to_red']} | {x['yellow_to_red']} | "
                     f"{x['red_calls_per_100']:.1f} | {em} | {emailed} | {nonred} | {sup} |")
    L.append("")
    L.append(f"Shipped classifier: `{mi['model_used']}`, t_red {_f(mi['t_red'])}, "
             f"t_yel {_f(mi['t_yel'])}, t_alert {_f(mi['t_alert'])}. Unseen-scenario rows use the "
             f"unseen-split M2 (seed 0) cached probabilities with that split's val thresholds "
             f"(t_red {_f(res['unseen_thresholds']['t_red'])}, t_alert "
             f"{_f(res['unseen_thresholds']['t_alert'])}); 191 of its 275 test rows are in the "
             f"main train split, so the shipped weights are not scored there. \"classifier only\" "
             f"is the same run without overrides (no gate). Rules mode emails on every RED.")
    L.append("")
    L.append("Per-scenario RED recall, unseen-scenario test:")
    L.append("")
    L.append("| scenario | RED rows | rules | classifier only | hybrid |")
    L.append("|---|---:|---:|---:|---:|")
    for sc, v in sorted(res["unseen_test_per_scenario_red"].items()):
        L.append(f"| {sc} | {v['n']} | {v['rules']}/{v['n']} | {v['clf']}/{v['n']} | "
                 f"{v['hybrid']}/{v['n']} |")
    L.append("")
    L.append("The 7 audit_regression rows (challenge set):")
    L.append("")
    L.append("| id | text | label | rules | rules email | hybrid | reasons | p(RED) | email |")
    L.append("|---|---|---|---|---|---|---|---:|---|")
    for a in res["audit_rows"]:
        def b(lvl):
            return lvl if lvl == a["label"] else f"**{lvl}**"
        em = "yes" if a["email"] else ("no (suppressed)" if a["flags"] else "no")
        L.append(f"| {a['id']} | {a['text']} | {a['label']} | {b(a['rules'])} | "
                 f"{'yes' if a['rules_email'] else 'no'} | {b(a['hybrid'])} | "
                 f"{', '.join(a['reasons'])} | {_f(a['p_red'])} | {em} |")
    L.append("")
    L.append("Bold = differs from the label.")
    L.append("")
    L.append("RED messages the hybrid pipeline still does not call RED:")
    L.append("")
    L.append("| set | id | hybrid | p(RED) | text |")
    L.append("|---|---|---|---:|---|")
    for m in res["hybrid_red_misses"]:
        L.append(f"| {m['set']} | {m['id']} | {m['hybrid']} | {m['p_red']} | {m['text']} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
