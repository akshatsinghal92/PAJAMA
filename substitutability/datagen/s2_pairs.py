"""Step 2 — write ingredient / USDA-style pairs, 6 foods per call (LLM).

Usage:
  s2_pairs.py submit pilot|main
  s2_pairs.py collect pilot|main [--wait]
The slot plan (label, difficulty level, pair type) is fixed in CODE so the data is balanced by construction;
the LLM only writes the pairs. Intended labels are provisional: step 4 (production judge) is run by the user later.
"""
import json
import random
import sys

from common import WORK, collect_batch, load_results, parse_json, strip_qty, submit_batch

SEED = 42
FOODS_PER_CALL = 4     # 4 foods x 4 slots = 16 slots per call
LEVEL_SHARE = {"easy": 0.30, "medium": 0.30, "hard": 0.30, "edge": 0.10}
# label -> level -> {type: weight}
TYPES = {
    "good": {"easy": {"G1": .30, "G2": .35, "G3": .35}, "medium": {"G4": .5, "G5": .5},
             "hard": {"G6": .7, "G7": .3}, "edge": {"E1": 1.0}},
    "bad": {"easy": {"B1": .3, "B2": .4, "B3": .3}, "medium": {"B5": .35, "B6": .35, "B7": .3},
            "hard": {"B4": .2, "B8": .3, "B9": .3, "B10": .2}, "edge": {"B11": .5, "E2": .5}},
}
TYPE_DESC = {
    "G1": "EXACT: ingredient and USDA entry name the same plain food (honey -> Honey; soy sauce -> Soy sauce).",
    "G2": "REORDER: same food, USDA writes it in inverted FoodData Central order (black pepper -> Spices, pepper, black; feta cheese -> Cheese, feta; apple cider vinegar -> Vinegar, cider).",
    "G3": "TRIVIAL PREP: the ingredient has a harmless cut/freshness/temperature word a cook applies or ignores; USDA is the plain raw/default entry (fresh diced onion -> Onions, raw; melted butter -> Butter, without salt; fresh cilantro -> Cilantro, raw).",
    "G4": "MATCHING STATE: the ingredient's preservation and post-prep words AGREE with the USDA entry's state (frozen mango chunks, thawed -> Mango, frozen; canned mushrooms, drained -> Mushrooms, canned, drained solids; canned black beans, drained -> Black beans, from canned, no added fat).",
    "G5": "GENERIC -> DEFAULT: an unqualified ingredient maps to the regular/default USDA entry (milk -> Milk, whole; sour cream -> Sour cream, regular; olive oil -> Oil, olive, salad or cooking; mayo -> Mayonnaise, regular).",
    "G6": "SYNONYM/TAXONOMY (LOW word overlap, still the same food): different words for the same food (zucchini -> Squash, summer, zucchini, includes skin, raw; fresh mint -> Spearmint, fresh; shredded purple cabbage -> Cabbage, red, raw).",
    "G7": "BRAND OF THE PLAIN PRODUCT: a branded USDA entry for the same plain product (firm tofu -> HOUSE FOODS Premium Firm Tofu). Use only if natural for this food; otherwise use a G6-style synonym and report type G6.",
    "E1": "BORDERLINE-GOOD: a case a strict judge would still accept: an optional/garnish/parenthetical note that does not change the food, or a minor prep word on an otherwise identical food (heavy cream (optional) -> Cream, fluid, heavy whipping; diced ham -> Ham).",
    "B1": "UNRELATED: a USDA entry for a clearly different food that a weak retrieval step might return (breadcrumbs -> Popover; nori sheets -> Rice paper).",
    "B2": "SIBLING FOOD: a different food in the same category (chia seeds -> Seeds, flaxseed; duck breast -> Chicken breast, sauteed, skin eaten; beef broth -> Fish broth).",
    "B3": "DISH/PRODUCT MADE FROM IT: the USDA entry is a sauce, dish, juice or processed product containing the food (spaghetti -> Spaghetti sauce; mixed berries -> Crisp, berry; beet -> Beet juice; chopped almonds -> Almond butter).",
    "B4": "SHARED-WORD TRAP (HIGH word overlap, wrong thing): shares a word but is a different thing (ice -> Italian Ice, no sugar added; cherry tomatoes -> Maraschino cherries; diced potato -> Bread, potato; cinnamon -> Sugar, cinnamon).",
    "B5": "COOKING-STATE MISMATCH: raw/unspecified ingredient vs a USDA entry that is cooked, baked, fried or grilled (penne pasta -> Pasta, cooked; fresh mushrooms -> Fried mushrooms; potato -> Potato, baked, peel eaten).",
    "B6": "PHYSICAL-FORM MISMATCH: different physical form (garlic paste (from tube) -> Garlic sauce; cumin -> Spices, cumin seed; chili flakes -> Spices, chili powder; diced carrot -> Carrot, dehydrated).",
    "B7": "PRESERVATION MISMATCH: jarred/frozen/canned vs fresh, or pickled etc. (jarred minced garlic -> Garlic, raw; frozen grated ginger -> Ginger root, raw; zucchini -> Zucchini, pickled).",
    "B8": "NON-DEFAULT VARIANT (HIGH word overlap): a plain ingredient vs a specific non-default composition (almond milk -> Almond milk, unsweetened; cream cheese -> Cream cheese, light; Greek yogurt -> Yogurt, Greek, plain, lowfat).",
    "B9": "FLAVOUR/PROCESS DIFFERENCE (HIGH word overlap): smoked, toasted, sweetened, syrup-packed, etc. (smoked paprika -> Spices, paprika; toasted almonds -> Almonds, unroasted; canned jackfruit -> Jackfruit, canned, syrup pack).",
    "B10": "WRONG VARIETY (HIGH word overlap): a specific variety vs a different or generic one (jasmine rice -> Rice, white, cooked, glutinous; kalamata olives -> Olives, black; Dijon mustard -> Mustard; rice vinegar -> Vinegar).",
    "B11": "PARTIAL COMPOSITE: write a COMPOSITE ingredient made of this food plus one other food, and match it to the entry for only ONE component (Salt and pepper (to taste) -> Salt, table; canned peas and carrots, drained -> Green peas, canned, cooked, no added fat).",
    "E2": "BORDERLINE-BAD: a case a strict judge would likely reject because of one minor attribute (chopped walnuts -> Nuts, walnuts, english; a generic herb vs a fresh-only or dried-only entry; skin/bone differences on a poultry part).",
}
TYPE_LABEL = {t: ("good" if lab == "good" else "bad") for lab, lv in TYPES.items() for ts in lv.values() for t in ts}

