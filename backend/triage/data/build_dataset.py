"""Build the triage dataset and its group split.

Inputs (all in this folder):
  source_relabelled.jsonl   the 63 original sentences, re-labelled (relabel_source.py)
  authored/*.tsv            synthetic messages, one file per scenario

Outputs:
  splits/{train,val,test}.jsonl
  SPLIT_REPORT.md, stats.json

Steps: validate rows -> drop exact duplicates -> group split by scenario_id (70/15/15,
label mix balanced) -> MiniLM near-duplicate check across splits (cosine > 0.92), removing
the train-side row of any crossing pair -> re-check -> write.

Needs sentence-transformers with all-MiniLM-L6-v2 cached; run with the backend venv:
  HF_HUB_OFFLINE=1 backend/.venv/Scripts/python backend/triage/data/build_dataset.py
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
AUTHORED = HERE / "authored"
OUT = HERE / "splits"
LABELS = ("RED", "YELLOW", "GREEN")
RANK = {"GREEN": 0, "YELLOW": 1, "RED": 2}
SPLITS = ("train", "val", "test")
TARGET = {"train": 0.70, "val": 0.15, "test": 0.15}
NEAR_DUP = 0.92
GENERATOR = "claude-opus-5-5"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TAGS = {"hard_pos", "hard_neg", "negation", "temp_in_text", "indian_english", "typo",
        "indirect", "multi_symptom", "question", "carer"}


def norm_text(t: str) -> str:
    t = t.lower().replace("’", "'")
    t = re.sub(r"[^a-z0-9.' ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip(" .")


# ---------------------------------------------------------------- temperatures
TEMP_CTX = re.compile(r"(temp|temprature|temperature|fever|thermometer|reading|showing|showed|"
                      r"shows|bukhar|pyrexia|feverish|running)", re.I)
NUM = re.compile(r"(?<![\d.])(\d{2,3}(?:\.\d{1,2})?)\s*(°|º|deg(?:rees?)?)?\s*([cf])?(?![a-z])", re.I)


def temperatures_c(text: str) -> list[float]:
    """Temperatures (in C) stated in the text. Heuristic, for consistency checks only."""
    out = []
    for m in NUM.finditer(text):
        v = float(m.group(1))
        unit = (m.group(3) or "").lower()
        ctx = text[max(0, m.start() - 30):m.start()]
        if not unit and not m.group(2) and not TEMP_CTX.search(ctx):
            continue
        if unit == "f" or (not unit and 95 <= v <= 108):
            c = (v - 32) * 5 / 9
        elif unit == "c" or (not unit and 34 <= v <= 43):
            c = v
        else:
            continue
        if 34 <= c <= 43:
            out.append(round(c, 2))
    return out


def temp_floor(cs: list[float]) -> str:
    if not cs:
        return "GREEN"
    mx = max(cs)
    return "RED" if mx >= 38.5 else "YELLOW" if mx >= 37.8 else "GREEN"


# ---------------------------------------------------------------- loading
def load_rows() -> tuple[list[dict], list[str]]:
    rows, problems = [], []
    with open(HERE / "source_relabelled.jsonl", encoding="utf-8") as f:
        per = Counter()
        for line in f:
            r = json.loads(line)
            per[r["scenario_id"]] += 1
            rows.append({
                "id": f"SRC-{r['scenario_id']}-{per[r['scenario_id']]:02d}",
                "text": r["text"], "label": r["label"], "scenario_id": r["scenario_id"],
                "surgery": r["surgery"], "tags": [], "origin": "source_template",
                "source_template": r["source_template"], "old_label": r["old_label"],
                "generator": r["generator"],
            })
    for path in sorted(AUTHORED.glob("*.tsv")):
        scen = path.stem
        n = 0
        for ln, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = line.split("\t")
            where = f"{path.name}:{ln}"
            if len(parts) != 4:
                problems.append(f"{where}: expected 4 tab-separated fields, got {len(parts)}")
                continue
            label, surgery, tags, text = (p.strip() for p in parts)
            if label not in LABELS:
                problems.append(f"{where}: bad label {label!r}")
                continue
            if surgery not in ("TKA", "THA", "ANY"):
                problems.append(f"{where}: bad surgery {surgery!r}")
                continue
            tag_list = [] if tags in ("-", "") else [t.strip() for t in tags.split(",") if t.strip()]
            bad = [t for t in tag_list if t not in TAGS]
            if bad:
                problems.append(f"{where}: unknown tags {bad} (kept)")
            n += 1
            rows.append({
                "id": f"{scen}-{n:03d}", "text": text, "label": label, "scenario_id": scen,
                "surgery": surgery, "tags": tag_list, "origin": "generated",
                "source_template": None, "old_label": None, "generator": GENERATOR,
            })
    for r in rows:
        if r["surgery"] == "ANY":
            r["surgery"] = random.Random("surgery:" + r["text"]).choice(["TKA", "THA"])
    return rows, problems


# ---------------------------------------------------------------- group split
def split_cost(assign: dict[str, str], scen_counts: dict[str, Counter], overall: dict[str, float],
               total: int) -> float:
    agg = {s: Counter() for s in SPLITS}
    for scen, sp in assign.items():
        agg[sp].update(scen_counts[scen])
    cost = 0.0
    for sp in SPLITS:
        n = sum(agg[sp].values())
        if n == 0:
            return 1e9
        cost += 4 * (n / total - TARGET[sp]) ** 2
        for lab in LABELS:
            cost += (agg[sp][lab] / n - overall[lab]) ** 2
    return cost


def group_split(rows: list[dict], seed: int = 13) -> dict[str, str]:
    scen_counts: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        scen_counts[r["scenario_id"]][r["label"]] += 1
    total = len(rows)
    lab_tot = Counter(r["label"] for r in rows)
    overall = {l: lab_tot[l] / total for l in LABELS}
    scens = sorted(scen_counts)
    lead = {s: scen_counts[s].most_common(1)[0][0] for s in scens}
    rng = random.Random(seed)

    def full_cost(a):
        c = split_cost(a, scen_counts, overall, total)
        # val and test must each hold at least one RED-led and one non-RED-led scenario
        for sp in ("val", "test"):
            leads = {lead[s] for s, x in a.items() if x == sp}
            if "RED" not in leads or len(leads) < 2:
                c += 1.0
        return c

    best, best_c = None, float("inf")
    for _ in range(300):
        a = {s: rng.choices(SPLITS, weights=[0.7, 0.15, 0.15])[0] for s in scens}
        c = full_cost(a)
        improved = True
        while improved:
            improved = False
            for s in scens:
                for sp in SPLITS:
                    if sp == a[s]:
                        continue
                    old = a[s]
                    a[s] = sp
                    nc = full_cost(a)
                    if nc < c - 1e-12:
                        c, improved = nc, True
                    else:
                        a[s] = old
            for i, s1 in enumerate(scens):
                for s2 in scens[i + 1:]:
                    if a[s1] == a[s2]:
                        continue
                    a[s1], a[s2] = a[s2], a[s1]
                    nc = full_cost(a)
                    if nc < c - 1e-12:
                        c, improved = nc, True
                    else:
                        a[s1], a[s2] = a[s2], a[s1]
        if c < best_c:
            best, best_c = dict(a), c
    return best


# ---------------------------------------------------------------- near duplicates
def embed(texts: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBED_MODEL)
    return model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)


def cross_pairs(rows, emb, thr=NEAR_DUP):
    sims = emb @ emb.T
    sp = np.array([r["split"] for r in rows])
    mask = (sp[:, None] != sp[None, :]) & (sims > thr)
    iu = np.triu_indices(len(rows), 1)
    sel = mask[iu]
    return sorted(((float(sims[i, j]), int(i), int(j)) for i, j in zip(iu[0][sel], iu[1][sel])),
                  reverse=True)


def main() -> None:
    rows, problems = load_rows()
    hard = [p for p in problems if "(kept)" not in p]
    if hard:
        print("\n".join(hard))
        sys.exit("fix the authored files first")

    rep: list[str] = []
    w = rep.append
    w("# Split report\n")
    w("Generated by `build_dataset.py`.\n")
    if problems:
        w("Format warnings:\n")
        for p in problems:
            w(f"- {p}")
        w("")

    # word counts
    wc = [len(r["text"].split()) for r in rows]
    out_of_range = [r for r in rows if not 3 <= len(r["text"].split()) <= 40]

    # exact duplicates
    seen: dict[str, dict] = {}
    kept, dups, dup_conflicts = [], [], []
    for r in rows:
        k = norm_text(r["text"])
        if k in seen:
            dups.append((r, seen[k]))
            if r["label"] != seen[k]["label"]:
                dup_conflicts.append((r, seen[k]))
            continue
        seen[k] = r
        kept.append(r)
    rows = kept

    # temperature consistency
    temp_rows, under, over = 0, [], []
    for r in rows:
        cs = temperatures_c(r["text"])
        if cs:
            temp_rows += 1
            fl = temp_floor(cs)
            if RANK[r["label"]] < RANK[fl]:
                under.append((r, cs))

    w("## Input\n")
    w(f"- rows read: {len(rows) + len(dups)} (source_template {sum(r['origin']=='source_template' for r in rows) + sum(d[0]['origin']=='source_template' for d in dups)})")
    w(f"- exact duplicates after normalising case/punctuation, dropped: {len(dups)}"
      + (f" ({len(dup_conflicts)} with conflicting labels)" if dup_conflicts else ""))
    for r, first in dups:
        w(f"  - `{r['id']}` duplicates `{first['id']}`: \"{r['text']}\"")
    w(f"- words per message: min {min(wc)}, median {int(np.median(wc))}, max {max(wc)}; "
      f"outside 3-40 words: {len(out_of_range)}")
    for r in out_of_range:
        w(f"  - `{r['id']}` ({len(r['text'].split())} words) {r['text']}")
    w(f"- rows with a temperature in the text: {temp_rows}; labelled below the temperature "
      f"threshold: {len(under)}")
    for r, cs in under:
        w(f"  - `{r['id']}` {r['label']} temps {cs}: \"{r['text']}\"")
    w("")

    # split
    assign = group_split(rows)
    for r in rows:
        r["split"] = assign[r["scenario_id"]]

    emb = embed([r["text"] for r in rows])
    pairs = cross_pairs(rows, emb)
    w("## Near-duplicate check (MiniLM all-MiniLM-L6-v2, cosine > 0.92)\n")
    w(f"Cross-split pairs before resolution: {len(pairs)}")
    drop = set()
    for s, i, j in pairs:
        if i in drop or j in drop:
            continue
        a, b = rows[i], rows[j]
        victim = i if a["split"] == "train" else j if b["split"] == "train" else (i if a["split"] == "val" else j)
        drop.add(victim)
        w(f"- {s:.3f} `{a['id']}` ({a['split']}) / `{b['id']}` ({b['split']}): dropped `{rows[victim]['id']}`"
          f" - \"{a['text']}\" / \"{b['text']}\"")
    keep_idx = [k for k in range(len(rows)) if k not in drop]
    rows = [rows[k] for k in keep_idx]
    emb = emb[keep_idx]
    after = cross_pairs(rows, emb)
    sims = emb @ emb.T
    sp = np.array([r["split"] for r in rows])
    cross_max = float(np.where(sp[:, None] != sp[None, :], sims, -1).max())
    exact_cross = len({norm_text(r["text"]) for r in rows if r["split"] == "train"}
                      & {norm_text(r["text"]) for r in rows if r["split"] != "train"})
    w(f"\nAfter resolution: cross-split pairs with cosine > {NEAR_DUP}: **{len(after)}**; "
      f"highest cross-split cosine: **{cross_max:.3f}**; identical normalised sentences across "
      f"splits: **{exact_cross}**.")
    scen_split = defaultdict(set)
    for r in rows:
        scen_split[r["scenario_id"]].add(r["split"])
    w(f"Scenarios appearing in more than one split: {sum(len(v) > 1 for v in scen_split.values())}.\n")
    assert not after and exact_cross == 0 and all(len(v) == 1 for v in scen_split.values())

    # within-split near-dups (informational)
    within = int(((sims > NEAR_DUP) & (sp[:, None] == sp[None, :])).sum() - len(rows)) // 2
    w(f"Within-split pairs above {NEAR_DUP} (allowed; same scenario paraphrases): {within}.\n")

    # stats
    w("## Splits\n")
    w("| split | rows | RED | YELLOW | GREEN | RED % | YELLOW % | GREEN % | scenarios |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    stats = {"splits": {}, "scenarios": {}, "tags": {}, "origin": {}}
    for s in SPLITS + ("all",):
        rs = rows if s == "all" else [r for r in rows if r["split"] == s]
        c = Counter(r["label"] for r in rs)
        n = len(rs)
        ns = len({r["scenario_id"] for r in rs})
        w(f"| {s} | {n} | {c['RED']} | {c['YELLOW']} | {c['GREEN']} | {100*c['RED']/n:.1f} | "
          f"{100*c['YELLOW']/n:.1f} | {100*c['GREEN']/n:.1f} | {ns} |")
        stats["splits"][s] = {"rows": n, **{l: c[l] for l in LABELS}, "scenarios": ns}
    w("")
    w("| scenario_id | split | rows | RED | YELLOW | GREEN | source_template | generated |")
    w("|---|---|---:|---:|---:|---:|---:|---:|")
    by_s = defaultdict(list)
    for r in rows:
        by_s[r["scenario_id"]].append(r)
    for scen in sorted(by_s, key=lambda x: (SPLITS.index(assign[x]), x)):
        rs = by_s[scen]
        c = Counter(r["label"] for r in rs)
        o = Counter(r["origin"] for r in rs)
        w(f"| {scen} | {assign[scen]} | {len(rs)} | {c['RED']} | {c['YELLOW']} | {c['GREEN']} | "
          f"{o['source_template']} | {o['generated']} |")
        stats["scenarios"][scen] = {"split": assign[scen], "rows": len(rs), **{l: c[l] for l in LABELS},
                                    "source_template": o["source_template"], "generated": o["generated"]}
    w("")
    tagc = Counter(t for r in rows for t in r["tags"])
    w("| tag | rows | RED | YELLOW | GREEN |")
    w("|---|---:|---:|---:|---:|")
    for t, n in tagc.most_common():
        c = Counter(r["label"] for r in rows if t in r["tags"])
        w(f"| {t} | {n} | {c['RED']} | {c['YELLOW']} | {c['GREEN']} |")
        stats["tags"][t] = {"rows": n, **{l: c[l] for l in LABELS}}
    w("")
    oc = Counter((r["origin"], r["split"]) for r in rows)
    w("| origin | train | val | test |")
    w("|---|---:|---:|---:|")
    for o in ("source_template", "generated"):
        w(f"| {o} | {oc[(o,'train')]} | {oc[(o,'val')]} | {oc[(o,'test')]} |")
        stats["origin"][o] = {s: oc[(o, s)] for s in SPLITS}
    surg = Counter(r["surgery"] for r in rows)
    w(f"\nSurgery: TKA {surg['TKA']}, THA {surg['THA']}.")
    stats["surgery"] = dict(surg)
    stats["near_duplicates"] = {"threshold": NEAR_DUP, "cross_pairs_before": len(pairs),
                                "dropped": len(drop), "cross_pairs_after": len(after),
                                "max_cross_cosine": round(cross_max, 4)}
    stats["exact_duplicates_dropped"] = len(dups)

    OUT.mkdir(exist_ok=True)
    fields = ("id", "text", "label", "scenario_id", "surgery", "tags", "origin",
              "source_template", "old_label", "generator", "split")
    for s in SPLITS:
        with open(OUT / f"{s}.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for r in sorted((r for r in rows if r["split"] == s), key=lambda r: r["id"]):
                f.write(json.dumps({k: r[k] for k in fields}, ensure_ascii=False) + "\n")
    (HERE / "SPLIT_REPORT.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
    (HERE / "stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print("\n".join(rep))


if __name__ == "__main__":
    main()
