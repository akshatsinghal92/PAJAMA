import re

# Variant 3: feature-category ledger. Each side is mapped to a set of
# processing/additive "flags" (grouped into categories with diner-perceptibility
# weights). The score starts from a base, subtracts weighted penalties for flags
# the USDA entry ADDS relative to the ingredient, smaller penalties for flags the
# ingredient has that USDA drops, and adds a bonus for "plain" USDA descriptors
# and core-noun agreement. Result is squashed to 0-100.

_CATEGORIES = {
    # category: (weight_added, weight_missing, {flag: [patterns]})
    "salt": (14.0, 6.0, {
        "salted": [r"\bsalted\b", r"\bwith salt\b", r"\bbrined?\b", r"\bcured\b", r"\bpickled\b"],
    }),
    "sweet": (16.0, 8.0, {
        "sweetened": [r"\bsweetened\b", r"\bsugar(ed)?\b", r"\bsyrup\b", r"\bhoney\b", r"\bcandied\b",
                      r"\bglazed\b", r"\bfrosted\b"],
    }),
    "fat": (11.0, 4.0, {
        "oiled": [r"\bwith (added )?(oil|butter|fat|margarine)\b", r"\bfried\b", r"\bin oil\b",
                  r"\bbuttered\b", r"\boil[- ]roasted\b"],
    }),
    "coating": (18.0, 8.0, {
        "breaded": [r"\bbreaded\b", r"\bbattered\b", r"\bbatter\b", r"\bcoated\b", r"\bcrumbs?\b",
                    r"\btempura\b"],
    }),
    "seasoning": (15.0, 6.0, {
        "seasoned": [r"\bseasoned\b", r"\bspiced\b", r"\bmarinated\b", r"\bherbed\b",
                     r"\band pepper\b", r"\bseasoning\b", r"\brub\b"],
    }),
    "flavor": (17.0, 7.0, {
        "flavored": [r"\bflavou?red\b", r"\bbalsamic\b", r"\bsmoked\b", r"\bbarbecue\b", r"\bbbq\b",
                     r"\bteriyaki\b", r"\bhoney[- ]?roasted\b", r"\bvanilla\b", r"\bchocolate\b"],
    }),
    "sauce": (16.0, 9.0, {
        "sauced": [r"\bsauce\b", r"\bgravy\b", r"\bdressing\b", r"\bin (tomato|cream|cheese)\b",
                   r"\bcondiment\b", r"\bspread\b"],
    }),
    "compound": (13.0, 5.0, {
        "composite": [r"\bpatty\b", r"\bpatties\b", r"\bnuggets?\b", r"\bsticks?\b", r"\bmix\b",
                      r"\bprepared\b", r"\bdish\b", r"\bsoup\b", r"\bcasserole\b", r"\bsalad\b(?! or)",
                      r"\bsandwich\b", r"\bsausage\b", r"\bloaf\b", r"\bpie\b", r"\bfilling\b",
                      r"\bready[- ]to[- ]eat\b", r"\bfrozen dinner\b", r"\bentree\b"],
    }),
    "texture_proc": (8.0, 5.0, {
        "dried": [r"\bdried\b", r"\bdehydrated\b", r"\bpowder(ed)?\b", r"\bground\b", r"\bflakes?\b"],
        "paste": [r"\bpaste\b", r"\bpuree[d]?\b", r"\bconcentrate\b", r"\bjuice\b"],
    }),
}

_PLAIN_MARKERS = [r"\braw\b", r"\bplain\b", r"\bunsalted\b", r"\bunsweetened\b",
                  r"\bwithout salt\b", r"\bno salt\b", r"\bnatural\b", r"\bfresh\b",
                  r"\bsalad or cooking\b", r"\bdrained solids\b"]

# words in the recipe text that describe handling, not composition
_PREP_NOISE = {
    "cubed", "diced", "chopped", "sliced", "minced", "thawed", "warmed", "cold", "ripe",
    "drained", "rinsed", "peeled", "trimmed", "frozen", "canned", "fresh", "large", "small",
    "medium", "for", "serving", "garnish", "about", "and", "or", "of", "the", "a", "to",
    "taste", "finely", "roughly", "whole", "cut", "into", "pieces", "from", "tube", "optional",
    "room", "temperature", "halved", "quartered", "grated", "shredded", "boneless", "skinless",
}

_USDA_NOISE = {
    "raw", "cooked", "boiled", "canned", "frozen", "drained", "solids", "species", "mixed",
    "separable", "lean", "fat", "and", "only", "or", "with", "without", "choice", "select",
    "trimmed", "to", "all", "grades", "commercial", "salad", "cooking", "fresh", "includes",
    "unprepared", "regular", "nfs", "ns", "as", "to", "eat", "ready",
}

