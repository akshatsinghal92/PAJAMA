import re
import math

# Variant 2: soft category-distribution vectors.
# Each text is mapped to a probability distribution over food categories via
# weighted stem voting (head noun weighted more heavily); the score combines the
# Bhattacharyya coefficient between the two distributions with a fine-grained
# sub-category (species/kind) agreement term and a form-change penalty.

_CATEGORY_STEMS = {
    "dairy": {"milk": 3, "chees": 3, "yogurt": 3, "yoghurt": 3, "cream": 2, "butter": 2,
              "kefir": 3, "whey": 3, "ricotta": 3, "brie": 3, "camembert": 3, "cheddar": 3,
              "mozzarella": 3, "parmesan": 3, "feta": 3, "cottage": 2, "ghee": 2, "curd": 2},
    "produce_fruit": {"apple": 3, "orange": 3, "banana": 3, "berr": 3, "grape": 3, "lemon": 3,
                      "lime": 3, "peach": 3, "pear": 3, "plum": 3, "mango": 3, "melon": 3,
                      "cherr": 3, "fruit": 3, "applesauc": 3, "apricot": 3, "fig": 2, "date": 1,
                      "raisin": 3, "pineappl": 3, "papaya": 3, "kiwi": 3},
    "produce_veg": {"radish": 3, "carrot": 3, "onion": 3, "potato": 3, "tomato": 3, "lettuc": 3,
                    "spinach": 3, "cabbag": 3, "kale": 3, "borag": 3, "pepper": 1, "celery": 3,
                    "squash": 3, "zucchini": 3, "broccoli": 3, "cauliflow": 3, "seaweed": 3,
                    "kombu": 3, "laver": 3, "nori": 3, "kelp": 3, "mushroom": 3, "vegetabl": 3,
                    "greens": 3, "leek": 3, "beet": 3, "cucumb": 3, "eggplant": 3, "corn": 1},
    "meat_poultry": {"chicken": 3, "turkey": 3, "beef": 3, "pork": 3, "lamb": 3, "veal": 3,
                     "liver": 2, "duck": 3, "bacon": 3, "ham": 2, "sausag": 3, "meat": 3,
                     "patt": 1, "steak": 1, "ground": 0.5, "variety": 1, "goat": 2, "venison": 3},
    "fish_seafood": {"fish": 3, "salmon": 3, "swordfish": 3, "tuna": 3, "cod": 3, "shrimp": 3,
                     "crab": 3, "lobster": 3, "clam": 3, "oyster": 3, "mussel": 3, "anchov": 3,
                     "sardin": 3, "trout": 3, "halibut": 3, "tilapia": 3, "squid": 3},
    "grain": {"rice": 3, "bran": 2, "wheat": 3, "flour": 3, "oat": 3, "barley": 3, "bread": 3,
              "cornbread": 3, "pasta": 3, "noodl": 3, "cereal": 3, "quinoa": 3, "rye": 3,
              "cracker": 2, "tortilla": 3, "cornmeal": 3, "millet": 3, "couscous": 3},
    "legume_soy": {"bean": 3, "lentil": 3, "chickpea": 3, "pea": 2, "tofu": 3, "sufu": 3,
                   "fuyu": 3, "soy": 2, "tempeh": 3, "edamam": 3, "peanut": 2, "miso": 2},
    "nut_seed": {"nut": 3, "seed": 3, "flaxseed": 3, "linseed": 3, "pinyon": 3, "pine": 1,
                 "almond": 3, "pecan": 3, "walnut": 3, "cashew": 3, "pistachio": 3,
                 "hazelnut": 3, "sesam": 3, "chia": 3, "sunflow": 2, "pumpkin": 1,
                 "kernel": 2, "coconut": 2, "macadamia": 3},
    "spice_herb": {"spice": 3, "ginger": 2, "cinnamon": 3, "cumin": 3, "basil": 3, "oregano": 3,
                   "thyme": 3, "parsley": 2, "pepper": 1, "paprika": 3, "turmeric": 3,
                   "nutmeg": 3, "clove": 2, "herb": 3, "dill": 3, "rosemary": 3, "vanilla": 1,
                   "garlic": 2, "salt": 2},
    "oil_fat": {"oil": 3, "lard": 3, "shortening": 3, "margarin": 3, "fat": 0.5, "tallow": 3},
    "sweetener": {"sugar": 3, "honey": 3, "syrup": 3, "molass": 3, "sweeten": 2,
                  "substitut": 1, "agave": 3, "confection": 2, "candy": 2, "pudding": 2,
                  "dessert": 2, "chocolat": 2},
    "condiment_sauce": {"sauce": 3, "ketchup": 3, "mustard": 3, "mayonnais": 3, "dressing": 3,
                        "vinegar": 3, "relish": 3, "salsa": 3, "paste": 1, "chutney": 3,
                        "gravy": 3, "dip": 2},
    "beverage": {"tea": 3, "coffee": 3, "juice": 2, "soda": 3, "beverag": 3, "drink": 3,
                 "wine": 3, "beer": 3, "water": 1},
    "egg": {"egg": 3, "yolk": 3, "albumen": 3},
}

