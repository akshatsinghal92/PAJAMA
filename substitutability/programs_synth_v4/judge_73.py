import re

_NOTES = [
    r"\boptional\b", r"\bto taste\b", r"\bfor garnish\b", r"\bfor serving\b",
    r"\bas needed\b", r"\bdivided\b", r"\bplus more\b", r"\bif desired\b",
    r"\bor more\b", r"\bat room temperature\b", r"\bfrom tube\b",
]

_STOP = {
    "a", "an", "the", "of", "and", "or", "with", "in", "for", "to", "from",
    "on", "into", "about", "some", "few", "parts", "part", "equal", "nfs",
    "ns", "type", "style", "made", "plus", "piece", "pieces", "large",
    "small", "medium", "fresh", "good", "quality", "strong",
}

# prep actions that don't change the food identity for the USDA entry
_PREP = {
    "chopped", "diced", "minced", "sliced", "cubed", "grated", "shredded",
    "peeled", "trimmed", "halved", "quartered", "crushed", "thawed",
    "drained", "rinsed", "washed", "cut", "torn", "julienned", "melted",
    "softened", "beaten", "sifted", "packed", "pitted", "seeded", "cored",
    "brewed", "finely", "roughly", "coarsely", "thinly", "lightly",
}

# material qualifier groups; members of the same group contradict each other
_GROUPS = {
    "state": {"raw": "raw", "fresh": "raw", "uncooked": "raw",
              "cooked": "cooked", "boiled": "cooked", "baked": "cooked",
              "roasted": "cooked", "fried": "cooked", "grilled": "cooked",
              "steamed": "cooked", "toasted": "cooked", "braised": "cooked",
              "stewed": "cooked", "broiled": "cooked"},
    "preserve": {"canned": "canned", "frozen": "frozen", "dried": "dried",
                 "dry": "dried", "dehydrated": "dried", "smoked": "smoked",
                 "pickled": "pickled"},
    "fat": {"nonfat": "nonfat", "fat-free": "nonfat", "skim": "nonfat",
            "lowfat": "lowfat", "low-fat": "lowfat", "reduced-fat": "lowfat",
            "whole": "whole", "full-fat": "whole"},
    "sugar": {"sweetened": "sweet", "unsweetened": "unsweet",
              "sugar-free": "unsweet"},
    "salt": {"salted": "salt", "unsalted": "nosalt"},
    "color": {"white": "white", "brown": "brown", "red": "red",
              "green": "green", "yellow": "yellow", "black": "black",
              "golden": "yellow", "dark": "dark"},
    "form": {"ground": "ground", "powder": "ground", "powdered": "ground",
             "whole": "whole", "paste": "paste", "juice": "juice",
             "sauce": "sauce", "pie": "dish", "filling": "dish",
             "bar": "dish", "ball": "dish", "soup": "dish", "patty": "dish"},
}

_SYN = {
    "pinyon": "pine", "pignoli": "pine", "jamun": "java-plum",
    "jambolan": "java-plum", "greek": "greek", "yoghurt": "yogurt",
    "scallion": "onion", "scallions": "onion", "cilantro": "coriander",
    "tea": "tea", "half-and-half": "cream", "garbanzo": "chickpea",
    "chickpeas": "chickpea", "aubergine": "eggplant", "courgette": "zucchini",
    "bing": "sweet", "concord": "concord", "skin-on": "skin",
}


def _stem(w):
    w = _SYN.get(w, w)
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _clean_ing(s):
    s = s.lower()
    s = re.sub(r"^\s*[\d./]+\s*(g|kg|mg|ml|l|oz|lb|grams?)?\b", " ", s)
    for p in _NOTES:
        s = re.sub(p, " ", s)
    s = s.replace("(", " , ").replace(")", " , ")
    return s


def _tokens(s):
    toks = re.findall(r"[a-z][a-z\-]*", s)
    out = []
    for t in toks:
        if t in _STOP or len(t) < 2:
            continue
        out.append(t)
    return out


