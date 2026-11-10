"""Step 1 — build the core-food list (LLM). Usage: s1_foods.py submit | collect [--wait]"""
import json
import sys

from blocklist import build as build_block, is_blocked
from common import WORK, collect_batch, load_results, norm, parse_json, singular, submit_batch
from s3_snap import toks

GROUPS = {
    "vegetables": ["leafy greens and brassicas", "alliums, roots and tubers", "nightshades, squash and gourds",
                   "mushrooms, sprouts and sea vegetables", "pods, stalks and other fresh vegetables"],
    "fruits": ["citrus and berries", "tropical fruits", "stone and pome fruits", "melons, grapes and dried fruits",
               "avocado, olives, coconut and less common fruits"],
    "herbs_spices": ["fresh herbs", "whole and ground spices", "chili and pepper products",
                     "spice blends and seasoning mixes", "dried aromatics and flavorings"],
    "oils_fats": ["cooking oils", "butter, ghee and animal fats", "nut, seed and specialty oils",
                  "spreads, shortenings and fat substitutes"],
    "dairy_eggs": ["cheeses", "milk, cream and yogurt", "plant-based milks and dairy alternatives",
                   "eggs and egg products", "cultured and fresh dairy (kefir, paneer, ricotta, quark)"],
    "meat": ["beef cuts", "pork and cured pork", "lamb, goat and game", "sausages, ground meat and offal",
             "processed and deli meats"],
    "poultry": ["chicken parts and whole chicken", "turkey", "duck, goose and game birds", "ground and prepared poultry"],
    "seafood": ["finfish", "shellfish and crustaceans", "canned, smoked and cured fish", "roe, sea vegetables and other seafood",
                "surimi and prepared seafood"],
    "grains_pasta_bread": ["rice and whole grains", "pasta and noodles", "flours and baking staples",
                           "breads, crumbs, wraps and crackers", "oats and breakfast cereals"],
    "legumes_nuts_seeds": ["beans, peas and lentils", "soy products (tofu, tempeh, soy milk)", "tree nuts and peanuts",
                           "seeds", "nut and seed butters and pastes"],
    "sauces_condiments": ["East and Southeast Asian sauces and pastes", "tomato and Italian sauces and pastes",
                          "salsas, dips and Latin American sauces", "dressings, mayo-based and creamy sauces",
                          "mustards, ketchups, pickles and relishes"],
    "broths_drinks_baking": ["broths, stocks and bouillon", "vinegars", "sweeteners and syrups",
                             "wines, spirits and beverages used in cooking", "baking agents, thickeners and gelling agents"],
}

STYLES_TOPUP = {
    "C": "mainstream foods that are sold in ordinary US supermarkets and widely eaten in the US (the kind that appear as their own entry in the USDA FoodData Central database)",
    "D": "foods from non-Western cuisines (East/Southeast Asia, South Asia, Middle East, Africa, Latin America) that ARE commonly sold in US supermarkets or ethnic grocery chains and are likely to be listed in the USDA FoodData Central database",
}
STYLES = {
    "A": "foods that are common in everyday US/European home cooking",
    "B": "foods typical of NON-Western cuisines (East/Southeast Asia, South Asia, Middle East, Africa, Latin America)",
}

SYSTEM = """You help build a taxonomy of recipe ingredients.
Return ONLY valid JSON, no markdown. A JSON array of objects: {"food": "<core food name>", "cuisine": "western" | "non-western"}.
Rules:
- "food" is the CORE food as a recipe would name it, with no preparation, cooking state, preservation or quantity words
  (write "onion", not "diced onion" or "frozen onion"; write "chickpeas", not "canned chickpeas").
- Specific varieties are fine when they are a distinct food (e.g. "basmati rice", "kalamata olives", "gruyere cheese").
- No brand names. No dishes or prepared meals. Every item must be a real ingredient a home cook would buy.
- All items must be DIFFERENT foods (no near-duplicates, no singular/plural repeats).
- Prefer a spread of well-known and less-known items within the requested subcategory."""


def requests(styles=None, n=30, tag=""):
    items = []
    for g, subs in GROUPS.items():
        for si, sub in enumerate(subs):
            for st, desc in (styles or STYLES).items():
                user = (f"Group: {g}\nSubcategory: {sub}\nFocus: {desc}.\n"
                        f"List {n} different core foods in this subcategory that fit the focus. "
                        f"Tag each with its cuisine ('western' or 'non-western').")
                items.append({"id": f"{g}-{si}-{st}", "user": user, "max_tokens": 9000})
    return items


