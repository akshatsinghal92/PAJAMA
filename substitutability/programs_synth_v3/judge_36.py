import re

# Qualifier ledger: every qualifier on either side is an "account".
# Ingredient-side qualifiers are DEMANDS; USDA-side qualifiers are SUPPLY.
# Demands met -> credit, demands unmet -> debit, unrequested supply -> debit
# weighted by how noticeable the qualifier would be to a diner.

_UNITS = r"(?:g|gr|grams?|kg|mg|ml|l|oz|lb|lbs|cups?|tbsp|tsp|tablespoons?|teaspoons?|pieces?|slices?|cloves?)"

# Prep / state words in recipe text that do not define the food itself.
_PREP = {
    "diced", "chopped", "minced", "sliced", "melted", "thawed", "softened", "grated",
    "shredded", "crushed", "peeled", "trimmed", "cubed", "halved", "quartered",
    "beaten", "whisked", "rinsed", "drained", "divided", "packed", "sifted", "toasted",
    "leftover", "jarred", "canned", "bottled", "store", "bought", "homemade", "fresh",
    "large", "small", "medium", "into", "paste", "about", "and", "or", "of", "the",
    "a", "an", "to", "for", "from", "with", "in", "at", "room", "temperature", "taste",
    "finely", "roughly", "coarsely", "thinly", "optional", "tube", "warm", "cold",
}

# USDA descriptors that are "default" — they don't constitute a noticeable qualifier.
_NEUTRAL = {
    "raw", "uncooked", "fresh", "plain", "regular", "unprepared", "ns", "nfs",
    "as", "to", "form", "purchased", "commercial", "all", "types", "varieties",
    "includes", "type", "or", "and", "with", "without", "made", "prepared",
    "salted", "solids", "liquids", "ready", "serve", "eat", "general", "other",
}

# Highly noticeable qualifier families, with their debit weights.
_LOUD = {
    "lowfat": 2.5, "nonfat": 1.5, "fat": 1.2, "milkfat": 2.0, "reduced": 2.0,
    "lactose": 2.0, "sodium": 1.8, "low": 1.5, "light": 2.0, "lite": 2.0,
    "sweetened": 2.0, "unsweetened": 1.5, "sugar": 1.8, "free": 1.5, "diet": 2.0,
    "flavored": 2.0, "fortified": 1.0, "smoked": 2.2, "cured": 2.0, "fried": 2.0,
    "breaded": 2.5, "battered": 2.5, "dried": 2.0, "dehydrated": 2.2, "powder": 2.5,
    "frozen": 1.0, "cooked": 1.0, "roasted": 1.6, "baked": 1.6, "canned": 1.2,
    "souffle": 3.0, "pate": 2.5, "oil": 3.0, "juice": 2.8, "sauce": 2.0,
    "patty": 2.5, "imitation": 3.0, "substitute": 3.0, "extra": 1.6, "virgin": 1.6,
    "giblets": 2.0, "broilers": 0.6, "fryers": 0.6, "spaghetti": 0.5,
    "marinara": 1.0, "added": 0.8, "vanilla": 1.5, "chocolate": 2.0, "strawberry": 2.0,
}

# Mild equivalences so demand tokens can be satisfied by supply tokens.
_ALIASES = {
    "nonfat": {"non", "fat", "nonfat", "skim", "fat-free"},
    "non": {"nonfat", "non"},
    "skim": {"nonfat", "skim"},
    "lowfat": {"low", "fat", "lowfat", "reduced"},
    "chicken": {"chicken", "broilers", "fryers"},
    "pasta": {"pasta", "spaghetti"},
    "spaghetti": {"spaghetti", "pasta"},
    "gizzards": {"gizzard", "giblets"},
    "livers": {"liver", "giblets"},
}


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.split(",")[0]
    t = re.sub(r"^\s*[\d./\s]+\s*" + _UNITS + r"?\b", " ", t)
    t = re.sub(r"\b\d+(?:\.\d+)?\s*" + _UNITS + r"\b", " ", t)
    t = t.replace("non-fat", "nonfat").replace("low-fat", "lowfat").replace("fat-free", "nonfat")
    words = re.findall(r"[a-z]+", t)
    return [_stem(w) for w in words if w not in _PREP and len(w) > 1]


