import re

_ALIASES = {
    "maize": "corn", "granada": "pomegranate", "garbanzo": "chickpea",
    "aubergine": "eggplant", "courgette": "zucchini", "coriander": "cilantro",
    "capsicum": "pepper", "prawn": "shrimp", "scallion": "onion",
    "asadero": "asadero", "arils": "pomegranate", "flats": "wing",
    "drumettes": "wing", "mince": "ground", "minced": "ground",
}

_PREP = {
    "fresh", "frozen", "thawed", "melted", "shredded", "diced", "sliced", "chopped",
    "minced", "grated", "dried", "canned", "whole", "trimmed", "lean", "raw", "cooked",
    "sweetened", "unsweetened", "skin", "on", "off", "boneless", "skinless", "large",
    "small", "medium", "finely", "roughly", "crushed", "ground", "peeled", "plain",
    "of", "and", "or", "the", "a", "with", "from", "tube", "equal", "parts",
    "muscle", "nfs", "ns", "fluid", "uncooked", "prepared", "fat", "reduced",
    "nonfat", "lowfat", "low", "only", "separable", "choice", "select", "all",
}

_CATEGORY = {
    "fish", "nuts", "snacks", "cereal", "cereals", "spices", "oil", "cheese",
    "beverages", "candies", "soup", "sauce", "beef", "pork", "chicken", "turkey",
    "lamb", "veal", "yogurt",
}


def _norm_word(w):
    w = _ALIASES.get(w, w)
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 4 and w.endswith("oes"):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return _ALIASES.get(w, w)


def _words(text):
    return [_norm_word(w) for w in re.findall(r"[a-z]+", text.lower())]


def _clean_ingredient(ing):
    s = ing.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.split(",")[0]
    s = re.sub(r"^\s*[\d./]+\s*(g|kg|ml|l|oz|lb)?\b", " ", s)
    s = s.replace("-", " ")
    return [w for w in _words(s) if w not in _PREP]


def _usda_segments(usda):
    s = re.sub(r"\([^)]*\)", " ", usda.lower()).replace("-", " ")
    segs = []
    for part in s.split(","):
        ws = [w for w in _words(part) if w not in _PREP]
        if ws:
            segs.append(ws)
    return segs


def _trigrams(word):
    w = "^" + word + "$"
    return {w[i:i + 3] for i in range(len(w) - 2)} if len(w) >= 3 else {w}


def _word_sim(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.85
    ta, tb = _trigrams(a), _trigrams(b)
    j = len(ta & tb) / float(len(ta | tb) or 1)
    return j if j >= 0.5 else 0.0


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = _clean_ingredient(str(ingredient))
        segs = _usda_segments(str(usda_match))
        if not ing or not segs:
            return 0.0

        head = ing[-1]                 # head noun of ingredient: last content word
        modifiers = ing[:-1]

        # Locate the USDA "identity phrase": first segment, or second if first is a category word
        primary = segs[0]
        identity = list(primary)
        if len(primary) == 1 and primary[0] in _CATEGORY and len(segs) > 1:
            identity = primary + segs[1]
        usda_head = primary[-1]
        all_usda = [w for seg in segs for w in seg]

        # 1. Head-noun identity (dominant feature)
        head_in_identity = max(_word_sim(head, w) for w in identity)
        head_anywhere = max(_word_sim(head, w) for w in all_usda)
        head_score = max(head_in_identity, 0.6 * head_anywhere)

        # If the ingredient's head matches but as a modifier of a different USDA head
        # (e.g. "beef kidney" vs "Kidney beans"), penalise.
        clash = 0.0
        if len(primary) >= 2 and head_in_identity > 0.8:
            ph = primary[-1]
            if _word_sim(head, ph) < 0.5 and ph not in _CATEGORY:
                if all(_word_sim(ph, m) < 0.5 for m in ing):
                    clash = 0.5

        # Reverse: does the USDA head food appear in the ingredient?
        rev = max(_word_sim(usda_head, w) for w in ing)
        if usda_head in _CATEGORY:
            rev = max(rev, 0.5)

        # 2. Modifier agreement within the identity phrase
        if modifiers:
            mod_hits = sum(1 for m in modifiers
                           if max(_word_sim(m, w) for w in all_usda) >= 0.5)
            mod_ratio = mod_hits / float(len(modifiers))
        else:
            mod_ratio = 1.0

        # 3. Extra identity words in USDA that ingredient lacks (different substance)
        extra = [w for w in identity if w not in _CATEGORY
                 and max(_word_sim(w, x) for x in ing) < 0.5]
        extra_pen = min(len(extra), 3) / 3.0

        score = (5.0 * head_score + 2.5 * rev + 1.5 * mod_ratio
                 + 1.0 * (1.0 - extra_pen))
        score -= 4.0 * clash
        if head_score < 0.3 and rev < 0.3:
            score *= 0.4
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