_PART_WORDS = {"seed", "seeds", "peel", "rind", "zest", "skin", "leaves", "leaf", "stem",
               "stems", "pit", "core", "bones", "bone", "juice", "greens", "tops", "flower",
               "blossom", "husk", "kernel", "kernels", "oil", "extract", "water", "milk"}


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*[\d.,/]+\s*(g|gr|grams?|kg|ml|l|oz|lb)?\b", " ", t)
    # drop post-comma state ("thawed", "cubed")
    head, _, tail = t.partition(",")
    return head.strip(), tail.strip(), t


def _flags(text):
    found = {}
    for cat, (_, _, flagmap) in _CATEGORIES.items():
        for flag, pats in flagmap.items():
            for p in pats:
                if re.search(p, text):
                    found[(cat, flag)] = True
                    break
    return set(found)


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxzh":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(text, noise):
    return {_stem(w) for w in re.findall(r"[a-z]+", text) if w not in noise and len(w) > 1}


def judging_function(ingredient, usda_match):
    try:
        if not isinstance(ingredient, str) or not isinstance(usda_match, str):
            return 0.0
        if not ingredient.strip() or not usda_match.strip():
            return 0.0

        head, tail, ing_full = _clean_ingredient(ingredient)
        ing_text = head if head else ing_full
        usda = usda_match.lower()
        usda_noparen = re.sub(r"\([^)]*\)", " ", usda)
        usda_desc = re.sub(r"\b[A-Z][A-Z!'&.]{2,}(\s+[A-Z][A-Z!'&.]*)*", " ", usda_match).lower()

        ing_flags = _flags(ing_text)
        usda_flags = _flags(usda_desc)

        # When the ingredient itself names the processed form (e.g. "hot chile
        # sauce" vs "Sauce, ..."), the flag is shared, not added.
        added = usda_flags - ing_flags
        missing = ing_flags - usda_flags

        penalty = 0.0
        cats_added = set()
        for cat, flag in added:
            w_add = _CATEGORIES[cat][0]
            # diminishing returns within the same category
            penalty += w_add * (0.5 if cat in cats_added else 1.0)
            cats_added.add(cat)
        for cat, flag in missing:
            penalty += _CATEGORIES[cat][1]

        # Multiple distinct additive categories compound perceptibly
        if len(cats_added) >= 2:
            penalty *= 1.0 + 0.15 * (len(cats_added) - 1)

        # Plainness bonus: USDA explicitly states plain form while ingredient
        # carries no processing flags.
        plain_hits = sum(1 for p in _PLAIN_MARKERS if re.search(p, usda_noparen))
        plain_bonus = 0.0
        if not ing_flags and not added:
            plain_bonus = min(10.0, 5.0 * plain_hits) + 4.0
        elif plain_hits and not added:
            plain_bonus = 3.0

        # Core-identity agreement: the primary USDA food (before first comma)
        # should match something in the ingredient head.
        ing_tok = _tokens(ing_text, _PREP_NOISE)
        primary = usda_noparen.split(",")[0]
        prim_tok = _tokens(primary, _USDA_NOISE)
        usda_tok = _tokens(usda_noparen, _USDA_NOISE)

        core_score = 0.0
        if ing_tok:
            hit_primary = len(ing_tok & prim_tok)
            hit_any = len(ing_tok & usda_tok)
            coverage = hit_any / float(len(ing_tok))
            core_score = 12.0 * coverage + (8.0 if hit_primary else -10.0)
            # USDA-specific descriptors not present in the ingredient that are
            # flavor/variety words (unexplained extras) — mild penalty.
            extras = usda_tok - ing_tok - prim_tok
            extras = {e for e in extras if len(e) > 3}
            core_score -= min(8.0, 1.5 * len(extras))

        # Part mismatch: ingredient names a distinct part (seeds, peel, juice)
        # that USDA entry does not mention -> a different component entirely.
        ing_parts = {_stem(w) for w in re.findall(r"[a-z]+", ing_text)} & {_stem(p) for p in _PART_WORDS}
        usda_parts = {_stem(w) for w in re.findall(r"[a-z]+", usda_noparen)} & {_stem(p) for p in _PART_WORDS}
        part_penalty = 0.0
        if ing_parts - usda_parts:
            part_penalty += 22.0
        if usda_parts - ing_parts:
            part_penalty += 12.0

        raw = 60.0 - penalty + plain_bonus + core_score - part_penalty
        return round(max(0.0, min(100.0, raw)), 3)
    except Exception:
        return 0.0
