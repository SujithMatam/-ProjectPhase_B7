"""Main split: within-scenario cluster split (every scenario in train, val and test).

Input:   splits_unseen_scenario/{train,val,test}.jsonl  (all rows, from build_dataset.py)
Outputs: splits/{train,val,test}.jsonl, SPLIT_REPORT.md, stats.json

Steps
1. Embed every row with all-MiniLM-L6-v2 (normalised, cosine = dot product).
2. Within each scenario, agglomerative clustering with single linkage, cosine distance and
   distance_threshold 0.15. Single linkage stops merging only when every pair of points in
   different clusters is at distance >= 0.15, so no cross-cluster pair inside a scenario has
   cosine > 0.85 (checked explicitly below).
3. Rows from different scenarios with cosine > 0.92 must not be split apart; their clusters are
   joined into one unit (union-find).
4. Units are assigned to train/val/test by a seeded local search that minimises, per scenario and
   per label, the squared gap to a 70/15/15 share, plus a small term keeping tags and origin
   balanced. Hard constraints (large penalties): every scenario has at least one row in each
   split, and every RED-led scenario has at least 6 RED rows in val and in test.
5. Checks: identical normalised sentences across splits, cross-split cosine > 0.92, and the
   within-scenario 0.85 guarantee. Assertions fail the build if any is violated.

  cd backend/triage/data && HF_HUB_OFFLINE=1 ../../.venv/Scripts/python build_split_clustered.py
"""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from build_dataset import EMBED_MODEL, LABELS, NEAR_DUP, SPLITS, TARGET, embed, norm_text

HERE = Path(__file__).resolve().parent
SRC = HERE / "splits_unseen_scenario"
OUT = HERE / "splits"
CLUSTER_SIM = 0.85          # no cross-cluster pair inside a scenario above this
MIN_RED_EVAL = 6            # RED rows per RED-led scenario in val and in test
SEED = 20261111
RESTARTS = 5
TAG_WEIGHT = 0.05
PENALTY = 1000.0
FIELDS = ("id", "text", "label", "scenario_id", "surgery", "tags", "origin",
          "source_template", "old_label", "generator", "split")


def load() -> list[dict]:
    rows = [json.loads(l) for s in SPLITS for l in open(SRC / f"{s}.jsonl", encoding="utf-8")]
    return sorted(rows, key=lambda r: r["id"])


class DSU:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def cluster(rows, emb):
    """Return per-row cluster ids (within scenario) and unit ids (clusters joined across scenarios)."""
    scen = np.array([r["scenario_id"] for r in rows])
    cid = np.empty(len(rows), dtype=object)
    for s in sorted(set(scen)):
        idx = np.where(scen == s)[0]
        lab = AgglomerativeClustering(n_clusters=None, linkage="single", metric="cosine",
                                      distance_threshold=1 - CLUSTER_SIM).fit(emb[idx]).labels_
        for i, l in zip(idx, lab):
            cid[i] = f"{s}#{l}"
    keys = sorted(set(cid))
    kidx = {k: n for n, k in enumerate(keys)}
    dsu = DSU(len(keys))
    sims = emb @ emb.T
    cross = (scen[:, None] != scen[None, :]) & (sims > NEAR_DUP)
    joined = []
    for i, j in zip(*np.where(np.triu(cross, 1))):
        dsu.union(kidx[cid[i]], kidx[cid[j]])
        joined.append((float(sims[i, j]), int(i), int(j)))
    unit = np.array([dsu.find(kidx[c]) for c in cid])
    return cid, unit, joined, sims


