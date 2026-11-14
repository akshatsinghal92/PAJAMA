import re

# Variant 2: category-ledger approach. Each side is mapped to a set of
# "processing/additive categories". The score starts from an identity-anchor
# base and then subtracts weighted penalties for categories the USDA entry
# introduces that the ingredient does not mention (asymmetric difference),
# plus smaller penalties for form/state category conflicts.

_CATEGORIES = {
    "salt": (["salted", "salt", "brine", "brined", "pickled", "cured", "corned"], 2.0),
    "sugar": (["sweetened", "sugar", "sugared", "candied", "syrup", "honey", "glazed",
               "frosted", "candies", "candy", "confectioner", "coating"], 2.2),
    "fat": (["oil", "fried", "buttered", "butter", "roasted in oil", "oil roasted",
             "margarine", "lard", "palm"], 1.8),
    "sauce": (["sauce", "gravy", "dressing", "marinade", "marinated", "in sauce", "ketchup"], 2.4),
    "breading": (["breaded", "battered", "coated", "crumbs", "tempura"], 2.4),
    "seasoning": (["seasoned", "spiced", "pepper", "herbs", "flavored", "flavor", "smoked",
                   "barbecue", "bbq", "seasoning"], 1.6),
    "compound": (["patty", "nuggets", "sticks", "casserole", "soup", "pie", "mix",
                  "with", "and", "dish", "sandwich", "salad", "stew", "frozen yogurt",
                  "plus", "fortified", "enriched", "drink", "beverage", "soymilk"], 1.4),
    "dried": (["dried", "dehydrated", "powder", "powdered", "dry"], 1.5),
    "canned": (["canned", "drained", "solids"], 1.0),
    "reduced": (["lowfat", "nonfat", "reduced", "light", "lite", "skim", "lactose",
                 "fat free", "low sodium", "diet"], 1.0),
}

_NEUTRAL_USDA = {
    "raw", "nfs", "ns", "fresh", "regular", "plain", "unprepared", "whole", "choice",
    "select", "separable", "lean", "fat", "boneless", "trimmed", "frozen", "or",
    "to", "as", "of", "major", "type", "unsweetened", "without", "unsalted", "the",
}

_STOP = {"a", "an", "the", "of", "for", "and", "or", "with", "to", "in", "on", "from",
         "fresh", "large", "small", "medium", "chopped", "sliced", "diced", "minced",
         "cubed", "thawed", "sifted", "trimmed", "visible", "skin", "leaves", "bagged",
         "high", "into", "cut", "peeled"}

_NEGATORS = ("without", "unsweetened", "unsalted", "no added", "not")


def _clean(s):
    s = str(s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)\b", " ", s)
    s = s.replace("'", "")
    s = re.sub(r"[^a-z0-9,\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _words(s):
    return [_stem(w) for w in re.findall(r"[a-z]+", s)]


def _categories(text, negate=False):
    found = set()
    padded = " " + text.replace(",", " , ") + " "
    for cat, (terms, _w) in _CATEGORIES.items():
        for t in terms:
            for m in re.finditer(r"(?<![a-z])" + re.escape(t) + r"(?![a-z])", padded):
                if negate:
                    pre = padded[max(0, m.start() - 14): m.start()]
                    if any(n in pre for n in _NEGATORS):
                        continue
                    if t in ("unsweetened",):
                        continue
                found.add(cat)
                break
            if cat in found:
                break
    return found


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing or not usda:
            return 0.0

        ing_main = ing.split(",")[0]
        ing_words = [w for w in _words(ing) if w not in _STOP and len(w) > 2]
        main_words = [w for w in _words(ing_main) if w not in _STOP and len(w) > 2]
        usda_words = [w for w in _words(usda) if len(w) > 2]
        usda_set = set(usda_words)
        primary = usda.split(",")[0]
        primary_words = set(w for w in _words(primary) if len(w) > 2)

        # --- identity anchor: does the ingredient's head noun appear in USDA? ---
        head = main_words[-1] if main_words else ""
        anchor = 0.0
        if head and head in usda_set:
            anchor = 4.0
        elif head and any(head[:5] == u[:5] and len(head) >= 5 for u in usda_set):
            anchor = 3.0
        hits = sum(1 for w in set(ing_words) if w in usda_set)
        cover = hits / max(1, len(set(ing_words)))
        anchor += 3.0 * cover
        # USDA primary food must be tied to the ingredient somehow
        if primary_words and not (primary_words & set(ing_words)):
            anchor -= 1.5
        if hits == 0:
            anchor -= 2.0

        # --- processing/additive ledger ---
        ing_cats = _categories(ing)
        usda_cats = _categories(usda, negate=True)
        introduced = usda_cats - ing_cats
        dropped = ing_cats - usda_cats
        penalty = 0.0
        for c in introduced:
            w = _CATEGORIES[c][1]
            # flavors that the ingredient explicitly asked for are not additions
            penalty += w
        for c in dropped:
            penalty += 0.6 * _CATEGORIES[c][1]

        # extra unexplained descriptors in USDA (beyond neutral words) add mild noise
        extra = [w for w in usda_words if w not in set(ing_words) and w not in _NEUTRAL_USDA
                 and w not in primary_words]
        penalty += min(1.5, 0.15 * len(extra))

        # reward plain-for-plain: neither side carries additives
        bonus = 0.0
        if not usda_cats and not ing_cats:
            bonus += 1.5
        if "raw" in usda_set and not ing_cats:
            bonus += 0.5

        score = 3.0 + anchor + bonus - penalty
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
