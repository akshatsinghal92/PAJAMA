import re

# Variant 7: axis-slot alignment. Each side is projected onto a set of
# qualifier "axes" (color, fat, sweetness, part, cut, form, flavor ...).
# For every axis we compare the slot values as sets and accumulate an
# evidence ledger (agree / unspecified / implied-extra / contradiction),
# then map the ledger through a logistic curve to a 0-100 score.

_AXES = {
    "color": {
        "red": "red", "green": "green", "yellow": "yellow", "orange": "orange",
        "white": "white", "black": "black", "brown": "brown", "purple": "purple",
        "golden": "yellow", "gold": "yellow", "dark": "dark", "light": "light",
    },
    "fat": {
        "whole-milk": "full", "whole": "full", "full-fat": "full", "fullfat": "full", "regular": "full",
        "lowfat": "low", "low-fat": "low", "reduced-fat": "low", "light": "low",
        "lite": "low", "skim": "none", "nonfat": "none", "fat-free": "none",
        "fatfree": "none", "lean": "low", "1%": "low", "2%": "low",
        "fatty": "full", "extra-lean": "none",
    },
    "sweet": {
        "sweet": "sweet", "sweetened": "sweet", "unsweetened": "unsweet",
        "sugar-free": "unsweet", "sugarless": "unsweet", "hot": "hot",
        "spicy": "hot", "mild": "mild", "bitter": "bitter", "sour": "sour",
        "semisweet": "semisweet", "bittersweet": "bitter",
        "bell": "sweet", "chili": "hot", "chile": "hot", "jalapeno": "hot",
        "cayenne": "hot", "habanero": "hot", "serrano": "hot",
    },
    "part": {
        "breast": "breast", "thigh": "thigh", "drumstick": "leg", "leg": "leg",
        "wing": "wing", "skin": "skin", "liver": "liver", "heart": "heart",
        "yolk": "yolk", "white": "eggwhite", "whites": "eggwhite",
        "leaves": "leaf", "leaf": "leaf", "stem": "stem", "stalk": "stem",
        "root": "root", "seed": "seed", "seeds": "seed", "peel": "peel",
        "zest": "peel", "juice": "juice", "pulp": "pulp", "kernel": "seed",
        "flesh": "flesh", "meat": "flesh", "bone": "bone",
    },
    "cut": {
        "loin": "loin", "tenderloin": "loin", "sirloin": "sirloin",
        "chuck": "chuck", "brisket": "brisket", "rib": "rib", "ribs": "rib",
        "shoulder": "shoulder", "shank": "shank", "round": "round",
        "flank": "flank", "belly": "belly", "ground": "ground",
        "minced": "ground", "mince": "ground", "fillet": "fillet",
        "filet": "fillet", "steak": "steak", "chop": "chop", "chops": "chop",
    },
    "form": {
        "dried": "dry", "dry": "dry", "dehydrated": "dry", "powder": "powder",
        "powdered": "powder", "fresh": "fresh", "raw": "fresh",
        "canned": "canned", "frozen": "frozen", "paste": "paste",
        "puree": "paste", "pureed": "paste", "flakes": "flake",
        "flaked": "flake", "smoked": "smoked", "fried": "fried",
        "battered": "fried", "crispy": "fried", "roasted": "roasted",
        "toasted": "roasted", "pickled": "pickled", "salted": "salted",
        "unsalted": "unsalted", "cured": "cured",
    },
    "flavor": {
        "vanilla": "vanilla", "chocolate": "chocolate", "strawberry": "strawberry",
        "plain": "plain", "unflavored": "plain", "honey": "honey",
        "cinnamon": "cinnamon", "garlic": "garlic", "lemon": "lemon",
        "butter": "butter", "buttery": "butter", "cheese": "cheese",
    },
}

# value pairs that are compatible (not contradictions) on an axis
_SOFT = {
    ("form", "fresh", "frozen"), ("form", "frozen", "fresh"),
    ("form", "dry", "powder"), ("form", "powder", "dry"),
    ("form", "fresh", "canned"), ("form", "canned", "fresh"),
    ("form", "fried", "roasted"), ("sweet", "sweet", "mild"),
    ("sweet", "mild", "sweet"), ("fat", "low", "none"), ("fat", "none", "low"),
    ("color", "dark", "brown"), ("color", "brown", "dark"),
    ("flavor", "plain", "butter"),
}

# how much a contradiction on an axis is noticeable to a diner
_AXIS_WEIGHT = {"color": 2.2, "fat": 1.8, "sweet": 2.0, "part": 2.6,
                "cut": 1.6, "form": 1.0, "flavor": 2.0}

# axes where USDA adds an unrequested qualifier that would be noticed
_EXTRA_PENALTY = {"fat": 1.3, "flavor": 1.0, "sweet": 0.7, "part": 0.9,
                  "color": 0.4, "cut": 0.3, "form": 0.15}

