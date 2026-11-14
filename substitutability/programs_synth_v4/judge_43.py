import re

# Variant 3: concept-canonicalization with category-aware conflict detection.
# Both strings are rewritten into sets of canonical concept IDs via a phrase alias
# lexicon (longest-match-first). Each concept belongs to a category; two concepts in
# the same category that differ signal "resolves to a different food".

_ALIAS = {
    # vegetables
    "aubergine": "eggplant", "brinjal": "eggplant", "eggplant": "eggplant",
    "courgette": "zucchini", "zucchini": "zucchini", "summer squash": "zucchini",
    "scallion": "scallion", "scallions": "scallion", "spring onion": "scallion",
    "spring onions": "scallion", "green onion": "scallion", "green onions": "scallion",
    "onions spring or scallions": "scallion",
    "rocket": "arugula", "arugula": "arugula", "roquette": "arugula",
    "coriander leaves": "cilantro", "cilantro": "cilantro", "fresh coriander": "cilantro",
    "capsicum": "bell_pepper", "bell pepper": "bell_pepper", "sweet pepper": "bell_pepper",
    "peppers sweet": "bell_pepper",
    "swede": "rutabaga", "rutabaga": "rutabaga",
    "beetroot": "beet", "beet": "beet", "beets": "beet",
    "mangetout": "snow_pea", "snow peas": "snow_pea", "snow pea": "snow_pea",
    "okra": "okra", "ladies fingers": "okra", "bhindi": "okra",
    "endive": "endive", "chicory": "endive",
    "celeriac": "celeriac", "celery root": "celeriac",
    "pak choi": "bok_choy", "bok choy": "bok_choy", "chinese cabbage": "bok_choy",
    "garden peas": "pea", "green peas": "pea", "peas": "pea",
    "snap beans": "green_bean", "green beans": "green_bean", "string beans": "green_bean",
    "french beans": "green_bean", "beans snap": "green_bean",
    "maize": "corn", "corn": "corn", "sweetcorn": "corn",
    "yam": "yam", "sweet potato": "sweet_potato", "sweet potatoes": "sweet_potato",
    "potato": "potato", "potatoes": "potato",
    "borage": "borage", "giblets": "giblets",
    "tomato": "tomato", "tomatoes": "tomato", "carrot": "carrot", "carrots": "carrot",
    "cabbage": "cabbage", "spinach": "spinach", "lettuce": "lettuce", "kale": "kale",
    "garlic": "garlic", "onion": "onion", "onions": "onion", "leek": "leek", "leeks": "leek",
    "mushroom": "mushroom", "mushrooms": "mushroom", "celery": "celery",
    "broccoli": "broccoli", "cauliflower": "cauliflower", "cucumber": "cucumber",
    # legumes
    "garbanzo": "chickpea", "garbanzo beans": "chickpea", "chickpeas": "chickpea",
    "chickpea": "chickpea", "chick peas": "chickpea", "bengal gram": "chickpea",
    "pinto": "pinto_bean", "pinto beans": "pinto_bean",
    "kidney": "kidney_bean", "kidney beans": "kidney_bean",
    "black beans": "black_bean", "black turtle": "black_bean",
    "navy beans": "navy_bean", "haricot beans": "navy_bean",
    "fava": "fava_bean", "broad beans": "fava_bean", "fava beans": "fava_bean",
    "lima": "lima_bean", "butter beans": "lima_bean", "lima beans": "lima_bean",
    "lentils": "lentil", "lentil": "lentil", "soybeans": "soybean", "edamame": "soybean",
    "peanuts": "peanut", "peanut": "peanut", "groundnuts": "peanut",
    # nuts
    "pine nuts": "pine_nut", "pinyon": "pine_nut", "pinon": "pine_nut",
    "pignoli": "pine_nut", "pinyon nuts": "pine_nut",
    "hazelnuts": "hazelnut", "filberts": "hazelnut", "hazelnut": "hazelnut",
    "pecans": "pecan", "pecan": "pecan", "walnuts": "walnut", "walnut": "walnut",
    "almonds": "almond", "almond": "almond", "cashews": "cashew", "cashew": "cashew",
    "pistachios": "pistachio", "macadamia": "macadamia",
    "brazil nuts": "brazil_nut",
    # dairy
    "half and half": "half_and_half", "equal parts milk and cream": "half_and_half",
    "single cream": "light_cream", "light cream": "light_cream",
    "double cream": "heavy_cream", "heavy cream": "heavy_cream",
    "whipping cream": "heavy_cream",
    "cream": "cream", "milk": "milk", "kefir": "kefir", "yogurt": "yogurt",
    "yoghurt": "yogurt", "curd": "yogurt", "butter": "butter",
    "buttermilk": "buttermilk", "ghee": "ghee", "clarified butter": "ghee",
    # cheeses
    "asadero": "asadero", "colby": "colby", "cheddar": "cheddar", "mozzarella": "mozzarella",
    "parmesan": "parmesan", "parmigiano": "parmesan", "swiss": "swiss", "emmental": "swiss",
    "feta": "feta", "ricotta": "ricotta", "brie": "brie", "gouda": "gouda",
    "monterey": "monterey", "monterey jack": "monterey", "provolone": "provolone",
    "queso blanco": "queso_blanco", "paneer": "paneer", "cottage": "cottage",
    "cream cheese": "cream_cheese", "neufchatel": "cream_cheese",
    # sugars
    "confectioners sugar": "powdered_sugar", "powdered sugar": "powdered_sugar",
    "icing sugar": "powdered_sugar", "sugars powdered": "powdered_sugar",
    "caster sugar": "white_sugar", "granulated sugar": "white_sugar",
    "sugars granulated": "white_sugar", "brown sugar": "brown_sugar",
    "sugars brown": "brown_sugar", "sugar substitute": "sweetener",
    "sweetener": "sweetener", "stevia": "sweetener", "honey": "honey",
    # meats
    "pork": "pork", "beef": "beef", "lamb": "lamb", "mutton": "lamb", "veal": "veal",
    "chicken": "chicken", "poultry": "chicken", "turkey": "turkey", "duck": "duck",
    "goat": "goat", "venison": "venison", "bison": "bison", "buffalo": "bison",
    "fish": "fish", "salmon": "salmon", "whitefish": "whitefish", "tuna": "tuna",
    "cod": "cod", "haddock": "haddock", "trout": "trout", "shrimp": "shrimp",
    "prawn": "shrimp", "prawns": "shrimp", "crab": "crab", "lobster": "lobster",
    # cuts and parts
    "chicken flats": "wing", "flats": "wing", "wingettes": "wing", "wing": "wing",
    "wings": "wing", "drumette": "wing", "drumettes": "wing",
    "drumstick": "drumstick", "drumsticks": "drumstick", "thigh": "thigh",
    "thighs": "thigh", "breast": "breast", "breasts": "breast", "skin": "skin",
    "liver": "liver", "tongue": "tongue", "heart": "heart", "kidneys": "kidney_organ",
    "shank": "shank", "chuck": "chuck", "sirloin": "sirloin", "brisket": "brisket",
    "tenderloin": "tenderloin", "ribeye": "ribeye", "loin": "loin", "shoulder": "shoulder",
    "leg": "leg", "rib": "rib", "ribs": "rib", "belly": "belly",
    # processed meats
    "sausage": "sausage", "frankfurter": "frankfurter", "hot dog": "frankfurter",
    "wiener": "frankfurter", "jerky": "jerky", "bacon": "bacon", "ham": "ham",
    "salami": "salami", "pepperoni": "pepperoni", "patty": "patty", "chorizo": "chorizo",
    # grains / cereals
    "corn flakes": "corn_flakes", "maize flakes": "corn_flakes", "cornflakes": "corn_flakes",
    "oat": "oat", "oats": "oat", "oatmeal": "oat", "rice": "rice", "wheat": "wheat",
    "barley": "barley", "quinoa": "quinoa", "flour": "flour", "plain flour": "flour",
    "all purpose flour": "flour", "cornstarch": "cornstarch", "cornflour": "cornstarch",
    # fruits
    "strawberry": "strawberry", "strawberries": "strawberry", "apple": "apple",
    "banana": "banana", "lemon": "lemon", "lime": "lime", "orange": "orange",
    "mango": "mango", "grape": "grape", "raisins": "raisin", "sultanas": "raisin",
    "cantaloupe": "cantaloupe", "rockmelon": "cantaloupe",
    # oils / misc
    "olive oil": "olive_oil", "vegetable oil": "veg_oil", "canola": "canola",
    "rapeseed oil": "canola", "ginger": "ginger", "cinnamon": "cinnamon",
    "cumin": "cumin", "paprika": "paprika", "turmeric": "turmeric",
}

