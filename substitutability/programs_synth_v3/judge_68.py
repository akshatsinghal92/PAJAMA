import re

# Culinary role lexicon: role -> set of indicative stems
_ROLE_LEXICON = {
    "fat": ["oil", "butter", "lard", "ghee", "shortening", "margarine", "tallow", "drippings", "suet"],
    "sweetener": ["sugar", "honey", "syrup", "molasses", "agave", "sweetener", "dextrose", "jaggery", "treacle"],
    "starch_thickener": ["flour", "starch", "cornstarch", "arrowroot", "tapioca", "meal", "semolina", "gelatin", "agar", "pectin"],
    "binder": ["egg", "flax", "chia", "psyllium", "breadcrumb", "crumbs"],
    "aromatic": ["garlic", "onion", "shallot", "ginger", "leek", "scallion", "chive", "lemongrass", "celery"],
    "spice_herb": ["spice", "pepper", "cumin", "paprika", "cinnamon", "nutmeg", "clove", "basil", "oregano",
                   "thyme", "rosemary", "parsley", "cilantro", "coriander", "turmeric", "mint", "dill", "sage", "vanilla"],
    "protein_meat": ["beef", "pork", "lamb", "chicken", "turkey", "veal", "duck", "goose", "venison", "bison",
                     "heart", "liver", "kidney", "tongue", "sausage", "bacon", "ham", "meat"],
    "protein_sea": ["fish", "salmon", "tuna", "cod", "shrimp", "crab", "lobster", "clam", "mussel", "oyster",
                    "scallop", "anchovy", "sardine", "squid", "octopus"],
    "seaweed": ["seaweed", "kombu", "kelp", "nori", "laver", "wakame", "dulse", "agar"],
    "dairy": ["milk", "cream", "cheese", "yogurt", "yoghurt", "kefir", "buttermilk", "curd", "whey"],
    "fruit": ["apple", "pear", "grape", "mandarin", "papaya", "mango", "orange", "tangerine", "mandarin", "clementine",
              "banana", "berry", "berries", "strawberry", "blueberry", "raspberry", "cherry", "peach", "plum",
              "apricot", "pineapple", "melon", "kiwi", "lemon", "lime", "fig", "date", "coconut", "fruit"],
    "vegetable": ["carrot", "potato", "tomato", "cabbage", "spinach", "lettuce", "broccoli", "cauliflower",
                  "zucchini", "squash", "pumpkin", "pepper", "eggplant", "kale", "bean", "pea", "corn",
                  "mushroom", "beet", "radish", "turnip", "cucumber", "vegetable"],
    "grain": ["rice", "oat", "wheat", "barley", "quinoa", "pasta", "noodle", "bread", "germ", "bran", "millet", "rye"],
    "nut_seed": ["almond", "walnut", "pecan", "cashew", "peanut", "hazelnut", "pistachio", "seed", "nut", "sesame"],
    "liquid_acid": ["vinegar", "juice", "wine", "broth", "stock", "water", "sauce"],
}

# Physical form classes - changes here can force a recipe change
_FORM_GROUPS = {
    "whole_fresh": ["raw", "fresh", "whole", "ripe"],
    "cut": ["sliced", "chopped", "diced", "cubed", "minced", "segments", "shredded", "grated", "julienned"],
    "cooked": ["baked", "boiled", "roasted", "fried", "cooked", "grilled", "braised", "stewed", "steamed", "broiled", "microwaved"],
    "dried": ["dried", "dehydrated", "powder", "powdered", "ground", "flakes"],
    "preserved": ["canned", "jarred", "pickled", "drained", "juice pack", "syrup pack"],
    "formed": ["patty", "patties", "nugget", "nuggets", "breaded", "loaf", "sticks", "battered", "links", "meatball"],
    "paste": ["paste", "puree", "pureed", "mashed", "sauce", "gel", "jam", "spread"],
    "liquid": ["juice", "liquid", "extract", "milk", "oil"],
}

