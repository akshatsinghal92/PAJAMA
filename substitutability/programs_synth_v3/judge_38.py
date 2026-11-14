import re
import math

# Variant 6: "qualifier ledger" approach.
# Every qualifier on either side is classified into a sensory category with a
# noticeability weight. Qualifiers are then reconciled pairwise: matched,
# added (USDA-only), dropped (ingredient-only), or conflicting (same category,
# different value). The final score is a logistic over a debit/credit balance.

_DEFAULT_STATES = {
    "raw", "fresh", "uncooked", "regular", "plain", "unprepared", "whole",
    "without", "salt", "added", "ns", "nfs", "as", "to", "form", "or", "and",
    "frozen", "unenriched", "enriched", "commercial", "commercially", "includes",
    "made", "with", "from", "the", "a", "of", "in", "all", "purpose", "type",
    "unheated", "solids", "liquids", "drained", "unsalted", "mature", "seeds",
    "usda", "commodity", "general", "retail", "store", "brand", "ready", "eat",
}

_PREP_WORDS = {
    "chopped", "diced", "minced", "sliced", "grated", "shredded", "peeled",
    "thawed", "softened", "melted", "beaten", "divided", "packed", "trimmed",
    "rinsed", "cubed", "halved", "quartered", "crushed", "julienned", "torn",
    "for", "frying", "serving", "garnish", "taste", "optional", "large",
    "small", "medium", "finely", "roughly", "coarsely", "thinly", "about",
    "plus", "more", "extra", "needed", "room", "temperature", "cut", "into",
    "pieces", "inch", "cups", "cup", "tbsp", "tsp", "g", "kg", "ml", "oz",
}

# category -> (weight, vocabulary). Weight = how noticeable a mismatch is.
_CATEGORIES = {
    "cooking": (2.2, {"cooked", "boiled", "baked", "roasted", "fried", "grilled",
                      "toasted", "steamed", "braised", "broiled", "stewed",
                      "microwaved", "sauteed", "smoked", "dried", "dehydrated",
                      "canned", "pickled", "cured", "prepared", "oil-roasted",
                      "dry-roasted", "blanched", "stir-fried", "breaded"}),
    "flavor": (2.5, {"sweetened", "unsweetened", "salted", "spiced", "honey",
                     "chocolate", "vanilla", "strawberry", "cinnamon", "garlic",
                     "barbecue", "bbq", "lemon", "lime", "orange", "maple",
                     "balsamic", "cider", "apple", "red", "white", "wine",
                     "malt", "rice", "flavored", "seasoned", "sugar"}),
    "fat": (1.6, {"lowfat", "low", "fat", "nonfat", "skim", "reduced", "lite",
                  "light", "fat-free", "full", "lean", "whole", "1%", "2%"}),
    "grade": (1.8, {"extra", "virgin", "refined", "unrefined", "high", "oleic",
                    "linoleic", "mid", "cold", "pressed", "organic"}),
    "part": (1.9, {"skin", "breast", "thigh", "wing", "leg", "drumstick",
                   "leaves", "leaf", "stem", "root", "seed", "kernel", "peel",
                   "juice", "zest", "pulp", "flesh", "meat", "fillet", "loin",
                   "giblets", "liver", "yolk", "egg"}),
    "form": (1.5, {"ground", "paste", "powder", "flakes", "flake", "puree",
                   "sauce", "syrup", "concentrate", "patty", "nuggets", "strips",
                   "sticks", "chips", "crumbs", "mix", "instant", "condensed",
                   "evaporated", "whipped", "spread", "bar", "crunch", "cereal",
                   "cereals"}),
    "dietary": (1.7, {"dairy-free", "vegan", "gluten-free", "soy", "almond",
                      "coconut", "oat", "nondairy", "imitation", "substitute",
                      "meatless", "decaffeinated", "sugar-free"}),
}

_WORD_TO_CAT = {}
for _cat, (_w, _vocab) in _CATEGORIES.items():
    for _v in _vocab:
        _WORD_TO_CAT.setdefault(_v, _cat)


def _stem(w):
    try:
        if len(w) > 4 and w.endswith("ies"):
            return w[:-3] + "y"
        if len(w) > 4 and w.endswith("es") and not w.endswith("ses"):
            return w[:-2]
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            return w[:-1]
    except Exception:
        pass
    return w