_CATEGORY = {}
def _cat(cat, items):
    for i in items:
        _CATEGORY[i] = cat
_cat("veg", ["eggplant", "zucchini", "scallion", "arugula", "cilantro", "bell_pepper",
             "rutabaga", "beet", "snow_pea", "okra", "endive", "celeriac", "bok_choy",
             "pea", "green_bean", "corn", "yam", "sweet_potato", "potato", "borage",
             "tomato", "carrot", "cabbage", "spinach", "lettuce", "kale", "garlic",
             "onion", "leek", "mushroom", "celery", "broccoli", "cauliflower", "cucumber"])
_cat("legume", ["chickpea", "pinto_bean", "kidney_bean", "black_bean", "navy_bean",
                "fava_bean", "lima_bean", "lentil", "soybean", "peanut"])
_cat("nut", ["pine_nut", "hazelnut", "pecan", "walnut", "almond", "cashew",
             "pistachio", "macadamia", "brazil_nut"])
_cat("dairy", ["half_and_half", "light_cream", "heavy_cream", "cream", "milk", "kefir",
               "yogurt", "butter", "buttermilk", "ghee"])
_cat("cheese", ["asadero", "colby", "cheddar", "mozzarella", "parmesan", "swiss", "feta",
                "ricotta", "brie", "gouda", "monterey", "provolone", "queso_blanco",
                "paneer", "cottage", "cream_cheese"])
