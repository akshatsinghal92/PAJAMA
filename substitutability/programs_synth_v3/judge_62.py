import re

# NOVA-inspired processing tiers: each lexical cue maps to a processing level.
# 0 = unprocessed/minimal, 1 = culinary ingredient / light processing,
# 2 = processed (salted, cured, canned in syrup), 3 = ultra-processed / compound dish.
_TIER_CUES = {
    0: ["raw", "fresh", "plain", "whole", "unsalted", "unsweetened", "unenriched",
        "lean", "boneless", "trimmed", "separable", "variety meats", "by-products",
        "frozen", "thawed", "chilled", "skinless", "dried", "dry"],
    1: ["ground", "chopped", "sliced", "diced", "minced", "flour", "oil", "butter",
        "boiled", "steamed", "baked", "roasted", "cooked", "grilled", "broiled"],
    2: ["salted", "salt added", "with salt", "cured", "smoked", "pickled", "brined",
        "canned", "in syrup", "heavy syrup", "light syrup", "sweetened", "sugar",
        "marinated", "seasoned", "corned", "kippered", "fried", "candied",
        "may contain additives", "additives", "enhanced", "solution", "glazed",
        "honey", "flavored", "spiced"],
    3: ["sausage", "frankfurter", "hot dog", "bologna", "salami", "nugget", "patty",
        "breaded", "battered", "sauce", "gravy", "dressing", "spread", "dip",
        "soup", "stew", "casserole", "sandwich", "pie", "pizza", "mix", "blend",
        "imitation", "loaf", "luncheon", "meatball", "merguez", "chorizo",
        "pudding", "paste", "puree", "jam", "jelly", "fast food", "restaurant",
        "frozen meal", "entree", "dinner", "sauerkraut", "stuffed", "prepared"],
}

_COMPOUND_JOINERS = re.compile(r"\b(and|with|in|w/|plus|&)\b")
_GRAM = re.compile(r"^\s*\d+(?:\.\d+)?\s*(?:g|kg|mg|ml|l|oz|lb)\b\.?", re.I)
_PAREN = re.compile(r"\([^)]*\)")


def _clean(text):
    text = (text or "").lower()
    text = _GRAM.sub(" ", text)
    return text


def _tier_profile(text):
    """Return (max_tier, set_of_tier>=2 cues) found in text."""
    hits = {}
    for tier, cues in _TIER_CUES.items():
        for cue in cues:
            if re.search(r"\b" + re.escape(cue) + r"(?:s|es)?\b", text):
                hits[cue] = tier
    max_tier = max([t for t in hits.values()] + [0])
    heavy = {c for c, t in hits.items() if t >= 2}
    return max_tier, heavy, hits


def _content_words(text):
    words = re.findall(r"[a-z]+", text)
    stop = {"and", "or", "with", "the", "a", "of", "for", "in", "to", "from",
            "raw", "fresh", "plain", "cooked", "frozen", "thawed", "serving",
            "garnish", "boneless", "skinless", "whole", "sliced", "chopped"}
    out = set()
    for w in words:
        if w in stop or len(w) < 3:
            continue
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("es") and len(w) > 4 and w[-3] in "shxo":
            w = w[:-2]
        elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            w = w[:-1]
        out.add(w)
    return out


def judging_function(ingredient, usda_match):
    try:
        ing_full = _clean(ingredient)
        usda_full = (usda_match or "").lower()
        if not ing_full.strip() or not usda_full.strip():
            return 0.0

        # Parenthetical notes on the ingredient are mostly serving notes;
        # on the USDA side they can declare additives, so keep them there.
        ing_core = _PAREN.sub(" ", ing_full)
        ing_core = ing_core.split(",")[0]

        ing_tier, ing_heavy, _ = _tier_profile(ing_core)
        usda_tier, usda_heavy, _ = _tier_profile(usda_full)

        # Start from a neutral plain-for-plain baseline.
        score = 60.0

        # 1. Tier gap: processing introduced by USDA beyond the ingredient.
        gap = usda_tier - ing_tier
        if gap > 0:
            score -= 14.0 * gap * gap ** 0.5  # superlinear penalty
        elif gap < 0:
            # ingredient is more processed than USDA (e.g. sausage vs raw cut)
            score -= 11.0 * (-gap) ** 1.3

        # 2. Additive cues present on USDA but absent from ingredient.
        introduced = {c for c in usda_heavy
                      if not re.search(r"\b" + re.escape(c.split()[0]), ing_core)}
        missing = {c for c in ing_heavy
                   if not re.search(r"\b" + re.escape(c.split()[0]), usda_full)}
        score -= 7.0 * len(introduced)
        score -= 6.0 * len(missing)

        # 3. Compound-food detection: joiners mean multiple components.
        usda_primary = usda_full.split(",")[0]
        ing_joins = len(_COMPOUND_JOINERS.findall(ing_core))
        usda_joins = len(_COMPOUND_JOINERS.findall(usda_primary))
        if usda_joins > ing_joins:
            score -= 15.0 * (usda_joins - ing_joins)
        elif ing_joins > usda_joins:
            score -= 12.0 * (ing_joins - usda_joins)

        # 4. Explicit plainness bonus.
        if usda_tier == 0 and re.search(r"\braw\b", usda_full) and ing_tier <= 1:
            score += 10.0
        if usda_tier == 0 and ing_tier == 0:
            score += 6.0

        # 5. Identity anchor: the processing judgment only matters if the
        # USDA primary food relates to the ingredient at all.
        ing_words = _content_words(ing_core)
        usda_words = _content_words(usda_full)
        prim_words = _content_words(usda_full.split(",")[0])
        if ing_words:
            shared = ing_words & usda_words
            cover = len(shared) / float(len(ing_words))
            prim_hit = bool(ing_words & prim_words)
            score += 18.0 * cover - 6.0
            if not prim_hit:
                score -= 12.0
            if not shared:
                score -= 15.0

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
