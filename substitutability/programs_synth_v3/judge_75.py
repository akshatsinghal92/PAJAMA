import re
import math

# Variant 3: log-odds "qualifier ledger".
# Each side is mapped onto a set of discrete qualifier AXES (color, fat level,
# cut/part, form, sweetness, variety, preservation). For each axis we record
# evidence: agreement adds log-odds, a one-sided qualifier costs a little
# (or a lot when the USDA side injects something noticeable), and a direct
# contradiction costs heavily. Core-food anchoring gates the whole ledger.
# Final score = 100 * sigmoid(total log-odds).

_AXES = {
    "color": {
        "red": "red", "green": "green", "yellow": "yellow", "orange": "orange",
        "white": "white", "black": "black", "brown": "brown", "purple": "purple",
        "golden": "yellow", "pink": "pink", "dark": "dark", "light": "light",
    },
    "fat": {
        "lean": "lean", "extra lean": "xlean", "low fat": "low", "lowfat": "low",
        "reduced fat": "low", "light": "low", "lite": "low", "nonfat": "none",
        "fat free": "none", "skim": "none", "whole": "full", "full fat": "full",
        "2%": "two", "1%": "one", "85% lean": "p85", "90% lean": "p90",
        "93% lean": "p93", "80% lean": "p80", "95% lean": "p95",
    },
    "part": {
        "breast": "breast", "thigh": "thigh", "wing": "wing", "drumstick": "leg",
        "leg": "leg", "loin": "loin", "tenderloin": "loin", "shoulder": "shoulder",
        "belly": "belly", "rib": "rib", "ribs": "rib", "chuck": "chuck",
        "brisket": "brisket", "sirloin": "sirloin", "flank": "flank",
        "yolk": "yolk", "white": None, "leaf": "leaf", "leaves": "leaf",
        "root": "root", "seed": "seed", "seeds": "seed", "stem": "stem",
        "peel": "peel", "zest": "peel", "juice": "juice", "bran": "bran",
        "germ": "germ", "liver": "liver", "skin": "skin",
    },
    "form": {
        "ground": "ground", "minced": "ground", "paste": "paste", "puree": "paste",
        "butter": "butter", "powder": "powder", "powdered": "powder",
        "flakes": "flake", "flaked": "flake", "chips": "chip", "chip": "chip",
        "dried": "dried", "dehydrated": "dried", "sun-dried": "dried",
        "patty": "patty", "patties": "patty", "sauce": "sauce", "oil": "oil",
        "flour": "flour", "meal": "flour", "syrup": "syrup", "jam": "jam",
        "mayonnaise": "mayo", "spread": "spread", "fermented": "fermented",
        "pickled": "pickled", "smoked": "smoked", "canned": "canned",
        "sliced": None, "whole": None, "concentrate": "conc",
    },
    "sweet": {
        "sweetened": "sweet", "unsweetened": "unsweet", "sweet": "sweet",
        "bittersweet": "bitter", "semisweet": "semi", "sugar free": "unsweet",
        "salted": "salt", "unsalted": "unsalt", "low sodium": "unsalt",
    },
    "variety": {
        "bell": "bell", "jalapeno": "jalapeno", "serrano": "serrano",
        "habanero": "habanero", "chili": "chili", "chile": "chili",
        "russet": "russet", "sweet potato": "sweetpot", "red potato": "redpot",
        "mountain": "mountain", "hawaii": "hawaii", "basmati": "basmati",
        "jasmine": "jasmine", "arborio": "arborio", "wild": "wild",
        "granny smith": "granny", "fuji": "fuji", "roma": "roma",
        "cherry": "cherry", "plum": "plum", "baby": "baby", "cottage": "cottage",
        "cheddar": "cheddar", "mozzarella": "mozz", "parmesan": "parm",
        "feta": "feta", "ricotta": "ricotta", "cream": "cream", "goat": "goat",
        "sea": "sea", "kosher": "kosher", "pearl": "pearl", "rolled": "rolled",
        "steel cut": "steel",
    },
}

# How noticeable a contradiction on each axis is (log-odds penalty).
_CONTRA = {"color": 2.6, "fat": 2.2, "part": 3.0, "form": 3.2,
           "sweet": 1.8, "variety": 2.8}
# Cost when ONLY the USDA side carries a qualifier on this axis (it adds
# something the recipe did not ask for).
_USDA_ONLY = {"color": 0.6, "fat": 1.9, "part": 1.0, "form": 2.0,
              "sweet": 0.7, "variety": 2.4}
# Cost when ONLY the ingredient specifies a qualifier the USDA lacks.
_ING_ONLY = {"color": 0.7, "fat": 0.5, "part": 1.2, "form": 2.6,
             "sweet": 0.6, "variety": 0.9}