# Form compatibility matrix (0..1), symmetric
_FORM_COMPAT = {
    ("whole_fresh", "cut"): 0.95,
    ("whole_fresh", "preserved"): 0.7,
    ("cut", "preserved"): 0.75,
    ("whole_fresh", "cooked"): 0.3,
    ("cut", "cooked"): 0.25,
    ("whole_fresh", "dried"): 0.2,
    ("cut", "dried"): 0.2,
    ("cooked", "preserved"): 0.6,
    ("dried", "preserved"): 0.35,
    ("paste", "whole_fresh"): 0.35,
    ("paste", "dried"): 0.4,
    ("paste", "cut"): 0.4,
    ("paste", "cooked"): 0.5,
    ("paste", "preserved"): 0.5,
    ("liquid", "whole_fresh"): 0.25,
    ("liquid", "cut"): 0.2,
    ("liquid", "paste"): 0.45,
    ("liquid", "preserved"): 0.5,
    ("liquid", "dried"): 0.15,
    ("liquid", "cooked"): 0.3,
    ("cooked", "dried"): 0.3,
}

# Behaviour-sensitive modifiers that flip function (sweet vs unsweet, etc.)
_POLAR_PAIRS = [
    ({"sweetened"}, {"unsweetened"}),
    ({"salted"}, {"unsalted"}),
    ({"skim", "nonfat", "fat-free"}, {"whole"}),
    ({"lean"}, {"fatty"}),
]

