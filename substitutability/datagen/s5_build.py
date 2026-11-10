"""Step 5 — dedupe, balance, split by food, and check the plan's gates.
Usage: s5_build.py [--target 4000]
Reads work/s6_{pilot,main}_pairs.json if present (else s3_*), writes ../data_synth/*.jsonl and prints a gate report.
Labels here are PROVISIONAL (intended labels, optionally cross-checked by the Haiku reviewer). The user runs the
production judge later (step 4) and overwrites `label` with `judge_label`.
"""
import collections as C
import json
import random
import sys

from common import HERE, MODEL, WORK, canon_key, jaccard, norm

OUT = HERE.parent / "data_synth"
BINS = 10
LEVEL_SHARE = {"easy": 0.30, "medium": 0.30, "hard": 0.30, "edge": 0.10}
SPLIT_FRAC = {"fewshot": 0.01, "fit": 0.35, "router": 0.25, "test": 0.39}
USDA_MAX_USES = 3
GOLD = 150
SEED = 11


def load():
    rows = []
    for name in ("pilot", "main"):
        for pref in ("s6", "s3"):
            p = WORK / f"{pref}_{name}_pairs.json"
            if p.exists():
                for r in json.loads(p.read_text()):
                    r["batch"] = name
                    rows.append(r)
                break
    return rows


def overlap_match(rows, frac, rng):
    """Inside each token-overlap (Jaccard) bin keep all of the minority class and a fraction `frac` of the surplus of the
    majority class. frac=0 -> overlap carries no label information; frac=1 -> keep everything."""
    bins = C.defaultdict(lambda: {0: [], 1: []})
    for r in rows:
        bins[min(BINS - 1, int(jaccard(r["ingredient"], r["usda_match"]) * BINS))][r["intended"]].append(r)
    out = []
    for d in bins.values():
        for lab in (0, 1):
            rng.shuffle(d[lab])
        m = min(len(d[0]), len(d[1]))
        for lab in (0, 1):
            out += d[lab][: m + int(frac * (len(d[lab]) - m))]
    return out


def main(target, match=None):
    global OUT
    rng = random.Random(SEED)
    rows = [r for r in load() if r.get("snapped")]
    n0 = len(rows)
    log = {"loaded_snapped": n0}

    # 1. quality filter: a disputed pair in the unambiguous levels is probably mislabeled -> drop
    keep = []
    for r in rows:
        if r.get("disputed") == 1 and r["level"] in ("easy", "medium"):
            log["dropped_disputed_easy_medium"] = log.get("dropped_disputed_easy_medium", 0) + 1
            continue
        keep.append(r)
    rows = keep

    # 2. dedupe on the canonical (ingredient, usda) key; cap USDA string reuse
    seen, uses, out = set(), C.Counter(), []
    rng.shuffle(rows)
    for r in rows:
        k = canon_key(r["ingredient"], r["usda_match"])
        if k in seen:
            log["dropped_duplicate"] = log.get("dropped_duplicate", 0) + 1
            continue
        if uses[norm(r["usda_match"])] >= USDA_MAX_USES:
            log["dropped_usda_reuse"] = log.get("dropped_usda_reuse", 0) + 1
            continue
        seen.add(k)
        uses[norm(r["usda_match"])] += 1
        out.append(r)
    rows = out

    # 3. balance 50/50 inside every level, levels toward 30/30/30/10
    pool = C.defaultdict(lambda: {0: [], 1: []})
    for r in rows:
        pool[r["level"]][r["intended"]].append(r)
    sel, shortfall = [], {}
    for lvl, share in LEVEL_SHARE.items():
        want = int(round(target * share / 2))
        n_avail = min(len(pool[lvl][0]), len(pool[lvl][1]))
        take = min(want, n_avail)
        shortfall[lvl] = {"wanted_per_class": want, "available_min_class": n_avail}
        for lab in (0, 1):
            cand = sorted(pool[lvl][lab], key=lambda r: (r.get("disputed") == 1, rng.random()))
            sel += cand[:take]
    rows = sel
    log["after_balance"] = len(rows)
    if match is not None:
        rows = overlap_match(rows, match, rng)
        log["after_overlap_match(frac=%s)" % match] = len(rows)

    # 4. split BY FOOD (never split a food across splits), approx stratified by level
    foods = sorted({r["food"] for r in rows})
    rng.shuffle(foods)
    cnt = C.Counter(r["food"] for r in rows)
    total = len(rows)
    quota = {s: SPLIT_FRAC[s] * total for s in SPLIT_FRAC}
    got = {s: 0 for s in SPLIT_FRAC}
    food_split = {}
    for f in sorted(foods, key=lambda f: -cnt[f]):
        s = max(quota, key=lambda s: quota[s] - got[s])
        food_split[f] = s
        got[s] += cnt[f]
    # 5. build records
    recs = []
    for i, r in enumerate(rows):
        recs.append({
            "id": f"sub-{i:05d}", "ingredient": r["ingredient_q"], "usda_match": r["usda_match"],
            "label": r["intended"], "label_status": "intended_unjudged", "judge_label": None,
            "review_label": r.get("review"), "review_disputed": r.get("disputed"),
            "core_food": r["food"], "core_food_id": f"{r['group']}:{r['food']}", "family": r["group"],
            "cuisine": r["cuisine"], "tier": r["level"], "relation_code": r["type_used"],
            "relation_requested": r["type_requested"], "decisive_attribute": r["decisive"],
            "jaccard": round(jaccard(r["ingredient"], r["usda_match"]), 3),
            "boundary_flag": bool(r["level"] == "edge" or r.get("disputed") == 1),
            "usda_llm": r["usda_llm"], "snap_exact": r["snap_exact"], "snap_score": r["snap_score"],
            "fdc_id": r["fdc_id"], "fdc_source": r.get("fdc_source"), "synthetic_usda": False,
            "variant_of": None, "perturbation": None, "split": food_split[r["food"]],
            "generator_model": MODEL, "source_batch": r["batch"]})
    # gold subset: stratified by tier, taken from test
    test = [x for x in recs if x["split"] == "test"]
    by_t = C.defaultdict(list)
    for x in test:
        by_t[x["tier"]].append(x)
    for x in recs:
        x["gold_for_human_label"] = False
    for t, lst in by_t.items():
        rng.shuffle(lst)
        for x in lst[: int(round(GOLD * len(lst) / max(1, len(test))))]:
            x["gold_for_human_label"] = True

    OUT.mkdir(exist_ok=True)
    for s in list(SPLIT_FRAC) + ["all"]:
        with open(OUT / f"{s}.jsonl", "w", encoding="utf-8") as f:
            for x in recs:
                if s == "all" or x["split"] == s:
                    f.write(json.dumps(x, ensure_ascii=False) + "\n")
    report(recs, log, shortfall, target)


