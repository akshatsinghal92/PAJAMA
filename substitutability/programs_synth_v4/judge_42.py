import re

# Canonical concept lexicon: each alias phrase maps to a canonical food concept id.
_ALIASES = {
    "aubergine": "eggplant", "brinjal": "eggplant", "eggplant": "eggplant",
    "garbanzo": "chickpea", "garbanzos": "chickpea", "chickpea": "chickpea", "chickpeas": "chickpea",
    "chick peas": "chickpea", "bengal gram": "chickpea",
    "scallion": "scallion", "scallions": "scallion", "spring onion": "scallion",
    "spring onions": "scallion", "green onion": "scallion", "green onions": "scallion",
    "courgette": "zucchini", "courgettes": "zucchini", "zucchini": "zucchini",
    "linseed": "flaxseed", "linseeds": "flaxseed", "flaxseed": "flaxseed", "flax": "flaxseed",
    "flax seeds": "flaxseed", "flaxseeds": "flaxseed",
    "maize": "corn", "corn": "corn", "sweetcorn": "corn",
    "pinyon": "pinenut", "pine nut": "pinenut", "pine nuts": "pinenut", "pignoli": "pinenut",
    "pinon": "pinenut",
    "lox": "smokedsalmon", "smoked salmon": "smokedsalmon",
    "coriander leaves": "cilantro", "cilantro": "cilantro", "fresh coriander": "cilantro",
    "rocket": "arugula", "arugula": "arugula", "roquette": "arugula",
    "capsicum": "bellpepper", "bell pepper": "bellpepper", "bell peppers": "bellpepper",
    "sweet pepper": "bellpepper", "sweet peppers": "bellpepper",
    "beetroot": "beet", "beets": "beet", "beet": "beet",
    "swede": "rutabaga", "rutabaga": "rutabaga",
    "mangetout": "snowpea", "snow peas": "snowpea", "snow pea": "snowpea",
    "prawn": "shrimp", "prawns": "shrimp", "shrimp": "shrimp", "shrimps": "shrimp",
    "icing sugar": "powderedsugar", "confectioners sugar": "powderedsugar",
    "powdered sugar": "powderedsugar", "confectioner's sugar": "powderedsugar",
    "caster sugar": "granulatedsugar", "superfine sugar": "granulatedsugar",
    "granulated sugar": "granulatedsugar", "white sugar": "granulatedsugar",
    "cornflour": "cornstarch", "cornstarch": "cornstarch", "corn starch": "cornstarch",
    "plain flour": "apflour", "all-purpose flour": "apflour", "all purpose flour": "apflour",
    "double cream": "heavycream", "heavy cream": "heavycream", "whipping cream": "heavycream",
    "single cream": "lightcream", "light cream": "lightcream",
    "minced beef": "groundbeef", "ground beef": "groundbeef", "beef mince": "groundbeef",
    "mince": "groundbeef",
    "broad beans": "favabean", "broad bean": "favabean", "fava beans": "favabean", "fava": "favabean",
    "haricot beans": "navybean", "navy beans": "navybean", "navy bean": "navybean",
    "butter beans": "limabean", "lima beans": "limabean", "lima bean": "limabean",
    "okra": "okra", "ladies fingers": "okra", "lady's fingers": "okra", "bhindi": "okra",
    "dutch-process cocoa": "alkalicocoa", "dutch process cocoa": "alkalicocoa",
    "dutch-processed cocoa": "alkalicocoa", "processed with alkali": "alkalicocoa",
    "cocoa": "cocoa", "cacao": "cocoa",
    "yam": "yam", "sweet potato": "sweetpotato", "sweet potatoes": "sweetpotato", "kumara": "sweetpotato",
    "chili": "chili", "chilli": "chili", "chile": "chili", "chilies": "chili", "chillies": "chili",
    "cos lettuce": "romaine", "romaine": "romaine",
    "celeriac": "celeriac", "celery root": "celeriac",
    "kombu": "kelp", "kelp": "kelp", "laver": "laver", "nori": "laver",
    "wakame": "wakame",
    "filbert": "hazelnut", "filberts": "hazelnut", "hazelnut": "hazelnut", "hazelnuts": "hazelnut",
    "kefir": "kefir",
    "mangold": "chard", "swiss chard": "chard", "chard": "chard", "silverbeet": "chard",
    "bok choy": "bokchoy", "pak choi": "bokchoy", "pak-choi": "bokchoy", "chinese cabbage": "bokchoy",
    "aubergines": "eggplant",
    "cornflakes": "cornflakes", "corn flakes": "cornflakes", "maize flakes": "cornflakes",
    "garden peas": "pea", "peas": "pea", "petits pois": "pea",
    "tomato ketchup": "ketchup", "ketchup": "ketchup", "catsup": "ketchup",
    "soy sauce": "soysauce", "shoyu": "soysauce", "tamari": "soysauce",
    "jello": "gelatindessert", "jelly crystals": "gelatindessert",
    "biscuit": "cookie", "biscuits": "cookie", "cookie": "cookie", "cookies": "cookie",
    "crisps": "potatochips", "potato chips": "potatochips",
    "aubergine slices": "eggplant",
    "coconut sugar": "coconutsugar", "palm sugar": "coconutsugar",
    "brown sugar": "brownsugar",
    "red wine vinegar": "redwinevinegar", "balsamic": "balsamic", "balsamic vinegar": "balsamic",
    "cider vinegar": "cidervinegar", "apple cider vinegar": "cidervinegar",
    "cervelat": "cervelat", "saveloy": "cervelat",
    "brie": "brie", "camembert": "camembert", "cheese ball": "cheeseball",
    "soymilk": "soymilk", "soy milk": "soymilk",
}

