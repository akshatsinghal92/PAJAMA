import re

# Culinary Role Interchangeability, variant 6: kitchen substitution graph.
# Cooks rely on known substitution pairs that preserve a food's function:
# butter <-> margarine, shallot <-> onion, lemon <-> lime, honey <-> maple
# syrup, stock <-> broth, cornstarch <-> arrowroot, egg <-> flax egg ...
# These are encoded as a weighted undirected graph (weight = how well the
# role is preserved, 0..1). The interchangeability of two foods is the best
# path product within three hops (a "max-product" search), so
# shallot -> onion -> leek is accepted with decay, while garlic -> guava has
# no path. Form words (ground, juice, paste, sauce) map nodes onto
# form-specific nodes, e.g. "ginger, ground" -> ground_ginger.

_EDGES = [
    ("butter", "margarine", 0.9), ("butter", "ghee", 0.85), ("butter", "oil", 0.55),
    ("oil", "olive_oil", 0.9), ("oil", "vegetable_oil", 0.95), ("olive_oil", "vegetable_oil", 0.8),
    ("oil", "lard", 0.6), ("butter", "lard", 0.6), ("oil", "shortening", 0.6),
    ("onion", "shallot", 0.85), ("onion", "leek", 0.75), ("onion", "scallion", 0.7),
    ("garlic", "garlic_paste", 0.9), ("garlic", "garlic_powder", 0.55), ("garlic", "shallot", 0.4),
    ("ginger", "ginger_paste", 0.9), ("ginger", "ground_ginger", 0.5),
    ("lemon", "lime", 0.85), ("lemon", "vinegar", 0.5), ("lime", "vinegar", 0.45),
    ("honey", "maple_syrup", 0.8), ("honey", "agave", 0.85), ("honey", "sugar", 0.55),
    ("sugar", "brown_sugar", 0.85), ("sugar", "maple_syrup", 0.5), ("syrup", "maple_syrup", 0.9),
    ("egg", "flax_egg", 0.7), ("egg", "chia_egg", 0.65), ("flax_egg", "chia_egg", 0.75),
    ("flaxseed", "flax_egg", 0.8), ("chia", "chia_egg", 0.8), ("chia", "flaxseed", 0.55),
    ("cornstarch", "arrowroot", 0.9), ("cornstarch", "flour", 0.6), ("flour", "arrowroot", 0.5),
    ("broth", "stock", 0.95), ("broth", "bouillon", 0.75), ("stock", "bouillon", 0.7),
    ("broth", "soup", 0.35),
    ("yogurt", "sour_cream", 0.8), ("yogurt", "cottage_cheese", 0.4), ("cream", "milk", 0.5),
    ("milk", "soy_milk", 0.8), ("cream", "sour_cream", 0.55), ("cottage_cheese", "ricotta", 0.8),
    ("yogurt", "frozen_yogurt", 0.25),
    ("rice", "quinoa", 0.7), ("rice", "couscous", 0.65), ("pasta", "noodle", 0.9),
    ("pasta", "gnocchi", 0.55), ("gnocchi", "potato", 0.3), ("potato", "sweet_potato", 0.75),
    ("chicken", "turkey", 0.85), ("chicken", "pork", 0.6), ("beef", "pork", 0.65),
    ("beef", "lamb", 0.7), ("fish", "swordfish", 0.8), ("fish", "salmon", 0.75),
    ("swordfish", "tuna", 0.75), ("fish", "cod", 0.85), ("chicken", "chicken_patty", 0.35),
    ("tomato", "canned_tomato", 0.75), ("tomato", "tomato_paste", 0.4), ("tomato", "tomato_sauce", 0.45),
    ("corn", "creamed_corn", 0.4), ("spinach", "kale", 0.75), ("spinach", "chard", 0.8),
    ("zucchini", "squash", 0.85), ("broccoli", "cauliflower", 0.8),
    ("blueberry", "blackberry", 0.8), ("blueberry", "raspberry", 0.75), ("berry", "blueberry", 0.9),
    ("fruit", "fruit_juice", 0.2), ("orange", "grapefruit", 0.7), ("ugli", "grapefruit", 0.85),
    ("ugli", "orange", 0.75), ("guava", "guava_paste", 0.4), ("apple", "pear", 0.7),
    ("almond", "walnut", 0.75), ("walnut", "pecan", 0.9), ("peanut", "almond", 0.65),
    ("italian_dressing", "vinaigrette", 0.85), ("salad_dressing", "vinaigrette", 0.7),
    ("italian_dressing", "salad_dressing", 0.8), ("pesto", "sauce", 0.3),
]
_GRAPH = {}
for _a, _b, _w in _EDGES:
    _GRAPH.setdefault(_a, {})[_b] = _w
    _GRAPH.setdefault(_b, {})[_a] = _w

