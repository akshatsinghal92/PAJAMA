import re

_STOP = {
    "fresh", "frozen", "canned", "raw", "cooked", "chopped", "diced", "sliced",
    "minced", "large", "small", "medium", "whole", "uncooked", "boiled", "baked",
    "roasted", "dried", "ground", "the", "and", "of", "with", "a", "an", "or",
    "nfs", "ns", "as", "to", "from", "in", "for", "plain", "regular", "peeled",
    "thawed", "drained", "rinsed", "segmented", "grated", "shredded", "unsalted",
    "salted", "low", "fat", "reduced", "calorie", "sodium", "lowfat", "nonfat",
}

_CATEGORY_WORDS = {
    "spices", "fish", "cereals", "cheese", "beverages", "vegetables", "fruit",
    "nuts", "seeds", "beef", "pork", "chicken", "turkey", "salad", "snacks",
    "candies", "soup", "sauce", "oil", "babyfood", "crustaceans", "mollusks",
}


def _singular(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.split(",")[0]
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|grams?|ml|kg|oz)\b", " ", t)
    t = re.sub(r"[^a-z\s-]", " ", t)
    return [_singular(w) for w in t.replace("-", " ").split() if w]


def _head_noun(tokens):
    content = [w for w in tokens if w not in _STOP]
    if not content:
        content = tokens
    return content[-1] if content else "", content


def _usda_parts(text):
    t = re.sub(r"\([^)]*\)", " ", text.lower())
    parts = [p.strip() for p in t.split(",") if p.strip()]
    out = []
    for p in parts:
        toks = [_singular(w) for w in re.sub(r"[^a-z\s]", " ", p).split()]
        out.append(toks)
    return out


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing_tokens = _clean_ingredient(str(ingredient))
        ing_head, ing_content = _head_noun(ing_tokens)
        parts = _usda_parts(str(usda_match))
        if not ing_head or not parts:
            return 0.0

        primary = [w for w in parts[0] if w not in _STOP]
        primary_head = primary[-1] if primary else ""
        # If primary segment is a broad category, the true head usually sits in segment 2
        secondary = []
        if len(parts) > 1:
            secondary = [w for w in parts[1] if w not in _STOP]
        cat_like = primary_head in _CATEGORY_WORDS or (len(primary) == 1 and secondary)

        score = 0.0
        # Head noun identity
        if ing_head == primary_head:
            score += 6.0
        elif ing_head in primary:
            score += 4.5
        elif cat_like and ing_head in secondary:
            score += 5.0
        elif any(ing_head == w for p in parts[2:] for w in p):
            score += 1.5
        else:
            # partial stem identity (e.g. flaxseed vs flax seed)
            joined = "".join(primary + secondary)
            if len(ing_head) >= 4 and ing_head in joined:
                score += 3.0

        # Modifier agreement: content tokens of ingredient present in first two segments
        top = set(primary) | set(secondary)
        mods = [w for w in ing_content if w != ing_head]
        if mods:
            hit = sum(1 for w in mods if w in top)
            score += 3.0 * hit / len(mods)
            if hit == 0 and score >= 4.5:
                score -= 1.0
        else:
            score += 1.5

        # Penalize distinct primary food that does not appear in ingredient at all
        if primary_head and primary_head not in ing_tokens and not cat_like:
            score -= 2.0

        # Extra USDA descriptors (outside first two segments) mildly dilute identity
        extra = sum(len(p) for p in parts[2:])
        score -= min(1.0, 0.2 * extra)

        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