SYSTEM = """You write training data for a classifier that decides whether a USDA FoodData Central entry is an acceptable match for a recipe ingredient.

THE RULE (this is the exact standard of the strict judge whose labels we will copy):
A match is SUBSTITUTABLE (good) if and only if BOTH hold:
  1. It could be used in place of the ingredient without changing how the dish is prepared.
  2. A person eating the dish would not notice ANY difference in taste, texture, or appearance.
If the match would alter cooking method, the dish's flavour, texture or appearance, or a diner would notice they were eating something different, it is NOT substitutable (bad).
Because the rule says "any difference", the judge is strict: an unqualified ingredient matches the regular/default USDA entry, but NOT a specific non-default variant (almond milk vs "Almond milk, unsweetened" is bad).

HOW TO WRITE THE TWO STRINGS
Ingredient: as a recipe line lists it, WITHOUT any quantity (we add quantities later). Natural, lowercase except proper nouns. It may carry a preservation/form word, a cut word, a post-prep clause and/or a note. Real examples: "fresh diced onion", "frozen chicken breast, thawed", "canned black beans, drained", "garlic paste (from tube)", "Salt and pepper (to taste)", "heavy cream (optional)", "dried kidney beans, soaked and cooked", "jarred roasted red bell pepper", "shredded Monterey Jack cheese".
USDA match: exactly how a FoodData Central entry is named, in SR Legacy or FNDDS style: head food first, then comma-separated modifiers, state last. Real examples: "Onions, raw", "Spices, pepper, black", "Beef, chuck for stew, separable lean and fat, choice, raw", "Black beans, from canned, no added fat", "Tomatoes, red, ripe, raw, year round average", "Cheese, parmesan, grated", "Potato, roasted, from fresh, peel eaten, made with oil", "Rice, white, cooked, no added fat", "Oil, olive, salad or cooking", "Sauce, pasta, spaghetti/marinara, ready-to-serve", "Chicken, NS as to part, rotisserie, skin not eaten".
The USDA entry must be one that plausibly EXISTS in FoodData Central. Do not invent odd or marketing-style names.

REAL USDA ENTRIES (provided under each food)
For every food we list real FoodData Central entries found near it. Use them:
- Copy the usda_match EXACTLY, character for character, from a listed entry whenever one fits the slot. Real matching systems only ever see real entries, so bad pairs should be real near-misses taken from this list (a sibling food, another form or state, a non-default variant, a dish containing it).
- Only if NO listed entry can fill the slot, you may write one other entry that you are SURE exists in FoodData Central, and set "invented": true.
- If a GOOD slot cannot honestly be filled (no real entry is an acceptable swap for this ingredient), SKIP it: {"slot": "<id>", "skip": true}. Never force a good pair that a strict diner would notice. A skipped slot is far better than a wrong label.

QUALITY RULES (very important)
- Write exactly one pair per slot, of the slot's requested pair type and label.
- GOOD pairs: you must be confident that a strict diner would notice NO difference. BAD pairs: you must be confident that a diner WOULD notice (or the prep would change). Never write a 'bad' pair that is actually an acceptable swap, nor a 'good' pair that is not.
- Bad pairs should look like mistakes a real matching system could make (plausible near-misses), not absurd ones — except type B1.
- Make the pairs for one food DIFFERENT from each other (different phrasing, different USDA entries, not the same template). Do not reuse a USDA string within this request.
- For 'HIGH word overlap' types make the bad pair share most of its words with the ingredient; for 'LOW word overlap' types make the good pair use different words.
- If a requested type truly cannot apply naturally to the food, use a different type with the SAME label and report the type you used.
- Do not include quantities or digits-plus-g in the ingredient string.

PAIR TYPES
""" + "\n".join(f"{t}: {d}" for t, d in TYPE_DESC.items()) + """

OUTPUT: JSON only, no markdown:
{"items": [{"slot": "<slot id>", "ingredient": "...", "usda_match": "...", "intended": 1 or 0, "type": "<type code used>", "decisive": "<<=6 words: the attribute that decides the label>", "invented": false}, {"slot": "<slot id>", "skip": true}]}"""


