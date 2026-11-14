import re

# Alias table: surface phrase -> canonical concept id.
_ALIASES = {
    "aubergine": "eggplant", "eggplant": "eggplant", "brinjal": "eggplant",
    "courgette": "zucchini", "zucchini": "zucchini",
    "garbanzo": "chickpea", "garbanzos": "chickpea", "chickpea": "chickpea", "chickpeas": "chickpea", "chick peas": "chickpea", "chana": "chickpea",
    "scallion": "scallion", "scallions": "scallion", "spring onion": "scallion", "spring onions": "scallion", "green onion": "scallion", "green onions": "scallion",
    "coriander leaves": "cilantro", "cilantro": "cilantro", "fresh coriander": "cilantro",
    "rocket": "arugula", "arugula": "arugula", "roquette": "arugula",
    "capsicum": "bell pepper", "bell pepper": "bell pepper", "sweet pepper": "bell pepper", "peppers sweet": "bell pepper",
    "mangetout": "snow pea", "snow pea": "snow pea", "snow peas": "snow pea",
    "beetroot": "beet", "beet": "beet", "beets": "beet",
    "swede": "rutabaga", "rutabaga": "rutabaga",
    "granada": "pomegranate", "pomegranate": "pomegranate", "pomegranates": "pomegranate",
    "mandarin": "mandarin", "mandarin orange": "mandarin", "clementine": "mandarin", "clementines": "mandarin", "tangerine": "mandarin", "tangerines": "mandarin", "satsuma": "mandarin",
    "prawn": "shrimp", "prawns": "shrimp", "shrimp": "shrimp",
    "minced beef": "ground beef", "beef mince": "ground beef", "ground beef": "ground beef", "hamburger meat": "ground beef",
    "icing sugar": "powdered sugar", "powdered sugar": "powdered sugar", "confectioners sugar": "powdered sugar", "sugars powdered": "powdered sugar",
    "caster sugar": "sugar", "granulated sugar": "sugar", "white sugar": "sugar", "sugars granulated": "sugar", "sugar": "sugar",
    "cornflour": "cornstarch", "cornstarch": "cornstarch", "corn starch": "cornstarch",
    "plain flour": "wheat flour", "all purpose flour": "wheat flour", "wheat flour": "wheat flour", "flour": "wheat flour",
    "double cream": "heavy cream", "heavy cream": "heavy cream", "whipping cream": "heavy cream", "heavy whipping": "heavy cream",
    "single cream": "light cream", "light cream": "light cream", "half and half": "half and half",
    "maize": "corn", "sweetcorn": "corn", "sweet corn": "corn", "corn": "corn",
    "chilli": "chili", "chili": "chili", "chile": "chili", "chilies": "chili", "chillies": "chili", "hot pepper": "chili", "peppers hot chili": "chili",
    "okra": "okra", "ladies fingers": "okra", "bhindi": "okra",
    "pak choi": "bok choy", "bok choy": "bok choy", "pak choy": "bok choy", "cabbage chinese pak choi": "bok choy",
    "chinese broccoli": "gai lan", "gai lan": "gai lan", "kai lan": "gai lan", "broccoli chinese": "gai lan",
    "broad bean": "fava", "broad beans": "fava", "fava": "fava", "fava beans": "fava",
    "haricot": "navy bean", "navy beans": "navy bean", "navy bean": "navy bean", "beans navy": "navy bean",
    "pinto": "pinto", "kidney": "kidney bean", "beans kidney": "kidney bean", "kidney beans": "kidney bean",
    "tan beans": "tan bean", "beans tan": "tan bean",
    "black turtle": "black bean", "black beans": "black bean", "beans black": "black bean",
    "lima": "lima", "butter beans": "lima", "butter bean": "lima",
    "cocoa butter": "cocoa butter", "cocoa": "cocoa", "cocoa powder": "cocoa",
    "pumpkin seeds": "pumpkin seed", "pepitas": "pumpkin seed", "pumpkin seed": "pumpkin seed",
    "watermelon seed": "watermelon seed",
    "sunflower seeds": "sunflower seed", "sunflower seed": "sunflower seed",
    "pecans": "pecan", "pecan": "pecan", "walnuts": "walnut", "walnut": "walnut",
    "almonds": "almond", "almond": "almond", "filbert": "hazelnut", "filberts": "hazelnut", "hazelnut": "hazelnut", "hazelnuts": "hazelnut",
    "groundnut": "peanut", "groundnuts": "peanut", "peanut": "peanut", "peanuts": "peanut",
    "escarole": "escarole", "endive": "endive", "chicory": "endive",
    "asparagus": "asparagus", "broccoli": "broccoli", "cauliflower": "cauliflower",
    "butternut": "butternut", "squash": "squash", "pumpkin": "pumpkin",
    "stew meat": "stew meat", "beef stew": "beef stew dish",
    "sirloin": "sirloin", "steak": "steak",
    "sea bass": "sea bass", "seabass": "sea bass", "branzino": "sea bass",
    "cod": "cod", "salmon": "salmon", "tuna": "tuna", "tilapia": "tilapia",
    "liver": "liver", "heart": "heart", "kidneys": "kidney organ", "tongue": "tongue",
    "lamb": "lamb", "mutton": "lamb", "beef": "beef", "pork": "pork", "chicken": "chicken", "turkey": "turkey", "veal": "veal",
    "ham": "ham", "bacon": "bacon", "sausage": "sausage", "cervelat": "sausage", "salami": "salami", "bratwurst": "sausage",
    "olive oil": "olive oil", "palm oil": "palm oil", "oil palm": "palm oil", "canola": "canola oil", "rapeseed oil": "canola oil",
    "olives": "olive", "olive": "olive",
    "yogurt": "yogurt", "yoghurt": "yogurt", "curd": "yogurt",
    "cheese": "cheese", "milk": "milk", "butter": "butter", "egg": "egg", "eggs": "egg",
    "italian dressing": "italian dressing", "salad dressing": "dressing", "dressing": "dressing", "vinaigrette": "dressing",
    "crackers": "cracker", "cracker": "cracker", "wheat thins": "cracker",
    "rice": "rice", "pasta": "pasta", "noodles": "noodle", "bread": "bread",
    "soup": "soup", "soups": "soup",
    "garlic": "garlic", "ginger": "ginger", "onion": "onion", "onions": "onion", "shallot": "shallot", "shallots": "shallot",
    "tomato": "tomato", "tomatoes": "tomato", "potato": "potato", "potatoes": "potato", "carrot": "carrot", "carrots": "carrot",
    "sweet potato": "sweet potato", "yam": "yam", "kumara": "sweet potato",
    "spinach": "spinach", "kale": "kale", "lettuce": "lettuce", "cabbage": "cabbage",
    "apple": "apple", "apples": "apple", "banana": "banana", "bananas": "banana", "orange": "orange", "oranges": "orange",
    "lemon": "lemon", "lime": "lime", "grape": "grape", "grapes": "grape", "mango": "mango", "papaya": "papaya", "pawpaw": "papaya",
    "molasses": "molasses", "treacle": "molasses", "golden syrup": "cane syrup",
    "soda": "soda", "baking soda": "baking soda", "bicarbonate of soda": "baking soda", "bicarb": "baking soda",
}

