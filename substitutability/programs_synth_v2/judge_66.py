import re

# Culinary Role Interchangeability, variant 2: context-cued primary role plus
# physical-behaviour (texture) compatibility.
# The recipe text carries cues about the role an ingredient plays:
#   "minced"/"crushed" garlic -> aromatic, "diced"/"cubed" -> bulk,
#   "melted"/"for frying" -> fat, "beaten" -> binder, "to taste" -> seasoning,
#   "zest"/"juice of" -> acid/aroma.
# The ingredient's primary role = context cue if present, else the food's
# default role. The USDA entry's role = its food's default role, adjusted by
# form (ground spice -> seasoning, juice -> liquid, sauce -> sauce).
# Physical behaviour (whole, piece, ground, paste, liquid, gel, fat) is
# compared separately, because the same role in the wrong shape still forces
# a recipe change. Score = 65 * role_agreement + 35 * behaviour_agreement.

_DEFAULT_ROLE = {
    "aromatic": "garlic onion onions shallot shallots leek ginger scallion scallions chili",
    "bulk": "tomato tomatoes carrot carrots broccoli spinach kale cabbage pepper peppers zucchini squash celery mushroom mushrooms corn eggplant peas beans lentils potato potatoes",
    "fat": "oil butter lard margarine ghee shortening",
    "binder": "egg eggs flaxseed flax chia gelatin",
    "sweetener": "sugar honey syrup molasses jam jelly",
    "thickener": "flour cornstarch starch arrowroot",
    "acid": "lemon lime vinegar",
    "protein": "chicken turkey beef pork lamb fish swordfish salmon tuna cod shrimp tofu ham sausage bacon patty",
    "starch": "rice pasta noodle noodles spaghetti gnocchi bread oats cereal couscous quinoa tortilla",
    "liquid": "milk broth stock water juice",
    "creamy": "cream yogurt cheese cottage ricotta",
    "crunch": "nuts nut almonds almond walnuts walnut peanuts peanut seeds seed cashews pecans",
    "seasoning": "salt spices spice cinnamon cumin paprika nutmeg turmeric oregano thyme basil parsley",
    "sauce": "sauce dressing ketchup mustard mayonnaise pesto gravy salsa",
    "fruit": "fruit apple apples banana bananas berries blueberries strawberries orange mango peach pear grapes guava ugli",
}
_W2R = {w: r for r, ws in _DEFAULT_ROLE.items() for w in ws.split()}
_FORM_WORDS = {"paste", "puree", "juice", "powder", "sauce", "oil", "seed", "seeds"}
_CONTEXT = [
    (r"\bminced\b|\bcrushed\b|\bgrated\b|\bpaste\b", "aromatic", {"garlic", "ginger", "onion", "shallot", "chili"}),
    (r"\bmelted\b|\bfor frying\b|\bfor greasing\b", "fat", None),
    (r"\bbeaten\b|\bwhisked\b", "binder", None),
    (r"\bto taste\b|\bpinch\b", "seasoning", None),
    (r"\bzest\b", "acid", None),
]
_RELATED_ROLES = {frozenset(["aromatic", "seasoning"]): 0.6, frozenset(["aromatic", "bulk"]): 0.5,
                  frozenset(["bulk", "fruit"]): 0.5, frozenset(["binder", "thickener"]): 0.55,
                  frozenset(["creamy", "liquid"]): 0.45, frozenset(["fat", "creamy"]): 0.4,
                  frozenset(["sauce", "seasoning"]): 0.45, frozenset(["sweetener", "fruit"]): 0.35,
                  frozenset(["starch", "bulk"]): 0.35, frozenset(["liquid", "sauce"]): 0.45}
_BEHAV_COMPAT = {frozenset(["whole", "piece"]): 0.85, frozenset(["ground", "paste"]): 0.5,
                 frozenset(["paste", "liquid"]): 0.45, frozenset(["piece", "paste"]): 0.45,
                 frozenset(["whole", "gel"]): 0.3, frozenset(["ground", "gel"]): 0.55,
                 frozenset(["whole", "ground"]): 0.3, frozenset(["piece", "ground"]): 0.3}


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _food_word(words):
    """Last known food word; form nouns (paste, juice) yield to a preceding food."""
    found = None
    for i, w in enumerate(words):
        key = w if w in _W2R else (_sing(w) if _sing(w) in _W2R else None)
        if key is None:
            continue
        if key in _FORM_WORDS and found is not None:
            continue
        if key == "cheese" and i > 0 and words[i - 1] == "cottage":
            key = "cottage"
        found = key
    return found


def _behaviour(words):
    ws = set(words)
    if ws & {"oil", "butter", "lard", "margarine", "ghee"}:
        return "fat"
    if ws & {"juice", "broth", "stock", "milk", "water", "syrup"}:
        return "liquid"
    if ws & {"paste", "puree", "sauce", "pesto", "jam", "dressing", "creamed"}:
        return "paste"
    if ws & {"ground", "powder", "powdered", "flour", "spices"} and not ws & {"beef", "turkey", "pork", "chicken", "lamb"}:
        return "ground"
    if ws & {"chia"} and not ws & {"ground"}:
        return "gel"
    if ws & {"chopped", "diced", "sliced", "minced", "cubed", "shredded", "segmented"}:
        return "piece"
    return "whole"


def judging_function(ingredient, usda_match):
    try:
        full_ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", str(ingredient or "").lower())
        main = re.sub(r"\([^)]*\)", " ", full_ing).split(",")[0]
        iw = re.findall(r"[a-z]+", main)
        fields = [re.findall(r"[a-z]+", f) for f in str(usda_match or "").lower().split(",")]
        fields = [f for f in fields if f]
        if not iw or not fields:
            return 0.0
        order = fields[0] + (fields[1] if len(fields[0]) == 1 and len(fields) > 1 else [])
        uw = [w for f in fields for w in f]
        fi, fu = _food_word(iw), _food_word(order)
        ri = _W2R.get(fi) if fi else None
        ru = _W2R.get(fu) if fu else None
        if fi == "cottage":
            ri = "creamy"
        if fu == "cottage":
            ru = "creamy"
        for rx, role, foods in _CONTEXT:
            if re.search(rx, full_ing) and (foods is None or fi in foods):
                ri = role
                break
        if ru in ("aromatic", "bulk", "fruit") and set(uw) & {"ground", "powder", "spices", "dried"}:
            ru = "seasoning"
        if ru in ("fruit", "bulk") and "juice" in uw:
            ru = "liquid"
        if fields[0][-1] in ("sauce", "dressing") and fu not in ("sauce", "dressing"):
            ru = "sauce"
        if ri is None or ru is None:
            same = _sing(iw[-1]) in {_sing(w) for w in order}
            return 65.0 if same else 25.0
        if ri == ru:
            role = 1.0
        else:
            role = _RELATED_ROLES.get(frozenset([ri, ru]), 0.0)
        bi, bu = _behaviour(full_ing.split(",")[0].split() + iw), _behaviour(uw)
        # cutting is trivial: piece vs whole is compatible
        behav = 1.0 if bi == bu else _BEHAV_COMPAT.get(frozenset([bi, bu]), 0.2)
        score = 65.0 * role + 35.0 * behav
        if fi and fu and fi == fu:
            score = max(score, 85.0)
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
