import re
import math

# Variant 8: "flavor-channel ledger" approach.
# Each side is projected onto a set of sensory channels (sweet, salty, fat,
# spicy/seasoned, sauce/compound, coating, smoke/cure, flavoring, cooking-state).
# The score is driven by channels the USDA entry ADDS that the ingredient does
# not request, weighted by how perceptible each channel is to a diner, with
# explicit "plain" assertions (unsalted, unsweetened, plain, raw) acting as
# negative evidence that cancels channel activation. A soft trigram similarity
# on the head food anchors the score.

_CHANNELS = {
    "sweet": (3.0, ["sweetened", "sugar added", "with sugar", "syrup", "honey", "candied",
                    "glazed", "frosted", "sweet", "maple", "molasses", "caramel", "chocolate"]),
    "salty": (2.2, ["salted", "with salt", "salt added", "brine", "brined", "pickled",
                    "salt and pepper", "soy", "teriyaki"]),
    "fat": (2.0, ["fried", "in oil", "with oil", "oil-packed", "packed in oil", "buttered",
                  "with butter", "with margarine", "creamed", "with cream", "fat added"]),
    "seasoned": (2.6, ["seasoned", "spiced", "seasoning", "herbed", "with herbs", "pepper",
                       "garlic", "onion", "spicy", "hot", "chili", "cajun", "barbecue", "bbq",
                       "ranch", "lemon pepper", "curry"]),
    "compound": (3.2, ["sauce", "gravy", "dressing", "dip", "spread", "mix", "prepared",
                       "with ", "and ", "stuffed", "filled", "patty", "meal", "dinner",
                       "entree", "casserole", "soup", "salad", "sandwich"]),
    "coating": (2.8, ["breaded", "battered", "coated", "crumbs", "tempura"]),
    "cured": (2.4, ["smoked", "cured", "dried", "jerky", "kippered"]),
    "flavored": (2.5, ["flavored", "flavor", "vanilla", "strawberry", "cinnamon",
                       "artificial", "imitation", "fruit"]),
}

_PLAIN_MARKERS = {
    "sweet": ["unsweetened", "no sugar", "without sugar", "sugar free", "sugar-free"],
    "salty": ["unsalted", "without salt", "no salt", "low sodium", "salt-free"],
    "fat": ["without added fat", "no fat added", "dry roasted", "without oil"],
    "seasoned": ["unseasoned", "plain"],
    "compound": ["plain", "regular"],
    "flavored": ["unflavored", "plain", "natural"],
    "coating": [],
    "cured": ["fresh", "raw"],
}

_UNITS = r"(?:g|kg|mg|ml|l|oz|lb|lbs|cup|cups|tbsp|tsp|tablespoons?|teaspoons?|grams?)"
_STOP = {"fresh", "raw", "large", "small", "medium", "chopped", "diced", "sliced", "cubed",
         "minced", "ground", "whole", "frozen", "thawed", "peeled", "of", "the", "a", "an",
         "and", "or", "to", "taste", "finely", "roughly", "for", "cut", "into", "pieces",
         "nfs", "ns", "as", "to", "eaten"}


def _norm(s):
    s = str(s or "").lower()
    s = re.sub(r"\(([^)]*)\)", r" \1 ", s)
    s = re.sub(r"^\s*\d+(?:[.,]\d+)?\s*" + _UNITS + r"?\b", " ", s)
    s = s.replace("é", "e").replace("è", "e")
    s = re.sub(r"[^a-z0-9,\- ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _has(text, phrase):
    if phrase.endswith(" "):
        return (" " + phrase) in (" " + text + " ")
    return re.search(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])", text) is not None


def _channels(text):
    active = {}
    for ch, (w, cues) in _CHANNELS.items():
        hits = [c for c in cues if _has(text, c)]
        plain = [p for p in _PLAIN_MARKERS.get(ch, []) if _has(text, p)]
        # "without salt" contains "salt"-ish cues; plain assertions cancel activation
        if ch == "salty" and any(_has(text, p) for p in _PLAIN_MARKERS["salty"]):
            hits = [h for h in hits if h not in ("with salt",)]
            hits = []
        if ch == "sweet" and plain:
            hits = []
        if hits and not plain:
            active[ch] = min(1.0, 0.6 + 0.2 * len(hits))
        elif hits and plain:
            active[ch] = 0.25
    return active


def _trigrams(word):
    w = "  " + word + " "
    return {w[i:i + 3] for i in range(len(w) - 2)}


def _head_similarity(ing, usda):
    ing_toks = [t for t in re.split(r"[ ,\-]+", ing) if t and t not in _STOP and not t.isdigit()]
    segs = [s.strip() for s in usda.split(",") if s.strip()]
    if not ing_toks or not segs:
        return 0.0
    usda_toks = [t for t in re.split(r"[ ,\-]+", usda) if t and t not in _STOP]
    head = segs[0]
    best_all = []
    for t in ing_toks:
        tg = _trigrams(t.rstrip("s"))
        best = 0.0
        for u in usda_toks:
            ug = _trigrams(u.rstrip("s"))
            inter = len(tg & ug)
            if inter:
                j = inter / float(len(tg | ug))
                if u in head.split():
                    j *= 1.15
                best = max(best, j)
        best_all.append(min(best, 1.0))
    # emphasize last token of the ingredient (usually the head noun)
    weights = [1.0] * len(best_all)
    weights[-1] = 2.0
    return sum(b * w for b, w in zip(best_all, weights)) / sum(weights)


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient)
        usda = _norm(usda_match)
        if not ing or not usda:
            return 0.0

        ing_ch = _channels(ing)
        usda_ch = _channels(usda)

        # ledger of added components: perceptible additions the ingredient lacks
        added = 0.0
        for ch, level in usda_ch.items():
            w = _CHANNELS[ch][0]
            req = ing_ch.get(ch, 0.0)
            gap = max(0.0, level - req)
            added += w * gap
        # removed components (ingredient expects it, usda is plain) count less
        removed = 0.0
        for ch, level in ing_ch.items():
            gap = max(0.0, level - usda_ch.get(ch, 0.0))
            removed += 0.5 * _CHANNELS[ch][0] * gap

        # explicit plainness bonus in USDA when ingredient is plain too
        plain_bonus = 0.0
        for ch, markers in _PLAIN_MARKERS.items():
            if any(_has(usda, m) for m in markers) and ch not in ing_ch:
                plain_bonus += 0.4
        plain_bonus = min(plain_bonus, 1.2)

        # USDA descriptor count beyond the head: more qualifiers = more processing risk
        n_desc = max(0, len([s for s in usda.split(",") if s.strip()]) - 1)
        desc_pen = 0.35 * max(0, n_desc - 2)

        sim = _head_similarity(ing, usda)

        penalty = added + removed + desc_pen
        purity = math.exp(-penalty / 4.0)  # 1.0 when nothing added
        score = 10.0 * (0.55 * sim + 0.45 * purity) + plain_bonus
        if sim < 0.2:
            score *= 0.5
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
