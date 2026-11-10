"""Step 3 — snap LLM-written USDA strings to real FoodData Central descriptions (local, free).

A snap is accepted only if (a) the match is exact, or (b) it is very similar AND the 'critical words'
(raw/cooked/frozen/canned/dried/unsweetened/paste/sauce/powder/...) are the same in both strings,
so snapping can never silently change what the pair means.
Usage: s3_snap.py pilot|main
"""
import collections as C
import difflib
import json
import math
import re
import sys

from common import WORK, fdc, norm, singular

PHRASES = [("low fat", "lowfat"), ("reduced fat", "lowfat"), ("lower fat", "lowfat"), ("fat free", "nonfat"),
           ("lite", "light"), ("low sodium", "lowsodium"), ("reduced sodium", "lowsodium"), ("no salt added", "unsalted"),
           ("without salt", "unsalted"), ("salt added", "salted"), ("uncooked", "raw"), ("fresh", "raw"),
           ("dry", "dried"), ("ready to serve", "readytoserve"), ("ready to eat", "readytoserve")]
CRIT = {"raw", "cooked", "boiled", "baked", "fried", "roasted", "grilled", "broiled", "steamed", "sauteed", "stewed",
        "frozen", "canned", "dried", "dehydrated", "pickled", "smoked", "toasted", "sweetened", "unsweetened",
        "salted", "unsalted", "lowfat", "nonfat", "light", "lowsodium", "paste", "sauce", "powder", "juice", "soup",
        "bouillon", "syrup", "flakes", "seed", "readytoserve", "glazed", "candied", "creamed", "pureed", "puree"}
METHODS = {"boiled", "baked", "fried", "roasted", "grilled", "broiled", "steamed", "sauteed", "stewed"}
MIN_SCORE = 0.78


def prep(s: str) -> str:
    s = norm(s)
    for a, b in PHRASES:
        s = re.sub(rf"\b{a}\b", b, s)
    return s


def toks(s: str) -> list[str]:
    return [singular(t) for t in prep(s).split() if t not in {"nfs", "ns", "as", "to", "for", "with", "no", "added", "from", "and", "the", "of", "in"}]


def crit(s: str) -> set[str]:
    return {t for t in toks(s) if t in CRIT}


def crit_equal(orig: str, snapped: str) -> bool:
    a, b = crit(orig), crit(snapped)
    if "cooked" in a:                      # generic 'cooked' accepts any specific cooking method
        b = {("cooked" if t in METHODS else t) for t in b}
    if "readytoserve" in b:
        b.discard("readytoserve")
    return a == b


class Index:
    def __init__(self):
        self.rows = fdc()
        self.tok = [set(toks(r["description"])) for r in self.rows]
        self.exact = {}
        for i, r in enumerate(self.rows):
            self.exact.setdefault(norm(r["description"]), i)
        df = C.Counter(t for s in self.tok for t in s)
        n = len(self.rows)
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}
        self.inv = C.defaultdict(list)
        for i, s in enumerate(self.tok):
            for t in s:
                self.inv[t].append(i)

    def snap(self, usda: str):
        k = norm(usda)
        if k in self.exact:
            i = self.exact[k]
            return i, 1.0, True
        q = set(toks(usda))
        if not q:
            return None, 0.0, False
        cand = C.Counter()
        for t in q:
            for i in self.inv.get(t, ()):
                cand[i] += self.idf.get(t, 1.0)
        best = None
        for i, _ in cand.most_common(40):
            s = self.tok[i]
            inter = sum(self.idf.get(t, 1.0) for t in q & s)
            union = sum(self.idf.get(t, 1.0) for t in q | s)
            score = 0.5 * (inter / union) + 0.5 * difflib.SequenceMatcher(None, prep(usda), prep(self.rows[i]["description"])).ratio()
            if score >= MIN_SCORE and crit_equal(usda, self.rows[i]["description"]):
                if best is None or score > best[1]:
                    best = (i, score, False)
        return best if best else (None, 0.0, False)


QTY_RANGE = {"herbs_spices": (1, 15), "oils_fats": (5, 120), "sauces_condiments": (10, 250),
             "broths_drinks_baking": (5, 900)}


def quantity(group: str, rng) -> int:
    lo, hi = QTY_RANGE.get(group, (30, 600))
    q = math.exp(rng.uniform(math.log(lo), math.log(hi)))
    return max(1, int(round(q))) if q < 20 else int(round(q / 5.0) * 5)


def run(name):
    import random
    rng = random.Random(7)
    pairs = json.loads((WORK / f"s2_{name}_pairs.json").read_text())
    ix = Index()
    out, st = [], C.Counter()
    for p in pairs:
        i, score, exact = ix.snap(p["usda_llm"])
        q = dict(p)
        q["ingredient_q"] = f"{quantity(p['group'], rng)}g {p['ingredient']}"   # decoration; the judge sees this full string
        if i is None:
            q.update(snapped=False, usda_match=None, fdc_id=None, snap_score=0.0, snap_exact=False)
            st["rejected"] += 1
        else:
            r = ix.rows[i]
            q.update(snapped=True, usda_match=r["description"], fdc_id=r["fdc_id"], fdc_source=r["source"],
                     snap_score=round(score, 3), snap_exact=exact)
            st["exact" if exact else "fuzzy"] += 1
        out.append(q)
    (WORK / f"s3_{name}_pairs.json").write_text(json.dumps(out, indent=1))
    n = len(out)
    print(f"{name}: {n} pairs -> exact {st['exact']} ({st['exact']/n:.0%}), fuzzy {st['fuzzy']} ({st['fuzzy']/n:.0%}), "
          f"rejected {st['rejected']} ({st['rejected']/n:.0%})")
    by = C.defaultdict(lambda: [0, 0])
    for q in out:
        by[q["type_used"]][0] += 1
        by[q["type_used"]][1] += q["snapped"]
    print("snap rate by type:", {t: f"{b}/{a}" for t, (a, b) in sorted(by.items())})


if __name__ == "__main__":
    run(sys.argv[1])