GENERIC = {"meat", "sauce", "oil", "cheese", "milk", "paste", "powder", "seed", "nut", "bean", "fruit", "juice", "wine",
           "vinegar", "fish", "sausage", "egg", "cream", "flour", "noodle", "rice", "spice", "blend", "seasoning", "dried",
           "smoked", "salted", "fresh", "green", "red", "white", "black", "yellow", "sweet", "wild", "baby", "dry", "mix",
           "puree", "butter", "syrup", "sugar", "bread", "pasta", "root", "leaf", "leave", "dip", "jam", "chutney"}


def realistic(food: str, vocab: set) -> bool:
    """Keep a food only if its distinctive words exist in FoodData Central (otherwise no real entry can match it)."""
    # any word found in USDA keeps the food: 'jasmine rice' has no 'jasmine' entry but real 'Rice, ...' entries exist,
    # which is exactly what makes wrong-variety hard negatives. Only foods with NO word in USDA are dropped.
    ts = [singular(t) for t in norm(food).split()]
    return any(t in vocab for t in ts)


def process():
    from common import fdc
    from s3_snap import toks
    vocab = {t for r in fdc() for t in toks(r["description"])}
    import os
    from common import WORK as _W
    res = load_results("s1_foods")
    if os.path.exists(_W / "s1_foods_topup_results.jsonl"):
        res = res + load_results("s1_foods_topup")
    terms = build_block()
    seen, foods, dropped = {}, [], {"duplicate": 0, "blocked": 0, "bad": 0, "not_in_usda": 0}
    fails = 0
    for r in res:
        if r["status"] != "succeeded":
            fails += 1
            continue
        arr = parse_json(r["text"])
        if not isinstance(arr, list):
            fails += 1
            continue
        group = r["id"].split("-")[0]
        for it in arr:
            if not isinstance(it, dict) or not it.get("food"):
                dropped["bad"] += 1
                continue
            food = str(it["food"]).strip().lower()
            key = " ".join(sorted(singular(t) for t in norm(food).split()))
            if not key:
                dropped["bad"] += 1
                continue
            if key in seen:
                dropped["duplicate"] += 1
                continue
            if is_blocked(food, terms):
                dropped["blocked"] += 1
                continue
            if not realistic(food, vocab):
                dropped["not_in_usda"] += 1
                continue
            seen[key] = 1
            foods.append({"food": food, "group": group,
                          "cuisine": "non-western" if str(it.get("cuisine", "")).startswith("non") else "western"})
    # measured USDA presence: number of real FDC descriptions that contain ALL the food's words
    from s3_snap import Index
    ix = Index()
    for f in foods:
        q = set(toks(f["food"]))
        ids = None
        for t in sorted(q, key=lambda t: len(ix.inv.get(t, ()))):
            cur = set(ix.inv.get(t, ()))
            ids = cur if ids is None else ids & cur
            if not ids:
                break
        f["n_entries"] = len(ids) if ids and q else 0
    (WORK / "foods.json").write_text(json.dumps(foods, indent=1))
    ne = [f["n_entries"] for f in foods]
    print("USDA presence: foods with >=1 entry:", sum(1 for x in ne if x >= 1), " >=5 entries:", sum(1 for x in ne if x >= 5), " zero:", sum(1 for x in ne if x == 0))
    import collections as C
    print(f"calls failed/unparsed: {fails}; kept foods: {len(foods)}; dropped: {dropped}")
    print("per group:", dict(C.Counter(f["group"] for f in foods)))
    nw = sum(1 for f in foods if f["cuisine"] == "non-western")
    print(f"non-western: {nw} ({nw/max(1,len(foods)):.0%})")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "submit":
        submit_batch("s1_foods", SYSTEM, requests(), effort="low")
    elif cmd == "sync":
        from common import run_sync
        run_sync("s1_foods", SYSTEM, requests(), effort="low")
        process()
    elif cmd == "topup":
        from common import run_sync
        run_sync("s1_foods_topup", SYSTEM, requests(STYLES_TOPUP, n=40), effort="low")
        process()
    elif cmd == "collect":
        out = collect_batch("s1_foods", wait="--wait" in sys.argv)
        if out is not None:
            process()
    elif cmd == "process":
        process()