def pick(rng, weights):
    ks, ws = zip(*weights.items())
    return rng.choices(ks, ws)[0]


def alloc(n, shares):
    raw = {k: n * v for k, v in shares.items()}
    out = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - out[k], reverse=True)[: n - sum(out.values())]:
        out[k] += 1
    return out


def build_slots(foods, rng, per_food=2):
    """per_food=2 -> 1 good + 1 bad; per_food=4 -> 2 good + 2 bad (plan cap is 4 pairs per food).
    Good/bad pools are equal; levels inside each pool follow LEVEL_SHARE; a food's two slots of one label use different types."""
    n = len(foods)
    k = per_food // 2
    pools = {}
    for lab in ("good", "bad"):
        slots = []
        for lvl, cnt in alloc(n * k, LEVEL_SHARE).items():
            for _ in range(cnt):
                slots.append((lvl, pick(rng, TYPES[lab][lvl])))
        rng.shuffle(slots)
        pools[lab] = slots
    plan = []
    for i, f in enumerate(foods):
        fs = []
        for lab in ("good", "bad"):
            pool = pools[lab]
            chosen = pool[i * k:(i + 1) * k]
            if k == 2 and chosen[0][1] == chosen[1][1]:           # avoid two identical types for one food
                for j in range(len(pool) - 1, (i + 1) * k - 1, -1):
                    if pool[j][1] != chosen[0][1]:
                        pool[j], pool[i * k + 1] = pool[i * k + 1], pool[j]
                        chosen = pool[i * k:(i + 1) * k]
                        break
            fs += [(lab, lv, ty) for lv, ty in chosen]
        rng.shuffle(fs)
        plan.append({**f, "slots": fs})
    return plan


def choose_foods(name):
    foods = json.loads((WORK / "foods.json").read_text())
    rng = random.Random(SEED)
    if name == "pilot":
        by_group = {}
        for f in foods:
            by_group.setdefault(f["group"], []).append(f)
        for g in by_group:
            rng.shuffle(by_group[g])
        return [f for g in sorted(by_group) for f in by_group[g][:6]]
    pilot = {f["food"] for f in json.loads((WORK / "pilot_plan.json").read_text())}
    # measured: foods with 0 USDA entries fill only ~20% of good slots; >=1 entry fills 85-100%
    chosen = [f for f in foods if f.get("n_entries", 0) >= 1 and f["food"] not in pilot]
    rng.shuffle(chosen)
    return chosen


_IX = None


def refs(food, k=25):
    """Top-k real FoodData Central descriptions near a food name (lexical, local, free)."""
    global _IX
    import collections as C
    from s3_snap import Index, toks
    if _IX is None:
        _IX = Index()
    q = set(toks(food))
    if not q:
        return []
    sc = C.Counter()
    for t in q:
        for i in _IX.inv.get(t, ()):
            sc[i] += _IX.idf.get(t, 1.0)
    out = []
    for i, base in sc.most_common(400):
        first = toks(_IX.rows[i]["description"].split(",")[0])
        bonus = 0.6 * _IX.idf.get(next(iter(q & set(first)), ""), 0) if q & set(first) else 0.0
        out.append((base + bonus - 0.02 * len(_IX.tok[i]), i))
    out.sort(reverse=True)
    return [_IX.rows[i]["description"] for _, i in out[:k]]