def _clean_ingredient(text):
    t = (text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.split(",")[0]
    t = re.sub(r"^\s*[\d./]+\s*(g|kg|ml|l|oz|lb|grams?)?\b", " ", t)
    t = re.sub(r"[^a-z0-9%\-\s]", " ", t)
    return [w for w in t.split() if w and w not in _PREP_WORDS and not w.isdigit()]


def _clean_usda(text):
    t = (text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    segments = [s.strip() for s in t.split(",") if s.strip()]
    out = []
    for i, seg in enumerate(segments):
        seg = re.sub(r"[^a-z0-9%\-\s]", " ", seg)
        words = [w for w in seg.split() if w]
        out.append((i, words))
    return out


def _segment_qualifiers(words):
    quals = []
    cores = []
    for w in words:
        cat = _WORD_TO_CAT.get(w) or _WORD_TO_CAT.get(_stem(w))
        if cat:
            quals.append((cat, _stem(w)))
        elif w not in _DEFAULT_STATES and len(w) > 2:
            cores.append(_stem(w))
    return quals, cores


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        if not str(ingredient).strip() or not str(usda_match).strip():
            return 0.0

        ing_words = _clean_ingredient(str(ingredient))
        if not ing_words:
            return 5.0
        ing_quals, ing_cores = _segment_qualifiers(ing_words)
        ing_core_set = set(ing_cores)
        ing_qual_set = set(v for _, v in ing_quals)
        ing_all = ing_core_set | ing_qual_set

        segs = _clean_usda(str(usda_match))
        if not segs:
            return 0.0

        usda_quals = []      # (cat, val, segment_index)
        usda_cores = []      # (val, segment_index)
        n_segments = len(segs)
        for idx, words in segs:
            q, c = _segment_qualifiers(words)
            usda_quals.extend((cat, v, idx) for cat, v in q)
            usda_cores.extend((v, idx) for v in c)

        usda_core_set = set(v for v, _ in usda_cores)
        usda_qual_vals = set(v for _, v, _ in usda_quals)
        usda_all = usda_core_set | usda_qual_vals

        credit = 0.0
        debit = 0.0

        # 1) Head-noun anchoring: the ingredient's core nouns must appear.
        if ing_core_set:
            anchored = ing_core_set & usda_all
            anchor_ratio = len(anchored) / float(len(ing_core_set))
            credit += 4.0 * anchor_ratio
            # Last ingredient core word is usually the head noun.
            head = ing_cores[-1]
            head_hit = [i for v, i in usda_cores if v == head]
            if head_hit:
                credit += 2.0 if min(head_hit) == 0 else 1.0
            elif head in usda_qual_vals:
                credit += 0.8
            else:
                debit += 2.5
        else:
            anchor_ratio = 1.0 if ing_qual_set & usda_all else 0.0
            credit += 2.0 * anchor_ratio

        # 2) Qualifier reconciliation by category.
        ing_by_cat = {}
        for cat, v in ing_quals:
            ing_by_cat.setdefault(cat, set()).add(v)
        usda_by_cat = {}
        for cat, v, idx in usda_quals:
            usda_by_cat.setdefault(cat, {})[v] = idx

        for cat in set(ing_by_cat) | set(usda_by_cat):
            weight = _CATEGORIES[cat][0]
            iv = ing_by_cat.get(cat, set())
            uv = set(usda_by_cat.get(cat, {}).keys())
            matched = iv & uv
            added = uv - iv - ing_core_set
            dropped = iv - uv - usda_core_set
            credit += weight * 0.9 * len(matched)
            if iv and uv and not matched and added and dropped:
                # Conflicting values in the same dimension (e.g. red wine vs balsamic).
                debit += weight * 1.6
            else:
                debit += weight * 0.75 * len(dropped)
                # Added qualifiers deeper in the description are less salient.
                for v in added:
                    idx = usda_by_cat[cat][v]
                    depth = 1.0 / (1.0 + 0.35 * max(0, idx - 1))
                    debit += weight * 0.65 * depth

        # 3) Unexplained extra core nouns in USDA (e.g. list of other foods).
        extra_cores = [v for v, i in usda_cores if v not in ing_all]
        extra_unique = set(extra_cores)
        if extra_unique:
            # Primary-segment extras are worse: they change the food identity.
            primary_extra = set(v for v, i in usda_cores if i == 0 and v not in ing_all)
            debit += 1.4 * len(primary_extra)
            debit += 0.45 * len(extra_unique - primary_extra)

        # 4) Ingredient core words that USDA dropped (lost specificity).
        lost = ing_core_set - usda_all
        if ing_core_set:
            debit += 1.2 * len(lost)

        # 5) Generality bonus: generic ingredient matched by short generic entry.
        ing_specificity = len(ing_quals) + max(0, len(ing_cores) - 1)
        usda_specificity = len(usda_quals) + max(0, len(extra_unique))
        gap = abs(usda_specificity - ing_specificity)
        credit += 1.5 * math.exp(-0.6 * gap)

        # 6) Enumeration penalty: USDA groups many alternatives ("X, Y, or Z").
        raw_usda = str(usda_match).lower()
        if re.search(r"\bor\b", raw_usda) and n_segments >= 3:
            debit += 0.8

        balance = credit - debit
        score = 10.0 / (1.0 + math.exp(-0.55 * (balance - 1.5)))
        if score != score:
            return 5.0
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 5.0
