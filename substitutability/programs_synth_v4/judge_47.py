import re
import math

_GENERIC_LEADS = {
    "nuts", "spices", "beverages", "cereal", "cereals", "bread", "cheese", "beef",
    "pork", "lamb", "veal", "chicken", "turkey", "fish", "candies", "snacks",
    "soup", "soups", "sauce", "sauces", "fast", "babyfood", "infant", "game",
    "crustaceans", "mollusks", "oil", "vegetables", "fruit", "fruits", "yogurt",
    "milk", "cream", "egg", "eggs", "seeds", "beans", "peas", "rice", "pasta",
}

_PREP = {
    "fresh", "frozen", "thawed", "dried", "dry", "raw", "cooked", "chopped",
    "minced", "sliced", "diced", "ground", "canned", "crumbled", "trimmed",
    "foraged", "wild", "crispy", "lean", "whole", "large", "small", "medium",
    "organic", "finely", "roughly", "peeled", "boiled", "braised", "baked",
    "roasted", "grated", "shredded", "into", "and", "or", "the", "a", "of",
    "with", "from", "for", "in", "to", "soft", "plain", "creamed",
}

# Words that, when they follow a food in the lead segment, turn it into a modifier
_CARRIER = {
    "milk", "soup", "pie", "juice", "sauce", "bread", "cake", "muffin", "jam",
    "jelly", "butter", "oil", "flavored", "flavor", "drink", "beverage", "candy",
    "bar", "bars", "cookie", "cookies", "cereal", "dressing", "paste", "spread",
    "syrup", "chips", "crackers", "puree", "filling", "tart", "pudding", "ice",
    "yogurt", "cheese", "salad", "stew", "casserole", "sandwich", "pizza",
    "nectar", "mix", "powder", "extract", "zest", "peel", "tea", "wine",
}


def _norm(word):
    w = word.lower()
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            return w[: -len(suf)]
    return w


def _tokens(text):
    return re.findall(r"[a-z]+", text.lower())


def _similar(a, b):
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.85
    # common prefix ratio
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    if n >= 5:
        return 0.6
    return 0.0


def _clean_ingredient(ingredient):
    s = ingredient.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.split(",")[0]
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|grams?)\b", " ", s)
    s = re.sub(r"\d+", " ", s)
    return [_norm(t) for t in _tokens(s) if t not in _PREP and len(t) > 1]


def judging_function(ingredient, usda_match):
    try:
        if not isinstance(ingredient, str) or not isinstance(usda_match, str):
            return 0.0
        ing = _clean_ingredient(ingredient)
        if not ing or not usda_match.strip():
            return 0.0

        head = ing[-1]               # the noun at the end is typically the food
        mods = ing[:-1]

        segments = [seg.strip() for seg in re.sub(r"\([^)]*\)", " ", usda_match).split(",")]
        segments = [seg for seg in segments if seg]
        if not segments:
            return 0.0
        seg_toks = [[_norm(t) for t in _tokens(seg)] for seg in segments]

        # Locate the best position of the ingredient head in USDA segments.
        best_seg, best_pos, best_sim = None, None, 0.0
        for si, toks in enumerate(seg_toks):
            for ti, t in enumerate(toks):
                sim = _similar(head, t)
                if sim > best_sim:
                    best_sim, best_seg, best_pos = sim, si, ti

        score = 0.0
        lead_toks = seg_toks[0]
        lead_is_generic = len(lead_toks) == 1 and lead_toks[0] in {_norm(g) for g in _GENERIC_LEADS}

        if best_seg is None:
            # Head food absent: check whether any modifier word leads instead.
            mod_hit = 0.0
            for m in mods:
                for t in lead_toks:
                    mod_hit = max(mod_hit, _similar(m, t))
            score = 15.0 + 10.0 * mod_hit
        else:
            effective_seg = best_seg
            if lead_is_generic and best_seg > 0:
                # "Nuts, hazelnuts" / "Beef, steak, sirloin": category prefix; the
                # first specific segment is the real head.
                effective_seg = best_seg - 1
            pos_weight = math.exp(-0.9 * effective_seg)
            score = 40.0 + 45.0 * pos_weight * best_sim

            toks = seg_toks[best_seg]
            # Demotion: head food followed by a carrier noun in the same segment.
            trailing = toks[best_pos + 1:]
            if any(t in _CARRIER or _norm(t) in _CARRIER for t in trailing):
                if not any(_similar(c, t) > 0.8 for c in trailing for c in [head]):
                    carrier_in_ing = any(t in _CARRIER for t in ing)
                    if not carrier_in_ing:
                        score -= 25.0
            # Head appears only in a later descriptor while lead is another specific food
            if best_seg > 0 and not lead_is_generic:
                lead_overlap = max((_similar(i, t) for i in ing for t in lead_toks), default=0.0)
                if lead_overlap < 0.5:
                    score -= 15.0 * min(best_seg, 2)

            # Modifier support: ingredient modifiers found anywhere earn a little.
            all_toks = [t for toks2 in seg_toks for t in toks2]
            if mods:
                support = sum(max((_similar(m, t) for t in all_toks), default=0.0) for m in mods) / len(mods)
                score += 10.0 * support - 3.0

        # Ingredient's own form words that indicate a derived product (zest, chips, paste)
        derived = {"zest", "chip", "crumb", "paste", "peel", "juice", "flake"}
        if head in derived and best_seg is not None and best_sim < 0.8:
            score -= 10.0

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