_cat("sugar", ["powdered_sugar", "white_sugar", "brown_sugar", "sweetener", "honey"])
_cat("animal", ["pork", "beef", "lamb", "veal", "chicken", "turkey", "duck", "goat",
                "venison", "bison", "fish", "salmon", "whitefish", "tuna", "cod",
                "haddock", "trout", "shrimp", "crab", "lobster"])
_cat("part", ["wing", "drumstick", "thigh", "breast", "skin", "liver", "tongue", "heart",
              "kidney_organ", "shank", "chuck", "sirloin", "brisket", "tenderloin",
              "ribeye", "loin", "shoulder", "leg", "rib", "belly", "giblets"])
_cat("processed", ["sausage", "frankfurter", "jerky", "bacon", "ham", "salami",
                   "pepperoni", "patty", "chorizo"])
_cat("grain", ["corn_flakes", "oat", "rice", "wheat", "barley", "quinoa", "flour",
               "cornstarch"])
_cat("fruit", ["strawberry", "apple", "banana", "lemon", "lime", "orange", "mango",
               "grape", "raisin", "cantaloupe"])
_cat("fat", ["olive_oil", "veg_oil", "canola"])
_cat("spice", ["ginger", "cinnamon", "cumin", "paprika", "turmeric"])

# Categories where a same-category mismatch means a genuinely different food.
_EXCLUSIVE = {"veg", "legume", "nut", "cheese", "sugar", "animal", "processed", "grain",
              "fruit", "fat", "spice", "dairy"}

# Concepts that are generic parents of more specific ones (not a conflict).
_PARENT = {"fish": {"salmon", "whitefish", "tuna", "cod", "haddock", "trout"},
           "cream": {"half_and_half", "light_cream", "heavy_cream"},
           "onion": {"scallion"}, "chicken": {"turkey"} and set(),
           "corn": {"corn_flakes"}, "oat": set()}

_NOISE = set("""g kg mg ml l oz lb cup cups tbsp tsp fresh frozen raw cooked chopped sliced
diced minced shredded grated crumbled drained thawed soaked overnight trimmed of visible
fat plain and or with without salt added the a an from tube canned dried ground whole large
small medium boneless skinless nfs ns ready to eat ready-to-eat separable lean choice
select prime unheated uncooked boiled pan fried roasted toasted to 1 8 inch in""".split())

_FLAVOR = {"strawberry", "vanilla", "chocolate", "honey", "blueberry", "peach", "cherry",
           "lemon", "cinnamon", "maple", "raspberry"}