def _categorize(tok):
    hits = {}
    for g, m in _GROUPS.items():
        if tok in m:
            hits[g] = m[tok]
    return hits


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = _clean_ing(str(ingredient))
        usda = str(usda_match).lower()

        ing_toks = _tokens(ing)
        usda_segments = [seg.strip() for seg in usda.split(",") if seg.strip()]
        if not ing_toks or not usda_segments:
            return 0.0
        usda_toks = _tokens(usda)
        usda_stems = set(_stem(t) for t in usda_toks)
        for t in usda_toks:
            for part in t.split("-"):
                usda_stems.add(_stem(part))
        primary_stems = set(_stem(t) for t in _tokens(usda_segments[0]))

        # Separate ingredient tokens into food words, material qualifiers, prep words
        main_part = re.split(r",", ing)[0]
        main_toks = _tokens(main_part)
        head = _stem(main_toks[-1]) if main_toks else _stem(ing_toks[-1])

        food_words, qual_words = [], []
        for t in ing_toks:
            if t in _PREP:
                continue
            if _categorize(t):
                qual_words.append(t)
            else:
                food_words.append(t)

        def covered(t):
            st = _stem(t)
            if st in usda_stems:
                return True
            for u in usda_stems:
                if len(st) >= 4 and len(u) >= 4 and (u.startswith(st) or st.startswith(u)):
                    return True
            return False

        # Head noun coverage (most important)
        head_cov = 1.0 if covered(head) else 0.0
        head_in_primary = head in primary_stems or any(
            len(head) >= 4 and (p.startswith(head) or head.startswith(p)) for p in primary_stems)

        # Food word coverage, weighted toward later tokens (closer to head)
        fw_total, fw_hit = 0.0, 0.0
        n = len(food_words)
        for i, t in enumerate(food_words):
            w = 1.0 + (i / max(1, n - 1)) if n > 1 else 2.0
            fw_total += w
            if covered(t):
                fw_hit += w
        food_cov = fw_hit / fw_total if fw_total else head_cov

        # Qualifier coverage & contradiction
        usda_cats = {}
        for t in usda_toks:
            for g, v in _categorize(t).items():
                usda_cats.setdefault(g, set()).add(v)
        q_cov, q_contra, q_total = 0, 0, 0
        for t in qual_words:
            cats = _categorize(t)
            q_total += 1
            if covered(t):
                q_cov += 1
                continue
            matched = False
            contra = False
            for g, v in cats.items():
                if g in usda_cats:
                    if v in usda_cats[g]:
                        matched = True
                    else:
                        contra = True
            if matched:
                q_cov += 1
            elif contra:
                q_contra += 1
        qual_cov = q_cov / q_total if q_total else 1.0

        # USDA introduces a processed-dish form the ingredient did not ask for
        ing_forms = set()
        for t in ing_toks:
            v = _GROUPS["form"].get(t)
            if v:
                ing_forms.add(v)
        dish_penalty = 0.0
        if "dish" in usda_cats.get("form", set()) and "dish" not in ing_forms:
            dish_penalty = 1.5
        if "canned" in usda_cats.get("preserve", set()) and not any(
                _GROUPS["preserve"].get(t) == "canned" for t in ing_toks):
            dish_penalty += 0.8

        # Primary segment unexplained by ingredient (USDA is about something else)
        ing_stems = set(_stem(t) for t in ing_toks)
        prim_unexpl = [p for p in primary_stems if p not in ing_stems and p not in _PREP
                       and not _categorize(p)]
        prim_frac = len(prim_unexpl) / max(1, len(primary_stems))

        score = 0.0
        score += 3.5 * head_cov
        score += 1.0 if head_in_primary else 0.0
        score += 2.5 * food_cov
        score += 2.0 * qual_cov
        score -= 1.5 * q_contra
        score -= dish_penalty
        score -= 1.0 * prim_frac * (1.0 - head_cov)
        score += 1.0  # baseline offset

        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
