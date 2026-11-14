import re

# Qualifier-ledger approach: build a ledger of "noticeable" qualifiers on each side,
# reconcile them against each other, and score based on the balance of the ledger
# (qualifiers added by USDA, qualifiers dropped from the ingredient) once the
# core food identity is anchored.

_NEUTRAL = {
    "raw", "fresh", "uncooked", "all", "varieties", "variety", "ns", "as", "to",
    "major", "flour", "type", "regular", "plain", "commercial", "prepared",
    "imported", "domesticated", "new", "zealand", "australian", "us", "usda",
    "broilers", "fryers", "or", "and", "of", "with", "without", "the", "a", "an",
    "meats", "by", "products", "made", "from", "includes", "include", "edible",
    "portion", "solids", "liquids", "mature", "seeds", "seed", "boneless",
    "separable", "only", "trimmed", "retail", "cuts", "composite", "unenriched",
    "enriched", "unprepared", "ready", "eat", "store", "brand", "generic",
}

_PREP = {
    "chopped", "diced", "sliced", "minced", "cubed", "shredded", "grated",
    "thawed", "peeled", "halved", "quartered", "crushed", "torn", "trimmed",
    "rinsed", "drained", "softened", "melted", "beaten", "divided", "optional",
    "leftover", "large", "small", "medium", "finely", "roughly", "thinly",
    "cut", "into", "pieces", "for", "serving", "garnish", "taste", "about",
    "whole", "fresh", "packed", "loosely", "firmly", "room", "temperature",
}

# Qualifiers a diner would notice if added or dropped.
_NOTICEABLE = {
    "smoked", "cured", "salted", "unsalted", "sweetened", "unsweetened",
    "low", "reduced", "fat", "free", "nonfat", "lowfat", "lite", "light",
    "sodium", "sugar", "diet", "flavored", "seasoned", "spiced", "breaded",
    "battered", "fried", "roasted", "toasted", "grilled", "baked", "boiled",
    "steamed", "braised", "stewed", "cooked", "canned", "frozen", "dried",
    "dehydrated", "pickled", "marinated", "processed", "process", "pasteurized",
    "creamed", "cream", "style", "extra", "virgin", "skin", "skinless",
    "lean", "ground", "powder", "paste", "sauce", "juice", "concentrate",
    "syrup", "instant", "whole", "wheat", "grain", "white", "brown", "red",
    "green", "yellow", "black", "sweet", "sour", "hot", "mild", "spicy",
    "chocolate", "vanilla", "strawberry", "banana", "nut", "honey", "vegetables",
    "fruit", "cheese", "tomato", "garlic", "onion", "mountain", "hawaii",
    "split", "seeds", "leaves", "chop", "neck", "liver", "kidney", "heart",
    "tongue", "giblets", "breast", "thigh", "wing", "leg", "shank", "patty",
    "steak", "sirloin", "flank", "merguez", "sausage", "ham", "bacon",
}

_UNITS = r"(?:g|gr|grams?|kg|mg|ml|l|oz|lb|lbs|cups?|tbsp|tsp|tablespoons?|teaspoons?)"


def _stem(w):
    try:
        if len(w) > 4 and w.endswith("ies"):
            return w[:-3] + "y"
        if len(w) > 4 and w.endswith("oes"):
            return w[:-2]
        if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
            return w[:-2]
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            return w[:-1]
    except Exception:
        pass
    return w


def _words(s):
    return [_stem(w) for w in re.findall(r"[a-z]+", s.lower())]


def _parse_ingredient(text):
    t = (text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*[\d./]+\s*" + _UNITS + r"?\b", " ", t)
    head, _, tail = t.partition(",")
    head_w = [w for w in _words(head) if w not in _PREP or w in ("whole",)]
    tail_w = [w for w in _words(tail) if w not in _PREP]
    return head_w, tail_w


def _parse_usda(text):
    t = (text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    parts = [p.strip() for p in t.split(",") if p.strip()]
    if not parts:
        return [], []
    primary = _words(parts[0])
    desc = []
    for p in parts[1:]:
        desc.extend(_words(p))
    return primary, desc


def _is_noticeable(w):
    return w in _NOTICEABLE or (w not in _NEUTRAL and len(w) > 2)


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing_head, ing_tail = _parse_ingredient(ingredient)
        u_primary, u_desc = _parse_usda(usda_match)
        if not ing_head or not u_primary:
            return 0.0

        ing_set = set(ing_head) | set(ing_tail)
        u_all = set(u_primary) | set(u_desc)

        # Anchor: the ingredient head noun (last content word) should appear in USDA.
        content_head = [w for w in ing_head if w not in _NEUTRAL]
        if not content_head:
            content_head = ing_head
        head_noun = content_head[-1]
        anchor = 0.0
        if head_noun in u_all:
            anchor = 4.0
            if head_noun in u_primary:
                anchor += 1.0
        else:
            # partial anchor via prefix match (e.g. tamarind/tamarinds handled by stem)
            for w in u_all:
                if len(w) > 3 and len(head_noun) > 3 and (w.startswith(head_noun[:4]) or head_noun.startswith(w[:4])):
                    anchor = 2.0
                    break
        primary_hit = any(w in ing_set for w in u_primary if w not in _NEUTRAL)
        if primary_hit:
            anchor += 1.5

        # Ledger of noticeable qualifiers.
        ing_quals = {w for w in ing_set if w != head_noun and _is_noticeable(w)}
        u_quals = {w for w in (set(u_primary) | set(u_desc))
                   if w != head_noun and _is_noticeable(w) and w not in ing_set}
        # USDA primary words are category nouns (e.g. "Beef", "Chicken"); only treat
        # those as added qualifiers if they are explicitly noticeable.
        u_quals = {w for w in u_quals if w in _NOTICEABLE or w in set(u_desc)}

        matched = {w for w in ing_quals if w in u_all}
        dropped = ing_quals - matched
        added = u_quals

        # Weight: strongly-marked qualifiers (in _NOTICEABLE) cost more.
        def cost(ws, base_hi, base_lo):
            return sum(base_hi if w in _NOTICEABLE else base_lo for w in ws)

        penalty = cost(dropped, 1.6, 0.9) + cost(added, 1.3, 0.5)
        reward = 1.2 * len(matched)

        # Specificity bonus: unqualified ingredient + generic USDA (only neutral descriptors).
        generic_usda = all((w in _NEUTRAL or w in ing_set) for w in u_desc)
        if not ing_quals and generic_usda:
            reward += 2.0
        if ing_quals and not dropped:
            reward += 1.5

        if anchor == 0.0:
            score = 1.0 + 0.5 * reward - 0.5 * penalty
        else:
            score = anchor + reward - penalty
        score = max(0.0, min(10.0, score + 2.0))
        return round(score, 3)
    except Exception:
        return 0.0