def build_requests(plan, name):
    items, calls = [], {}
    for ci in range(0, len(plan), FOODS_PER_CALL):
        chunk = plan[ci: ci + FOODS_PER_CALL]
        lines, slot_info = [], {}
        for j, f in enumerate(chunk, 1):
            lines.append(f"Food {j}: {f['food']}  [group: {f['group']}]")
            lines.append("  Real USDA entries near this food: " + " | ".join(refs(f["food"])))
            for s, (lab, lvl, ty) in enumerate(f["slots"], 1):
                sid = f"f{j}s{s}"
                slot_info[sid] = {"food": f["food"], "group": f["group"], "cuisine": f["cuisine"],
                                  "label": lab, "level": lvl, "type": ty}
                lines.append(f"  slot {sid}: {lab.upper()} | level {lvl} | type {ty} - {TYPE_DESC[ty].split(':')[0]}")
        user = "Write one pair for every slot below.\n\n" + "\n".join(lines)
        cid = f"{name}-{ci // FOODS_PER_CALL:04d}"
        items.append({"id": cid, "user": user, "max_tokens": 22000})
        calls[cid] = slot_info
    return items, calls


def process(name):
    calls = json.loads((WORK / f"s2_{name}_calls.json").read_text())
    res = load_results(f"s2_{name}")
    pairs, stats = [], {"skipped": 0, "call_fail": 0, "no_slot": 0, "polarity": 0, "bad_field": 0, "missing": 0, "truncated": 0}
    for r in res:
        slots = calls.get(r["id"], {})
        if r["status"] != "succeeded":
            stats["call_fail"] += 1
            continue
        if r.get("stop") == "max_tokens":
            stats["truncated"] += 1
        obj = parse_json(r["text"])
        items = obj.get("items") if isinstance(obj, dict) else obj
        if not isinstance(items, list):
            stats["call_fail"] += 1
            continue
        got = set()
        for it in items:
            sid = str(it.get("slot", ""))
            s = slots.get(sid)
            if not s:
                stats["no_slot"] += 1
                continue
            if it.get("skip"):
                stats["skipped"] += 1
                got.add(sid)
                continue
            ing = strip_qty(str(it.get("ingredient", "")).strip())
            usda = str(it.get("usda_match", "")).strip()
            if not ing or not usda or len(ing) > 120 or len(usda) > 200:
                stats["bad_field"] += 1
                continue
            used = str(it.get("type", s["type"])).strip()
            if used not in TYPE_LABEL:
                used = s["type"]
            want = 1 if s["label"] == "good" else 0
            if int(it.get("intended", -1)) != want or TYPE_LABEL[used] != s["label"]:
                stats["polarity"] += 1
                continue
            got.add(sid)
            pairs.append({"call": r["id"], "slot": sid, **s, "type_requested": s["type"], "type_used": used,
                          "intended": want, "ingredient": ing, "usda_llm": usda,
                          "decisive": str(it.get("decisive", ""))[:80]})
        stats["missing"] += len(set(slots) - got)
    (WORK / f"s2_{name}_pairs.json").write_text(json.dumps(pairs, indent=1))
    n_req = sum(len(v) for v in calls.values())
    print(f"slots requested {n_req}; pairs kept {len(pairs)}; issues {stats}")
    th = sum(r.get("think_tok", 0) for r in res if r["status"] == "succeeded")
    ot = sum(r.get("out_tok", 0) for r in res if r["status"] == "succeeded")
    nin = sum(r.get("in_tok", 0) for r in res if r["status"] == "succeeded")
    print(f"tokens: in {nin} out {ot} (thinking {th}) over {len(res)} calls -> per call in {nin//max(1,len(res))} out {ot//max(1,len(res))}")


if __name__ == "__main__":
    cmd, name = sys.argv[1], sys.argv[2]
    if cmd == "submit":
        foods = choose_foods(name)
        plan = build_slots(foods, random.Random(SEED + (1 if name == "main" else 0)), per_food=4 if name == "main" else 2)
        (WORK / f"{name}_plan.json").write_text(json.dumps(plan, indent=1))
        items, calls = build_requests(plan, name)
        (WORK / f"s2_{name}_calls.json").write_text(json.dumps(calls))
        print(f"{name}: {len(plan)} foods, {sum(len(p['slots']) for p in plan)} slots, {len(items)} calls")
        if "--sync" in sys.argv:
            from common import run_sync
            run_sync(f"s2_{name}", SYSTEM, items, effort="medium")
            process(name)
        else:
            submit_batch(f"s2_{name}", SYSTEM, items, effort="medium")
    elif cmd == "collect":
        out = collect_batch(f"s2_{name}", wait="--wait" in sys.argv)
        if out is not None:
            process(name)
    elif cmd == "process":
        process(name)
