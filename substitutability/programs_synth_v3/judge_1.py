import re

_PREP = {
    "chopped", "diced", "minced", "sliced", "melted", "softened", "thawed", "frozen",
    "fresh", "freshly", "grated", "shredded", "peeled", "cooked", "raw", "dried",
    "large", "small", "medium", "finely", "roughly", "thinly", "crushed", "ground",
    "toasted", "roasted", "boiled", "drained", "rinsed", "packed", "whole", "halved",
    "cubed", "trimmed", "beaten", "cold", "warm", "hot", "room", "temperature",
    "optional", "of", "the", "a", "an", "and", "or", "for", "to", "taste", "about",
    "plus", "more", "extra", "florets", "pieces", "piece", "cut", "into", "with",
    "from", "tube", "jar", "can", "canned", "lightly", "well", "pitted", "seeded",
}
_GENERIC = {
    "nfs", "raw", "cooked", "canned", "frozen", "dried", "uncooked", "boiled",
    "without", "with", "salt", "added", "sweetened", "unsweetened", "prepared",
    "regular", "plain", "commercial", "mature", "seeds", "or", "and", "lump",
    "fat", "ns", "as", "to", "type", "from", "made", "drained", "solids", "liquids",
    "all", "varieties", "fluid", "store", "bought", "ready", "eat", "heated",
    "white", "stalks", "fresh",
}
_SYN = {
    "favas": "fava", "broadbeans": "fava", "broadbean": "fava", "faba": "fava",
    "plant-based": "vegan", "plantbased": "vegan", "vegetable": "vegetable",
    "garbanzo": "chickpea", "chickpeas": "chickpea", "cilantro": "coriander",
    "scallion": "onion", "scallions": "onion", "aubergine": "eggplant",
    "courgette": "zucchini", "prawns": "shrimp", "prawn": "shrimp",
    "mayo": "mayonnaise", "confectioners": "powdered", "icing": "powdered",
}


def _norm(tok):
    tok = _SYN.get(tok, tok)
    if len(tok) > 4 and tok.endswith("ies"):
        tok = tok[:-3] + "y"
    elif len(tok) > 4 and tok.endswith("oes"):
        tok = tok[:-2]
    elif len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        tok = tok[:-1]
    return _SYN.get(tok, tok)


def _tokens(text):
    return [t for t in re.findall(r"[a-z][a-z\-]*", text.lower()) if t]


def _parse_ingredient(text):
    s = text.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.split(",")[0]
    s = re.sub(r"^\s*[\d./]+\s*(g|kg|ml|l|oz|lb|grams?|cups?|tbsp|tsp)?\b", " ", s)
    toks = [_norm(t) for t in _tokens(s) if t not in _PREP]
    toks = [t for t in toks if t not in _PREP]
    return toks


def _parse_usda(text):
    segs = [seg.strip().lower() for seg in re.sub(r"\([^)]*\)", lambda m: "," + m.group(0)[1:-1] + ",", text).split(",")]
    segs = [s for s in segs if s]
    out = []
    for i, seg in enumerate(segs):
        toks = [_norm(t) for t in _tokens(seg)]
        toks = [t for t in toks if t not in _GENERIC]
        if toks:
            out.append((i, toks))
    return out


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = _parse_ingredient(str(ingredient))
        segs = _parse_usda(str(usda_match))
        if not ing or not segs:
            return 0.0
        head = ing[-1]
        mods = ing[:-1]
        all_usda = []
        for _, toks in segs:
            all_usda.extend(toks)
        usda_set = set(all_usda)

        def matches(a, b):
            if a == b:
                return True
            if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
                return True
            return False

        # Locate the head noun in USDA segments; earlier segments carry more identity weight.
        head_pos = None
        for i, toks in segs:
            if any(matches(head, t) for t in toks):
                head_pos = i
                break
        # compound head e.g. "cocoa butter" -> check joined form too
        if head_pos is None and len(ing) >= 2:
            joined = ing[-2] + ing[-1]
            for i, toks in segs:
                if joined in "".join(toks):
                    head_pos = i
                    break

        score = 0.0
        if head_pos is not None:
            score += 6.0 - min(head_pos, 3) * 0.6
        else:
            score += 0.5

        # Primary USDA noun (first segment) should appear in the ingredient.
        primary = segs[0][1]
        prim_hit = sum(1 for p in primary if any(matches(p, t) for t in ing))
        if prim_hit:
            score += 2.0 * prim_hit / len(primary)
        else:
            score -= 1.5

        # Modifier agreement: ingredient qualifiers present in USDA (e.g. 'olive', 'pinto').
        if mods:
            mod_hit = sum(1 for m in mods if any(matches(m, t) for t in usda_set))
            frac = mod_hit / len(mods)
            score += 2.0 * frac
            if frac == 0 and head_pos is not None:
                score -= 1.5  # same head but different variety (chinese broccoli, etc.)
        else:
            score += 1.0

        # Distinct USDA identity words not explained by ingredient: possibly different food.
        primary_extra = [p for p in primary if not any(matches(p, t) for t in ing)]
        score -= 0.7 * len(primary_extra)
        if len(segs) > 1:
            second_extra = [p for p in segs[1][1] if not any(matches(p, t) for t in ing)]
            if head_pos is not None and head_pos <= 1 and second_extra and segs[1][0] == 1:
                score -= 0.4 * min(len(second_extra), 2)

        return float(max(0.0, min(10.0, score)))
    except Exception:
        return 0.0
