"""Final numbers for every contender. Reads test / challenge / unseen-scenario test for the first
and only time; every threshold and model choice comes from artifacts/selection.json (val only).

  backend/.venv/Scripts/python backend/triage/model/train.py all     # first
  backend/.venv/Scripts/python backend/triage/model/evaluate.py

Writes artifacts/results.json, results.md (every table), reliability_<model>.png and, if
report_template.md exists, backend/triage/REPORT.md (template + tables).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ART, EMBED_MODEL, G, HERE, LABELS, R, SETFIT_SEEDS, SETFIT_DIR, TRIAGE, Y,  # noqa: E402
                    argmax_rule, ece, hybrid, labels_of, load_challenge, load_rules, load_split,
                    metrics, rule_predict, threshold_rule)
from train import load_preds  # noqa: E402

AUDIT_SCEN_TEST = ("ALLERGIC_REACTION", "HIGH_FEVER")
AUDIT_SCEN_VAL = ("FALL_INJURY", "WOUND_OPEN")
CAT_ORDER = ("negation", "keyword_free_red", "indian_english", "typo_or_slang", "numeric_in_text",
             "multi_symptom", "benign_scary_word", "audit_regression")


def f3(x):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.3f}"


def pct(x):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:.1f}%"


def ms(vals, fmt="{:.3f}"):
    v = np.array(vals, dtype=float)
    return (fmt + " ± " + fmt).format(v.mean(), v.std(ddof=1))


# ---------------------------------------------------------------- contenders
def build(split: str, sel: dict) -> dict:
    """name -> {"set": {"pred": array | [arrays per seed], "p": probs or None}} for every eval set."""
    s = sel["splits"][split]
    sets = {"val": load_split(split, "val"), "test": load_split(split, "test")}
    if split == "main":
        sets["challenge"] = load_challenge()
    texts = {k: [r["text"] for r in v] for k, v in sets.items()}
    out: dict = {"_sets": sets}
    for b in ("B0", "B1"):
        eng = load_rules(b)
        out[b] = {k: {"pred": rule_predict(eng, t)} for k, t in texts.items()}
    m1 = load_preds(f"m1_{split}")
    th = s["M1"]
    out["M1 argmax"] = {k: {"pred": argmax_rule(m1[f"{k}_p"]), "p": m1[f"{k}_p"]} for k in sets}
    out["M1 thresholded"] = {k: {"pred": threshold_rule(m1[f"{k}_p"], th["t_red"], th["t_yel"]),
                                 "p": m1[f"{k}_p"]} for k in sets}
    it = s["M2"]["num_iterations"]
    seeds = SETFIT_SEEDS[split]
    m2 = {sd: load_preds(f"m2_{split}_it{it}_seed{sd}") for sd in seeds}
    for rule in ("argmax", "thresholded"):
        out[f"M2 {rule}"] = {}
        for k in sets:
            preds = []
            for sd in seeds:
                p = m2[sd][f"{k}_p"]
                t = s["M2"]["seeds"][str(sd)] if str(sd) in s["M2"]["seeds"] else s["M2"]["seeds"][sd]
                preds.append(argmax_rule(p) if rule == "argmax" else threshold_rule(p, t["t_red"], t["t_yel"]))
            out[f"M2 {rule}"][k] = {"pred": preds, "p": [m2[sd][f"{k}_p"] for sd in seeds]}
    best = s["best_model"]
    ship = s["M2"]["best_seed"]
    for rule in ("argmax", "thresholded"):
        src = out[f"{best} {rule}"]
        out[f"H1 {rule}"] = {}
        for k in sets:
            mp = src[k]["pred"][seeds.index(ship)] if best == "M2" else src[k]["pred"]
            out[f"H1 {rule}"][k] = {"pred": hybrid(out["B1"][k]["pred"], mp)}
    out["_best"] = best if best == "M1" else f"M2 (seed {ship})"
    return out


CONTENDERS = ("B0", "B1", "M1 argmax", "M1 thresholded", "M2 argmax", "M2 thresholded",
              "H1 argmax", "H1 thresholded")


def is_multi(c, k):
    return isinstance(c[k]["pred"], list)


def mets(c, k, y, mask=None):
    preds = c[k]["pred"] if is_multi(c, k) else [c[k]["pred"]]
    yy = y if mask is None else y[mask]
    return [metrics(yy, p if mask is None else p[mask]) for p in preds]


def cell(ml, key, fmt=f3):
    if len(ml) == 1:
        v = ml[0][key]
        return str(v) if isinstance(v, int) else fmt(v)
    v = [m[key] for m in ml]
    if isinstance(v[0], int):
        return ms(v, "{:.1f}")
    return ms(v)


def ci_cell(ml):
    if len(ml) > 1:
        lo = min(m["red_recall_ci"][0] for m in ml)
        hi = max(m["red_recall_ci"][1] for m in ml)
        return f"seeds' CIs span {lo:.3f}-{hi:.3f}"
    lo, hi = ml[0]["red_recall_ci"]
    return f"{lo:.3f}-{hi:.3f}"


def metric_table(C, k, y, mask=None, contenders=CONTENDERS) -> str:
    lines = ["| contender | RED recall | 95% CI (Wilson) | RED precision | macro F1 | RED->GREEN | RED->YELLOW | GREEN->RED | YELLOW->GREEN |",
             "|---|---:|---|---:|---:|---:|---:|---:|---:|"]
    for name in contenders:
        ml = mets(C[name], k, y, mask)
        lines.append(f"| {name} | {cell(ml, 'red_recall')} | {ci_cell(ml)} | {cell(ml, 'red_precision')} | "
                     f"{cell(ml, 'macro_f1')} | {cell(ml, 'red_to_green')} | {cell(ml, 'red_to_yellow')} | "
                     f"{cell(ml, 'green_to_red')} | {cell(ml, 'yellow_to_green')} |")
    n = int(len(y) if mask is None else mask.sum())
    nr = int((y == R).sum() if mask is None else (y[mask] == R).sum())
    lines.append(f"\nn = {n}, RED = {nr}. M2 rows: mean ± sd over seeds (5 main, 3 unseen-scenario; CI column: range of the per-seed Wilson intervals).")
    return "\n".join(lines)


def confusion_block(C, k, y, mask=None, contenders=CONTENDERS) -> str:
    out = []
    for name in contenders:
        preds = C[name][k]["pred"] if is_multi(C[name], k) else [C[name][k]["pred"]]
        yy = y if mask is None else y[mask]
        cms = np.array([metrics(yy, p if mask is None else p[mask])["confusion"] for p in preds])
        cm = cms.mean(0)
        f = (lambda v: f"{v:.1f}") if len(preds) > 1 else (lambda v: f"{int(v)}")
        title = name + (f" (mean of {len(preds)} seeds)" if len(preds) > 1 else "")
        out += [f"**{title}**\n", "| true \\ pred | RED | YELLOW | GREEN |", "|---|---:|---:|---:|"]
        for i, lab in enumerate(("RED", "YELLOW", "GREEN")):
            out.append(f"| {lab} | " + " | ".join(f(v) for v in cm[i]) + " |")
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------- latency / size
def dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def hf_model_dir() -> Path | None:
    from huggingface_hub import snapshot_download
    try:
        return Path(snapshot_download(EMBED_MODEL, local_files_only=True))
    except Exception:
        return None


def latency(texts: list[str], sel: dict) -> list[dict]:
    import torch
    from sentence_transformers import SentenceTransformer
    rows = []

    def bench(name, fn, size, params, note=""):
        for t in texts[:10]:
            fn(t)
        ts = []
        for t in texts:
            t0 = time.perf_counter()
            fn(t)
            ts.append(1000 * (time.perf_counter() - t0))
        rows.append({"model": name, "median_ms": float(np.median(ts)), "p95_ms": float(np.percentile(ts, 95)),
                     "size": size, "params": params, "note": note})

    b0, b1 = load_rules("B0"), load_rules("B1")
    for nm, eng in (("B0", b0), ("B1", b1)):
        src = (ART / "cache").glob(f"safety_triage_{nm}_*.py")
        bench(nm, lambda t, e=eng: e.evaluate(t), sum(f.stat().st_size for f in src), 0, "regex rules")
    st = SentenceTransformer(EMBED_MODEL, device="cpu")
    head = json.loads((ART / "m1_main.json").read_text(encoding="utf-8"))
    W, b = np.array(head["coef"]), np.array(head["intercept"])
    nparams = sum(p.numel() for p in st.parameters())

    def m1(t):
        e = st.encode([t], normalize_embeddings=True, show_progress_bar=False)
        z = e @ W.T + b
        z = np.exp(z - z.max(1, keepdims=True))
        return z / z.sum(1, keepdims=True)
    mdir = hf_model_dir()
    enc_size = dir_size(mdir) if mdir else 0
    bench("M1", m1, enc_size + (ART / "m1_main.json").stat().st_size, nparams + W.size + b.size,
          "frozen MiniLM + LR head (head JSON committed)")
    s = sel["splits"]["main"]
    name = f"m2_main_it{s['M2']['num_iterations']}_seed{s['M2']['best_seed']}"
    if (SETFIT_DIR / name).exists():
        from setfit import SetFitModel
        sf = SetFitModel.from_pretrained(str(SETFIT_DIR / name))
        np_sf = sum(p.numel() for p in sf.model_body.parameters()) + sf.model_head.coef_.size
        bench("M2", lambda t: sf.predict_proba([t], as_numpy=True, show_progress_bar=False),
              dir_size(SETFIT_DIR / name), np_sf, f"SetFit {name} (weights not committed)")
        best_fn = (lambda t: sf.predict_proba([t], as_numpy=True, show_progress_bar=False)) \
            if s["best_model"] == "M2" else m1
    else:
        best_fn = m1
    bench("H1", lambda t: (b1.evaluate(t), best_fn(t)), 0, 0, "B1 + best model, sequential")
    rows[-1]["size"] = rows[1]["size"] + next(r["size"] for r in rows if r["model"] == ("M2" if s["best_model"] == "M2" else "M1"))
    rows[-1]["params"] = next(r["params"] for r in rows if r["model"] == ("M2" if s["best_model"] == "M2" else "M1"))
    rows.append({"threads": torch.get_num_threads(), "n_messages": len(texts), "cpu": os.environ.get("PROCESSOR_IDENTIFIER", "")})
    return rows


# ---------------------------------------------------------------- reliability diagram
def reliability_png(p: np.ndarray, y: np.ndarray, title: str, path: Path) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    res = ece(p, y)
    surface, ink, ink2, grid, series, ref = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6", "#8d8c87"
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.2), gridspec_kw={"height_ratios": [4, 1]},
                             facecolor=surface, sharex="col")
    for col, (key, lab, e) in enumerate((("bins_top", "Top-label confidence", res["ece_top"]),
                                         ("bins_red", "Predicted p(RED)", res["ece_red"]))):
        ax, axh = axes[0, col], axes[1, col]
        rows = [r for r in res[key] if r[2] > 0]
        conf = [r[3] for r in rows]
        acc = [r[4] for r in rows]
        ax.plot([0, 1], [0, 1], ls=(0, (4, 3)), color=ref, lw=1.2, zorder=1)
        ax.plot(conf, acc, color=series, lw=2, zorder=2)
        ax.scatter(conf, acc, s=36, color=series, edgecolor=surface, linewidth=2, zorder=3)
        ax.set_ylabel("Observed accuracy" if col == 0 else "Observed fraction RED", color=ink2)
        ax.set_title(f"{lab}  (ECE {e:.3f})", color=ink, fontsize=11, loc="left")
        ax.text(0.97, 0.05, "perfect calibration", color=ref, ha="right", fontsize=8,
                transform=ax.transAxes)
        widths = [r[1] - r[0] for r in res[key]]
        axh.bar([r[0] for r in res[key]], [r[2] for r in res[key]], width=[w * 0.92 for w in widths],
                align="edge", color=ref)
        axh.set_ylabel("rows", color=ink2)
        axh.set_xlabel(lab, color=ink2)
        for a in (ax, axh):
            a.set_facecolor(surface)
            a.set_xlim(0, 1)
            a.grid(color=grid, lw=0.8)
            a.set_axisbelow(True)
            for sp in ("top", "right"):
                a.spines[sp].set_visible(False)
            for sp in ("left", "bottom"):
                a.spines[sp].set_color(grid)
            a.tick_params(colors=ink2, labelsize=8)
        ax.set_ylim(0, 1)
    fig.suptitle(title, color=ink, fontsize=12, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=130, facecolor=surface)
    plt.close(fig)
    return res


# ---------------------------------------------------------------- main
def main() -> None:
    sel = json.loads((ART / "selection.json").read_text(encoding="utf-8"))
    T: dict[str, str] = {}
    res: dict = {}

    # ---- main split
    C = build("main", sel)
    sets = C["_sets"]
    yt, yc = labels_of(sets["test"]), labels_of(sets["challenge"])
    best_main = C["_best"]

    # headline
    h = ["| contender | test RED recall | test 95% CI | challenge RED recall | challenge 95% CI | test RED->GREEN | challenge RED->GREEN | test macro F1 | challenge macro F1 |",
         "|---|---:|---|---:|---|---:|---:|---:|---:|"]
    for name in CONTENDERS:
        mt, mc = mets(C[name], "test", yt), mets(C[name], "challenge", yc)
        h.append(f"| {name} | {cell(mt, 'red_recall')} | {ci_cell(mt)} | {cell(mc, 'red_recall')} | {ci_cell(mc)} | "
                 f"{cell(mt, 'red_to_green')} | {cell(mc, 'red_to_green')} | {cell(mt, 'macro_f1')} | {cell(mc, 'macro_f1')} |")
    h.append(f"\ntest n = {len(yt)} (RED {int((yt == R).sum())}); challenge n = {len(yc)} (RED {int((yc == R).sum())}). "
             f"H1 = max(B1, {best_main}). M2 rows: mean ± sd over 5 seeds.")
    T["headline"] = "\n".join(h)
    T["test_metrics"] = metric_table(C, "test", yt)
    T["test_confusion"] = confusion_block(C, "test", yt)
    T["challenge_metrics"] = metric_table(C, "challenge", yc)
    T["challenge_confusion"] = confusion_block(C, "challenge", yc)

    # rules without source_template rows
    src_t = np.array([r["origin"] != "source_template" for r in sets["test"]])
    T["rules_no_template_test"] = metric_table(C, "test", yt, src_t, ("B0", "B1", "M1 argmax", "M1 thresholded", "M2 argmax", "M2 thresholded", "H1 argmax", "H1 thresholded"))

    # challenge per category
    cats = np.array([r["category"] for r in sets["challenge"]])
    lines = ["| category | n (R/Y/G) | " + " | ".join(CONTENDERS) + " |", "|---|---|" + "---:|" * len(CONTENDERS)]
    lines_r = ["| category | RED rows | " + " | ".join(CONTENDERS) + " |", "|---|---:|" + "---:|" * len(CONTENDERS)]
    for cat in CAT_ORDER:
        m = cats == cat
        yy = yc[m]
        cnt = f"{int(m.sum())} ({int((yy == R).sum())}/{int((yy == Y).sum())}/{int((yy == G).sum())})"
        cells, cells_r = [], []
        for name in CONTENDERS:
            ml = mets(C[name], "challenge", yc, m)
            accs = [x["accuracy"] for x in ml]
            und = [x["under_triage"] for x in ml]
            if len(ml) > 1:
                cells.append(f"{100 * np.mean(accs):.0f}% / {np.mean(und):.1f}")
            else:
                cells.append(f"{100 * accs[0]:.0f}% / {und[0]}")
            if (yy == R).any():
                rr = [x["red_recall"] for x in ml]
                cells_r.append(f"{np.mean(rr):.2f}" + (f" ± {np.std(rr, ddof=1):.2f}" if len(ml) > 1 else ""))
        lines.append(f"| {cat} | {cnt} | " + " | ".join(cells) + " |")
        if (yy == R).any():
            lines_r.append(f"| {cat} | {int((yy == R).sum())} | " + " | ".join(cells_r) + " |")
    T["challenge_categories"] = "\n".join(lines) + "\n\nCell = accuracy / number of under-triaged rows (predicted level below the label). M2: mean over 5 seeds."
    T["challenge_categories_red"] = "\n".join(lines_r) + "\n\nRED recall per category (categories with RED rows only)."

    # audit regression rows
    ship = sel["splits"]["main"]["M2"]["best_seed"]
    aud = [i for i, r in enumerate(sets["challenge"]) if r["category"] == "audit_regression"]
    a = ["| id | text | label | " + " | ".join(CONTENDERS) + " |", "|---|---|---|" + "---|" * len(CONTENDERS)]
    for i in aud:
        r = sets["challenge"][i]
        cs = []
        for name in CONTENDERS:
            pr = C[name]["challenge"]["pred"]
            if isinstance(pr, list):
                levels = [LABELS[p[i]] for p in pr]
                ok = sum(l == r["label"] for l in levels)
                cs.append(f"{LABELS[pr[SETFIT_SEEDS['main'].index(ship)][i]]} ({ok}/{len(pr)} ok)")
            else:
                lv = LABELS[pr[i]]
                cs.append(lv if lv == r["label"] else f"**{lv}**")
        a.append(f"| {r['id']} | {r['text']} | {r['label']} | " + " | ".join(cs) + " |")
    T["audit_rows"] = "\n".join(a) + (f"\n\nBold = wrong. M2 cells show the shipped seed ({ship}) and how many of the 5 seeds got the row right.")

    # selection summary
    s = sel["splits"]["main"]
    su = sel["splits"]["unseen"]
    sl = ["| split | model | choice (val) | t_red | t_yel | val RED recall (thr.) | val YELLOW found (thr.) | val macro F1 (argmax) |",
          "|---|---|---|---:|---:|---:|---:|---:|"]
    for spn, ss in (("main", s), ("unseen", su)):
        m1 = ss["M1"]
        sl.append(f"| {spn} | M1 | C = {m1['C']:g} | {m1['t_red']:.3f} | {m1['t_yel']:.3f} | {m1['val_red_recall']:.3f} | {m1['val_yellow_found']:.3f} | {m1['val_macro_f1']:.3f} |")
        for sd, v in ss["M2"]["seeds"].items():
            star = " (shipped)" if int(sd) == ss["M2"]["best_seed"] else ""
            sl.append(f"| {spn} | M2 seed {sd}{star} | num_iterations = {ss['M2']['num_iterations']} | {v['t_red']:.3f} | {v['t_yel']:.3f} | {v['val_red_recall']:.3f} | {v['val_yellow_found']:.3f} | {v['val_macro_f1']:.3f} |")
        tune = ", ".join(f"{k}: {v:.3f}" for k, v in ss["M2"]["tuning_val_macro_f1"].items())
        sl.append(f"| {spn} | best model | {ss['best_model']} | | | | | M2 num_iterations tuning (seed 0, val macro F1): {tune} |")
    T["selection"] = "\n".join(sl)

    # calibration (best model on main test; also all models for comparison)
    cal = ["| model | test ECE (top label) | test ECE (p(RED) vs RED) |", "|---|---:|---:|"]
    m1p = C["M1 argmax"]["test"]["p"]
    e1 = ece(m1p, yt)
    cal.append(f"| M1 | {e1['ece_top']:.3f} | {e1['ece_red']:.3f} |")
    e2 = [ece(p, yt) for p in C["M2 argmax"]["test"]["p"]]
    cal.append(f"| M2 (5 seeds) | {ms([e['ece_top'] for e in e2])} | {ms([e['ece_red'] for e in e2])} |")
    if s["best_model"] == "M2":
        bp, bname = C["M2 argmax"]["test"]["p"][SETFIT_SEEDS["main"].index(ship)], f"M2 seed {ship}"
    else:
        bp, bname = m1p, "M1"
    png = HERE / "reliability_best_model.png"
    eb = reliability_png(bp, yt, f"Reliability on main-split test: {bname} (best model on val), n = {len(yt)}", png)
    cal.append(f"| **{bname} (best)** | {eb['ece_top']:.3f} | {eb['ece_red']:.3f} |")
    cal.append("\n10 equal-width bins. Diagram: `backend/triage/model/reliability_best_model.png`.")
    T["calibration"] = "\n".join(cal)
    res["calibration_best"] = {"model": bname, **eb}

    # ---- unseen-scenario split
    U = build("unseen", sel)
    us = U["_sets"]
    yu = labels_of(us["test"])
    T["unseen_metrics"] = metric_table(U, "test", yu)
    T["unseen_confusion"] = confusion_block(U, "test", yu)
    src_u = np.array([r["origin"] != "source_template" for r in us["test"]])
    T["rules_no_template_unseen"] = metric_table(U, "test", yu, src_u)
    yv = labels_of(us["val"])
    ps = ["| scenario | set | RED rows | " + " | ".join(CONTENDERS) + " |", "|---|---|---:|" + "---:|" * len(CONTENDERS)]
    for part, scs in (("test", AUDIT_SCEN_TEST), ("val", AUDIT_SCEN_VAL)):
        yy = yu if part == "test" else yv
        scen = np.array([r["scenario_id"] for r in us[part]])
        for sc in scs:
            m = (scen == sc) & (yy == R)
            cs = []
            for name in CONTENDERS:
                pr = U[name][part]["pred"]
                pr = pr if isinstance(pr, list) else [pr]
                rec = [float((p[m] == R).mean()) for p in pr]
                k = [int((p[m] == R).sum()) for p in pr]
                cs.append(f"{np.mean(rec):.2f} ± {np.std(rec, ddof=1):.2f}" if len(pr) > 1 else f"{rec[0]:.2f} ({k[0]}/{int(m.sum())})")
            ps.append(f"| {sc} | {part}{' (tuning set)' if part == 'val' else ''} | {int(m.sum())} | " + " | ".join(cs) + " |")
    T["unseen_per_scenario"] = "\n".join(ps) + (
        f"\n\nModels retrained on `splits_unseen_scenario/train`; H1 = max(B1, {U['_best']}). FALL_INJURY and WOUND_OPEN are in the "
        "unseen-scenario **val** split, which chose C, num_iterations and both thresholds, so their numbers are optimistic.")
    res["unseen_best"] = U["_best"]

    # ---- latency
    lat = latency([r["text"] for r in sets["test"]][:200], sel)
    meta = lat.pop()
    ll = ["| model | median ms / message | p95 ms | size on disk | parameters | note |", "|---|---:|---:|---:|---:|---|"]
    for r in lat:
        size = f"{r['size'] / 1e6:.1f} MB" if r["size"] > 1e6 else f"{r['size'] / 1e3:.0f} KB"
        ll.append(f"| {r['model']} | {r['median_ms']:.2f} | {r['p95_ms']:.2f} | {size} | {r['params']:,} | {r['note']} |")
    ll.append(f"\nSingle message at a time on CPU ({meta['cpu'] or 'unknown CPU'}, torch threads {meta['threads']}), "
              f"{meta['n_messages']} test messages after 10 warm-up calls. Size for M1 = MiniLM snapshot + head JSON.")
    T["latency"] = "\n".join(ll)
    res["latency"] = lat

    # ---- raw numbers
    def dump(Cx, k, y):
        return {name: mets(Cx[name], k, y) for name in CONTENDERS}
    res.update({"main_test": dump(C, "test", yt), "challenge": dump(C, "challenge", yc),
                "unseen_test": dump(U, "test", yu), "best_main": best_main})
    (ART / "results.json").write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
    md = ["# Triage classifier results (generated by evaluate.py)\n"]
    for k, v in T.items():
        md += [f"## {k}\n", v, ""]
    (HERE / "results.md").write_text("\n".join(md), encoding="utf-8")
    tpl = HERE / "report_template.md"
    if tpl.exists():
        text = tpl.read_text(encoding="utf-8")
        missing = set(re.findall(r"\{\{(\w+)\}\}", text)) - set(T)
        assert not missing, missing
        text = re.sub(r"\{\{(\w+)\}\}", lambda m: T[m.group(1)], text)
        (TRIAGE / "REPORT.md").write_text(text, encoding="utf-8")
    print("\n\n".join(f"## {k}\n{v}" for k, v in T.items()))


if __name__ == "__main__":
    main()