# Concepts that are generic "heads" (category nouns) - less decisive alone.
_GENERIC = {"beef", "pork", "lamb", "chicken", "turkey", "veal", "squash", "cheese", "milk", "yogurt",
            "dressing", "soup", "sugar", "wheat flour", "corn", "onion", "oil", "orange"}

# Processed / dish words that signal a different food when only on one side.
_DISH_WORDS = {"soup", "stew", "entree", "patty", "casserole", "sandwich", "pie", "sauce", "salad", "pizza",
               "burrito", "dinner", "frozen meal", "nuggets", "condensed", "baby food", "babyfood"}

# Modifier pairs that indicate a different variety.
_CONFLICT_MODS = [("reduced fat", "full"), ("reduced calorie", "regular"), ("nonfat", None), ("sweet", None)]

_STOP = {"g", "kg", "mg", "ml", "and", "or", "with", "of", "the", "a", "fresh", "raw", "chopped", "sliced", "diced",
         "minced", "shredded", "grated", "cubed", "melted", "baked", "cooked", "roasted", "frozen", "thawed",
         "canned", "dried", "dry", "soaked", "overnight", "boiled", "braised", "fried", "peeled", "whole",
         "plain", "regular", "commercial", "ns", "as", "to", "eaten", "mixed", "species", "heat", "without",
         "salt", "uncooked", "mature", "seeds", "prepared", "large", "small", "medium", "from", "tube"}


