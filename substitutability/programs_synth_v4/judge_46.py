import re
import math

_PREP = {
    "fresh", "frozen", "dried", "dry", "canned", "chopped", "diced", "minced", "sliced",
    "ground", "grated", "shredded", "thawed", "drained", "boiled", "cooked", "raw",
    "large", "small", "medium", "whole", "fine", "finely", "coarsely", "roughly", "peeled",
    "crushed", "packed", "softened", "melted", "cubed", "trimmed", "rinsed", "toasted",
    "roasted", "smoked", "of", "and", "or", "with", "the", "a", "an", "to", "for", "in",
    "from", "tube", "jar", "can", "taste", "optional", "plus", "extra", "about", "into",
    "pieces", "piece", "cut", "halved", "quartered", "skinless", "boneless",
}

_ALIASES = {
    "sugar": "sugars", "crawfish": "crayfish", "kernel": "nut", "pinyon": "pine",
    "innard": "giblet", "kidneys": "kidney", "seed": "pomegranate",
}

_DEMOTING = {
    "milk", "soup", "pie", "sauce", "stew", "juice", "bar", "cake", "cookie", "cookies",
    "drink", "beverage", "candy", "bread", "muffin", "entree", "dinner", "pudding",
    "relish", "spread", "dressing", "flavored", "flavor", "chips", "cereal", "salad",
    "casserole", "patty", "nuggets", "sandwich", "pizza", "butter", "oil", "powder",
    "paste", "syrup", "jam", "jelly", "extract", "ice", "cream", "yogurt", "cheese",
}


def _stem(w):
    w = w.lower()
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 4 and w.endswith("oes"):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return _ALIASES.get(w, w)


def _words(text):
    return [t for t in re.findall(r"[a-z]+", text.lower())]


def _ingredient_terms(ingredient):
    s = str(ingredient or "")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.split(",")[0]
    s = re.sub(r"^\s*[\d./]+\s*(g|kg|mg|ml|l|oz|lb|grams?)?\b", " ", s, flags=re.I)
    toks = [w for w in _words(s) if w not in _PREP and len(w) > 1]
    return [_stem(t) for t in toks]


def judging_function(ingredient, usda_match):
    try:
        terms = _ingredient_terms(ingredient)
        usda = str(usda_match or "").strip()
        if not terms or not usda:
            return 0.0
        segments = [seg.strip() for seg in usda.split(",") if seg.strip()]
        if not segments:
            return 0.0
        seg_tokens = [[_stem(w) for w in _words(seg)] for seg in segments]
        if not any(seg_tokens):
            return 0.0

        head = terms[-1]  # English head noun is typically last
        modifiers = terms[:-1]
        term_set = set(terms)

        # Position of each ingredient term in the USDA segment list
        def first_pos(t):
            for i, toks in enumerate(seg_tokens):
                if t in toks:
                    return i
            return None

        head_pos = first_pos(head)
        lead = seg_tokens[0]
        lead_head = lead[-1] if lead else ""

        score = 0.0

        # Component 1: head-noun placement (exponential positional decay)
        if head_pos is None:
            # try any ingredient term as the lead food
            alt = [first_pos(t) for t in modifiers]
            alt = [p for p in alt if p is not None]
            if alt and min(alt) == 0:
                score += 18.0
            else:
                score += 0.0
        else:
            score += 50.0 * math.exp(-0.7 * head_pos)

        # Component 2: is the lead segment's own head noun one of our terms?
        if lead_head in term_set:
            score += 25.0
        elif any(t in lead for t in term_set):
            # Our food appears in the lead segment but only as modifier of another noun
            if lead_head in _DEMOTING or len(lead) >= 2:
                score -= 22.0
            else:
                score -= 8.0
        else:
            score -= 10.0

        # Component 3: lead segment introduces a dish/product noun that the ingredient lacks
        extra_demote = [w for w in lead if w in _DEMOTING and w not in term_set]
        if extra_demote:
            score -= 12.0 * len(extra_demote)

        # Component 4: modifier coverage, discounted by depth
        if modifiers:
            cov = 0.0
            for m in modifiers:
                p = first_pos(m)
                if p is not None:
                    cov += 1.0 / (1.0 + 0.3 * p)
            score += 20.0 * cov / len(modifiers)
        else:
            score += 10.0

        # Component 5: USDA terms that are foods not in the ingredient, in lead slot
        all_usda = set(w for toks in seg_tokens for w in toks)
        overlap = len(term_set & all_usda) / float(len(term_set))
        score += 10.0 * overlap

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