def _norm(s):
    s = (s or "").lower()
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)\b", " ", s)
    s = s.replace("-", " ").replace("/", " ")
    s = re.sub(r"[^a-z0-9,() ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _concepts(text):
    """Longest-match phrase scan producing ordered list of concept ids."""
    words = re.sub(r"[,()]", " ", text).split()
    out = []
    i = 0
    max_n = 5
    while i < len(words):
        hit = None
        for n in range(min(max_n, len(words) - i), 0, -1):
            phrase = " ".join(words[i:i + n])
            if phrase in _ALIAS:
                hit = (_ALIAS[phrase], n)
                break
            if n == 1 and phrase.endswith("s") and phrase[:-1] in _ALIAS:
                hit = (_ALIAS[phrase[:-1]], 1)
                break
        if hit:
            out.append(hit[0])
            i += hit[1]
        else:
            i += 1
    return out


def _residual(text):
    toks = re.sub(r"[,()]", " ", text).split()
    return {t.rstrip("s") for t in toks if t not in _NOISE and len(t) > 2}


def _related(a, b):
    if a == b:
        return True
    if b in _PARENT.get(a, set()) or a in _PARENT.get(b, set()):
        return True
    return False


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient)
        usda = _norm(usda_match)
        if not ing or not usda:
            return 0.0

        # Strip prep/state after the first comma in the ingredient, but keep it for flavor check.
        ing_core = ing.split(",")[0]
        # Pull parenthetical aliases out of the USDA string and treat them as extra names.
        usda_paren = " ".join(re.findall(r"\(([^)]*)\)", usda))
        usda_flat = re.sub(r"\([^)]*\)", " ", usda)
        ing_core = re.sub(r"\([^)]*\)", " ", ing_core)

        ci = _concepts(ing_core)
        cu = _concepts(usda_flat) + _concepts(usda_paren)
        # USDA primary food = concepts in the first two comma segments
        usda_head = _concepts(" ".join(usda_flat.split(",")[:2]))

        score = 50.0
        si, su = set(ci), set(cu)

        if si and su:
            shared = {a for a in si if any(_related(a, b) for b in su)}
            coverage = len(shared) / len(si)
            score += 30.0 * coverage
            # head agreement: ingredient's last concept (head noun) found in USDA head
            head_i = ci[-1]
            if any(_related(head_i, b) for b in usda_head):
                score += 10.0
            elif any(_related(head_i, b) for b in su):
                score += 4.0
            else:
                score -= 12.0

            # conflicts: same exclusive category, unrelated concepts, not otherwise matched
            conflicts = 0
            for a in si - shared:
                ca = _CATEGORY.get(a)
                if ca in _EXCLUSIVE:
                    if any(_CATEGORY.get(b) == ca and not _related(a, b) for b in su):
                        conflicts += 1
            for b in su - si:
                cb = _CATEGORY.get(b)
                if cb == "part" and any(_CATEGORY.get(a) == "part" for a in si) and \
                        not any(_related(a, b) for a in si):
                    conflicts += 1
            score -= 18.0 * conflicts

            # ingredient is a mix ("x and y") but USDA only covers part
            if " and " in ing_core and coverage < 1.0 and len(si) >= 2:
                score -= 12.0
            # total category miss
            cats_i = {_CATEGORY.get(a) for a in si}
            cats_u = {_CATEGORY.get(b) for b in su}
            if not (cats_i & cats_u):
                score -= 25.0
        else:
            # fall back to residual lexical overlap when the lexicon is silent
            ri, ru = _residual(ing_core), _residual(usda_flat + " " + usda_paren)
            if ri and ru:
                j = len(ri & ru) / float(len(ri | ru))
                score += 40.0 * j - 15.0
                if ri & ru:
                    score += 5.0
            else:
                score -= 15.0

        # flavor added in USDA but not requested
        u_words = set(usda.replace(",", " ").split())
        i_words = set(ing.replace(",", " ").split())
        if (u_words & _FLAVOR) - i_words:
            score -= 15.0
        # sweetener substitute vs real sugar
        if "substitute" in u_words and "substitute" not in i_words:
            score -= 15.0
        # cooking state conflicts: fresh/raw ingredient vs cooked/boiled USDA product
        if ("fresh" in i_words or "raw" in i_words) and \
                (u_words & {"cooked", "boiled", "fried", "baked"}):
            if "fried" not in i_words and "crispy" not in i_words:
                score -= 10.0
        # canned ingredient vs raw USDA
        if "canned" in i_words and "raw" in u_words:
            score -= 10.0
        # brand names in caps in original USDA usually indicate a specific product
        if re.search(r"\b[A-Z]{4,}\b", usda_match or ""):
            if not re.search(r"\b[A-Z]{4,}\b", ingredient or ""):
                score -= 8.0

        return float(max(0.0, min(100.0, score)))
    except Exception:
        return 0.0