def _parse_usda(text):
    t = text.lower()
    t = t.replace("non-fat", "nonfat").replace("low-fat", "lowfat").replace("fat-free", "nonfat")
    t = re.sub(r"\([^)]*\)", " ", t)
    segs = [s.strip() for s in t.split(",") if s.strip()]
    if not segs:
        return [], []
    head = [_stem(w) for w in re.findall(r"[a-z]+", segs[0])]
    rest = []
    for idx, s in enumerate(segs[1:], start=1):
        for w in re.findall(r"[a-z0-9%]+", s):
            if re.fullmatch(r"[\d%]+", w):
                rest.append(("#num", idx))
            else:
                rest.append((_stem(w), idx))
    return head, rest


def _satisfies(demand, supply_set):
    if demand in supply_set:
        return True
    for alt in _ALIASES.get(demand, ()):
        if _stem(alt) in supply_set:
            return True
    for s in supply_set:
        if len(demand) >= 4 and len(s) >= 4 and (s.startswith(demand) or demand.startswith(s)):
            return True
    return False


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = _clean_ingredient(str(ingredient))
        head, rest = _parse_usda(str(usda_match))
        if not ing or not head:
            return 0.0

        supply_all = set(head) | {w for w, _ in rest if w != "#num"}
        ing_set = set(ing)

        # The ingredient's "noun" is usually its final word; the rest are modifiers.
        noun = ing[-1]
        modifiers = ing[:-1]

        # --- Core identity account ---
        head_set = set(head)
        if _satisfies(noun, head_set):
            core = 4.0
        elif _satisfies(noun, supply_all):
            core = 2.0
        else:
            core = -3.0

        # The USDA head must also not be a *different* food that the ingredient
        # merely mentions as a modifier (e.g. 'hazelnut' -> 'Oil, hazelnut').
        head_unrequested = [h for h in head if h not in _NEUTRAL and not _satisfies(h, ing_set)]
        head_debit = 0.0
        for h in head_unrequested:
            head_debit += _LOUD.get(h, 1.5) * 1.4

        # --- Demand account: ingredient modifiers ---
        credit = 0.0
        unmet = 0.0
        for m in modifiers:
            if _satisfies(m, supply_all):
                credit += 1.3
            else:
                unmet += _LOUD.get(m, 1.0)

        # --- Supply account: USDA descriptors not requested ---
        extra = 0.0
        seen = set()
        nums = 0
        for w, seg_idx in rest:
            if w == "#num":
                nums += 1
                continue
            if w in seen or w in _NEUTRAL or len(w) < 2:
                continue
            seen.add(w)
            if _satisfies(w, ing_set):
                continue
            weight = _LOUD.get(w, 0.7)
            # Deeper descriptors in USDA naming tend to be finer-grained variants.
            weight *= 1.0 + 0.12 * min(seg_idx - 1, 4)
            extra += weight
        # Numeric specs (e.g. '1% milkfat') are a strong specificity marker.
        extra += 1.2 * min(nums, 2)

        # Specificity ratio: how many non-neutral descriptor segments vs demands.
        n_desc_segs = len({i for w, i in rest if w not in _NEUTRAL})
        n_demands = max(len(modifiers), 0)
        gap = max(0, n_desc_segs - n_demands - 1)
        gap_penalty = 0.8 * gap

        raw = 5.0 + core + credit - 0.9 * unmet - 0.75 * extra - head_debit - gap_penalty
        score = max(0.0, min(10.0, raw))
        return round(score, 3)
    except Exception:
        return 0.0
