import re
import math

# Each form cue maps to a point in a 3-D "physical state" space:
#   (moisture 0..1, concentration 0..1, processing/handling 0..1)
_FORM_POINTS = {
    "fresh": (0.85, 0.2, 0.0), "raw": (0.85, 0.2, 0.0), "foraged": (0.85, 0.2, 0.0),
    "wild": (0.85, 0.2, 0.05), "ripe": (0.85, 0.2, 0.0),
    "frozen": (0.85, 0.2, 0.25), "thawed": (0.85, 0.2, 0.2), "unthawed": (0.85, 0.2, 0.25),
    "canned": (0.9, 0.25, 0.5), "tinned": (0.9, 0.25, 0.5), "jarred": (0.85, 0.3, 0.5),
    "drained": (0.8, 0.25, 0.45), "pickled": (0.85, 0.35, 0.6), "brined": (0.85, 0.35, 0.6),
    "in syrup": (0.9, 0.5, 0.55), "syrup": (0.9, 0.55, 0.55),
    "dried": (0.1, 0.8, 0.5), "dehydrated": (0.08, 0.85, 0.55), "sun-dried": (0.15, 0.75, 0.5),
    "freeze-dried": (0.05, 0.85, 0.6), "ground": (0.08, 0.85, 0.55),
    "powder": (0.05, 0.9, 0.6), "powdered": (0.05, 0.9, 0.6), "granules": (0.05, 0.9, 0.6),
    "flakes": (0.08, 0.8, 0.5), "leaf": (0.1, 0.7, 0.4), "leaves": (0.6, 0.4, 0.2),
    "paste": (0.45, 0.85, 0.6), "puree": (0.75, 0.5, 0.45), "pureed": (0.75, 0.5, 0.45),
    "concentrate": (0.4, 0.95, 0.65), "concentrated": (0.4, 0.95, 0.65),
    "condensed": (0.45, 0.9, 0.65), "evaporated": (0.6, 0.7, 0.6),
    "juice": (0.95, 0.35, 0.4), "extract": (0.5, 0.95, 0.7),
    "ready-to-serve": (0.95, 0.15, 0.7), "ready to serve": (0.95, 0.15, 0.7),
    "prepared": (0.8, 0.3, 0.6), "reconstituted": (0.9, 0.3, 0.6),
    "broth": (0.97, 0.1, 0.5), "stock": (0.97, 0.15, 0.5), "bouillon": (0.3, 0.9, 0.65),
    "soup": (0.9, 0.25, 0.7), "stew": (0.85, 0.3, 0.75),
    "cooked": (0.7, 0.3, 0.35), "boiled": (0.75, 0.25, 0.35), "steamed": (0.75, 0.25, 0.35),
    "roasted": (0.5, 0.45, 0.4), "smoked": (0.5, 0.5, 0.55), "cured": (0.45, 0.55, 0.6),
    "salted": (0.5, 0.5, 0.5), "hot": (0.95, 0.2, 0.4), "brewed": (0.97, 0.1, 0.4),
}

# Product-type nouns that represent composite dishes rather than raw ingredients.
_COMPOSITE = {"stew", "soup", "patty", "pie", "casserole", "sandwich", "dinner",
              "entree", "meal", "salad", "pizza", "burrito", "nuggets"}

_STOP = {"and", "or", "with", "of", "the", "a", "an", "in", "for", "from", "to", "type",
         "style", "only", "meat", "made", "fresh", "raw", "cooked", "frozen", "canned",
         "dried", "large", "small", "medium", "chopped", "sliced", "diced", "minced",
         "cubed", "thawed", "drained", "peeled", "whole", "tube", "salt", "without",
         "plain", "regular", "all", "other", "includes"}

_GRAM = re.compile(r"^\s*\d+(?:[.,]\d+)?\s*(?:g|kg|mg|ml|l|oz|lb|grams?)\b\.?", re.I)


def _clean(text):
    t = str(text or "").lower()
    t = _GRAM.sub(" ", t)
    t = t.replace("_", " ")
    return t


def _forms(text):
    t = " " + re.sub(r"[^a-z\- ]", " ", text) + " "
    found = []
    # longest phrases first so "freeze-dried" wins over "dried"
    for key in sorted(_FORM_POINTS, key=len, reverse=True):
        pat = r"(?<![a-z\-])" + re.escape(key) + r"(?![a-z\-])"
        if re.search(pat, t):
            found.append(key)
            t = re.sub(pat, " ", t)
    return found


