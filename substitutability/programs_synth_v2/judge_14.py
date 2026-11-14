import re

# Preparation-State Equivalence, variant 6: positional role of state words.
# In recipe text, state words AFTER the comma or in parentheses
# ("150g ugli fruit, segmented", "chicken breast, thawed") are instructions
# the cook performs -> they never require a different product.
# State words BEFORE the head noun ("fried onions", "canned corn") describe
# the product that must be bought. Only those are compared with the USDA
# descriptor fields. Each state word has a "processing degree" (0..5); the
# score depends on the gap between the strongest required degree and the
# strongest USDA degree, with an asymmetric slope.

_DEGREE = {
    "fresh": 0, "raw": 0, "uncooked": 0, "whole": 0,
    "chopped": 0.2, "diced": 0.2, "minced": 0.2, "sliced": 0.2, "shredded": 0.3,
    "grated": 0.3, "thawed": 0.3, "peeled": 0.1, "segmented": 0.1, "cubed": 0.2,
    "frozen": 1.0, "chilled": 0.2, "blanched": 1.5, "steamed": 2.5, "boiled": 2.5,
    "poached": 2.5, "cooked": 2.6, "simmered": 2.6, "stewed": 3.0, "braised": 3.0,
    "baked": 3.0, "microwaved": 2.5, "canned": 3.0, "roasted": 3.5, "toasted": 3.3,
    "grilled": 3.6, "broiled": 3.6, "sauteed": 3.6, "smoked": 4.0, "cured": 4.0,
    "pickled": 4.2, "creamed": 3.8, "pureed": 3.5, "mashed": 3.2, "fried": 4.5,
    "breaded": 4.5, "battered": 4.6, "dried": 4.3, "dehydrated": 4.3, "candied": 4.8,
}
_UNIT = r"(g|kg|ml|l|oz|lb|grams?)"


def _split_ingredient(text):
    t = text.lower()
    paren = " ".join(re.findall(r"\(([^)]*)\)", t))
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*" + _UNIT + r"?\b", " ", t)
    if "," in t:
        before, after = t.split(",", 1)
    else:
        before, after = t, ""
    return re.findall(r"[a-z]+", before), re.findall(r"[a-z]+", after + " " + paren)


def _usda_states(text):
    fields = [re.findall(r"[a-z]+", f) for f in text.lower().split(",")]
    states = []
    for idx, f in enumerate(fields):
        for w in f:
            if w in _DEGREE:
                states.append((w, idx))
    return states


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        required, instructions = _split_ingredient(ing)
        req_deg = [_DEGREE[w] for w in required if w in _DEGREE]
        instr_deg = [_DEGREE[w] for w in instructions if w in _DEGREE]
        u_states = _usda_states(usda)
        u_deg = [_DEGREE[w] for w, _ in u_states]

        need = max(req_deg) if req_deg else 0.0
        have = max(u_deg) if u_deg else 0.0
        gap = have - need

        if gap > 0:
            # USDA product processed further than the recipe asks for
            score = 10.0 - 2.1 * gap
        else:
            # recipe wants something more processed; partly fixable by the cook
            score = 10.0 + 1.5 * gap

        # instruction-only states: if USDA already did the instructed step, fine;
        # if instruction is heavy cooking the cook will do anyway, reduce gap
        if instr_deg and u_deg:
            instr_max = max(instr_deg)
            if abs(instr_max - have) < 0.6 and have > need:
                score = max(score, 8.0)
        # explicitly raw requirement vs explicitly cooked product: extra cue
        if {"raw", "fresh"} & set(required) and have >= 2.5:
            score -= 1.0
        # implicit states on both sides: mild uncertainty
        if not req_deg and not u_deg:
            score -= 0.7
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
