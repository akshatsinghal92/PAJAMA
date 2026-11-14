import re
import math

# Hierarchical taxonomy: category -> subtype -> list of stem keywords.
# Each item text is converted into a soft probability distribution over
# categories and subtypes; similarity is computed with the Bhattacharyya
# coefficient at both levels, plus agreement on the most specific food stem.
_TAXONOMY = {
    "dairy": {
        "milk": ["milk", "buttermilk", "kefir"],
        "cheese": ["cheese", "cheddar", "mozzarella", "parmesan", "ricotta", "feta", "brie", "gouda"],
        "cultured": ["yogurt", "yoghurt", "sour cream", "creme fraiche"],
        "cream": ["cream", "half and half", "whipped"],
        "butter": ["butter", "ghee"],
    },
    "produce": {
        "vegetable": ["bean snap", "snap", "spinach", "carrot", "onion", "potato", "tomato", "pepper bell",
                      "broccoli", "lettuce", "cabbage", "celery", "squash", "pumpkin", "zucchini",
                      "cucumber", "kale", "mushroom", "eggplant", "corn", "pea", "beet", "radish"],
        "fruit": ["apple", "banana", "strawberry", "berry", "orange", "lemon", "lime", "mango",
                  "pineapple", "grape", "peach", "pear", "cherry", "tamarind", "coconut", "date",
                  "fig", "plum", "raisin", "melon", "avocado"],
        "juice": ["juice", "nectar", "drink", "beverage", "smoothie"],
    },
    "meat": {
        "poultry": ["chicken", "turkey", "duck", "goose", "giblet", "poultry", "hen"],
        "red": ["beef", "pork", "lamb", "veal", "bacon", "ham", "sausage", "venison", "goat"],
        "fish": ["fish", "salmon", "tuna", "cod", "tilapia", "trout", "halibut", "sardine", "anchovy"],
        "shellfish": ["crustacean", "crayfish", "crawfish", "lobster", "shrimp", "prawn", "crab",
                      "clam", "mussel", "oyster", "scallop", "mollusk"],
        "egg": ["egg"],
    },
    "grain": {
        "cereal": ["cereal", "granola", "muesli", "oat", "flake", "bran", "crunch"],
        "bread": ["bread", "bagel", "roll", "bun", "tortilla", "pita", "muffin"],
        "pasta": ["pasta", "noodle", "spaghetti", "macaroni"],
        "kernel": ["rice", "wheat", "barley", "quinoa", "flour", "cornmeal", "millet", "rye"],
    },
    "legume": {
        "bean": ["bean", "lentil", "chickpea", "garbanzo", "kidney", "pinto", "lima"],
        "soy": ["tofu", "soy", "tempeh", "edamame", "soybean"],
    },
    "nutseed": {
        "nut": ["nut", "almond", "pecan", "walnut", "cashew", "pistachio", "hazelnut", "macadamia", "peanut"],
        "seed": ["seed", "kernel", "sesame", "sunflower", "flax", "chia", "pepita", "tahini"],
        "nutbutter": ["peanut butter", "nut butter", "almond butter", "pecan butter", "seed butter"],
    },
    "spice": {
        "dried": ["spice", "ground", "powder", "cinnamon", "cumin", "paprika", "turmeric", "nutmeg",
                  "clove", "cardamom", "pepper black", "ginger ground", "chili powder"],
        "herb": ["herb", "basil", "oregano", "thyme", "parsley", "cilantro", "rosemary", "sage", "dill", "mint"],
        "aromatic": ["garlic", "ginger", "shallot", "scallion", "leek"],
    },
    "fat": {
        "oil": ["oil", "olive oil", "canola", "vegetable oil", "sesame oil", "coconut oil"],
        "solid": ["lard", "shortening", "margarine", "tallow", "spread"],
    },
    "sweetener": {
        "sugar": ["sugar", "sucrose", "dextrose", "brown sugar"],
        "syrup": ["syrup", "honey", "molasses", "agave", "nectar"],
        "confection": ["candy", "chocolate", "jam", "jelly", "preserve", "frosting"],
    },
    "condiment": {
        "sauce": ["sauce", "ketchup", "salsa", "dressing", "gravy", "pesto"],
        "emulsion": ["mayonnaise", "mayo", "aioli"],
        "acid": ["vinegar", "mustard", "relish", "pickle"],
        "paste": ["paste", "puree", "concentrate", "pulp"],
    },
}

# Phrases that dominate the classification (head-noun overrides).
_OVERRIDES = {
    "peanut butter": ("nutseed", "nutbutter"),
    "pecan butter": ("nutseed", "nutbutter"),
    "almond butter": ("nutseed", "nutbutter"),
    "coconut cream": ("produce", "fruit"),
    "coconut milk": ("produce", "fruit"),
    "soy milk": ("legume", "soy"),
    "olive oil": ("fat", "oil"),
    "bell pepper": ("produce", "vegetable"),
    "pumpkin seed": ("nutseed", "seed"),
    "watermelon seed": ("nutseed", "seed"),
}

_NOISE = {
    "g", "kg", "mg", "oz", "lb", "ml", "l", "cup", "cups", "tbsp", "tsp", "raw", "cooked", "fresh",
    "frozen", "canned", "dried", "chopped", "sliced", "diced", "minced", "thawed", "boiled", "roasted",
    "baked", "fried", "grilled", "steamed", "unsweetened", "sweetened", "reduced", "fat", "nonfat",
    "lowfat", "low", "free", "whole", "plain", "organic", "and", "or", "with", "without", "from",
    "the", "a", "of", "in", "tube", "mixed", "species", "wild", "moist", "heat", "uncooked",
    "prepared", "ready", "to", "eat", "style", "made", "vegan", "light", "extra", "large", "small",
    "medium", "tails", "tail", "on", "bottom", "pieces", "piece",
}