def _centroid(cues, default):
    if not cues:
        return default, 0
    xs = [_FORM_POINTS[c] for c in cues]
    n = float(len(xs))
    return tuple(sum(p[i] for p in xs) / n for i in range(3)), len(xs)


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _content(text):
    return {_stem(w) for w in re.findall(r"[a-z]{3,}", text) if w not in _STOP}


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0

        # Separate ingredient's post-comma state / parentheticals: they describe
        # recoverable transformations (thawed, from tube) rather than the purchase form.
        paren = " ".join(re.findall(r"\(([^)]*)\)", ing))
        ing_main = re.sub(r"\([^)]*\)", " ", ing)
        head_ing, _, tail_ing = ing_main.partition(",")

        usda_parts = [p.strip() for p in re.sub(r"\([^)]*\)", " ", usda).split(",")]
        usda_primary = usda_parts[0] if usda_parts else ""

        ing_cues = _forms(head_ing + " " + paren)
        tail_cues = _forms(tail_ing)
        usda_cues = _forms(usda)

        fresh_default = (0.85, 0.2, 0.0)
        ing_vec, n_ing = _centroid(ing_cues, fresh_default)
        usda_vec, n_usda = _centroid(usda_cues, fresh_default)

        # Recoverable transformations: "frozen X, thawed" ~ "X, frozen"
        if "thawed" in tail_cues and "frozen" in usda_cues:
            ing_vec = _FORM_POINTS["frozen"]
        if "drained" in tail_cues and any(c in usda_cues for c in ("canned", "drained")):
            ing_vec = _FORM_POINTS["canned"]

        # Weighted Euclidean distance in state space: moisture & concentration
        # changes matter most (they change the dish), handling slightly less.
        w = (1.4, 1.2, 0.6)
        dist = math.sqrt(sum(w[i] * (ing_vec[i] - usda_vec[i]) ** 2 for i in range(3)))
        max_dist = math.sqrt(sum(w))
        form_sim = 1.0 - min(1.0, dist / (max_dist * 0.6))

        # Exact shared cues boost confidence
        shared = set(ing_cues + tail_cues) & set(usda_cues)
        form_sim += 0.08 * len(shared)

        # Penalty when USDA describes a composite dish but the ingredient doesn't.
        usda_words = set(re.findall(r"[a-z]+", usda))
        ing_words = set(re.findall(r"[a-z]+", ing))
        composite_hit = (usda_words & _COMPOSITE) - ing_words
        primary_words = set(re.findall(r"[a-z]+", usda_primary))
        if composite_hit:
            form_sim -= 0.45 if (composite_hit & primary_words) else 0.25
        # Ingredient names a composite word, but USDA uses it as primary dish
        # for a different role (e.g. "stew meat" vs "Stew, beef").
        if (ing_words & primary_words & _COMPOSITE) and len(usda_parts) > 1:
            if not any(_stem(x) in _content(usda) for x in ("meat",)) and "meat" in ing_words:
                form_sim -= 0.35

        # Beverage form check: "hot/brewed" in USDA vs dry ingredient e.g. tea leaves
        if ("hot" in usda_cues or "brewed" in usda_cues) and not (set(ing_cues) & {"hot", "brewed"}):
            form_sim -= 0.2
        if "decaffeinated" in usda_words and "decaffeinated" not in ing_words:
            form_sim -= 0.15

        # Identity anchor: forms only matter if it is plausibly the same food.
        ic, uc = _content(ing_main + " " + paren), _content(usda)
        if ic and uc:
            overlap = len(ic & uc) / float(len(ic))
            prim_hit = bool(ic & _content(usda_primary))
        else:
            overlap, prim_hit = 0.0, False
        identity = 0.35 + 0.45 * overlap + (0.2 if prim_hit else 0.0)

        # Extra USDA descriptors in a multi-part name hint at a more specific
        # (possibly different) cut/part; slight penalty per extra unmatched form cue.
        extra = len(set(usda_cues) - set(ing_cues) - set(tail_cues))
        form_sim -= 0.04 * max(0, extra - 1)

        form_sim = max(0.0, min(1.2, form_sim))
        score = 100.0 * (0.65 * form_sim / 1.2 + 0.35 * identity) * (0.6 + 0.4 * identity)
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