def assign(rows, unit):
    """Seeded local search (single-unit moves + same-scenario swaps) with analytic cost deltas."""
    scens = sorted({r["scenario_id"] for r in rows})
    sidx = {s: n for n, s in enumerate(scens)}
    lidx = {l: n for n, l in enumerate(LABELS)}
    feats = sorted({t for r in rows for t in r["tags"]} | {"source_template"})
    fidx = {t: n for n, t in enumerate(feats)}
    S, L, F, P = len(scens), len(LABELS), len(feats), len(SPLITS)
    tgt = [TARGET[s] for s in SPLITS]
    R = lidx["RED"]

    units = sorted(set(unit.tolist()))
    uidx = {u: n for n, u in enumerate(units)}
    U = len(units)
    uc = [defaultdict(lambda: [0] * L) for _ in range(U)]   # unit -> scenario -> label counts
    uf = [Counter() for _ in range(U)]
    for r, u in zip(rows, unit):
        k = uidx[u]
        uc[k][sidx[r["scenario_id"]]][lidx[r["label"]]] += 1
        for t in r["tags"]:
            uf[k][fidx[t]] += 1
        if r["origin"] == "source_template":
            uf[k][fidx["source_template"]] += 1
    uc = [{s: v for s, v in d.items()} for d in uc]
    tot_c = [[0] * L for _ in range(S)]
    tot_f = [0] * F
    for k in range(U):
        for s, v in uc[k].items():
            for l in range(L):
                tot_c[s][l] += v[l]
        for f, c in uf[k].items():
            tot_f[f] += c
    T = [[[tot_c[s][l] * tgt[p] for l in range(L)] for p in range(P)] for s in range(S)]
    TF = [[tot_f[f] * tgt[p] for f in range(F)] for p in range(P)]
    red_led = [max(range(L), key=lambda l: tot_c[s][l]) == R for s in range(S)]

    def pen(C, s):
        c = PENALTY * sum(1 for p in range(P) if sum(C[s][p]) == 0)
        if red_led[s]:
            for p in (1, 2):
                c += PENALTY * max(0, MIN_RED_EVAL - C[s][p][R])
        return c

    def apply(C, Fc, k, a, b):
        for s, v in uc[k].items():
            for l in range(L):
                C[s][a][l] -= v[l]
                C[s][b][l] += v[l]
        for f, c in uf[k].items():
            Fc[a][f] -= c
            Fc[b][f] += c

    def delta(C, Fc, k, a, b):
        d = 0.0
        for s, v in uc[k].items():
            for l in range(L):
                x = v[l]
                if x:
                    d += 2 * x * ((C[s][b][l] - T[s][b][l]) - (C[s][a][l] - T[s][a][l])) + 2 * x * x
        for f, c in uf[k].items():
            d += TAG_WEIGHT * (2 * c * ((Fc[b][f] - TF[b][f]) - (Fc[a][f] - TF[a][f])) + 2 * c * c)
        before = sum(pen(C, s) for s in uc[k])
        apply(C, Fc, k, a, b)
        after = sum(pen(C, s) for s in uc[k])
        apply(C, Fc, k, b, a)
        return d + after - before

    def total(C, Fc):
        c = sum((C[s][p][l] - T[s][p][l]) ** 2 for s in range(S) for p in range(P) for l in range(L))
        c += sum(pen(C, s) for s in range(S))
        c += TAG_WEIGHT * sum((Fc[p][f] - TF[p][f]) ** 2 for p in range(P) for f in range(F))
        return c

    single = defaultdict(list)
    for k in range(U):
        if len(uc[k]) == 1:
            single[next(iter(uc[k]))].append(k)

    rng = random.Random(SEED)
    best_a, best_cost = None, float("inf")
    for _ in range(RESTARTS):
        a = [rng.choices(range(P), weights=tgt)[0] for _ in range(U)]
        C = [[[0] * L for _ in range(P)] for _ in range(S)]
        Fc = [[0] * F for _ in range(P)]
        for k in range(U):
            for s, v in uc[k].items():
                for l in range(L):
                    C[s][a[k]][l] += v[l]
            for f, c in uf[k].items():
                Fc[a[k]][f] += c
        order = list(range(U))
        improved = True
        while improved:
            improved = False
            rng.shuffle(order)
            for k in order:
                old = a[k]
                best_p, best_d = old, -1e-9
                for p in range(P):
                    if p != old:
                        d = delta(C, Fc, k, old, p)
                        if d < best_d:
                            best_p, best_d = p, d
                if best_p != old:
                    apply(C, Fc, k, old, best_p)
                    a[k] = best_p
                    improved = True
            for s in sorted(single):
                ks = single[s]
                for i in range(len(ks)):
                    for j in range(i + 1, len(ks)):
                        k1, k2 = ks[i], ks[j]
                        p1, p2 = a[k1], a[k2]
                        if p1 == p2 or uc[k1][s] == uc[k2][s]:
                            continue
                        d1 = delta(C, Fc, k1, p1, p2)
                        apply(C, Fc, k1, p1, p2)
                        d2 = delta(C, Fc, k2, p2, p1)
                        if d1 + d2 < -1e-9:
                            apply(C, Fc, k2, p2, p1)
                            a[k1], a[k2] = p2, p1
                            improved = True
                        else:
                            apply(C, Fc, k1, p2, p1)
        cost = total(C, Fc)
        if cost < best_cost:
            best_a, best_cost = list(a), cost
    return [SPLITS[best_a[uidx[u]]] for u in unit], best_cost