_UNIT_RE = re.compile(r"^\s*\d+(?:[.,]\d+)?\s*(?:g|kg|mg|ml|l|oz|lb|grams?)?\b\s*", re.I)
_PAREN_RE = re.compile(r"\([^)]*\)")
_TOKEN_RE = re.compile(r"[a-z0-9%]+(?:-[a-z0-9%]+)*")
_COMPOUND_RE = re.compile(r"\b(and|with|&|plus|or)\b")


def _norm_ingredient(text):
    t = str(text or "").lower()
    t = _UNIT_RE.sub("", t)
    paren = " ".join(_PAREN_RE.findall(t))
    t = _PAREN_RE.sub(" ", t)
    head, _, tail = t.partition(",")
    return head.strip(), tail.strip(), paren


def _norm_usda(text):
    t = str(text or "").lower()
    paren = " ".join(_PAREN_RE.findall(t))
    t = _PAREN_RE.sub(" ", t)
    parts = [p.strip() for p in t.split(",") if p.strip()]
    return parts, paren


def _project(tokens):
    slots = {}
    for i, tok in enumerate(tokens):
        cand = [tok]
        if tok.endswith("s") and len(tok) > 3:
            cand.append(tok[:-1])
        if i + 1 < len(tokens):
            cand.append(tok + "-" + tokens[i + 1])
        for c in cand:
            for axis, vocab in _AXES.items():
                if c in vocab:
                    # disambiguate "white" (color vs egg white) and "light"
                    if c in ("white", "whites") and axis == "part":
                        if "egg" not in tokens and "eggs" not in tokens:
                            continue
                    if c == "white" and axis == "color" and ("egg" in tokens or "eggs" in tokens):
                        continue
                    if c == "light" and axis == "color":
                        continue
                    if c == "round" and axis == "cut" and "beef" not in tokens:
                        continue
                    if c == "ground" and axis == "cut" and not any(
                            m in tokens for m in ("beef", "pork", "turkey", "chicken", "lamb", "meat", "veal")):
                        continue
                    slots.setdefault(axis, set()).add(vocab[c])
    return slots


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("oes", "ches", "shes", "sses")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        head, tail, ipar = _norm_ingredient(ingredient)
        uparts, upar = _norm_usda(usda_match)
        if not head or not uparts:
            return 5.0

        i_tokens = _TOKEN_RE.findall(head + " " + tail + " " + ipar)
        u_tokens = _TOKEN_RE.findall(" ".join(uparts) + " " + upar)
        if not i_tokens or not u_tokens:
            return 5.0

        i_slots = _project(i_tokens)
        u_slots = _project(u_tokens)

        ledger = {"agree": 0.0, "contra": 0.0, "extra": 0.0, "missing": 0.0}

        for axis in set(i_slots) | set(u_slots):
            iv = i_slots.get(axis, set())
            uv = u_slots.get(axis, set())
            w = _AXIS_WEIGHT[axis]
            if iv and uv:
                if iv & uv:
                    ledger["agree"] += w
                else:
                    soft = all(any((axis, a, b) in _SOFT for b in uv) for a in iv)
                    if soft:
                        ledger["agree"] += 0.3 * w
                    else:
                        ledger["contra"] += w
            elif uv and not iv:
                ledger["extra"] += _EXTRA_PENALTY.get(axis, 0.3)
            elif iv and not uv:
                # ingredient qualifier the USDA entry is silent on
                ledger["missing"] += 0.35 * w

        # Primary-food anchoring: the USDA head noun should appear in the ingredient.
        i_stems = {_stem(t) for t in i_tokens}
        u_head = {_stem(t) for t in _TOKEN_RE.findall(uparts[0])}
        u_all = {_stem(t) for t in u_tokens}
        if u_head & i_stems:
            anchor = 1.0
        elif u_all & i_stems:
            anchor = 0.6
        else:
            anchor = 0.0
        overlap = len(i_stems & u_all) / max(1, len(i_stems))
        _generic = {"raw", "cooked", "fresh", "or", "and", "with", "only",
                    "from", "in", "of", "the", "a", "fluid", "commercial",
                    "prepared", "ns", "nfs", "regular", "plain", "all", "type"}
        u_content = {t for t in u_all if t not in _generic and not t[0].isdigit()}
        rev = len(u_content & i_stems) / max(1, len(u_content))

        # Compound ingredients ("X and Y", "X with Y") name a second component
        # whose qualifiers the single USDA entry cannot honour.
        compound = 1.0 if _COMPOUND_RE.search(head) else 0.0

        compound = compound * (1.0 if len(i_stems - u_all) > 0 else 0.3)
        z = (-2.2
             + 0.45 * ledger["agree"]
             - 1.2 * ledger["contra"]
             - 0.45 * min(ledger["extra"], 2.5)
             - 0.35 * ledger["missing"]
             + 2.0 * anchor
             + 3.0 * overlap
             + 1.2 * rev
             - 1.8 * compound)
        try:
            import math
            score = 100.0 / (1.0 + math.exp(-z))
        except OverflowError:
            score = 0.0 if z < 0 else 100.0
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 50.0