# words that change form/state in ways that typically break substitutability
_FORM_GROUPS = [
    {"dried", "dehydrated", "powder", "powdered", "dry"},
    {"oil"},
    {"pudding", "mix"},
    {"substitute", "imitation"},
    {"toasted", "fried", "broiled", "roasted", "baked", "cooked", "grilled"},
]

_NOISE = {"g", "kg", "mg", "ml", "oz", "lb", "cup", "cups", "tbsp", "tsp", "fresh", "raw",
          "nfs", "ns", "and", "or", "with", "the", "a", "of", "for", "from", "to", "in",
          "all", "commercial", "varieties", "regular", "prepared", "unprepared", "sliced",
          "chopped", "diced", "minced", "thawed", "frozen", "large", "small", "medium",
          "whole", "low", "nonfat", "reduced", "lean", "bottled", "garnish", "tube"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)?\b", " ", t)
    t = re.sub(r"\d+%", " ", t)
    return t


def _tokens(text):
    return [w for w in re.findall(r"[a-z]+", text) if len(w) > 1]


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _head_terms(ing_clean, usda_clean):
    ing_main = ing_clean.split(",")[0]
    ing_toks = _tokens(ing_main)
    usda_parts = [p.strip() for p in usda_clean.split(",") if p.strip()]
    usda_head = _tokens(usda_parts[0]) if usda_parts else []
    # ingredient head: last content word of the main phrase
    content = [w for w in ing_toks if w not in _NOISE]
    ing_head = content[-1:] if content else ing_toks[-1:]
    return ing_head, usda_head


def _distribution(tokens, head):
    scores = {c: 0.0 for c in _CATEGORY_STEMS}
    head_set = set(head)
    for w in tokens:
        sw = _stem(w)
        mult = 2.5 if w in head_set or sw in {_stem(h) for h in head_set} else 1.0
        for cat, stems in _CATEGORY_STEMS.items():
            best = 0.0
            for st, wt in stems.items():
                if sw == st or w == st or (len(st) >= 4 and (sw.startswith(st) or w.startswith(st))):
                    best = max(best, wt)
            scores[cat] += best * mult
    total = sum(scores.values())
    if total <= 0:
        return None
    return {c: v / total for c, v in scores.items()}


def _bhattacharyya(p, q):
    return sum(math.sqrt(p[c] * q[c]) for c in p)


def _species_tokens(tokens):
    out = set()
    for w in tokens:
        if w in _NOISE:
            continue
        sw = _stem(w)
        for stems in _CATEGORY_STEMS.values():
            for st, wt in stems.items():
                if wt >= 3 and (sw == st or w == st or (len(st) >= 4 and sw.startswith(st))):
                    out.add(st)
    return out


def _form_penalty(ing_tokens, usda_tokens):
    pen = 0.0
    it, ut = set(ing_tokens), set(usda_tokens)
    for grp in _FORM_GROUPS:
        a, b = bool(it & grp), bool(ut & grp)
        if a != b:
            pen += 1.0
    return pen


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ic = _clean(ingredient)
        uc = _clean(usda_match)
        it = _tokens(ic)
        ut = _tokens(uc)
        if not it or not ut:
            return 0.0

        ing_head, usda_head = _head_terms(ic, uc)
        p = _distribution(it, ing_head)
        q = _distribution(ut, usda_head)

        if p is None or q is None:
            # unknown category on at least one side: fall back to lexical head overlap
            iset = {_stem(w) for w in it if w not in _NOISE}
            uset = {_stem(w) for w in ut if w not in _NOISE}
            if not iset or not uset:
                return 2.0
            j = len(iset & uset) / float(len(iset | uset))
            return round(2.0 + 5.0 * j, 4)

        bc = _bhattacharyya(p, q)  # 0..1 category consistency

        # dominant categories
        pi = max(p, key=p.get)
        qi = max(q, key=q.get)
        same_dom = 1.0 if pi == qi else 0.0

        # fine-grained kind agreement within category
        si = _species_tokens(it)
        su = _species_tokens(ut)
        if si and su:
            kind = len(si & su) / float(len(si | su))
            kind_bonus = 2.5 * kind
            if not (si & su):
                kind_bonus -= 1.5
        else:
            kind_bonus = 0.0

        form_pen = _form_penalty(it, ut)

        # lexical agreement on the remaining (non-category) words, e.g. "olive", "breast"
        iset = {_stem(w) for w in it if w not in _NOISE}
        uset = {_stem(w) for w in ut if w not in _NOISE}
        lex = len(iset & uset) / float(len(iset | uset)) if (iset and uset) else 0.0
        cover = len(iset & uset) / float(len(iset)) if iset else 0.0
        head_hit = 1.0 if ({_stem(h) for h in ing_head} & {_stem(h) for h in usda_head}) else 0.0

        raw = (3.5 * bc + 1.0 * same_dom + kind_bonus + 2.0 * lex + 1.5 * cover
               + 1.0 * head_hit - 0.9 * form_pen)
        score = (raw + 3.0) / 15.5 * 10.0
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
