import re

# Qualifier ledger: each qualifier word belongs to a category with a
# "noticeability" weight (how much a diner would notice if it were added/dropped).
_QUALIFIER_CATEGORIES = {
    "fat": (3.0, {"lean", "fat", "low", "reduced", "nonfat", "skim", "light", "lite",
                  "fat-free", "lowfat", "whole", "full", "trimmed", "separable"}),
    "sugar": (2.5, {"sweetened", "unsweetened", "sugar", "sugar-free", "sweet",
                    "syrup", "honey", "candied"}),
    "calorie": (2.5, {"calorie", "diet", "reduced-calorie"}),
    "caffeine": (3.0, {"decaffeinated", "decaf", "caffeine"}),
    "salt": (1.0, {"salt", "salted", "unsalted", "sodium"}),
    "process": (2.0, {"canned", "frozen", "dried", "dehydrated", "smoked", "cured",
                      "pickled", "fermented", "powder", "powdered", "instant",
                      "concentrate", "juice", "oil", "paste", "sauce", "flour"}),
    "cook": (1.5, {"cooked", "boiled", "roasted", "fried", "baked", "grilled",
                   "braised", "steamed", "broiled", "stewed", "microwaved", "raw", "fresh"}),
    "form": (2.0, {"ground", "steak", "chops", "roast", "patty", "stew", "sliced",
                   "chopped", "minced", "whole", "hearts", "neck", "gizzard", "heart",
                   "liver", "breast", "thigh", "wing", "leg", "tip", "loin", "sirloin",
                   "round", "brisket", "chuck", "rib", "shoulder", "bran", "paper"}),
    "dish": (3.0, {"mayonnaise", "made", "with", "prepared", "mix", "soup", "salad",
                   "dressing", "pie", "cake", "bread", "cookie"}),
}

# Qualifiers that carry little diner-visible meaning in USDA descriptions.
_NEUTRAL = {"raw", "fresh", "drained", "solids", "boneless", "skinless", "meat", "only",
            "broilers", "fryers", "or", "and", "type", "mature", "seeds", "variety",
            "meats", "by-products", "products", "plain", "regular", "commercial",
            "includes", "including", "usda", "commodity", "fluid", "all", "grades",
            "choice", "select", "eaten", "edible", "portion", "free", "range",
            "slip", "skin", "american", "globe", "french", "wild", "hot", "leaf",
            "nuts", "spices", "beverages", "fruit", "vegetables", "of", "the", "a",
            "in", "on", "for", "to", "inch", "trimmed", "separable"}

_PREP_WORDS = {"thawed", "cubed", "diced", "chopped", "sliced", "minced", "drained",
               "rinsed", "soaked", "overnight", "peeled", "halved", "quartered",
               "trimmed", "softened", "melted", "beaten", "divided", "packed",
               "foraged", "from", "tube", "large", "small", "medium", "about",
               "finely", "roughly", "thinly", "freshly", "optional", "taste",
               "room", "temperature", "cut", "into", "pieces", "boneless", "skinless"}

_SYNONYMS = {
    "para": "brazil", "bison": "buffalo", "romaine": "romaine", "cos": "romaine",
    "concord": "grapes", "flaxseeds": "flaxseed", "flax": "flaxseed",
    "garbanzo": "chickpea", "chickpeas": "chickpea", "cilantro": "coriander",
    "scallion": "onion", "scallions": "onion", "aubergine": "eggplant",
    "courgette": "zucchini", "prawns": "shrimp", "prawn": "shrimp",
}

_GENERIC_TO_VARIANT = {
    # generic ingredient term -> USDA tokens that indicate a narrower variant
    "tea": {"decaffeinated", "herbal", "green", "instant"},
    "cheese": {"low", "nonfat", "reduced", "lowfat"},
    "milk": {"skim", "nonfat", "lowfat", "reduced"},
    "dressing": {"reduced", "calorie", "fat-free", "light"},
}


