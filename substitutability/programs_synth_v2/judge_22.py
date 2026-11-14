import re

# Preservation and Form Match, variant 6: food-aware default forms and
# form-sensitivity. When a text omits the form, the food's TYPICAL recipe
# form is assumed (beans/chickpeas -> canned, herbs -> fresh, spices -> dried,
# berries -> fresh, peas -> frozen). Each food family also has a sensitivity
# saying how much a form change matters (herbs and fruit: a lot; oils,
# sugar, cheese: barely). The final score is 10 minus a sensitivity-scaled
# form distance taken from an ordinal form scale.

_FAMILY = {
    "herb": (["basil", "parsley", "cilantro", "coriander", "dill", "mint", "thyme",
              "rosemary", "oregano", "sage", "tarragon", "chives"], "fresh", 1.0),
    "spice": (["cinnamon", "cumin", "paprika", "nutmeg", "turmeric", "pepper", "ginger",
               "spices", "clove", "cardamom", "chili"], "dried", 0.8),
    "legume": (["bean", "beans", "chickpea", "chickpeas", "lentil", "lentils", "garbanzo"],
               "canned", 0.7),
    "fruit": (["berry", "berries", "blueberries", "strawberries", "apple", "banana", "fruit",
               "mango", "peach", "pear", "grape", "cherries", "pineapple", "orange", "ugli"],
              "fresh", 0.95),
    "veg": (["corn", "pea", "peas", "spinach", "tomato", "tomatoes", "carrot", "broccoli",
             "onion", "pepper", "mushroom", "mushrooms", "beans"], "fresh", 0.8),
    "liquid": (["broth", "stock", "soup", "juice", "milk"], "liquid", 0.9),
    "flesh": (["chicken", "beef", "pork", "fish", "salmon", "tuna", "turkey", "shrimp",
               "swordfish"], "fresh", 0.7),
    "stable": (["oil", "sugar", "salt", "cheese", "butter", "honey", "vinegar", "flour",
                "rice", "pasta", "cereal", "dressing"], "fresh", 0.25),
}

# ordinal form scale roughly following water removal / processing intensity
_SCALE = {"fresh": 0.0, "frozen": 0.6, "canned": 2.0, "liquid": 2.5, "ready": 2.8,
          "paste": 3.6, "condensed": 4.0, "dried": 4.6, "powder": 5.2}
_FORM_CUES = [
    ("powder", ("powder", "powdered", "instant", "granules")),
    ("dried", ("dried", "dehydrated", "flakes", "dry")),
    ("condensed", ("condensed", "concentrate", "concentrated", "bouillon")),
    ("paste", ("paste", "puree", "tube")),
    ("ready", ("ready", "soup", "chowder")),
    ("liquid", ("juice", "broth", "stock", "nectar")),
    ("canned", ("canned", "tinned", "jarred", "bottled")),
    ("frozen", ("frozen", "thawed")),
    ("fresh", ("fresh", "raw")),
]


def _family(words):
    for fam, (nouns, default, sens) in _FAMILY.items():
        if any(w in nouns for w in words):
            return fam, default, sens
    return None, "fresh", 0.6


def _form(words, default):
    ws = set(words)
    if "dry" in ws and "heat" in ws:
        ws.discard("dry")
    if "ground" in ws and not ws & {"beef", "pork", "turkey", "chicken", "lamb", "meat"}:
        return "powder"
    for form, cues in _FORM_CUES:
        if ws & set(cues):
            return form
    return default


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower().replace("-", " ")
        usda = str(usda_match or "").lower().replace("-", " ")
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        iw = re.findall(r"[a-z]+", ing)
        uw = re.findall(r"[a-z]+", usda)
        if not iw or not uw:
            return 0.0
        fam_u, default_u, sens_u = _family(uw[:4])
        fam_i, default_i, sens_i = _family(iw)
        sens = max(sens_i, sens_u)
        fi = _form(iw, default_i)
        # USDA "Spices, X" entries are dried by convention
        if uw and uw[0] == "spices":
            fu = _form(uw, "dried")
            if fu == "fresh":
                fu = "dried"
        else:
            fu = _form(uw, "fresh")
        dist = abs(_SCALE[fi] - _SCALE[fu])
        # frozen <-> fresh is nearly free for produce that will be cooked/thawed
        if {fi, fu} == {"fresh", "frozen"}:
            dist = 0.4 if "thawed" in iw or fam_i in ("veg", "fruit") else 0.6
        score = 10.0 - 1.9 * sens * dist
        # categorical jumps between liquid and solid families are extra costly
        solid = {"fresh", "frozen", "canned", "dried", "powder"}
        if (fi in solid) != (fu in solid) and sens > 0.5:
            score -= 1.5
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
