import re

# Variant 3: axis-based qualifier ledger.
# Each qualifier axis holds mutually exclusive values. For every axis we compare the
# value set expressed by the ingredient against the value set expressed by the USDA
# entry: agreement earns credit, silence on one side is neutral, contradiction is
# penalized by the axis' sensory weight. A species/identity axis and a core-noun
# coverage term anchor the score so that qualifier agreement on the wrong food does
# not score highly.

_AXES = {
    "species": (3.0, {
        "beef": ["beef", "chuck", "brisket", "sirloin"],
        "lamb": ["lamb", "mutton"],
        "pork": ["pork", "ham", "bacon"],
        "chicken": ["chicken", "broiler", "broilers", "fryers"],
        "turkey": ["turkey"],
        "fish": ["fish", "swordfish", "whiting", "salmon", "tuna", "cod"],
    }),
    "bean": (2.5, {
        "pinto": ["pinto"], "kidney": ["kidney"], "black_bean": ["black turtle"],
        "navy": ["navy"], "garbanzo": ["garbanzo", "chickpea", "chickpeas"],
        "lima": ["lima"],
    }),
    "color": (2.0, {
        "red": ["red"], "green": ["green"], "yellow": ["yellow"],
        "white": ["white"], "black": ["black"], "brown": ["brown"],
        "orange": ["orange"], "purple": ["purple"],
    }),
    "fat": (2.0, {
        "whole": ["whole milk", "full fat", "full-fat", "whole"],
        "reduced": ["reduced fat", "2%", "low fat", "lowfat", "low-fat", "1%", "light"],
        "skim": ["skim", "nonfat", "non-fat", "fat free", "fat-free"],
        "lean": ["lean only", "lean"],
    }),
    "sweet": (2.0, {
        "sweetened": ["sweetened", "sweet", "honey", "sugar", "with sugar"],
        "unsweetened": ["unsweetened", "no sugar", "sugar free", "sugar-free",
                        "without sugar", "diet"],
    }),
    "cut": (2.0, {
        "breast": ["breast"], "thigh": ["thigh"], "wing": ["wing", "wings"],
        "drumstick": ["drumstick", "leg"], "shank": ["shank"],
        "loin": ["loin", "tenderloin"], "shoulder": ["shoulder", "chuck"],
        "ground": ["ground", "minced"],
    }),
    "part": (2.5, {
        "leaf": ["leaf", "leaves", "greens"], "seed": ["seed", "seeds"],
        "root": ["root", "roots"], "bran": ["bran"], "germ": ["germ"],
        "flower": ["flower", "flowers", "blossom"], "stem": ["stem", "stems", "stalk"],
        "peel": ["peel", "zest", "rind"], "juice": ["juice"],
    }),
    "skin": (1.0, {
        "skin": ["skin-on", "with skin", "meat and skin", "skin"],
        "skinless": ["skinless", "without skin", "meat only"],
    }),
    "heat": (1.5, {
        "raw": ["raw", "fresh", "crude"],
        "cooked": ["cooked", "boiled", "roasted", "toasted", "fried", "baked",
                   "grilled", "steamed", "braised"],
    }),
    "form": (1.5, {
        "starch": ["starch"], "cracker": ["cracker", "crackers"],
        "flour": ["flour"], "sauce": ["sauce", "relish"], "cereal": ["cereal", "cereals"],
        "formed": ["chopped and formed", "formed", "restructured"],
        "whole_muscle": ["whole-muscle", "whole muscle"],
        "souffle": ["souffle"], "ball": ["ball"],
    }),
    "pepper": (2.0, {
        "bell": ["bell", "sweet pepper"], "hot": ["chili", "chile", "jalapeno",
                                                  "hot pepper", "cayenne"],
    }),
}

_NEUTRAL_WORDS = set("""
raw fresh nfs ns canned frozen bottled drained solids with without and or of in the
a an to for from only mature imported separable trimmed choice select prime plain
ready eat ready-to-eat ounce cup g oz optional divided thawed chopped sliced diced
minced soaked overnight visible fat including lean
""".split())


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)\b\.?", " ", t)
    # keep state after comma separately (it is mostly prep instructions)
    head, _, tail = t.partition(",")
    return head.strip(), tail.strip()


def _clean_usda(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    parts = [p.strip() for p in t.split(",") if p.strip()]
    return parts


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxzh":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _words(text):
    return [_stem(w) for w in re.findall(r"[a-z][a-z\-]*", text)]


def _axis_values(text, values):
    found = set()
    padded = " " + re.sub(r"[^a-z0-9%\- ]", " ", text) + " "
    for val, phrases in values.items():
        for ph in phrases:
            if re.search(r"(?<![a-z])" + re.escape(ph) + r"(?![a-z])", padded):
                found.add(val)
                break
    return found


def judging_function(ingredient, usda_match):
    try:
        if not isinstance(ingredient, str) or not isinstance(usda_match, str):
            return 0.0
        if not ingredient.strip() or not usda_match.strip():
            return 0.0

        ing_head, ing_tail = _clean_ingredient(ingredient)
        usda_parts = _clean_usda(usda_match)
        if not ing_head or not usda_parts:
            return 0.0
        usda_text = " ".join(usda_parts)
        ing_text = ing_head + " " + ing_tail

        # ---- qualifier ledger ----
        ledger = 0.0
        contradictions = 0
        for axis, (weight, values) in _AXES.items():
            a = _axis_values(ing_text if axis in ("heat", "skin", "fat") else ing_head, values)
            b = _axis_values(usda_text, values)
            if axis == "color" and "black" in a and "black" in b:
                pass
            if not a or not b:
                # one side silent: mild penalty only if ingredient specifies a
                # sensory-defining part/form that the USDA entry does not echo
                if a and not b and axis in ("part", "form", "species"):
                    ledger -= 0.4 * weight
                elif b and not a and axis in ("part", "form"):
                    ledger -= 0.5 * weight
                continue
            if a & b:
                ledger += weight
            else:
                ledger -= 1.6 * weight
                contradictions += 1

        # ---- anchor: core noun coverage ----
        ing_words = [w for w in _words(ing_head) if w not in _NEUTRAL_WORDS and len(w) > 2]
        usda_words = set(_words(usda_text))
        usda_primary = set(_words(usda_parts[0]))
        if ing_words:
            covered = [w for w in ing_words if w in usda_words or
                       any(len(w) > 4 and (w in u or u in w) and len(u) > 3 for u in usda_words)]
            coverage = len(covered) / float(len(ing_words))
            last = ing_words[-1]
            head_hit = 1.0 if (last in usda_words) else 0.0
            primary_hit = 1.0 if any(w in usda_primary for w in ing_words) else 0.0
        else:
            coverage, head_hit, primary_hit = 0.0, 0.0, 0.0

        # USDA extra non-neutral descriptors that introduce unrequested identity
        extra = [w for w in usda_words if w not in _NEUTRAL_WORDS and len(w) > 3
                 and w not in set(ing_words)]
        extra_pen = min(len(extra), 6) * 0.25

        # composite ingredients ("X and Y") rarely match a single entry
        compound_pen = 1.5 if re.search(r"\b(and|&)\b", ing_head) and not re.search(r"\band\b", usda_text) else 0.0

        score = 5.0
        score += 4.0 * coverage
        score += 1.5 * head_hit
        score += 1.0 * primary_hit
        score += ledger
        score -= extra_pen
        score -= compound_pen
        if contradictions >= 2:
            score -= 1.0
        if coverage == 0.0:
            score -= 3.0

        return round(max(0.0, min(15.0, score)) * (100.0 / 15.0), 3)
    except Exception:
        return 0.0