def _stem(w):
    try:
        w = w.lower().strip("-'")
        if len(w) > 4 and w.endswith("ies"):
            return w[:-3] + "y"
        if len(w) > 4 and w.endswith("oes"):
            return w[:-2]
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            return w[:-1]
        return w
    except Exception:
        return w


def _tokens(text):
    try:
        return [t for t in re.findall(r"[a-z][a-z\-']*", text.lower()) if t]
    except Exception:
        return []


def _clean_ingredient(ing):
    s = str(ing or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*[\d./]+\s*(g|kg|ml|l|oz|lb|grams?)?\b", " ", s)
    head, _, tail = s.partition(",")
    return head, tail


def _norm(w):
    w = _stem(w)
    return _SYNONYMS.get(w, w)


def _category(word):
    for name, (weight, words) in _QUALIFIER_CATEGORIES.items():
        if word in words or _stem(word) in words:
            return name, weight
    return None, 0.0


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        head, tail = _clean_ingredient(ingredient)
        ing_all = [_norm(t) for t in _tokens(head + " " + tail)]
        ing_core = [_norm(t) for t in _tokens(head) if t not in _PREP_WORDS]
        if not ing_core:
            ing_core = ing_all[:]
        ing_set = set(ing_all)
        core_set = set(ing_core)

        segs = [p.strip() for p in str(usda_match).lower().split(",") if p.strip()]
        if not segs:
            return 0.0
        primary = [_norm(t) for t in _tokens(segs[0])]
        rest = [_norm(t) for seg in segs[1:] for t in _tokens(seg)]
        usda_set = set(primary) | set(rest)

        score = 50.0

        # --- 1. Anchor: does the ingredient's core concept appear in the USDA entry?
        anchor_hits = core_set & usda_set
        head_noun = ing_core[-1] if ing_core else ""
        if head_noun and head_noun in usda_set:
            score += 18.0
        elif anchor_hits:
            score += 6.0 * min(len(anchor_hits), 2)
        else:
            score -= 25.0
        if set(primary) & core_set:
            score += 6.0

        # --- 2. Added qualifiers: USDA qualifiers the ingredient did not imply.
        added_penalty = 0.0
        seen_cats = set()
        for w in rest + primary:
            if w in ing_set or w in _NEUTRAL:
                continue
            cat, weight = _category(w)
            if cat is None:
                # Unknown descriptive word: mild specificity cost (diminishing).
                added_penalty += 1.0
                continue
            if cat in seen_cats:
                weight *= 0.4
            seen_cats.add(cat)
            # Cooking/state words count less when the ingredient implied a state.
            if cat == "cook" and ({"cooked", "fresh", "raw"} & ing_set):
                weight *= 0.3
            added_penalty += weight * 3.0
        score -= min(added_penalty, 40.0)

        # --- 3. Dropped qualifiers: ingredient specified a variant the USDA lacks.
        dropped_penalty = 0.0
        for w in core_set:
            if w == head_noun or w in usda_set:
                continue
            cat, weight = _category(w)
            if cat is not None:
                dropped_penalty += weight * 2.5
            elif w not in _PREP_WORDS and len(w) > 2:
                dropped_penalty += 2.0
        score -= min(dropped_penalty, 25.0)

        # --- 4. Generic ingredient mapped to a narrower variant entry.
        for gen, variants in _GENERIC_TO_VARIANT.items():
            if gen in core_set and (usda_set & variants) and not (ing_set & variants):
                score -= 12.0

        # --- 5. Specificity balance: reward concise entries for unqualified ingredients.
        extra = len([w for w in usda_set if w not in ing_set and w not in _NEUTRAL])
        if len(core_set) <= 2:
            score += max(0.0, 8.0 - 2.0 * extra)
        else:
            matched_ratio = len(core_set & usda_set) / float(len(core_set))
            score += 10.0 * matched_ratio

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
