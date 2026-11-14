import re

# Variant 7: "component ledger" survival model.
# Each side is mapped to a set of processing/additive component tags.
# Components the USDA entry ADDS (absent from the ingredient) each remove a
# fraction of the remaining "substitutability mass" (multiplicative survival).
# Components the USDA entry DROPS (ingredient has, USDA lacks) cost less.
# A food-identity gate scales the result by head-noun agreement.

_COMPONENT_LEXICON = {
    "salt": (0.30, ["salted", "with salt", "brine", "brined", "pickled", "sodium added", "salt and pepper"]),
    "sugar": (0.35, ["sweetened", "sugar added", "with sugar", "candied", "glazed", "honey", "syrup", "heavy syrup", "light syrup", "frosted", "sugared"]),
    "fat": (0.25, ["fried", "with oil", "oil added", "buttered", "with butter", "in oil", "oil pack", "creamed", "battered"]),
    "sauce": (0.40, ["sauce", "gravy", "in tomato sauce", "with sauce", "dressing", "marinade", "marinated", "teriyaki", "barbecue", "bbq"]),
    "breading": (0.40, ["breaded", "battered", "coated", "crusted", "tempura", "nuggets", "patty", "patties", "fritter"]),
    "seasoning": (0.30, ["and pepper", "seasoned", "spiced", "seasoning", "herbed", "flavored", "flavoured", "with pepper", "pepper and", "garlic and", "lemon pepper", "cajun"]),
    "cured": (0.35, ["smoked", "cured", "luncheon", "frankfurter", "sausage", "jerky", "bacon", "ham,", "salami", "deli"]),
    "mix": (0.40, ["dry mix", "mix,", "prepared from", "includes", "blend", "mixture", "with added", "fortified", "enriched", "imitation"]),
    "reduced": (0.25, ["reduced fat", "low fat", "lowfat", "fat free", "nonfat", "reduced sodium", "low sodium", "reduced sugar", "light", "lite", "low calorie", "diet", "zero", "sugar free"]),
    "cooked": (0.15, ["cooked", "boiled", "baked", "roasted", "simmered", "braised", "stewed", "steamed", "grilled", "broiled", "microwaved"]),
    "canned": (0.10, ["canned", "juice pack", "water pack", "jarred", "bottled"]),
    "dried": (0.20, ["dried", "dehydrated", "powder", "powdered", "freeze-dried", "crumbs", "flakes"]),
    "raw_sugar_variant": (0.30, ["turbinado", "brown sugar", "powdered sugar", "confectioners", "demerara", "muscovado"]),
}

# Ingredient-side words that indicate the ingredient itself already carries the component
_INGREDIENT_IMPLIES = {
    "cooked": ["cooked", "boiled", "baked", "roasted", "leftover", "grilled", "steamed"],
    "canned": ["canned", "tinned", "drained", "jarred", "can of"],
    "dried": ["dried", "powder", "crumbs", "flakes", "ground", "dehydrated"],
    "cured": ["deli", "smoked", "cured", "bacon", "ham", "sausage", "salami", "hot dog", "frank"],
    "reduced": ["diet", "low fat", "reduced", "light", "skim", "fat free", "zero", "sugar free", "low calorie"],
    "mix": ["mix", "blend"],
    "sugar": ["sweetened", "candied", "syrup", "honey", "glazed"],
    "salt": ["salted", "pickled", "brined"],
    "sauce": ["sauce", "dressing", "gravy", "marinade"],
    "seasoning": ["seasoned", "spiced", "flavored", "herbed"],
    "fat": ["fried", "buttered", "in oil"],
    "breading": ["breaded", "battered", "crumbs", "coated"],
}

_NEGATORS = ["without salt", "no salt", "unsalted", "unsweetened", "no sugar added",
             "without added", "plain", "unseasoned", "unflavored", "without sauce"]

_STOP = set("g kg mg ml l oz lb lbs cup cups tbsp tsp of and or the a an with in for to from "
            "fresh frozen thawed chopped sliced diced cubed shredded minced grated drained "
            "large small medium whole pieces piece segments raw uncooked style type".split())


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb|lbs)?\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _strip_parens(t):
    return re.sub(r"\([^)]*\)", " ", t)


def _contains(text, phrase):
    try:
        return re.search(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])", text) is not None
    except Exception:
        return phrase in text


def _usda_components(text):
    found = {}
    for comp, (weight, cues) in _COMPONENT_LEXICON.items():
        hits = sum(1 for c in cues if _contains(text, c.rstrip(",")) or (c.endswith(",") and c in text))
        if hits:
            found[comp] = weight * (1.0 + 0.15 * min(hits - 1, 3))
    # negators cancel the corresponding additive
    if any(_contains(text, n) for n in ("without salt", "no salt", "unsalted")):
        found.pop("salt", None)
    if any(_contains(text, n) for n in ("unsweetened", "no sugar added")):
        found.pop("sugar", None)
    return found


def _ingredient_components(text):
    comps = set()
    for comp, cues in _INGREDIENT_IMPLIES.items():
        if any(_contains(text, c) for c in cues):
            comps.add(comp)
    return comps


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(text):
    return [_stem(w) for w in re.findall(r"[a-z]+", text) if w not in _STOP and len(w) > 2]


def _identity_gate(ing, usda):
    it = set(_tokens(_strip_parens(ing.split(",")[0])))
    full_u = _tokens(usda)
    head_u = set(_tokens(usda.split(",")[0]))
    if not it or not full_u:
        return 0.35
    head_hit = len(it & head_u) > 0
    any_hit = len(it & set(full_u)) / float(len(it))
    paren_hit = len(it & set(_tokens(" ".join(re.findall(r"\(([^)]*)\)", usda))))) > 0
    gate = 0.25 + 0.45 * any_hit
    if head_hit:
        gate += 0.30
    elif paren_hit:
        gate += 0.15
    return max(0.1, min(1.0, gate))


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing or not usda:
            return 0.0

        u_comp = _usda_components(usda)
        i_comp = _ingredient_components(ing)

        survival = 1.0
        added = 0
        for comp, w in u_comp.items():
            if comp in i_comp:
                continue  # shared component: plain-for-plain on this axis
            survival *= (1.0 - min(0.85, w))
            added += 1

        dropped = [c for c in i_comp if c not in u_comp]
        for _ in dropped:
            survival *= 0.88

        # Shared components are a mild positive (same processing state)
        shared = len(set(u_comp) & i_comp)
        bonus = min(0.15, 0.06 * shared)

        # Plain-for-plain reward: neither side lists additives
        if not u_comp and not i_comp:
            bonus += 0.12

        # Explicit plainness in USDA when ingredient is plain
        if any(_contains(usda, n) for n in _NEGATORS) and not i_comp:
            bonus += 0.03

        # Length of descriptor tail as weak proxy for compound processing
        tail = max(0, usda.count(",") - 2)
        survival *= (0.97 ** tail)

        gate = _identity_gate(ing, usda)
        score = 100.0 * gate * min(1.0, survival + bonus)
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