_COMPOUNDS = [
    (r"\bolive oil\b|\boil, olive\b", "olive_oil"), (r"\bvegetable oil\b|\bcanola oil\b", "vegetable_oil"),
    (r"\bgarlic paste\b", "garlic_paste"), (r"\bgarlic powder\b", "garlic_powder"),
    (r"\bginger paste\b", "ginger_paste"), (r"\bginger, ground\b|\bground ginger\b", "ground_ginger"),
    (r"\bmaple syrup\b|\bsyrups?, maple\b", "maple_syrup"), (r"\bbrown sugar\b", "brown_sugar"),
    (r"\bsour cream\b", "sour_cream"), (r"\bcottage cheese\b|\bcheese, cottage\b", "cottage_cheese"),
    (r"\bfrozen yogurt\b", "frozen_yogurt"), (r"\bsoy ?milk\b", "soy_milk"),
    (r"\bsweet potato", "sweet_potato"), (r"\bchicken patty\b", "chicken_patty"),
    (r"\btomato paste\b", "tomato_paste"), (r"\btomato sauce\b", "tomato_sauce"),
    (r"\bcanned tomato|\btomatoes, canned\b", "canned_tomato"), (r"\bcreamed corn\b|\bcorn, .*cream style\b", "creamed_corn"),
    (r"\bfruit juice\b|\bjuice\b", "fruit_juice"), (r"\bguava paste\b", "guava_paste"),
    (r"\bitalian dressing\b", "italian_dressing"), (r"\bsalad dressing\b", "salad_dressing"),
    (r"\bflax egg\b", "flax_egg"), (r"\bchia egg\b", "chia_egg"),
]


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _node(text, primary_first):
    for rx, node in _COMPOUNDS:
        if re.search(rx, text):
            return node
    words = [_sing(w) for w in re.findall(r"[a-z]+", text)]
    known = [w for w in words if w in _GRAPH]
    if not known:
        if not words:
            return None
        return words[0] if primary_first else words[-1]
    return known[0] if primary_first else known[-1]


def _best_path(a, b, max_hops=3):
    if a == b:
        return 1.0
    best = 0.0
    frontier = {a: 1.0}
    for _ in range(max_hops):
        nxt = {}
        for node, val in frontier.items():
            for nb, w in _GRAPH.get(node, {}).items():
                v = val * w
                if nb == b:
                    best = max(best, v)
                if v > nxt.get(nb, 0.0):
                    nxt[nb] = v
        frontier = nxt
    return best


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing).split(",")[0]
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        fields = [f.strip() for f in usda.split(",") if f.strip()]
        zone = ", ".join(fields[:2]) if len(fields[0].split()) == 1 and len(fields) > 1 else fields[0]
        ni = _node(ing, primary_first=False)
        nu = _node(zone, primary_first=True)
        # form-specific compound nodes may sit in any USDA field ("Spices, ginger, ground")
        for rx, node in _COMPOUNDS:
            if node != nu and re.search(rx, usda) and node.split("_")[-1] != "juice":
                if nu is not None and nu in node.split("_"):
                    nu = node
                    break
        if ni is None or nu is None:
            return 0.0
        zone_words = {_sing(w) for w in re.findall(r"[a-z]+", zone)}
        if (ni not in _GRAPH or nu not in _GRAPH) and ni != nu:
            # vocabulary gap: the same head food in the USDA identity zone keeps its role
            return 9.0 if ni in zone_words else 1.0
        if ni == nu:
            sim = 1.0
            # cooked / fried primary state still slightly changes the role
            if re.search(r"\bfried\b|\bbreaded\b", usda) and not re.search(r"\bfried\b|\bbreaded\b", ing):
                sim = 0.7
        else:
            sim = _best_path(ni, nu)
            if sim == 0.0 and (ni not in _GRAPH or nu not in _GRAPH):
                # unknown node: fall back to shared head word evidence
                sim = 0.5 if ni in zone or nu in ing else 0.1
        return round(10.0 * sim, 3)
    except Exception:
        return 0.0
