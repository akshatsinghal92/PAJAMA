"""Step 10 — final PRE-JUDGE build -> ../data_synth_v2/  (feedback points 1-4).
Everything here is label-independent except stratification of the split; balancing/overlap-matching happen AFTER the judge.
Usage: s10_prejudge.py
"""
import collections as C
import json
import math
import random
import re
import sys

from blocklist import core_of
from common import HERE, MODEL, WORK, canon_key, jaccard, norm, singular, strip_qty

OUT = HERE.parent / "data_synth_v2"
SEED = 29
rng = random.Random(SEED)
POL = lambda t: 1 if (t[0] == "G" or t == "E1") else 0
TIER = {**{t: "easy" for t in ("G1", "G2", "G3", "B1", "B2", "B3")},
        **{t: "medium" for t in ("G4", "G5", "G8", "G9", "B5", "B6", "B7")},
        **{t: "hard" for t in ("G6", "G7", "B4", "B8", "B9", "B10")},
        **{t: "edge" for t in ("E1", "E2", "B11")}}
RETAG_TYPES = {"B8", "B4", "B10", "E2"}
SPLIT_FRAC = {"fewshot": 0.01, "fit": 0.35, "router": 0.25, "test": 0.39}
NOTE_RATE = 0.03          # production has parenthetical notes in ~1% of lines; keep a few, SAME rate in both classes
PAREN = re.compile(r"\s*\((?:optional|for garnish|for serving|to taste|divided|for frying|optional garnish|plus more[^)]*)\)", re.I)
TAIL = re.compile(r",\s*(?:optional|for garnish|for serving|to taste)\s*$", re.I)
CUE_WORDS = re.compile(r",?\s*\b(room temperature|chilled|refrigerated|sifted|at room temp)\b", re.I)
NOTE_POOL = ["(optional)", "(optional)", "(for garnish)", "(for serving)", "(divided)"]


# ───────────────────────── quantities ─────────────────────────
SPIKES = [5, 5, 10, 10, 15, 20, 25, 30, 30, 50, 75, 100, 100, 150, 200, 200, 250, 300, 400, 500]


def qrange(ing: str, usda: str):
    t = " " + norm(ing) + " " + norm(usda) + " "
    has = lambda *w: any(" " + x + " " in t or " " + x + "s " in t for x in w)
    if has("aspartame", "sucralose", "stevia", "saccharin", "splenda", "sweetener", "sweeteners"): return (1, 8)
    if has("salt", "pepper", "spice", "spices", "seasoning", "extract", "yeast", "gelatin", "agar", "cumin", "paprika", "cinnamon",
           "nutmeg", "oregano", "thyme", "basil", "cardamom", "turmeric", "saffron", "clove", "cloves", "vanilla", "baking powder",
           "baking soda", "bouillon", "curry", "masala", "garlic powder", "onion powder", "chili powder", "coriander", "fennel"): return (1, 15)
    if has("oil", "shortening", "lard", "ghee", "margarine", "butter", "tallow"): return (5, 120)
    if has("syrup", "honey", "molasses", "jam", "jelly"): return (15, 300)
    if has("sauce", "paste", "dressing", "vinegar", "mustard", "ketchup", "mayonnaise", "mayo", "salsa", "pesto", "relish", "chutney", "dip"): return (10, 250)
    if has("broth", "stock", "milk", "juice", "wine", "water", "cream", "yogurt", "kefir", "soymilk", "beer", "cider", "vermouth"): return (60, 1000)
    if has("almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut", "peanut", "seed", "seeds", "raisin", "currant", "cranberries", "nut", "nuts"): return (10, 150)
    if has("flour", "rice", "quinoa", "oat", "oats", "pasta", "noodle", "noodles", "couscous", "bulgur", "barley", "cornmeal", "grits", "lentil", "lentils", "bean", "beans", "chickpea", "chickpeas"): return (30, 400)
    if has("beef", "pork", "lamb", "chicken", "turkey", "fish", "salmon", "tuna", "shrimp", "steak", "sausage", "bacon", "ham", "duck", "veal", "cod", "crab", "lobster", "clam", "mussel"): return (100, 600)
    return (30, 500)


