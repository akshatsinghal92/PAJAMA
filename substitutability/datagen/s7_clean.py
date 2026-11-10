"""Step 7 — local, free quality cleaning of the pre-judge pool (feedback points 1, 2, 4).
Reads work/s6_{pilot,main}_pairs.json, writes work/pool_clean.json and prints what was removed (with examples).
Nothing here uses labels from the judge; it only removes leaks / unrealistic rows and builds split groups.
"""
import collections as C
import json
import random
import re

from blocklist import core_of
from common import DATA, WORK, canon_key, jaccard, norm, singular, strip_qty

rng = random.Random(3)

# animals/foods no ordinary recipe lists (checked against the data before removal)
ABSURD = {"armadillo", "zebra", "turtle", "terrapin", "caribou", "reindeer", "moose", "muskrat", "opossum", "possum",
          "squirrel", "beaver", "porcupine", "raccoon", "bear", "seal", "whale", "walrus", "agutuk", "akutaq", "iguana",
          "horse", "camel", "dove", "pigeon", "lapwing", "capercaillie", "ptarmigan", "woodcock", "crocodile", "emu",
          "ostrich", "kangaroo", "antelope", "wildebeest", "springbok", "elephant", "monkey", "snake", "grasshopper",
          "cricket", "mealworm", "guinea fowl", "guinea hen", "partridge", "grouse", "jackrabbit", "hare", "yak",
          "llama", "alpaca", "aspartame", "saccharin", "locust bean gum", "ambergris"}
USDA_WORDS = re.compile(r"\b(nfs|ns as to|separable|includes|meat only|unprepared|all grades|dry heat|trimmed to|"
                        r"lean and fat|solids and liquids|prepared from recipe|enriched|unenriched|fat eaten|"
                        r"commercially prepared|year round average|not further specified)\b", re.I)
STATE_END = re.compile(r",\s*(raw|cooked|dried|canned|frozen|fresh|boiled|baked|roasted|drained)\s*$", re.I)


def real_keys():
    out = set()
    for sp in ("val", "test"):
        for line in open(DATA / f"{sp}.jsonl"):
            r = json.loads(line)
            out.add(canon_key(r["ingredient"], r["usda_match"]))
    return out


def usda_styled(ing: str) -> bool:
    """Ingredient line that reads like a USDA database entry, not a recipe line."""
    if USDA_WORDS.search(ing):
        return True
    parts = [p.strip() for p in ing.split(",")]
    if len(parts) >= 3:
        return True                                  # 'greens, dandelion, raw'
    if len(parts) == 2 and STATE_END.search(ing) and len(parts[0].split()) <= 2 and parts[0].split()[0].lower() in {
            "greens", "beef", "pork", "fish", "nuts", "seeds", "spices", "oil", "cheese", "milk", "cereals", "beans"}:
        return True
    return False


def has_absurd(r) -> str | None:
    text = " " + norm(r["ingredient"]) + " " + norm(r["food"]) + " "
    for w in ABSURD:
        if " " + w + " " in text or " " + w + "s " in text:
            if w == "pigeon" and "pigeon pea" in text:      # pigeon peas are a normal legume
                continue
            return w
    return None


def main():
    pool = []
    for n in ("pilot", "main"):
        for r in json.load(open(WORK / f"s6_{n}_pairs.json")):
            if r.get("snapped"):
                r["batch"] = n
                pool.append(r)
    n0 = len(pool)
    removed = C.OrderedDict()

    def drop(name, pred, show=6):
        nonlocal pool
        gone = [r for r in pool if pred(r)]
        pool = [r for r in pool if not pred(r)]
        removed[name] = len(gone)
        ex = rng.sample(gone, min(show, len(gone)))
        print(f"\n[{name}] removed {len(gone)}")
        for r in ex:
            print(f"    {strip_qty(r['ingredient'])!r} -> {r['usda_match']!r}")

    # --- 1. leaks
    rk = real_keys()
    drop("exact copy of a REAL production pair", lambda r: canon_key(r["ingredient"], r["usda_match"]) in rk)
    block = set(json.load(open(WORK / "blocklist.json")))
    drop("ingredient core is a reserved real-data core", lambda r: core_of(strip_qty(r["ingredient"])) in block or norm(strip_qty(r["ingredient"])) in block)
    # --- 2. unrealistic
    drop("absurd food / additive", lambda r: has_absurd(r) is not None)
    drop("ingredient written in USDA wording", lambda r: usda_styled(r["ingredient"]))
    # strip leading 'raw ' (label-safe: unspecified state is what the plan's cooking-state pairs use)
    n_raw = 0
    for r in pool:
        if re.match(r"^raw\s+", r["ingredient"], re.I):
            r["ingredient"] = re.sub(r"^raw\s+", "", r["ingredient"], flags=re.I)
            n_raw += 1
    removed["leading 'raw ' stripped (kept row)"] = n_raw
    print(f"\n[leading 'raw ' stripped] {n_raw} rows rewritten")

    # --- exact-duplicate keys after rewriting
    seen, keep, dup = set(), [], 0
    for r in pool:
        k = canon_key(r["ingredient"], r["usda_match"])
        if k in seen:
            dup += 1
            continue
        seen.add(k)
        keep.append(r)
    pool = keep
    removed["duplicate after rewrite"] = dup
    print(f"\n[duplicate after rewrite] removed {dup}")

    # --- 3. split groups: merge synonym foods so they can never straddle splits
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

    for r in pool:
        r["_core"] = ctoks(strip_qty(r["ingredient"]))
        union("F:" + r["food"], "I:" + "_".join(sorted(r["_core"])))
    by_usda = C.defaultdict(set)
    for r in pool:
        by_usda[norm(r["usda_match"])].add(r["_core"])
    for cores in by_usda.values():
        cores = [c for c in cores if c]
        for i in range(len(cores)):
            for j in range(i + 1, len(cores)):
                a, b = cores[i], cores[j]
                if len(a & b) / len(a | b) >= 0.5:
                    union("I:" + "_".join(sorted(a)), "I:" + "_".join(sorted(b)))
    for r in pool:
        r["group_id"] = find("F:" + r["food"])
        del r["_core"]
    gsize = C.Counter(r["group_id"] for r in pool)
    print(f"\n[split groups] {len(gsize)} groups from {len({r['food'] for r in pool})} foods; largest group {max(gsize.values())} rows")

    (WORK / "pool_clean.json").write_text(json.dumps(pool, indent=1))
    print(f"\nPOOL: {n0} -> {len(pool)} rows after cleaning")
    print("summary:", json.dumps(removed))
    lab = C.Counter(r["intended"] for r in pool)
    print("label balance in pool: good %d bad %d" % (lab[1], lab[0]))


if __name__ == "__main__":
    main()
