import re
import math

# Variant 5: NOVA-style processing ladder + additive "flavor channel" vector comparison.
# Each text is projected onto a vector of taste-relevant additive channels and a
# processing tier (0 = whole/raw, 3 = ultra-processed / compound). The score is a
# weighted penalty on channels/tier that the USDA entry ADDS beyond the ingredient,
# gated by whether the core food noun is shared.

_CHANNELS = {
    "salt": ["salted", "salt added", "with salt", "brine", "brined", "cured", "corned", "pickled", "soy sauce", "teriyaki"],
    "sugar": ["sweetened", "sugar added", "with sugar", "candied", "glazed", "honey", "syrup", "frosted", "caramel", "sugared", "in heavy syrup", "in light syrup"],
    "fat": ["fried", "with oil", "in oil", "buttered", "with butter", "oil-roasted", "oil roasted", "creamed", "with cream", "batter-fried"],
    "coating": ["breaded", "battered", "coated", "crusted", "floured", "tempura"],
    "sauce": ["sauce", "gravy", "dressing", "in tomato", "marinated", "marinade", "with sauce", "condiment"],
    "season": ["seasoned", "spiced", "flavored", "flavoured", "and pepper", "herbed", "with herbs", "barbecue", "bbq", "ranch", "cajun", "chili-flavored", "garlic-flavored"],
    "smoke": ["smoked", "smoky"],
    "compound": ["with ", " and ", "mix", "mixture", "blend", "prepared", "dish", "casserole", "stuffed", "filled", "patty", "nuggets", "dinner", "entree", "imitation", "substitute", "ready-to-eat"],
}

_PLAIN_MARKERS = ["without salt", "no salt", "unsalted", "unsweetened", "plain", "raw", "unprepared",
                  "no added", "without added", "natural", "unseasoned", "drained", "boiled", "water pack"]

_TIER3 = ["patty", "nuggets", "loaf", "sausage", "frankfurter", "hot dog", "luncheon", "imitation", "snack", "chips", "candy", "frosted", "breaded", "fried", "dinner", "entree", "fast food"]
_TIER2 = ["smoked", "cured", "canned", "pickled", "salted", "sweetened", "seasoned", "dried", "roasted", "toasted", "sauce", "paste", "sugar", "juice"]
_TIER1 = ["cooked", "boiled", "steamed", "baked", "frozen", "ground", "chopped", "sliced", "flaked"]

_STOP = set("g kg mg ml l oz lb cup cups tbsp tsp tablespoon teaspoon of the a an fresh or and with to for from nfs ns raw cooked large small medium".split())


def _clean(s):
    s = (s or "").lower()
    s = re.sub(r"\(([^)]*)\)", r" \1 ", s)
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)?\b", " ", s)
    s = re.sub(r"[^a-z\-, ]", " ", s)
    return " " + re.sub(r"\s+", " ", s).strip() + " "


def _channels(text):
    vec = {}
    for ch, cues in _CHANNELS.items():
        hits = 0
        for c in cues:
            if c in text:
                hits += 1
        vec[ch] = hits
    return vec


def _tier(text):
    if any(w in text for w in _TIER3):
        return 3
    if any(w in text for w in _TIER2):
        return 2
    if any(w in text for w in _TIER1):
        return 1
    return 0


def _stem(w):
    w = w.strip("-")
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _content(text):
    return [_stem(w) for w in re.findall(r"[a-z]+", text) if w not in _STOP and len(w) > 2]


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usd = _clean(usda_match)
        if not ing.strip() or not usd.strip():
            return 0.0

        # --- core food anchor: primary USDA segment vs ingredient content words
        primary = _content(usd.split(",")[0])
        ing_words = set(_content(ing))
        usd_words = set(_content(usd))
        anchor = 0.0
        if primary:
            anchor = sum(1 for w in primary if w in ing_words) / float(len(primary))
        overall = len(ing_words & usd_words) / float(max(1, len(ing_words)))
        gate = 0.35 + 0.65 * max(anchor, overall)

        # --- additive channel deltas (only what USDA adds counts heavily)
        ci = _channels(ing)
        cu = _channels(usd)
        weights = {"salt": 1.2, "sugar": 1.6, "fat": 1.3, "coating": 2.0,
                   "sauce": 1.8, "season": 1.5, "smoke": 1.1, "compound": 0.8}
        added = 0.0
        missing = 0.0
        for ch, w in weights.items():
            d = cu[ch] - ci[ch]
            if d > 0:
                added += w * math.log1p(d)
            elif d < 0:
                missing += 0.4 * w * math.log1p(-d)

        # explicit plain markers on USDA side soften additive suspicion
        plain_bonus = sum(1 for m in _PLAIN_MARKERS if m in usd)
        added = max(0.0, added - 0.5 * plain_bonus)

        # --- processing tier gap
        ti, tu = _tier(ing), _tier(usd)
        tier_pen = 1.5 * max(0, tu - ti) + 0.5 * max(0, ti - tu)

        # --- compound ingredient on recipe side not reflected in USDA
        if re.search(r"\b(and|&)\b", ing.split(",")[0]) and not re.search(r"\band\b", usd):
            missing += 1.0

        penalty = added + missing + tier_pen
        base = 10.0 * math.exp(-0.35 * penalty)
        score = base * gate
        if plain_bonus and added == 0 and tu <= ti + 1:
            score += 0.5
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
