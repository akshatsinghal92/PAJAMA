import re

# Processing and Additive Difference, variant 8: implied-recipe expansion.
# A product name implies an ingredient list: "Italian dressing" implies oil,
# vinegar, herbs, salt, sugar; "pesto" implies basil, oil, cheese, nuts,
# garlic; "breaded" implies flour, egg, crumbs and frying oil; "sweetened"
# implies sugar; a "patty" implies binders, salt and seasoning. Both texts
# are expanded into weighted component sets via such templates (a plain
# food expands to itself). The score measures how much tasteable material
# the USDA expansion contains beyond the ingredient expansion:
#     added = sum(weight of USDA components not in ingredient components)
#     score = 10 * plain_share, plain_share = base / (base + added)

_TEMPLATES = {
    "dressing": {"oil": 1.0, "vinegar": 0.8, "salt": 0.5, "sugar": 0.5, "herbs": 0.5},
    "pesto": {"basil": 1.0, "oil": 1.0, "cheese": 0.8, "nuts": 0.6, "garlic": 0.6, "salt": 0.3},
    "sauce": {"liquid": 0.6, "salt": 0.6, "thickener": 0.4, "seasoning": 0.6},
    "gravy": {"stock": 0.8, "fat": 0.6, "flour": 0.5, "salt": 0.6},
    "breaded": {"flour": 0.6, "egg": 0.4, "crumbs": 0.9, "oil": 0.6, "salt": 0.3},
    "battered": {"flour": 0.8, "egg": 0.4, "oil": 0.8, "salt": 0.3},
    "fried": {"oil": 1.0},
    "sweetened": {"sugar": 1.0}, "candied": {"sugar": 1.4}, "glazed": {"sugar": 1.0},
    "frosted": {"sugar": 1.2}, "syrup": {"sugar": 1.0},
    "salted": {"salt": 0.9}, "smoked": {"smoke": 1.0, "salt": 0.4},
    "cured": {"salt": 1.0, "nitrite": 0.3}, "pickled": {"vinegar": 1.0, "salt": 0.6},
    "seasoned": {"seasoning": 1.0, "salt": 0.5}, "seasoning": {"seasoning": 1.0, "salt": 0.7},
    "patty": {"binder": 0.6, "salt": 0.5, "seasoning": 0.5},
    "marinated": {"oil": 0.4, "acid": 0.5, "salt": 0.5, "seasoning": 0.5},
    "creamed": {"cream": 0.8, "starch": 0.4, "sugar": 0.3}, "cream": {"cream": 1.0},
    "buttered": {"butter": 1.0}, "flavored": {"flavoring": 1.0, "sugar": 0.4},
    "frozen yogurt": {"sugar": 1.0, "stabilizer": 0.3},
    "ice cream": {"sugar": 1.0, "cream": 1.0},
    "blend": {"seasoning": 0.8, "salt": 0.5}, "mix": {"seasoning": 0.6, "starch": 0.5, "salt": 0.5},
    "soup": {"stock": 0.8, "salt": 0.6, "vegetables": 0.4},
    "pepper": {"pepper": 1.0}, "salt": {"salt": 1.0}, "garlic": {"garlic": 1.0},
    "vanilla": {"vanilla": 0.8, "sugar": 0.5}, "chocolate": {"chocolate": 1.0, "sugar": 0.6},
    "honey": {"honey": 1.0}, "cheese": {"cheese": 1.0},
}
_PLAIN = {"without salt": "salt", "unsalted": "salt", "unsweetened": "sugar",
          "no sugar added": "sugar", "sugar free": "sugar"}
_BASE = 2.0


def _expand(text, head_words):
    comps = {}
    t = " " + text + " "
    for key in sorted(_TEMPLATES, key=len, reverse=True):
        if re.search(r"\b" + re.escape(key) + r"\b", t):
            # the food that IS the item (e.g. ingredient "salt") is not an additive
            if key in head_words and key not in ("sauce", "dressing", "patty", "pesto", "soup"):
                continue
            for c, w in _TEMPLATES[key].items():
                comps[c] = max(comps.get(c, 0.0), w)
            t = re.sub(r"\b" + re.escape(key) + r"\b", " ", t)
    for phrase, comp in _PLAIN.items():
        if phrase in text:
            comps.pop(comp, None)
    return comps


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        ing = re.sub(r"\([^)]*\)", " ", ing).split(",")[0].strip()
        usda = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        if not ing or not usda.strip():
            return 0.0
        iw = re.findall(r"[a-z]+", ing)
        head = set(iw[-1:])
        # identity words named by the ingredient are the food itself on both sides
        ci = _expand(ing, head)
        cu = _expand(usda, set(iw))
        added = sum(w for c, w in cu.items() if c not in ci)
        removed = sum(w for c, w in ci.items() if c not in cu)
        plain_share = _BASE / (_BASE + added + 0.4 * removed)
        score = 10.0 * plain_share
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