def quantity(ing, usda):
    lo, hi = qrange(ing, usda)
    sp = [s for s in SPIKES if lo <= s <= hi]
    if sp and rng.random() < 0.6:
        return rng.choice(sp)
    q = math.exp(rng.uniform(math.log(lo), math.log(max(lo + 1, hi))))
    return max(1, int(round(q))) if q < 20 else int(round(q / 5) * 5)


# ───────────────────────── groups (synonym-merged) ─────────────────────────
def build_groups(rows):
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    def ctoks(s):
        return frozenset(singular(t) for t in norm(core_of(s)).split())

    for r in rows:
        r["_core"] = ctoks(r["ingredient"])
        union("F:" + r["food"], "I:" + "_".join(sorted(r["_core"])))
    by_usda = C.defaultdict(set)
    for r in rows:
        by_usda[norm(r["usda_match"])].add(r["_core"])
    for cores in by_usda.values():
        cores = [c for c in cores if c]
        for i in range(len(cores)):
            for j in range(i + 1, len(cores)):
                a, b = cores[i], cores[j]
                if len(a & b) / len(a | b) >= 0.5:
                    union("I:" + "_".join(sorted(a)), "I:" + "_".join(sorted(b)))
    for r in rows:
        r["group_id"] = find("F:" + r["food"])
        del r["_core"]


def assign_splits(rows):
    groups = C.defaultdict(list)
    for r in rows:
        groups[r["group_id"]].append(r)
    cells = C.Counter((r["tier"], r["label"]) for r in rows)
    target = {s: {c: SPLIT_FRAC[s] * n for c, n in cells.items()} for s in SPLIT_FRAC}
    have = {s: C.Counter() for s in SPLIT_FRAC}
    order = sorted(groups, key=lambda g: (-len(groups[g]), rng.random()))
    for g in order:
        add = C.Counter((r["tier"], r["label"]) for r in groups[g])
        best = max(SPLIT_FRAC, key=lambda s: sum((target[s][c] - have[s][c]) * n / max(1.0, target[s][c]) for c, n in add.items()))
        have[best].update(add)
        for r in groups[g]:
            r["split"] = best