_STOP = {"and", "or", "with", "the", "a", "of", "in", "for", "from", "to", "by", "as", "not", "added",
         "products", "variety", "meats", "includes", "ns", "nfs", "type", "style", "made", "prepared"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|grams?)\b", " ", t)
    t = re.sub(r"\b(frozen|thawed|uncooked)\b", " ", t)
    t = re.sub(r"[^a-z\s,\-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


# Culinary equivalence classes: items that play the identical role in a dish
_EQUIV = {
    "clementine": "mandarin", "tangerine": "mandarin", "satsuma": "mandarin",
    "scallion": "green_onion", "cilantro": "coriander", "garbanzo": "chickpea",
    "zucchini": "courgette", "eggplant": "aubergine", "prawn": "shrimp",
    "confectioner": "powdered", "icing": "powdered", "caster": "superfine",
}


def _tokens(text):
    out = []
    for w in re.split(r"[\s,\-]+", text):
        if not w or w in _STOP:
            continue
        s = _stem(w)
        out.append(_EQUIV.get(s, s))
    return out


def _role_profile(toks, raw):
    prof = {}
    joined = " " + " ".join(toks) + " "
    for role, stems in _ROLE_LEXICON.items():
        hits = 0
        for s in stems:
            ss = _stem(s)
            if (" " + ss + " ") in joined or any(t.startswith(ss) and len(ss) >= 4 for t in toks):
                hits += 1
        if hits:
            prof[role] = hits
    return prof


def _forms(raw):
    found = set()
    for grp, words in _FORM_GROUPS.items():
        for w in words:
            if re.search(r"\b" + re.escape(w) + r"\b", raw):
                found.add(grp)
                break
    return found


def _form_score(fi, fu):
    # Ingredient with no explicit form = assume fresh/as-sold
    if not fi:
        fi = {"whole_fresh"}
    if not fu:
        fu = {"whole_fresh"}
    best_per_i = []
    for a in fi:
        best = 0.0
        for b in fu:
            if a == b:
                v = 1.0
            else:
                v = _FORM_COMPAT.get((a, b), _FORM_COMPAT.get((b, a), 0.5))
            best = max(best, v)
        best_per_i.append(best)
    # an explicit cooking transform on usda side the ingredient lacks is a strong role change
    penalty = 1.0
    if "cooked" in fu and "cooked" not in fi:
        penalty *= 0.6
    if "dried" in fu and "dried" not in fi and "liquid" not in fi:
        penalty *= 0.8
    if "formed" in fu and "formed" not in fi:
        penalty *= 0.45
    return (sum(best_per_i) / len(best_per_i)) * penalty


def _role_overlap(pi, pu):
    if not pi and not pu:
        return 0.4
    if not pi or not pu:
        return 0.25
    a, b = set(pi), set(pu)
    shared = a & b
    if not shared:
        return 0.0
    # coverage of the ingredient's roles matters most; extra USDA roles cost a little
    return 0.75 * len(shared) / len(a) + 0.25 * len(shared) / len(a | b)


def _primary_identity(itoks, usda_clean):
    # USDA primary food is the first comma segment; check that the ingredient names it
    # USDA often leads with a category ("Spices, ginger, ground", "Beverages, ...");
    # in that case the real food name lives in the next segment.
    try:
        segs = [s.strip() for s in usda_clean.split(",") if s.strip()]
        if not segs:
            return 0.0
        candidates = [segs[0]]
        if _tokens(segs[0]) and all(t in _CATEGORY_HEADS for t in _tokens(segs[0])) and len(segs) > 1:
            candidates = [segs[1]]
        best = 0.0
        for head in candidates:
            htoks = [h for h in _tokens(head) if h not in _CATEGORY_HEADS] or _tokens(head)
            if not htoks:
                continue
            hit = 0
            for h in htoks:
                if any(h == t or (len(h) >= 4 and len(t) >= 4 and (t.startswith(h) or h.startswith(t))) for t in itoks):
                    hit += 1
            best = max(best, hit / len(htoks))
        return best
    except Exception:
        return 0.0


_CATEGORY_HEADS = {"spice", "beverage", "babyfood", "fast", "food", "restaurant", "snack", "candie",
                   "sweet", "soup", "sauce", "cereal", "dessert", "topping", "alcoholic", "infant",
                   "formula", "seasoning", "condiment", "fat", "vegetable", "fruit"}


def _descriptor_coverage(itoks, utoks):
    s_i = set(itoks)
    if not s_i:
        return 0.0
    s_u = set(utoks)
    covered = 0
    for t in s_i:
        if t in s_u or any(len(t) >= 4 and (u.startswith(t) or t.startswith(u)) and len(u) >= 4 for u in s_u):
            covered += 1
    return covered / len(s_i)


def _polarity_conflict(ri, ru):
    wi = set(re.findall(r"[a-z\-]+", ri))
    wu = set(re.findall(r"[a-z\-]+", ru))
    conflicts = 0
    for a, b in _POLAR_PAIRS:
        if (wi & a and wu & b) or (wi & b and wu & a):
            conflicts += 1
    return conflicts


def judging_function(ingredient, usda_match):
    try:
        ri = _clean(ingredient)
        ru = _clean(usda_match)
        if not ri or not ru:
            return 0.0
        itoks = _tokens(ri)
        utoks = _tokens(ru)
        if not itoks or not utoks:
            return 0.0

        pi = _role_profile(itoks, ri)
        pu = _role_profile(utoks, ru)
        role = _role_overlap(pi, pu)
        ident = _primary_identity(itoks, ru)
        cover = _descriptor_coverage(itoks, utoks)
        form = _form_score(_forms(ri), _forms(ru))
        polar = _polarity_conflict(ri, ru)

        # Distinct role families with no overlap at all -> function cannot be preserved
        disjoint_roles = bool(pi) and bool(pu) and not (set(pi) & set(pu))

        # Multiplicative gating: role compatibility gates everything, then form governs behaviour
        role_gate = 0.15 + 0.85 * max(role, 0.9 * ident)
        identity_term = 0.55 * ident + 0.45 * cover
        score = 100.0 * role_gate * (0.35 + 0.65 * identity_term) * (0.3 + 0.7 * form)

        if disjoint_roles and ident < 0.5:
            score *= 0.35
        if ident == 0.0 and role < 0.5:
            score *= 0.5
        score *= 0.6 ** polar

        # Blend with a monotone lexical-role anchor so that a closer naming of the
        # same food never falls below a looser one purely through gating effects.
        anchor = 100.0 * (0.5 * ident + 0.3 * cover + 0.2 * role) * (0.5 + 0.5 * form)
        if disjoint_roles and ident < 0.5:
            anchor *= 0.35
        anchor *= 0.6 ** polar
        score = 0.6 * score + 0.4 * anchor

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