def main() -> None:
    rows = load()
    emb = embed([r["text"] for r in rows])
    cid, unit, joined, sims = cluster(rows, emb)
    split, cost = assign(rows, unit)
    for r, s in zip(rows, split):
        r["split"] = s

    n = len(rows)
    sp = np.array(split)
    scen = np.array([r["scenario_id"] for r in rows])
    diff = sp[:, None] != sp[None, :]
    same_s = scen[:, None] == scen[None, :]
    eye = np.eye(n, dtype=bool)
    cross_max = float(np.where(diff, sims, -1).max())
    cross_over = int(np.triu(diff & (sims > NEAR_DUP), 1).sum())
    cl = np.array(cid)
    cross_cluster = same_s & (cl[:, None] != cl[None, :])
    within_scen_cross_cluster_max = float(np.where(cross_cluster, sims, -1).max())
    within_scen_cross_split_max = float(np.where(same_s & diff, sims, -1).max())
    norm_split = defaultdict(set)
    for r in rows:
        norm_split[norm_text(r["text"])].add(r["split"])
    exact_cross = sum(len(v) > 1 for v in norm_split.values())
    assert cross_over == 0 and exact_cross == 0 and within_scen_cross_cluster_max <= CLUSTER_SIM + 1e-6

    rep: list[str] = []
    w = rep.append
    w("# Split report: within-scenario cluster split (main)\n")
    w("Generated by `build_split_clustered.py` from the rows in `splits_unseen_scenario/` "
      "(the secondary, unseen-scenario split; see `SPLIT_REPORT_unseen_scenario.md`).\n")
    w("## Method\n")
    w(f"- Embeddings: {EMBED_MODEL}, normalised.")
    w(f"- Within each scenario: agglomerative clustering, single linkage, cosine distance, "
      f"threshold {1 - CLUSTER_SIM:.2f}, so no two rows of the same scenario in different clusters "
      f"have cosine > {CLUSTER_SIM}.")
    w(f"- Rows of different scenarios with cosine > {NEAR_DUP} are kept in the same split "
      f"(their clusters are joined).")
    w(f"- Whole clusters assigned to train/val/test by seeded local search (seed {SEED}, "
      f"{RESTARTS} restarts) against a 70/15/15 share of each label inside each scenario, with a "
      f"weak balance term on tags and origin; each scenario must be in all three splits and each "
      f"RED-led scenario must have >= {MIN_RED_EVAL} RED rows in val and in test. Final cost {cost:.2f}.\n")

    csize = Counter(cid)
    sizes = Counter(csize.values())
    w("## Clusters\n")
    w(f"- rows {n}, clusters {len(csize)}, units after cross-scenario joins {len(set(unit.tolist()))}")
    w("- cluster sizes: " + ", ".join(f"{k} rows x {v}" for k, v in sorted(sizes.items())))
    w(f"- cross-scenario pairs with cosine > {NEAR_DUP} (forced into one split): {len(joined)}")
    for s, i, j in joined:
        w(f"  - {s:.3f} `{rows[i]['id']}` / `{rows[j]['id']}` -> both {rows[i]['split']}: "
          f"\"{rows[i]['text']}\" / \"{rows[j]['text']}\"")
    multi = [c for c, k in csize.items() if k > 1]
    if multi:
        w("- multi-row clusters:")
        for c in sorted(multi):
            members = [r for r, x in zip(rows, cid) if x == c]
            w(f"  - {c.split('#')[0]} ({members[0]['split']}): "
              + " / ".join(f"`{m['id']}` {m['label']} \"{m['text']}\"" for m in members))
    w("")
    w("## Leakage checks\n")
    w(f"- identical normalised sentences in two splits: **{exact_cross}**")
    w(f"- cross-split pairs with cosine > {NEAR_DUP}: **{cross_over}**; highest cross-split cosine: "
      f"**{cross_max:.3f}**")
    w(f"- highest cosine between two rows of the same scenario in different clusters: "
      f"**{within_scen_cross_cluster_max:.3f}** (<= {CLUSTER_SIM}); in different splits: "
      f"{within_scen_cross_split_max:.3f}")
    nn = {}
    tr = sp == "train"
    for s in ("val", "test"):
        m = sp == s
        best = sims[m][:, tr].max(1)
        nn[s] = best
        w(f"- {s}: cosine to the closest train row: median {np.median(best):.3f}, "
          f"p90 {np.quantile(best, 0.9):.3f}, max {best.max():.3f}; rows whose closest train row "
          f"is in the same scenario: {sum(scen[np.where(tr)[0][sims[i][tr].argmax()]] == scen[i] for i in np.where(m)[0])}/{m.sum()}")
    w("")

    w("## Splits\n")
    w("| split | rows | share % | RED | YELLOW | GREEN | RED % | YELLOW % | GREEN % | scenarios |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    stats = {"method": "within-scenario cluster split", "splits": {}, "scenarios": {}, "tags": {},
             "origin": {}}
    for s in SPLITS + ("all",):
        rs = rows if s == "all" else [r for r in rows if r["split"] == s]
        c = Counter(r["label"] for r in rs)
        k = len(rs)
        ns = len({r["scenario_id"] for r in rs})
        w(f"| {s} | {k} | {100 * k / n:.1f} | {c['RED']} | {c['YELLOW']} | {c['GREEN']} | "
          f"{100 * c['RED'] / k:.1f} | {100 * c['YELLOW'] / k:.1f} | {100 * c['GREEN'] / k:.1f} | {ns} |")
        stats["splits"][s] = {"rows": k, **{l: c[l] for l in LABELS}, "scenarios": ns}
    w("")

    by_s = defaultdict(list)
    for r in rows:
        by_s[r["scenario_id"]].append(r)
    lead = {s: Counter(r["label"] for r in rs).most_common(1)[0][0] for s, rs in by_s.items()}
    w("Per scenario (R/Y/G per split):\n")
    w("| scenario_id | lead | rows | train R/Y/G | val R/Y/G | test R/Y/G | train % |")
    w("|---|---|---:|---|---|---|---:|")
    for s in sorted(by_s, key=lambda x: (LABELS.index(lead[x]), x)):
        rs = by_s[s]
        cells = []
        entry = {"lead": lead[s], "rows": len(rs)}
        for p in SPLITS:
            c = Counter(r["label"] for r in rs if r["split"] == p)
            cells.append(f"{c['RED']}/{c['YELLOW']}/{c['GREEN']}")
            entry[p] = {l: c[l] for l in LABELS}
        ntr = sum(r["split"] == "train" for r in rs)
        w(f"| {s} | {lead[s]} | {len(rs)} | " + " | ".join(cells) + f" | {100 * ntr / len(rs):.0f} |")
        stats["scenarios"][s] = entry
    w("")
    red_scen = sorted(s for s in by_s if lead[s] == "RED")
    w(f"RED-led scenarios ({len(red_scen)}): RED rows in val / test (required >= {MIN_RED_EVAL}):\n")
    w("| scenario_id | RED total | val RED | test RED | ok |")
    w("|---|---:|---:|---:|---|")
    ok_all = True
    for s in red_scen:
        v = stats["scenarios"][s]["val"]["RED"]
        t = stats["scenarios"][s]["test"]["RED"]
        ok = v >= MIN_RED_EVAL and t >= MIN_RED_EVAL
        ok_all &= ok
        w(f"| {s} | {sum(r['label'] == 'RED' for r in by_s[s])} | {v} | {t} | {'yes' if ok else 'NO'} |")
    assert ok_all
    assert all(len({r["split"] for r in rs}) == 3 for rs in by_s.values())
    w("")

    tagc = Counter(t for r in rows for t in r["tags"])
    w("| tag | train | val | test | all |")
    w("|---|---:|---:|---:|---:|")
    for t, k in tagc.most_common():
        c = Counter(r["split"] for r in rows if t in r["tags"])
        w(f"| {t} | {c['train']} | {c['val']} | {c['test']} | {k} |")
        stats["tags"][t] = {s: c[s] for s in SPLITS}
    oc = Counter((r["origin"], r["split"]) for r in rows)
    for o in ("source_template", "generated"):
        w(f"| origin={o} | {oc[(o, 'train')]} | {oc[(o, 'val')]} | {oc[(o, 'test')]} | "
          f"{sum(oc[(o, s)] for s in SPLITS)} |")
        stats["origin"][o] = {s: oc[(o, s)] for s in SPLITS}
    surg = Counter((r["surgery"], r["split"]) for r in rows)
    w(f"\nSurgery (train/val/test): TKA {surg[('TKA', 'train')]}/{surg[('TKA', 'val')]}/{surg[('TKA', 'test')]}, "
      f"THA {surg[('THA', 'train')]}/{surg[('THA', 'val')]}/{surg[('THA', 'test')]}.")
    stats["near_duplicates"] = {
        "threshold": NEAR_DUP, "cross_pairs": cross_over, "max_cross_cosine": round(cross_max, 4),
        "cluster_threshold": CLUSTER_SIM, "max_within_scenario_cross_cluster": round(within_scen_cross_cluster_max, 4),
        "clusters": len(csize), "cross_scenario_joins": len(joined),
        "nearest_train_median": {s: round(float(np.median(v)), 4) for s, v in nn.items()},
    }
    stats["exact_cross_split"] = exact_cross

    OUT.mkdir(exist_ok=True)
    for s in SPLITS:
        with open(OUT / f"{s}.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                if r["split"] == s:
                    f.write(json.dumps({k: r[k] for k in FIELDS}, ensure_ascii=False) + "\n")
    (HERE / "SPLIT_REPORT.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
    (HERE / "stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print("\n".join(rep))


if __name__ == "__main__":
    main()
