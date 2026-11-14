import re

# Variant 3: lexicon / taxonomy lookup. Each text is mapped to a canonical
# food concept and a broader family; scores reflect taxonomy distance.

_CONCEPTS = {
    # concept: (family, [surface forms])
    "olive oil": ("oil", ["olive oil"]),
    "vegetable oil": ("oil", ["vegetable oil", "canola oil", "sunflower oil", "corn oil", "soybean oil"]),
    "butter": ("dairy fat", ["butter"]),
    "cottage cheese": ("cheese", ["cottage cheese", "cheese cottage"]),
    "cheddar": ("cheese", ["cheddar", "cheese cheddar"]),
    "mozzarella": ("cheese", ["mozzarella", "cheese mozzarella"]),
    "parmesan": ("cheese", ["parmesan", "cheese parmesan"]),
    "cream cheese": ("cheese", ["cream cheese", "cheese cream"]),
    "yogurt": ("cultured dairy", ["yogurt", "yoghurt"]),
    "frozen yogurt": ("frozen dessert", ["frozen yogurt"]),
    "ice cream": ("frozen dessert", ["ice cream"]),
    "milk": ("dairy", ["milk"]),
    "chicken": ("poultry", ["chicken"]),
    "turkey": ("poultry", ["turkey"]),
    "beef": ("red meat", ["beef", "steak"]),
    "pork": ("red meat", ["pork", "ham", "bacon"]),
    "swordfish": ("fish", ["swordfish"]),
    "salmon": ("fish", ["salmon"]),
    "tuna": ("fish", ["tuna"]),
    "shrimp": ("shellfish", ["shrimp", "prawn"]),
    "corn": ("vegetable", ["corn", "sweet corn", "maize"]),
    "potato": ("starchy vegetable", ["potato", "potatoes"]),
    "gnocchi": ("pasta", ["gnocchi"]),
    "pasta": ("pasta", ["pasta", "spaghetti", "macaroni", "penne", "noodle", "noodles"]),
    "rice": ("grain", ["rice"]),
    "oat": ("grain", ["oat", "oats", "oatmeal"]),
    "cereal": ("breakfast cereal", ["cereal", "cereals", "granola"]),
    "bread": ("bakery", ["bread", "loaf", "toast"]),
    "garlic": ("allium", ["garlic"]),
    "onion": ("allium", ["onion", "onions", "shallot"]),
    "ginger": ("spice", ["ginger"]),
    "guava": ("fruit", ["guava"]),
    "banana": ("fruit", ["banana", "bananas"]),
    "apple": ("fruit", ["apple", "apples"]),
    "citrus": ("fruit", ["ugli fruit", "orange", "grapefruit", "tangerine", "lemon", "lime"]),
    "fruit juice": ("beverage", ["fruit juice", "juice"]),
    "chia seed": ("seed", ["chia"]),
    "flaxseed": ("seed", ["flaxseed", "flax seed", "linseed"]),
    "salad dressing": ("condiment", ["dressing", "salad dressing", "vinaigrette"]),
    "mayonnaise": ("condiment", ["mayonnaise", "mayo"]),
    "tomato": ("vegetable", ["tomato", "tomatoes"]),
    "sugar": ("sweetener", ["sugar"]),
    "honey": ("sweetener", ["honey"]),
    "egg": ("egg", ["egg", "eggs"]),
    "flour": ("flour", ["flour"]),
}

_FAMILY_GROUPS = [
    {"cheese", "dairy", "cultured dairy", "dairy fat"},
    {"poultry", "red meat"},
    {"fish", "shellfish"},
    {"vegetable", "starchy vegetable", "allium"},
    {"pasta", "grain", "flour", "bakery", "breakfast cereal"},
]


def _norm(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", t)
    t = re.sub(r"[^a-z, ]", " ", t)
    return t


def _locate(text):
    """Return list of (position, length, concept) matches in text."""
    hits = []
    for concept, (_fam, forms) in _CONCEPTS.items():
        for f in forms:
            for m in re.finditer(r"\b" + re.escape(f) + r"s?\b", text):
                hits.append((m.start(), len(f), concept))
    return hits


def _primary_concept(text, prefer_first):
    hits = _locate(text)
    if not hits:
        return None
    # longest surface form wins (more specific); tie broken by position
    if prefer_first:
        hits.sort(key=lambda h: (h[0] > 0 and -h[1], h[0], -h[1]))
        hits.sort(key=lambda h: (-h[1], h[0]))
    else:
        hits.sort(key=lambda h: (-h[1], -h[0]))
    return hits[0][2]


def _family_related(f1, f2):
    return any(f1 in g and f2 in g for g in _FAMILY_GROUPS)


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(str(ingredient or "")).split(",")[0]
        usda_full = _norm(str(usda_match or ""))
        segs = [s.strip() for s in usda_full.split(",") if s.strip()]
        if not ing.strip() or not segs:
            return 0.0
        # USDA reading: "cheese, cottage" -> "cottage cheese cottage"
        usda_text = " ".join(segs[:2][::-1]) + " " + segs[0]

        c_ing = _primary_concept(ing, prefer_first=False)
        c_usda = _primary_concept(usda_text, prefer_first=True)

        if c_ing is None or c_usda is None:
            # unknown vocabulary: fall back to raw head word identity
            ing_words = ing.split()
            head = ing_words[-1] if ing_words else ""
            head = head[:-1] if head.endswith("s") else head
            prim = segs[0].split()
            if head and any(w.rstrip("s") == head for w in prim):
                return 7.0
            if head and head in usda_text:
                return 5.0
            return 2.0

        if c_ing == c_usda:
            score = 9.0
        else:
            f_ing, f_usda = _CONCEPTS[c_ing][0], _CONCEPTS[c_usda][0]
            if f_ing == f_usda:
                score = 4.5
            elif _family_related(f_ing, f_usda):
                score = 2.5
            else:
                score = 0.5
            # concept appears somewhere in USDA but not as primary
            if any(h[2] == c_ing for h in _locate(usda_full)):
                score += 1.5
        # small bonus for extra shared words beyond the concept
        iw = set(ing.split())
        uw = set(usda_full.replace(",", " ").split())
        score += min(1.0, 0.25 * len(iw & uw))
        return round(min(10.0, score), 2)
    except Exception:
        return 0.0