def _normalize(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)                      # parentheticals
    t = re.sub(r"^\s*\d+(?:[.,]\d+)?\s*(?:g|kg|mg|ml|l|oz|lb)\b", " ", t)  # leading weight
    t = re.sub(r"\d+(?:[.,]\d+)?", " ", t)
    t = t.replace("-", " ")
    t = re.sub(r"[^a-z, ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            return w[:-len(suf)] if suf == "s" else w[:-1]
    return w


def _token_set(text):
    return [_stem(w) for w in re.findall(r"[a-z]+", text)]


def _contains(tokens_str, kw):
    kw_toks = " ".join(_stem(w) for w in kw.split())
    return re.search(r"(?:^| )" + re.escape(kw_toks) + r"(?: |$)", tokens_str) is not None


def _distribution(text, is_usda):
    """Return (category_dist, subtype_dist, head_stems)."""
    norm = _normalize(text)
    segments = [s.strip() for s in norm.split(",") if s.strip()] or [norm]
    cat_w = {}
    sub_w = {}
    for idx, seg in enumerate(segments):
        toks = _token_set(seg)
        if not toks:
            continue
        joined = " ".join(toks)
        # Position weights: for USDA, the first segment is primary; for recipe
        # text the main part precedes the comma (state descriptors follow).
        seg_weight = 1.0 / (1.0 + 0.8 * idx)
        n = len(toks)
        matched_override = False
        for phrase, (c, s) in _OVERRIDES.items():
            if _contains(joined, phrase):
                w = 3.0 * seg_weight
                cat_w[c] = cat_w.get(c, 0.0) + w
                sub_w[(c, s)] = sub_w.get((c, s), 0.0) + w
                matched_override = True
        for cat, subs in _TAXONOMY.items():
            for sub, kws in subs.items():
                for kw in kws:
                    m = re.search(r"(?:^| )" + re.escape(" ".join(_stem(w) for w in kw.split())) + r"(?: |$)", joined)
                    if not m:
                        continue
                    # Later tokens in an ingredient phrase are usually the head noun.
                    pos = joined[:m.start()].count(" ") + (0 if m.start() == 0 else 1)
                    rel = (pos + 1) / float(n)
                    head_boost = 0.6 + 0.8 * rel if not is_usda else 1.4 - 0.6 * rel
                    if is_usda and idx == 0:
                        head_boost = 1.4
                    spec = 1.0 + 0.4 * (len(kw.split()) - 1)
                    w = seg_weight * head_boost * spec * (0.5 if matched_override else 1.0)
                    cat_w[cat] = cat_w.get(cat, 0.0) + w
                    sub_w[(cat, sub)] = sub_w.get((cat, sub), 0.0) + w
    head = set()
    if segments:
        head = {t for t in _token_set(segments[0]) if t not in _NOISE and len(t) > 2}
    return _soft(cat_w), _soft(sub_w), head, set(t for t in _token_set(norm) if t not in _NOISE and len(t) > 2)


def _soft(weights):
    tot = sum(weights.values())
    if tot <= 0:
        return {}
    return {k: v / tot for k, v in weights.items()}


def _bhattacharyya(p, q):
    if not p or not q:
        return None
    return sum(math.sqrt(p[k] * q[k]) for k in p if k in q)


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").strip()
        usda = str(usda_match or "").strip()
        if not ing or not usda:
            return 0.0

        pc, ps, ihead, iall = _distribution(ing, False)
        qc, qs, uhead, uall = _distribution(usda, True)

        cat_bc = _bhattacharyya(pc, qc)
        sub_bc = _bhattacharyya(ps, qs)

        # Specific-food anchoring: fraction of ingredient content words that
        # appear anywhere in the USDA description (with stem prefix tolerance).
        def _hit(w, pool):
            for u in pool:
                if w == u or (len(w) > 4 and len(u) > 4 and (w.startswith(u[:5]) or u.startswith(w[:5]))):
                    return True
            return False

        anchor = (sum(1 for w in iall if _hit(w, uall)) / float(len(iall))) if iall else 0.0
        head_hit = 1.0 if ihead and uhead and any(_hit(w, uhead) for w in ihead) else 0.0

        if cat_bc is None:
            # No category evidence on one side: rely on lexical anchoring only, capped.
            score = 25.0 + 35.0 * anchor + 10.0 * head_hit
            return round(max(0.0, min(100.0, score)), 3)

        sub_term = sub_bc if sub_bc is not None else 0.0

        # Cross-category penalty grows with how confidently each side is classified.
        conf_i = max(pc.values())
        conf_u = max(qc.values())
        top_i = max(pc, key=pc.get)
        top_u = max(qc, key=qc.get)
        cross = 1.0 if top_i != top_u else 0.0
        penalty = 30.0 * cross * math.sqrt(conf_i * conf_u)

        # Same subtype but different specific food (e.g. lobster vs crayfish,
        # pecan vs peanut) is still a likely swap failure.
        specificity = 0.5 * anchor + 0.5 * head_hit

        score = (
            10.0
            + 30.0 * cat_bc
            + 20.0 * sub_term
            + 35.0 * specificity * (0.4 + 0.6 * cat_bc)
            + 5.0 * (1.0 - cross)
            - penalty
        )
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