def report(recs, log, shortfall, target):
    from sklearn.metrics import roc_auc_score
    n = len(recs)
    y = [r["label"] for r in recs]
    print("\n=== BUILD LOG ===", json.dumps(log))
    print("shortfalls (per class per level):", json.dumps(shortfall))
    print(f"\n=== GATES (rows: {n}; target {target}) ===")
    keys = {canon_key(r["ingredient"], r["usda_match"]) for r in recs}
    print(f"duplicate canonical pairs      : {n - len(keys)}  (target 0)")
    print(f"overall positive rate          : {sum(y)/n:.1%}  (target 50% +/- 3)")
    for t in LEVEL_SHARE:
        lv = [r for r in recs if r["tier"] == t]
        if lv:
            pr = sum(r["label"] for r in lv) / len(lv)
            print(f"  level {t:6s}: n={len(lv):4d} ({len(lv)/n:.0%}, target {LEVEL_SHARE[t]:.0%}) positive {pr:.1%}")
    auc = roc_auc_score(y, [r["jaccard"] for r in recs])
    print(f"overlap-only AUC (all)         : {auc:.3f}  (target <= 0.65; real data 0.78)")
    hard = [r for r in recs if r["tier"] == "hard"]
    if hard and len({r['label'] for r in hard}) == 2:
        print(f"overlap-only AUC (hard level)  : {roc_auc_score([r['label'] for r in hard], [r['jaccard'] for r in hard]):.3f}  (target <= 0.40)")
    print(f"USDA strings not found in FDC  : 0 (rejects dropped)   |  USDA reuse cap {USDA_MAX_USES}")
    nw = sum(1 for r in recs if r["cuisine"] == "non-western")
    print(f"non-western share              : {nw/n:.0%}  (target >= 25%)")
    print(f"unique core foods              : {len({r['core_food'] for r in recs})}; max pairs/food {max(C.Counter(r['core_food'] for r in recs).values())} (cap 4)")
    print("split sizes                    :", dict(C.Counter(r["split"] for r in recs)))
    sf = {}
    for s in ("fewshot", "fit", "router", "test"):
        rs = [r for r in recs if r["split"] == s]
        if rs:
            sf[s] = f"pos {sum(r['label'] for r in rs)/len(rs):.0%}"
    print("positive rate per split        :", sf)
    leak = {r["core_food"] for r in recs if r["split"] == "test"} & {r["core_food"] for r in recs if r["split"] != "test"}
    print(f"foods shared between test and other splits: {len(leak)} (must be 0)")
    test = [r for r in recs if r["split"] == "test"]
    tc = C.Counter(r["relation_code"] for r in test)
    low = {k: v for k, v in tc.items() if v < 15}
    print("relation types in test         :", dict(sorted(tc.items())), "| below 15:", low or "none")
    print("review disputed rows kept      :", sum(1 for r in recs if r["review_disputed"] == 1))
    print(f"gold subset to hand-label      : {sum(r['gold_for_human_label'] for r in recs)}")
    print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    t = 4000
    if "--target" in sys.argv:
        t = int(sys.argv[sys.argv.index("--target") + 1])
    m = float(sys.argv[sys.argv.index("--match") + 1]) if "--match" in sys.argv else None
    if "--out" in sys.argv:
        OUT = HERE.parent / sys.argv[sys.argv.index("--out") + 1]
    main(t, m)