_AGREE = {"color": 0.9, "fat": 1.1, "part": 1.2, "form": 1.0,
          "sweet": 0.6, "variety": 1.0}

# Words that never discriminate for a diner.
_NEUTRAL = {
    "nfs", "ns", "raw", "fresh", "frozen", "thawed", "cooked", "uncooked",
    "warmed", "heated", "chopped", "diced", "sliced", "fine", "finely",
    "roughly", "coarsely", "large", "small", "medium", "piece", "pieces",
    "salad", "cooking", "or", "and", "with", "of", "the", "a", "an", "for",
    "from", "tube", "jar", "to", "taste", "made", "prepared", "plain",
    "regular", "all", "purpose", "type", "style", "broiled", "baked",
    "boiled", "steamed", "grilled", "roasted", "fried", "drained", "rinsed",
    "peeled", "trimmed", "boneless", "skinless", "cup", "cups", "tbsp",
    "tsp", "g", "gram", "grams", "ml", "oz", "fat", "lean", "spices",
}


def _norm(text):
    t = str(text or "").lower()
    t = t.replace("é", "e").replace("-", " ")
    t = re.sub(r"\(([^)]*)\)", r" \1 ", t)
    t = re.sub(r"^\s*[\d.,/]+\s*(g|kg|ml|l|oz|lb|grams?)?\b", " ", t)
    t = re.sub(r"[^a-z0-9%\s,]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _words(t):
    out = []
    for w in re.findall(r"[a-z%0-9]+", t):
        if len(w) > 3 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
            w = w[:-2]
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def _extract(text):
    """Return {axis: set(values)} found in text, matching longest phrases first."""
    found = {}
    padded = " " + text.replace(",", " ") + " "
    consumed = padded
    for axis, table in _AXES.items():
        for phrase in sorted(table, key=len, reverse=True):
            val = table[phrase]
            pat = " " + phrase + " "
            if pat in consumed:
                if val is not None:
                    found.setdefault(axis, set()).add(val)
                consumed = consumed.replace(pat, " # ")
    return found


def _core_words(text):
    ws = [w for w in _words(text) if w not in _NEUTRAL and not w.isdigit()
          and not w.endswith("%")]
    return ws


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient)
        usda = _norm(usda_match)
        if not ing or not usda:
            return 0.0

        ing_core = set(_core_words(ing))
        usda_parts = [p.strip() for p in usda.split(",") if p.strip()]
        usda_core = set(_core_words(usda))
        head = set(_core_words(usda_parts[0])) if usda_parts else set()

        logit = 0.0

        # --- anchoring: does the USDA describe the same base food at all? ---
        shared = ing_core & usda_core
        if not shared:
            # partial stem overlap (e.g. "pecan" vs "pecans" handled; "tofu" etc.)
            partial = any(a[:5] == b[:5] and len(a) >= 4 and len(b) >= 4
                          for a in ing_core for b in usda_core)
            if not partial:
                return round(100.0 / (1.0 + math.exp(4.5)), 3)
            logit -= 1.5
        else:
            logit += 1.0 + 0.8 * len(shared)
        if head and not (head & ing_core):
            # USDA's primary food isn't the ingredient's food -> it's a product
            # that merely contains the ingredient (e.g. mayonnaise made with tofu)
            logit -= 2.5

        # --- qualifier ledger ---
        ing_q = _extract(ing)
        usda_q = _extract(usda)
        for axis in _AXES:
            a = ing_q.get(axis, set())
            b = usda_q.get(axis, set())
            if a and b:
                if a & b:
                    logit += _AGREE[axis]
                    # extra values on the USDA side within the same axis
                    if b - a:
                        logit -= 0.5 * _CONTRA[axis]
                else:
                    logit -= _CONTRA[axis]
            elif b:
                logit -= _USDA_ONLY[axis]
            elif a:
                logit -= _ING_ONLY[axis]

        # --- unexplained descriptive words on either side ---
        ing_extra = ing_core - usda_core
        usda_extra = usda_core - ing_core
        qual_words = set()
        for table in _AXES.values():
            for phrase in table:
                qual_words.update(phrase.split())
        ing_extra = {w for w in ing_extra if w not in qual_words}
        usda_extra = {w for w in usda_extra if w not in qual_words}
        logit -= 0.55 * len(ing_extra)
        logit -= 0.45 * len(usda_extra)

        # percent fat/lean figures on the USDA side when the recipe was vague
        if re.search(r"\d+\s*%", usda) and not re.search(r"\d+\s*%", ing):
            logit -= 0.6

        logit -= 1.0  # prior: most candidate pairs are not substitutable
        logit = max(-12.0, min(12.0, logit))
        return round(100.0 / (1.0 + math.exp(-logit)), 3)
    except Exception:
        return 0.0
