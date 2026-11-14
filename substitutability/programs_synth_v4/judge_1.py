import re

_PREP = {
    "fresh", "frozen", "thawed", "chopped", "diced", "sliced", "minced", "cubed",
    "melted", "ripe", "cooked", "raw", "dried", "dry", "ground", "grated", "shredded",
    "peeled", "large", "small", "medium", "whole", "finely", "roughly", "boneless",
    "skinless", "softened", "toasted", "roasted", "organic", "plain", "unsalted",
    "salted", "canned", "rinsed", "drained", "trimmed", "halved", "quartered",
    "crushed", "packed", "granulated", "florets", "hearts", "of", "the", "a", "and",
}

_SYN = {
    "fava": "broadbean", "favas": "broadbean", "broadbeans": "broadbean",
    "broadbean": "broadbean", "romaine": "lettuce", "cos": "lettuce",
    "plant-based": "vegan", "plantbased": "vegan", "mayo": "mayonnaise",
    "garbanzo": "chickpea", "chickpeas": "chickpea", "scallion": "onion",
    "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini",
}

# Words in the USDA entry that signal a transformed / different substance
_TRANSFORM = {
    "oil", "nectar", "juice", "pudding", "puddings", "frozen", "mix", "soup",
    "sauce", "candy", "flavored", "drink", "beverage", "powder", "taco",
    "sandwich", "pizza", "burrito", "patty", "substitute", "imitation", "baby",
}


def _norm(tok):
    tok = _SYN.get(tok, tok)
    if len(tok) > 4 and tok.endswith("ies"):
        tok = tok[:-3] + "y"
    elif len(tok) > 3 and tok.endswith("es") and tok[-3] in "sxz":
        tok = tok[:-2]
    elif len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        tok = tok[:-1]
    return _SYN.get(tok, tok)


def _tokens(text):
    return [_norm(t) for t in re.findall(r"[a-z][a-z\-]*", text.lower())]


def _ingredient_core(ingredient):
    s = ingredient.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.split(",")[0]
    s = re.sub(r"^\s*[\d./]+\s*(g|kg|ml|l|oz|lb)?\b", " ", s)
    toks = [t for t in _tokens(s) if t not in _PREP]
    if not toks:
        toks = _tokens(s)
    return toks


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        core = _ingredient_core(str(ingredient))
        if not core:
            return 0.0
        head = core[-1]
        modifiers = core[:-1]

        segs = [seg.strip() for seg in str(usda_match).lower().split(",") if seg.strip()]
        if not segs:
            return 0.0
        primary = _tokens(segs[0])
        seg_toks = [_tokens(sg) for sg in segs]
        all_toks = [t for st in seg_toks for t in st]
        all_set = set(all_toks)

        score = 0.0
        # 1. Head-noun identity: strongest when it appears in the primary segment
        if head in primary:
            score += 50.0
            # if head is the last word of the primary, it is the USDA head too
            if primary and primary[-1] == head:
                score += 10.0
        elif head in all_set:
            score += 32.0
        else:
            # partial stem match (e.g. flaxseed vs seed)
            partial = any(len(head) >= 4 and (head in t or t in head) and len(t) >= 4
                          for t in all_set)
            score += 12.0 if partial else 0.0

        # 2. Modifier agreement: fraction of ingredient modifiers found anywhere
        if modifiers:
            hit = sum(1 for m in modifiers if m in all_set)
            score += 25.0 * hit / len(modifiers)
            # modifier that is itself the USDA primary food (e.g. 'hazelnut' oil) with
            # head missing means core substance differs
        else:
            score += 12.0

        # 3. Transformation penalty: USDA primary introduces a different substance form
        ing_set = set(core)
        extra_transform = [t for t in primary if t in _TRANSFORM and t not in ing_set]
        if extra_transform:
            score -= 22.0 * min(2, len(extra_transform))
        other_transform = [t for st in seg_toks[1:] for t in st
                           if t in _TRANSFORM and t not in ing_set]
        if other_transform:
            score -= 8.0 * min(2, len(other_transform))

        # 4. Foreign primary noun: primary segment's head not in ingredient at all
        if primary:
            p_head = primary[-1]
            if p_head not in ing_set and p_head not in _TRANSFORM and head not in primary:
                score -= 15.0

        # 5. Sharing nothing at all
        if not (ing_set & all_set):
            score -= 20.0

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