def _norm(s):
    s = (s or "").lower()
    s = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb|tbsp|tsp|cups?)\b", " ", s)
    s = re.sub(r"[^a-z\s,()]", " ", s)
    return s


def _split_parens(s):
    inside = " ".join(re.findall(r"\(([^)]*)\)", s))
    outside = re.sub(r"\([^)]*\)", " ", s)
    return outside, inside


def _concepts(text):
    """Greedy longest-phrase alias lookup over a word sequence, plus comma-joined reversed USDA phrases."""
    found = []
    words = re.findall(r"[a-z]+", text)
    i = 0
    while i < len(words):
        hit = None
        for n in (4, 3, 2, 1):
            if i + n <= len(words):
                ph = " ".join(words[i:i + n])
                if ph in _ALIASES:
                    hit = (_ALIASES[ph], n)
                    break
        if hit:
            found.append(hit[0])
            i += hit[1]
        else:
            i += 1
    return found


def _usda_concepts(desc):
    """USDA descriptions are inverted ('Beans, kidney'); build phrases from adjacent segments both ways."""
    segs = [x.strip() for x in desc.split(",") if x.strip()]
    found = _concepts(" ".join(segs))
    for a, b in zip(segs, segs[1:]):
        found += _concepts(b + " " + a)
    if len(segs) >= 3:
        found += _concepts(segs[2] + " " + segs[1] + " " + segs[0])
    return found, segs


def _content_words(text):
    return {w for w in re.findall(r"[a-z]+", text) if w not in _STOP and len(w) > 2}


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient)
        usd = _norm(usda_match)
        if not ing.strip() or not usd.strip():
            return 0.0

        ing_main = ing.split(",")[0]
        ing_post = ing[len(ing_main):]
        ing_out, ing_par = _split_parens(ing_main)
        usd_out, usd_par = _split_parens(usd)

        ic = _concepts(ing_out) + _concepts(ing_par) + _concepts(ing_post)
        ic_main = _concepts(ing_out)
        uc, segs = _usda_concepts(usd_out)
        uc += _concepts(usd_par)

        ic_set, uc_set = set(ic), set(uc)
        ic_specific = {c for c in ic_set if c not in _GENERIC}
        uc_specific = {c for c in uc_set if c not in _GENERIC}

        score = 50.0

        # Head concept of ingredient = last specific concept in the main phrase (English head-final).
        head = None
        for c in reversed(ic_main):
            if c not in _GENERIC:
                head = c
                break
        if head is None and ic_main:
            head = ic_main[-1]

        if head is not None:
            if head in uc_set:
                score += 30
            elif uc_specific and head not in _GENERIC:
                score -= 30  # resolves to a different specific food
            elif head in _GENERIC and head in uc_set:
                score += 15

        shared_specific = ic_specific & uc_specific
        score += 8 * min(len(shared_specific), 2)
        shared_generic = (ic_set & uc_set) - shared_specific
        score += 4 * min(len(shared_generic), 2)

        # Specific foods on the USDA side the ingredient never mentions -> different food.
        extra = uc_specific - ic_specific
        score -= 10 * min(len(extra), 3)

        # Lexical fallback when the alias table knows nothing.
        iw, uw = _content_words(ing_out + " " + ing_par), _content_words(usd)
        if iw and uw:
            ov = len(iw & uw) / float(len(iw))
            if not ic_set or not uc_set:
                score += 30 * ov - 10
            else:
                score += 8 * ov

        # Dish / processed form on USDA side only.
        usd_words = " " + usd + " "
        for dw in _DISH_WORDS:
            if (" " + dw + " ") in usd_words or (" " + dw + ",") in usd_words:
                if dw not in ing:
                    score -= 15
                    break

        # Variety modifiers on USDA side not in ingredient (e.g. reduced fat).
        for mod in ("reduced fat", "reduced calorie", "low sodium", "fat free"):
            if mod in usd and mod not in ing:
                score -= 12
        if "sweet" in ing_out and "sweet" not in usd and "dressing" in ing_out:
            score -= 8

        return float(max(0.0, min(100.0, score)))
    except Exception:
        return 0.0