# Concepts that the USDA descriptor order may express as "head, modifier" (e.g. "Sugar, brown").
_STOP = set("""
g kg mg ml l oz lb lbs tsp tbsp cup cups fresh freshly chopped diced sliced minced grated
peeled thawed frozen optional garnish to taste for and or of the a an with without in into
finely roughly thinly thickly large small medium whole pieces piece slices slice raw
about approx divided plus extra more some can canned drained rinsed
""".split())

_GENERIC = set("""
raw cooked boiled baked fried roasted dried dry regular plain unprepared prepared
nfs ns form with without salt added made commercial home homemade enriched unenriched
variety meats by products separable lean fat choice select all grades frozen canned
""".split())


def _clean(text):
    t = str(text or "").lower()
    t = t.replace("’", "'")
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)?\b", " ", t)
    return t


def _parentheticals(text):
    return [p.strip() for p in re.findall(r"\(([^)]*)\)", text) if p.strip()]


def _strip_paren(text):
    return re.sub(r"\([^)]*\)", " ", text)


def _norm_spaces(t):
    t = re.sub(r"[^a-z0-9' \-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _concepts(phrase):
    """Greedy longest-match extraction of canonical concepts from a phrase."""
    words = phrase.split()
    found = []
    i = 0
    while i < len(words):
        hit = None
        for n in (4, 3, 2, 1):
            if i + n <= len(words):
                cand = " ".join(words[i:i + n])
                if cand in _ALIASES:
                    hit = (cand, n)
                    break
                cs = " ".join(_stem(w) for w in words[i:i + n])
                if cs in _ALIASES:
                    hit = (cs, n)
                    break
        if hit:
            found.append(_ALIASES[hit[0]])
            i += hit[1]
        else:
            i += 1
    return found


def _content_words(phrase):
    return [_stem(w) for w in phrase.split() if w not in _STOP and len(w) > 1 and not w.isdigit()]


def _usda_variants(usda):
    """Generate natural-language orderings of a USDA 'head, mod, mod' description."""
    base = _strip_paren(usda)
    parts = [_norm_spaces(p) for p in base.split(",")]
    parts = [p for p in parts if p]
    out = []
    if parts:
        out.append(" ".join(parts))
        if len(parts) >= 2:
            out.append(parts[1] + " " + parts[0])
            out.append(" ".join(parts[1:]) + " " + parts[0])
    for p in _parentheticals(usda):
        out.append(_norm_spaces(p))
    return out, parts


def judging_function(ingredient, usda_match):
    try:
        ing_raw = _clean(ingredient)
        usda_raw = str(usda_match or "").lower().replace("’", "'")
        if not ing_raw.strip() or not usda_raw.strip():
            return 0.0

        # Ingredient core: drop parentheticals and post-comma state.
        ing_core = _norm_spaces(_strip_paren(ing_raw).split(",")[0])
        ing_paren = " ".join(_norm_spaces(p) for p in _parentheticals(ing_raw))
        if not ing_core:
            ing_core = _norm_spaces(_strip_paren(ing_raw))

        variants, usda_parts = _usda_variants(usda_raw)
        if not usda_parts:
            return 0.0

        ing_concepts = set(_concepts(ing_core)) | set(_concepts(ing_paren))
        usda_concepts = set()
        for v in variants:
            usda_concepts |= set(_concepts(v))
        head_concepts = set(_concepts(usda_parts[0]))
        if len(usda_parts) > 1:
            head_concepts |= set(_concepts(usda_parts[1] + " " + usda_parts[0]))

        score = 5.0

        # 1. Alias/concept resolution (dominant signal).
        shared = ing_concepts & usda_concepts
        if ing_concepts and usda_concepts:
            if shared:
                score += 3.0
                if shared & head_concepts:
                    score += 1.0
                unmatched_ing = ing_concepts - usda_concepts
                score -= 1.2 * len(unmatched_ing)
            else:
                # Both sides resolve to known, different foods.
                score -= 3.5
        elif ing_concepts and not usda_concepts:
            score -= 0.5

        # 2. Lexical anchor: does the ingredient's head noun appear in USDA head segment?
        ing_words = _content_words(ing_core)
        usda_all_words = set(_content_words(" ".join(variants)))
        usda_head_words = set(_content_words(usda_parts[0]))
        if ing_words:
            head_noun = ing_words[-1]
            covered = sum(1 for w in ing_words if w in usda_all_words)
            coverage = covered / float(len(ing_words))
            if head_noun in usda_head_words:
                score += 1.5
            elif head_noun in usda_all_words:
                score += 0.6
            elif not shared:
                score -= 1.5
            score += 2.0 * (coverage - 0.5)

            # 3. Modifier conflict: USDA head matches but ingredient has extra
            # specific qualifiers absent from USDA (e.g. coconut sugar vs Sugar, brown).
            if head_noun in usda_head_words and not shared:
                extra = [w for w in ing_words[:-1] if w not in usda_all_words and w not in _GENERIC]
                score -= 1.3 * len(extra)

        # 4. USDA specificity penalty: distinctive descriptors not in ingredient
        # (e.g. decaffeinated, beaked) suggest a different variety.
        ing_set = set(ing_words) | set(_content_words(ing_paren))
        distinctive = set(["decaffeinated", "beaked", "souffle", "ball", "patty",
                           "imitation", "substitute", "flavored", "babyfood", "infant"])
        for w in usda_all_words:
            if w in distinctive and w not in ing_set:
                score -= 1.5

        # 5. Compound ingredient "x and y" only partially covered.
        if " and " in " " + ing_core + " " and len(ing_words) >= 3:
            halves = ing_core.split(" and ")
            hits = 0
            for h in halves:
                hw = _content_words(h)
                if hw and any(w in usda_all_words for w in hw):
                    hits += 1
            if hits < len(halves):
                score -= 1.5

        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
