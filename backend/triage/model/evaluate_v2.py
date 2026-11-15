"""v1 vs v2 SHIPPED pipeline (TRIAGE_MODE=hybrid) on test, challenge, challenge_v2 and the
unseen-scenario test. Same method as evaluate_shipped.py:

* Every pipeline row goes through ``classifier_triage.combine`` (overrides + thresholded
  classifier + doctor-alert gate) with that version's val-chosen thresholds; probabilities come
  from the cached predictions of train.py (challenge_v2 for v1 is predicted here from the saved
  v1 weights). For v2 the real code path ``classifier_triage.evaluate`` is also run on every main
  set row and must give the same level and email as the cached path.
* unseen-scenario test: the unseen-split models (v1: seed 0, v1 thresholds; v2: best val seed,
  v2 rule), as before - this measures the pipeline design on new scenarios, not shipped weights.
* "v1 model, v2 rule" = v1 shipped weights with thresholds re-chosen by the v2 rule (ablation:
  separates the effect of the new data from the effect of the new operating point).
* Prevalence-adjusted rows: per-class rates (share of RED / YELLOW / GREEN rows that get a RED
  call or an email) re-weighted to 5% RED, 25% YELLOW, 70% GREEN.

No temperature field; SMTP / DOCTOR_ALERT variables are removed. Writes
artifacts/v2_results.json and model/v2_report.md.

  set HF_HUB_OFFLINE=1
  backend/.venv/Scripts/python backend/triage/model/evaluate_v2.py
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
os.environ.pop("TRIAGE_MODEL_VERSION", None)              # the live path must load v2

from common import (ART, CACHE, L2I, LABELS, SETFIT_DIR, SETFIT_SEEDS, G, R, Y,  # noqa: E402
                    load_challenge, load_challenge_v2, load_split, macro_f1, wilson)
from triage import classifier_triage as ct  # noqa: E402
from triage.safety_triage import SafetyTriageEngine  # noqa: E402

MIX = {"RED": 0.05, "YELLOW": 0.25, "GREEN": 0.70}
AUDIT_IDS = [f"CH-{i}" for i in range(144, 151)]
ORCH = ["Since I didn't take my medicine yesterday, my knee wound is worse",
        "I am anxious, my knee hurts, and I need help with exercises"]
PREDS = CACHE / "preds"
SET_NAMES = {"test": "main test", "challenge": "challenge", "challenge_v2": "challenge_v2",
             "unseen_test": "unseen-scenario test"}


def summarise(rows, levels, emails) -> dict:
    y = np.array([L2I[r["label"]] for r in rows])
    p = np.array([L2I[x] for x in levels])
    e = np.array(emails, dtype=bool)
    n, n_red = len(y), int((y == R).sum())
    k = int(((y == R) & (p == R)).sum())
    pp = int((p == R).sum())
    lo, hi = wilson(k, n_red)
    rate = {c: {"red": float((p[y == L2I[c]] == R).mean()), "email": float(e[y == L2I[c]].mean())}
            for c in LABELS if (y == L2I[c]).any()}
    adj_red = 100 * sum(MIX[c] * rate[c]["red"] for c in rate)
    adj_email = 100 * sum(MIX[c] * rate[c]["email"] for c in rate)
    return {
        "n": n, "n_red": n_red, "n_yellow": int((y == Y).sum()), "n_green": int((y == G).sum()),
        "red_tp": k, "red_recall": k / n_red, "red_recall_ci": [lo, hi],
        "red_precision": k / pp if pp else float("nan"), "macro_f1": macro_f1(y, p),
        "red_to_green": int(((y == R) & (p == G)).sum()),
        "red_to_yellow": int(((y == R) & (p == Y)).sum()),
        "yellow_to_red": int(((y == Y) & (p == R)).sum()),
        "green_to_red": int(((y == G) & (p == R)).sum()),
        "yellow_to_green": int(((y == Y) & (p == G)).sum()),
        "red_calls_per_100": 100 * pp / n, "emails_per_100": 100 * e.sum() / n,
        "red_rows_emailed": int((e & (y == R)).sum()), "non_red_emails": int((e & (y != R)).sum()),
        "per_class_rates": rate,
        "adj_red_calls_per_100": adj_red, "adj_emails_per_100": adj_email,
        "adj_email_precision": (100 * MIX["RED"] * rate["RED"]["email"] / adj_email
                                if adj_email else float("nan")),
    }


def cached(npz: str) -> dict:
    d = np.load(PREDS / npz, allow_pickle=True)
    out = {}
    for k in d.files:
        if k.endswith("_ids"):
            part = k[:-4]
            out.update({str(i): p for i, p in zip(d[k], d[f"{part}_p"])})
    return out


def setfit_proba(weights: str, texts: list[str]) -> np.ndarray:
    from setfit import SetFitModel
    m = SetFitModel.from_pretrained(str(SETFIT_DIR / weights))
    return np.asarray(m.predict_proba(texts, as_numpy=True, show_progress_bar=False))


def pipeline(rows, pmap, t, name) -> list[dict]:
    out = []
    for r in rows:
        probs = {l: float(v) for l, v in zip(LABELS, pmap[r["id"]])}
        out.append(ct.combine(r["text"], probs, t["t_red"], t["t_yel"], t["t_alert"], name))
    return out


def thr(d: dict) -> dict:
    return {k: d[k] for k in ("t_red", "t_yel", "t_alert")}


def main() -> None:
    v1sel = json.loads((ART / "selection.json").read_text(encoding="utf-8"))["splits"]
    v2all = json.loads((ART / "selection_v2.json").read_text(encoding="utf-8"))
    v2sel = v2all["splits"]
    sets = {"test": load_split("main", "test"), "challenge": load_challenge(),
            "challenge_v2": load_challenge_v2()}

    # ---- probabilities
    s1 = v1sel["main"]["M2"]["best_seed"]
    v1name = f"m2_main_it3_seed{s1}"
    p_v1 = cached(f"{v1name}.npz")
    ch2_cache = PREDS / f"{v1name}_challenge_v2.npz"
    if not ch2_cache.exists():
        rows = sets["challenge_v2"]
        np.savez(ch2_cache, challenge_v2_ids=np.array([r["id"] for r in rows]),
                 challenge_v2_p=setfit_proba(v1name, [r["text"] for r in rows]))
    p_v1.update(cached(ch2_cache.name))
    s2 = v2sel["main"]["M2"]["best_seed"]
    p_v2 = {sd: cached(f"m2_main_v2_it3_seed{sd}.npz") for sd in SETFIT_SEEDS["main"]}

    t_v1 = thr(v1sel["main"]["M2"]["seeds"][str(s1)])
    t_v1_new = thr(v2all["v1_under_v2_rule"]["main"]["M2"])
    t_v2 = {sd: thr(v2sel["main"]["M2"]["seeds"][str(sd)]) for sd in SETFIT_SEEDS["main"]}
    p_m1v2 = cached("m1_main_v2.npz")
    t_m1v2 = thr(v2sel["main"]["M1"])

    res: dict = {"thresholds": {"v1": t_v1, "v1_model_v2_rule": t_v1_new, "v2": t_v2[s2]},
                 "seeds": {"v1": s1, "v2": s2}, "sets": {}}
    per_row: dict = {}
    for name, rows in sets.items():
        rules = [SafetyTriageEngine.evaluate_rules(r["text"])["triage_level"] for r in rows]
        v1 = pipeline(rows, p_v1, t_v1, f"M2:{v1name}")
        v1n = pipeline(rows, p_v1, t_v1_new, f"M2:{v1name} (v2 rule)")
        m1v2 = pipeline(rows, p_m1v2, t_m1v2, "M1:m1_main_v2")
        v2 = {sd: pipeline(rows, p_v2[sd], t_v2[sd], f"M2:m2_main_v2_it3_seed{sd}")
              for sd in SETFIT_SEEDS["main"]}
        live = [ct.evaluate(r["text"]) for r in rows]
        mism = [(r["id"], a["triage_level"], b["triage_level"]) for r, a, b in zip(rows, live, v2[s2])
                if a["triage_level"] != b["triage_level"] or a["doctor_alert"] != b["doctor_alert"]]
        dp = max(abs(a["probabilities"]["RED"] - b["probabilities"]["RED"])
                 for a, b in zip(live, v2[s2]))
        seed_stats = [summarise(rows, [h["triage_level"] for h in v2[sd]],
                                [h["doctor_alert"] for h in v2[sd]]) for sd in SETFIT_SEEDS["main"]]
        res["sets"][name] = {
            "rules": summarise(rows, rules, [x == "RED" for x in rules]),
            "v1": summarise(rows, [h["triage_level"] for h in v1], [h["doctor_alert"] for h in v1]),
            "v1_model_v2_rule": summarise(rows, [h["triage_level"] for h in v1n],
                                          [h["doctor_alert"] for h in v1n]),
            "v2": summarise(rows, [h["triage_level"] for h in v2[s2]],
                            [h["doctor_alert"] for h in v2[s2]]),
            "v2_m1": summarise(rows, [h["triage_level"] for h in m1v2],
                               [h["doctor_alert"] for h in m1v2]),
            "v2_seeds": {k: [float(np.mean([s[k] for s in seed_stats])),
                             float(np.std([s[k] for s in seed_stats]))]
                         for k in ("red_recall", "red_to_green", "yellow_to_red", "green_to_red",
                                   "emails_per_100", "adj_emails_per_100", "adj_red_calls_per_100",
                                   "macro_f1")},
            "live_check": {"model_used": live[0]["model_used"], "mismatches": mism,
                           "max_abs_p_red_diff": dp},
        }
        per_row[name] = {r["id"]: (r, rr, a, b) for r, rr, a, b in zip(rows, rules, v1, v2[s2])}

    # ---- unseen-scenario test
    rows = load_split("unseen", "test")
    rules = [SafetyTriageEngine.evaluate_rules(r["text"])["triage_level"] for r in rows]
    u1 = v1sel["unseen"]["M2"]["best_seed"]
    u2 = v2sel["unseen"]["M2"]["best_seed"]
    pu1 = cached(f"m2_unseen_it3_seed{u1}.npz")
    pu2 = cached(f"m2_unseen_v2_it3_seed{u2}.npz")
    tu1 = thr(v1sel["unseen"]["M2"]["seeds"][str(u1)])
    tu1n = thr(v2all["v1_under_v2_rule"]["unseen"]["M2"])
    tu2 = thr(v2sel["unseen"]["M2"]["seeds"][str(u2)])
    h1 = pipeline(rows, pu1, tu1, "unseen v1")
    h1n = pipeline(rows, pu1, tu1n, "unseen v1 (v2 rule)")
    h2 = pipeline(rows, pu2, tu2, "unseen v2")
    res["sets"]["unseen_test"] = {
        "rules": summarise(rows, rules, [x == "RED" for x in rules]),
        "v1": summarise(rows, [h["triage_level"] for h in h1], [h["doctor_alert"] for h in h1]),
        "v1_model_v2_rule": summarise(rows, [h["triage_level"] for h in h1n],
                                      [h["doctor_alert"] for h in h1n]),
        "v2": summarise(rows, [h["triage_level"] for h in h2], [h["doctor_alert"] for h in h2]),
    }
    res["thresholds"]["unseen"] = {"v1": tu1, "v1_model_v2_rule": tu1n, "v2": tu2,
                                   "v1_seed": u1, "v2_seed": u2}
    per_row["unseen_test"] = {r["id"]: (r, rr, a, b) for r, rr, a, b in zip(rows, rules, h1, h2)}

    # ---- per category (challenge_v2 and challenge)
    cats = {}
    for name in ("challenge_v2", "challenge"):
        for rid, (r, rr, a, b) in per_row[name].items():
            c = cats.setdefault(f"{name}:{r['category']}", {
                "n": 0, "R": 0, "Y": 0, "G": 0, "rules_ok": 0, "v1_ok": 0, "v2_ok": 0,
                "v1_red_tp": 0, "v2_red_tp": 0, "v1_over_red": 0, "v2_over_red": 0,
                "v1_under": 0, "v2_under": 0})
            c["n"] += 1
            c[r["label"][0]] += 1
            c["rules_ok"] += rr == r["label"]
            for v, h in (("v1", a), ("v2", b)):
                lv = h["triage_level"]
                c[f"{v}_ok"] += lv == r["label"]
                c[f"{v}_red_tp"] += r["label"] == "RED" and lv == "RED"
                c[f"{v}_over_red"] += r["label"] != "RED" and lv == "RED"
                c[f"{v}_under"] += L2I[lv] < L2I[r["label"]]
    res["categories"] = cats

    # ---- audit rows, orchestration messages, misses
    res["audit_rows"] = []
    for rid in AUDIT_IDS:
        r, rr, a, b = per_row["challenge"][rid]
        res["audit_rows"].append({
            "id": rid, "text": r["text"], "label": r["label"], "rules": rr,
            "v1": a["triage_level"], "v1_p_red": a["probabilities"]["RED"], "v1_email": a["doctor_alert"],
            "v2": b["triage_level"], "v2_p_red": b["probabilities"]["RED"], "v2_email": b["doctor_alert"],
            "v2_reason_codes": b["reason_codes"], "v2_reasons": b["reasons"]})
    pv1 = setfit_proba(v1name, ORCH)
    res["orchestration_messages"] = []
    for text, p1 in zip(ORCH, pv1):
        a = ct.combine(text, {l: float(v) for l, v in zip(LABELS, p1)}, **t_v1, model_used="v1")
        b = ct.evaluate(text)
        res["orchestration_messages"].append({
            "text": text, "rules": SafetyTriageEngine.evaluate_rules(text)["triage_level"],
            "v1": a["triage_level"], "v1_p_red": a["probabilities"]["RED"], "v1_email": a["doctor_alert"],
            "v2": b["triage_level"], "v2_p_red": b["probabilities"]["RED"], "v2_email": b["doctor_alert"]})
    res["v2_red_misses"] = [
        {"set": n, "id": rid, "text": r["text"], "v2": b["triage_level"],
         "p_red": round(b["probabilities"]["RED"], 3), "v1": a["triage_level"]}
        for n in per_row for rid, (r, rr, a, b) in per_row[n].items()
        if r["label"] == "RED" and b["triage_level"] != "RED"]
    res["v2_new_red_to_lower"] = [m for m in res["v2_red_misses"] if m["v1"] == "RED"]
    res["model_info"] = ct.model_info()

    (ART / "v2_results.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    md = render(res, v2all)
    (HERE / "v2_report.md").write_text(md, encoding="utf-8")
    print(md)


def _f(x, d=3):
    return f"{x:.{d}f}"


def render(res, v2all) -> str:
    L = []
    modes = {"rules": "rules (default)", "v1": "v1 hybrid (shipped before)",
             "v1_model_v2_rule": "v1 model, v2 rule (ablation)", "v2": "**v2 hybrid (shipped)**",
             "v2_m1": "v2 data, M1 head (not shipped)"}
    L += ["### v1 vs v2 shipped pipeline", "",
          "| set | pipeline | RED recall | 95% CI | RED->GREEN | RED->YELLOW | YELLOW->RED | "
          "GREEN->RED | RED prec. | macro F1 | RED calls / 100 | emails / 100 | RED rows emailed |",
          "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in ("test", "challenge", "challenge_v2", "unseen_test"):
        for m in modes:
            if m not in res["sets"][s]:
                continue
            x = res["sets"][s][m]
            L.append(f"| {SET_NAMES[s]} (n={x['n']}: R {x['n_red']} / Y {x['n_yellow']} / "
                     f"G {x['n_green']}) | {modes[m]} | {_f(x['red_recall'])} | "
                     f"{_f(x['red_recall_ci'][0])}-{_f(x['red_recall_ci'][1])} | {x['red_to_green']} | "
                     f"{x['red_to_yellow']} | {x['yellow_to_red']} | {x['green_to_red']} | "
                     f"{_f(x['red_precision'])} | {_f(x['macro_f1'])} | {x['red_calls_per_100']:.1f} | "
                     f"{x['emails_per_100']:.1f} | {x['red_rows_emailed']}/{x['n_red']} |")
    L += ["", "v2 seed spread (all 5 main-split v2 seeds, each with its own val-chosen thresholds; mean ± sd):", "",
          "| set | RED recall | RED->GREEN | YELLOW->RED | GREEN->RED | emails / 100 | macro F1 |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for s in ("test", "challenge", "challenge_v2"):
        v = res["sets"][s]["v2_seeds"]

        def ms(k, d=3):
            return f"{v[k][0]:.{d}f} ± {v[k][1]:.{d}f}"
        L.append(f"| {SET_NAMES[s]} | {ms('red_recall')} | {ms('red_to_green', 1)} | "
                 f"{ms('yellow_to_red', 1)} | {ms('green_to_red', 1)} | {ms('emails_per_100', 1)} | "
                 f"{ms('macro_f1')} |")
    L += ["", "### Prevalence-adjusted (5% RED, 25% YELLOW, 70% GREEN)", "",
          "Per-class rates from each set: share of RED / YELLOW / GREEN rows called RED and share "
          "emailed, re-weighted to the mix. Email precision = share of emails that are about a "
          "RED message at that mix.", "",
          "| set | pipeline | RED-call rate R / Y / G | email rate R / Y / G | RED calls / 100 | "
          "emails / 100 | email precision |", "|---|---|---|---|---:|---:|---:|"]
    for s in ("test", "challenge", "challenge_v2", "unseen_test"):
        for m in modes:
            if m not in res["sets"][s] or m == "v2_m1":
                continue
            x = res["sets"][s][m]
            pr = x["per_class_rates"]
            rr = " / ".join(f"{pr[c]['red']:.2f}" for c in LABELS[::-1])
            er = " / ".join(f"{pr[c]['email']:.2f}" for c in LABELS[::-1])
            L.append(f"| {SET_NAMES[s]} | {modes[m]} | {rr} | {er} | {x['adj_red_calls_per_100']:.1f} | "
                     f"{x['adj_emails_per_100']:.1f} | {_f(x['adj_email_precision'], 2)} |")
    L += ["", "### Per category", "",
          "| set:category | n (R/Y/G) | rules acc. | v1 acc. | v2 acc. | v1 RED recall | v2 RED recall | "
          "v1 non-RED called RED | v2 non-RED called RED | v1 under-triaged | v2 under-triaged |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for k, c in res["categories"].items():
        rr1 = f"{c['v1_red_tp']}/{c['R']}" if c["R"] else ""
        rr2 = f"{c['v2_red_tp']}/{c['R']}" if c["R"] else ""
        L.append(f"| {k} | {c['n']} ({c['R']}/{c['Y']}/{c['G']}) | {c['rules_ok'] / c['n']:.0%} | "
                 f"{c['v1_ok'] / c['n']:.0%} | {c['v2_ok'] / c['n']:.0%} | {rr1} | {rr2} | "
                 f"{c['v1_over_red']} | {c['v2_over_red']} | {c['v1_under']} | {c['v2_under']} |")
    L += ["", "### The 7 audit rows", "",
          "| id | text | label | rules | v1 | v1 p(RED) | v1 email | v2 | v2 p(RED) | v2 email | v2 reason codes |",
          "|---|---|---|---|---|---:|---|---|---:|---|---|"]
    for a in res["audit_rows"]:
        def b(l):
            return l if l == a["label"] else f"**{l}**"
        L.append(f"| {a['id']} | {a['text']} | {a['label']} | {b(a['rules'])} | {b(a['v1'])} | "
                 f"{_f(a['v1_p_red'])} | {'yes' if a['v1_email'] else 'no'} | {b(a['v2'])} | "
                 f"{_f(a['v2_p_red'])} | {'yes' if a['v2_email'] else 'no'} | "
                 f"{', '.join(a['v2_reason_codes'])} |")
    L += ["", "Bold = differs from the label.", "", "### Orchestration-test messages", "",
          "| message | rules | v1 | v1 p(RED) | v1 email | v2 | v2 p(RED) | v2 email |",
          "|---|---|---|---:|---|---|---:|---|"]
    for o in res["orchestration_messages"]:
        L.append(f"| {o['text']} | {o['rules']} | {o['v1']} | {_f(o['v1_p_red'])} | "
                 f"{'yes' if o['v1_email'] else 'no'} | {o['v2']} | {_f(o['v2_p_red'])} | "
                 f"{'yes' if o['v2_email'] else 'no'} |")
    L += ["", "### RED messages v2 does not call RED", "",
          "| set | id | v2 | p(RED) | v1 | text |", "|---|---|---|---:|---|---|"]
    for m in res["v2_red_misses"]:
        L.append(f"| {m['set']} | {m['id']} | {m['v2']} | {m['p_red']} | {m['v1']} | {m['text']} |")
    L += ["", "Live code path (`classifier_triage.evaluate`) vs cached probabilities, v2:"]
    for s in ("test", "challenge", "challenge_v2"):
        lc = res["sets"][s]["live_check"]
        L.append(f"- {s}: model `{lc['model_used']}`, {len(lc['mismatches'])} level/email "
                 f"mismatches, max |p(RED) diff| {lc['max_abs_p_red_diff']:.2e}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
