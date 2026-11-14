import re
import math

# Role lexicon: each cue word votes for one or more culinary roles with a weight.
_ROLE_CUES = {
    "protein_meat": ["beef", "pork", "lamb", "veal", "chicken", "turkey", "duck", "goat",
                     "venison", "bison", "heart", "kidney", "kidneys", "liver", "tongue",
                     "steak", "breast", "thigh", "loin", "chop", "ribs", "mince", "ground"],
    "protein_fish": ["fish", "salmon", "tuna", "cod", "swordfish", "tilapia", "trout",
                     "shrimp", "prawn", "crab", "lobster", "clam", "mussel", "oyster",
                     "scallop", "squid", "anchovy", "sardine", "halibut", "mackerel"],
    "cured_meat": ["sausage", "bacon", "ham", "salami", "chorizo", "pepperoni",
                   "prosciutto", "frankfurter", "hot dog", "pudding", "blood"],
    "dairy_melt": ["cheese", "queso", "asadero", "cheddar", "mozzarella", "parmesan",
                   "feta", "ricotta", "gouda", "brie", "monterey", "jack", "oaxaca"],
    "dairy_liquid": ["milk", "cream", "yogurt", "yoghurt", "buttermilk", "kefir"],
    "fat": ["oil", "butter", "lard", "ghee", "shortening", "margarine", "tallow"],
    "spread": ["butter", "paste", "spread", "jam", "jelly", "puree", "sauce", "dip"],
    "legume_bulk": ["beans", "bean", "lentil", "lentils", "chickpea", "chickpeas", "peas",
                    "garbanzo", "soybean", "tan", "pinto", "navy", "kidney"],
    "starch_veg": ["potato", "potatoes", "yam", "yams", "sweet", "cassava", "taro",
                   "plantain", "squash", "pumpkin", "parsnip", "turnip"],
    "bulk_veg": ["carrot", "onion", "celery", "pepper", "tomato", "cabbage", "spinach",
                 "kale", "lettuce", "broccoli", "zucchini", "eggplant", "mushroom"],
    "aromatic": ["garlic", "ginger", "shallot", "sage", "thyme", "rosemary", "basil",
                 "oregano", "parsley", "cilantro", "mint", "dill", "spices", "spice",
                 "cumin", "pepper", "cinnamon", "nutmeg", "clove", "herb", "herbs"],
    "nut_seed": ["pecan", "pecans", "almond", "almonds", "walnut", "walnuts", "cashew",
                 "peanut", "peanuts", "hazelnut", "pistachio", "seeds", "seed", "flax",
                 "chia", "sesame", "sunflower", "pumpkin"],
    "sweetener": ["sugar", "honey", "syrup", "molasses", "agave", "sweetener", "stevia"],
    "thickener": ["flour", "starch", "cornstarch", "arrowroot", "gelatin", "agar",
                  "xanthan", "tapioca"],
    "grain": ["rice", "wheat", "oats", "barley", "quinoa", "pasta", "noodles", "bread",
              "couscous", "bulgur", "millet"],
    "snack_product": ["cookies", "cookie", "crackers", "chips", "candy", "bar", "bars",
                      "cereal", "snack", "cake", "brownie", "sandwich", "gluten",
                      "vanilla", "chocolate", "frosted", "flavored", "mix"],
}

# Physical form classes and how disruptive swapping between them is (0 = fine, 1 = breaks role)
_FORM_CUES = {
    "whole": ["whole", "steak", "fillet", "breast", "heart", "kidney", "kidneys", "chop"],
    "piece": ["cubed", "diced", "chopped", "sliced", "cut", "chunks", "strips"],
    "shredded": ["shredded", "grated"],
    "ground": ["ground", "minced", "powder", "powdered", "meal"],
    "paste": ["paste", "butter", "puree", "pureed", "spread", "mashed"],
    "liquid": ["juice", "liquid", "broth", "stock", "milk", "oil", "syrup"],
    "cooked": ["cooked", "boiled", "baked", "roasted", "fried", "grilled", "drained",
               "canned", "steamed", "braised", "stewed"],
    "raw": ["raw", "fresh", "uncooked"],
    "dried": ["dry", "dried", "dehydrated"],
}

_FORM_CONFLICT = {
    frozenset(["paste", "whole"]): 0.9,
    frozenset(["paste", "piece"]): 0.85,
    frozenset(["paste", "ground"]): 0.55,
    frozenset(["ground", "whole"]): 0.6,
    frozenset(["ground", "piece"]): 0.5,
    frozenset(["liquid", "whole"]): 0.8,
    frozenset(["liquid", "piece"]): 0.75,
    frozenset(["liquid", "paste"]): 0.5,
    frozenset(["cooked", "raw"]): 0.55,
    frozenset(["cooked", "piece"]): 0.35,
    frozenset(["shredded", "paste"]): 0.6,
}

_PREP_NOISE = set("""
optional thawed frozen fresh large small medium finely roughly coarsely chopped diced
sliced minced cubed shredded grated peeled trimmed rinsed drained divided to taste for
from tube about and or of the a an into pieces cut plus more extra lightly
""".split())

_USDA_NOISE = set("""
nfs ns raw cooked boiled baked without with salt added imported variety meats by products
and or not further specified includes moisture style type prepared regular plain
""".split())


def _norm(text):
    text = (text or "").lower()
    text = re.sub(r"\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb|lbs|grams?)\b", " ", text)
    text = re.sub(r"[%\d]+", " ", text)
    return text


