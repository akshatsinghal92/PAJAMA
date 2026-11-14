import re
import math

# Additive / compound-ingredient families, each with a "taste impact" weight.
_ADDITIVE_FAMILIES = {
    "salt": (2.0, ["salt", "salted", "brine", "brined", "sodium", "cured", "corned"]),
    "sugar": (2.0, ["sugar", "sweetened", "sweet", "honey", "syrup", "candied", "glazed",
                    "frosted", "caramel", "molasses", "sugared"]),
    "fat": (1.5, ["oil", "butter", "buttered", "fried", "lard", "margarine", "shortening",
                  "creamed", "cream"]),
    "sauce": (2.5, ["sauce", "gravy", "dressing", "marinade", "marinated", "ketchup",
                    "mayonnaise", "salsa", "teriyaki", "barbecue", "bbq"]),
    "coating": (2.5, ["breaded", "battered", "breading", "batter", "coated", "crusted",
                      "tempura"]),
    "seasoning": (2.0, ["seasoned", "seasoning", "spiced", "pepper", "herb", "herbs",
                        "garlic", "onion", "flavored", "flavor", "smoked", "spicy"]),
    "compound": (2.0, ["with", "and", "mix", "mixed", "blend", "prepared", "dinner",
                       "entree", "meal", "filled", "stuffed", "added"]),
    "reformed": (2.5, ["formed", "chopped and formed", "restructured", "imitation",
                       "patty", "patties", "nuggets", "loaf", "substitute", "analog"]),
}

# Processing intensity ladder (ordinal).
_PROCESS_LEVELS = [
    (0, ["raw", "fresh", "plain", "unprepared", "uncooked", "whole", "dry", "dried"]),
    (1, ["frozen", "thawed", "chilled", "cold", "cubed", "sliced", "chopped", "diced",
         "ground", "crumbled", "brewed", "leaf"]),
    (2, ["cooked", "boiled", "steamed", "baked", "roasted", "broiled", "grilled",
         "braised", "simmered", "stewed", "toasted", "pan-broiled", "heated", "hot"]),
    (3, ["canned", "jarred", "pickled", "dehydrated", "instant", "concentrate",
         "reconstituted", "powdered", "paste", "puree"]),
    (4, ["fried", "breaded", "smoked", "cured", "processed", "formed", "jerky"]),
]

_STOP = {"g", "kg", "ml", "of", "the", "a", "an", "for", "from", "to", "in", "or",
         "ns", "nfs", "as", "by", "tube", "about", "approx"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb)?\b", " ", t)
    t = re.sub(r"\d+(\.\d+)?\s*%", " ", t)
    t = re.sub(r"[^a-z\- ,]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _words(text):
    out = []
    for w in re.split(r"[ ,]+", text):
        w = w.strip("-")
        if len(w) > 1 and w not in _STOP:
            out.append(w)
    return out


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _families(text, words):
    found = {}
    wset = set(words)
    for fam, (weight, cues) in _ADDITIVE_FAMILIES.items():
        hits = 0
        for c in cues:
            if " " in c:
                if c in text:
                    hits += 1
            elif c in wset:
                hits += 1
        if hits:
            found[fam] = (weight, hits)
    return found


def _process_level(words):
    wset = set(words)
    level = None
    for lvl, cues in _PROCESS_LEVELS:
        if any(c in wset for c in cues):
            level = lvl if level is None else max(level, lvl)
    return level


def judging_function(ingredient, usda_match):
    try:
        ing_raw = _clean(ingredient)
        usda_raw = _clean(usda_match)
        if not ing_raw or not usda_raw:
            return 0.0

        ing_w = _words(ing_raw)
        usda_w = _words(usda_raw)
        if not ing_w or not usda_w:
            return 0.0

        # --- 1. Additive asymmetry: components in USDA that the ingredient lacks.
        ing_f = _families(ing_raw, ing_w)
        usda_f = _families(usda_raw, usda_w)
        extra_penalty = 0.0
        for fam, (weight, hits) in usda_f.items():
            if fam not in ing_f:
                extra_penalty += weight * (1.0 + 0.25 * (hits - 1))
        # Reverse direction (ingredient has additive the USDA plain entry lacks) matters less.
        missing_penalty = 0.0
        for fam, (weight, hits) in ing_f.items():
            if fam not in usda_f:
                missing_penalty += 0.4 * weight

        # Explicit "plain"/"unsweetened"/"unsalted" signals in USDA reward plainness.
        plain_bonus = 0.0
        for cue in ("plain", "unsweetened", "unsalted", "without salt", "no salt", "raw"):
            if cue in usda_raw:
                plain_bonus += 0.6
        # But if the ingredient itself is flavored/sweetened, "plain" is a mismatch.
        if ("sugar" in ing_f or "seasoning" in ing_f) and "plain" in usda_raw:
            plain_bonus -= 1.2

        # --- 2. Processing level gap.
        li = _process_level(ing_w)
        lu = _process_level(usda_w)
        if li is None:
            li = 0
        if lu is None:
            lu = 0
        gap = lu - li
        process_penalty = 1.2 * max(0, gap) + 0.5 * max(0, -gap)

        # --- 3. Core-food anchor: plain-for-plain only counts if it is the same food.
        ing_s = {_stem(w) for w in ing_w}
        usda_s = [_stem(w) for w in usda_w]
        primary = usda_s[0] if usda_s else ""
        shared = ing_s.intersection(usda_s)
        anchor = len(shared) / float(max(1, min(len(ing_s), 4)))
        anchor = min(1.0, anchor)
        if primary and primary in ing_s:
            anchor = min(1.0, anchor + 0.3)
        # Count unexplained USDA descriptors (non-shared words) as mild extra components.
        unexplained = [w for w in usda_s if w not in ing_s]
        clutter = math.log1p(max(0, len(unexplained) - 2)) * 0.5

        # --- Combine: start at 10, subtract penalties, then scale by anchor.
        raw_score = 10.0 - extra_penalty - missing_penalty - process_penalty - clutter + plain_bonus
        raw_score = max(0.0, min(10.0, raw_score))
        score = raw_score * (0.45 + 0.55 * anchor)
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