# ───────────────────────── main ─────────────────────────
def main():
    pool = json.loads((WORK / "pool_audited.json").read_text())
    log = C.OrderedDict()
    log["pool in"] = len(pool)

    # 1. realism (audit pass)
    pool = [r for r in pool if r.get("audit_realistic") is not False]
    log["after realism filter"] = len(pool)

    # 2. type re-tag from the blind audit; polarity conflicts are flagged, never silently flipped
    retag = conflict = 0
    for r in pool:
        r["type_claimed"] = r["type_used"]
        bt = r.get("audit_type")
        r["audit_polarity_conflict"] = bool(bt and POL(bt) != r["intended"])
        conflict += r["audit_polarity_conflict"]
        # the blind 21-way classifier is noisy (41% agreement even on rows whose type is known by construction), so only the
        # types the independent audit found to be poor fits are re-tagged, and only when the label polarity is consistent
        if bt and bt != r["type_used"] and r["type_used"] in RETAG_TYPES and POL(bt) == r["intended"]:
            r["type_used"] = bt
            retag += 1
    log["types re-tagged by blind audit"] = retag
    log["rows where blind audit disagrees with the label's polarity (flagged)"] = conflict

    # 3. surface-cue equalisation
    notes_removed = cues_removed = notes_added = 0
    pos = [r for r in pool if r["intended"] == 1]
    neg = [r for r in pool if r["intended"] == 0]
    for r in pool:
        if CUE_WORDS.search(r["ingredient"]) and r["intended"] == 1 and rng.random() < 0.85:
            r["ingredient"] = CUE_WORDS.sub("", r["ingredient"]).strip(" ,")
            cues_removed += 1
    for cls_rows in (pos, neg):
        withnote = [r for r in cls_rows if PAREN.search(r["ingredient"]) or TAIL.search(r["ingredient"])]
        keep_n = int(NOTE_RATE * len(cls_rows))
        rng.shuffle(withnote)
        for r in withnote[keep_n:]:
            r["ingredient"] = TAIL.sub("", PAREN.sub("", r["ingredient"])).strip(" ,")
            r["_note_stripped"] = True
            notes_removed += 1
    for cls_rows in (pos, neg):
        have = [r for r in cls_rows if PAREN.search(r["ingredient"]) or TAIL.search(r["ingredient"])]
        need = int(NOTE_RATE * len(cls_rows)) - len(have)
        free = [r for r in cls_rows if not (PAREN.search(r["ingredient"]) or TAIL.search(r["ingredient"])) and "(" not in r["ingredient"]]
        rng.shuffle(free)
        for r in free[:max(0, need)]:
            r["ingredient"] = f"{r['ingredient']} {rng.choice(NOTE_POOL)}"
            notes_added += 1
    for r in pool:                                        # an 'edge/E1' row whose only edge-ness was a note is no longer borderline
        if r["type_used"] == "E1" and r.get("_note_stripped"):
            r["type_used"] = "G1" if jaccard(r["ingredient"], r["usda_match"]) >= 0.6 else "G3"
    log["notes stripped / added / cue words stripped"] = f"{notes_removed} / {notes_added} / {cues_removed}"

    # 3b. final leak filter AFTER all rewrites (quantity-free keys): real production pairs and reserved real-data cores
    from s7_clean import real_keys
    rk = real_keys()
    blockset = set(json.loads((WORK / "blocklist.json").read_text()))
    n_before = len(pool)
    pool = [r for r in pool if canon_key(r["ingredient"], r["usda_match"]) not in rk
            and core_of(r["ingredient"]) not in blockset and norm(r["ingredient"]) not in blockset]
    log["dropped by final leak filter (real copies / reserved cores)"] = n_before - len(pool)

    # 4. dedupe after rewriting, tiers from FINAL type
    seen, keep = set(), []
    for r in pool:
        k = canon_key(r["ingredient"], r["usda_match"])
        if k not in seen:
            seen.add(k)
            keep.append(r)
    log["duplicates after rewriting"] = len(pool) - len(keep)
    pool = keep
    for r in pool:
        r["tier"] = TIER.get(r["type_used"], "medium")
        r["label"] = r["intended"]

    # 5. quantities, groups, splits
    for r in pool:
        r["ingredient_q"] = f"{quantity(r['ingredient'], r['usda_match'])}g {r['ingredient']}"
    build_groups(pool)
    assign_splits(pool)
    tc = C.Counter(r["split"] for r in pool)
    gold = []
    by_t = C.defaultdict(list)
    for r in pool:
        if r["split"] == "test":
            by_t[r["tier"]].append(r)
    ntest = sum(len(v) for v in by_t.values())
    for t, lst in by_t.items():
        rng.shuffle(lst)
        gold += [x["rid"] for x in lst[:int(round(150 * len(lst) / ntest))]]
    gold = set(gold)

    # 6. write one stable-ID version
    rng.shuffle(pool)
    OUT.mkdir(exist_ok=True)
    recs = []
    for i, r in enumerate(pool):
        recs.append({
            "id": f"sub2-{i:05d}", "ingredient": r["ingredient_q"], "usda_match": r["usda_match"],
            "label": r["label"], "label_status": "intended_unjudged", "judge_label": None,
            "tier": r["tier"], "relation_code": r["type_used"], "relation_claimed": r["type_claimed"],
            "audit_type": r.get("audit_type"), "audit_polarity_conflict": r["audit_polarity_conflict"],
            "reviewer_label": r.get("review"), "reviewer_disputed": r.get("disputed"),
            "core_food": r["food"], "group_id": r["group_id"], "family": r["group"], "cuisine": r["cuisine"],
            "jaccard": round(jaccard(r["ingredient"], r["usda_match"]), 3),
            "fdc_id": r["fdc_id"], "fdc_source": r["fdc_source"], "snap_exact": r["snap_exact"],
            "synthetic_usda": False, "gold_for_human_label": r["rid"] in gold, "split": r["split"],
            "variant_of": None, "perturbation": None, "generator_model": MODEL, "source_batch": r["batch"]})
    for s in list(SPLIT_FRAC) + ["all"]:
        with open(OUT / f"{s}.jsonl", "w", encoding="utf-8") as f:
            for x in recs:
                if s == "all" or x["split"] == s:
                    f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with open(OUT / "prejudge_input.jsonl", "w", encoding="utf-8") as f:     # what the production judge must label
        for x in recs:
            f.write(json.dumps({"id": x["id"], "ingredient": x["ingredient"], "usda_match": x["usda_match"]}, ensure_ascii=False) + "\n")
    log["final rows"] = len(recs)
    log["split sizes"] = dict(tc)
    print("\n=== BUILD LOG ===")
    for k, v in log.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