def _words(text):
    return re.findall(r"[a-z]+", text)


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _role_vector(words, text):
    vec = {}
    wset = set(words)
    for role, cues in _ROLE_CUES.items():
        score = 0.0
        for c in cues:
            if " " in c:
                if c in text:
                    score += 1.0
            elif c in wset:
                score += 1.0
        if score:
            vec[role] = score
    return vec


def _cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b.get(k, 0.0) for k in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _forms(words):
    wset = set(words)
    return {f for f, cues in _FORM_CUES.items() if wset.intersection(cues)}


def _brand_penalty(raw_usda):
    # Branded product entries tend to be Title Cased multiword names with no commas
    # before a product noun; these rarely play a single-ingredient role.
    try:
        head = raw_usda.split(",")[0].strip()
        tokens = head.split()
        caps = sum(1 for t in tokens if t[:1].isupper())
        if len(tokens) >= 2 and caps >= 2 and caps == len(tokens):
            return 0.6
        if raw_usda.isupper() and len(tokens) >= 3:
            return 0.4
    except Exception:
        pass
    return 0.0


def judging_function(ingredient, usda_match):
    try:
        ing_raw = str(ingredient or "")
        usda_raw = str(usda_match or "")
        if not ing_raw.strip() or not usda_raw.strip():
            return 0.0

        # Separate the core ingredient name from parentheticals/post-comma state.
        ing_text = _norm(ing_raw)
        ing_core = re.sub(r"\([^)]*\)", " ", ing_text).split(",")[0]
        ing_all_words = _words(ing_text)
        ing_core_words = [w for w in _words(ing_core) if w not in _PREP_NOISE]

        usda_text = _norm(usda_raw)
        usda_words = _words(usda_text)
        usda_segments = [s.strip() for s in usda_text.split(",") if s.strip()]
        usda_head_words = _words(usda_segments[0]) if usda_segments else []

        if not ing_core_words:
            ing_core_words = [w for w in ing_all_words if w not in _PREP_NOISE] or ing_all_words
        if not usda_words:
            return 0.0

        # 1) Identity anchor: does the ingredient's head noun(s) appear in USDA (stemmed)?
        ing_stems = [_stem(w) for w in ing_core_words]
        usda_stems = set(_stem(w) for w in usda_words if w not in _USDA_NOISE)
        head_noun = ing_stems[-1] if ing_stems else ""
        anchor_hit = 1.0 if head_noun in usda_stems else 0.0
        if not anchor_hit and head_noun:
            # prefix match for things like "pecan"/"pecans", "asadero"
            for s in usda_stems:
                if len(s) >= 4 and (s.startswith(head_noun[:5]) or head_noun.startswith(s[:5])):
                    anchor_hit = 0.7
                    break
        covered = sum(1 for s in ing_stems if s in usda_stems) / float(len(ing_stems))

        # Unexplained USDA content words -> distinct item / extra components.
        usda_content = [_stem(w) for w in usda_words
                        if w not in _USDA_NOISE and len(w) > 2]
        extra = [w for w in usda_content if w not in set(ing_stems)]
        extra_ratio = len(extra) / float(len(usda_content)) if usda_content else 0.0

        # 2) Culinary role compatibility via role-vector cosine.
        ing_roles = _role_vector(ing_core_words, ing_core)
        usda_roles = _role_vector(usda_words, usda_text)
        role_sim = _cosine(ing_roles, usda_roles)
        role_known = 1.0 if ing_roles else 0.0
        snack_clash = 1.0 if ("snack_product" in usda_roles and "snack_product" not in ing_roles) else 0.0

        # Cured vs fresh meat products behave differently (blood sausage != pork sausage)
        modifier_lost = 0.0
        if len(ing_core_words) >= 2:
            mods = [_stem(w) for w in ing_core_words[:-1]]
            lost = [m for m in mods if m not in usda_stems]
            modifier_lost = len(lost) / float(len(mods))

        # 3) Form / texture behavior compatibility.
        ing_forms = _forms(ing_core_words + _words(ing_core))
        ing_state_forms = _forms(ing_all_words)
        usda_forms = _forms(usda_words)
        form_cost = 0.0
        for fa in ing_forms | ing_state_forms:
            for fb in usda_forms:
                if fa != fb:
                    form_cost = max(form_cost, _FORM_CONFLICT.get(frozenset([fa, fb]), 0.0))
        # Ingredient is a processed form (paste/butter) but USDA is plain whole item.
        if "paste" in ing_forms and "paste" not in usda_forms:
            form_cost = max(form_cost, 0.8)
        # Recipe adds a raw item to cook; USDA already cooked changes behavior.
        if "cooked" in usda_forms and "cooked" not in ing_state_forms:
            form_cost = max(form_cost, 0.5)

        brand = _brand_penalty(usda_raw)

        # Combine as additive log-odds.
        z = -1.2
        z += 2.6 * anchor_hit
        z += 1.6 * covered
        z += 1.8 * role_sim * role_known + (0.4 if not role_known else 0.0)
        z -= 1.4 * extra_ratio
        z -= 1.5 * modifier_lost
        z -= 3.0 * form_cost
        z -= 2.5 * snack_clash
        z -= 2.2 * brand
        if anchor_hit and len(usda_segments) >= 2 and usda_head_words and \
                _stem(usda_head_words[-1]) in set(ing_stems):
            z += 0.5  # primary-food-first agreement

        prob = 1.0 / (1.0 + math.exp(-z))
        return round(100.0 * prob, 3)
    except Exception:
        return 0.0
