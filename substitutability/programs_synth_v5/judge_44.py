import re

ALIASES = {
    "aubergine": "eggplant", "garbanzo": "chickpea", "garbanzos": "chickpea", "chickpeas": "chickpea",
    "scallion": "springonion", "scallions": "springonion", "spring onion": "springonion",
    "green onion": "springonion", "green onions": "springonion", "spring onions": "springonion",
    "courgette": "zucchini", "courgettes": "zucchini", "zucchinis": "zucchini",
    "coriander leaves": "cilantro", "cilantro": "cilantro", "rocket": "arugula", "arugula": "arugula",
    "capsicum": "bellpepper", "bell pepper": "bellpepper", "sweet pepper": "bellpepper",
    "prawn": "shrimp", "prawns": "shrimp", "shrimps": "shrimp",
    "swede": "rutabaga", "rutabaga": "rutabaga", "beetroot": "beet", "beets": "beet",
    "icing sugar": "powderedsugar", "confectioners sugar": "powderedsugar", "powdered sugar": "powderedsugar",
    "caster sugar": "sugar", "granulated sugar": "sugar", "white sugar": "sugar",
    "cornflour": "cornstarch", "cornstarch": "cornstarch", "corn starch": "cornstarch",
    "mince": "ground", "minced meat": "ground", "ground beef": "groundbeef",
    "plain flour": "flour", "all-purpose flour": "flour", "all purpose flour": "flour",
    "heavy cream": "cream", "double cream": "cream", "whipping cream": "cream",
    "chilli": "chile", "chili": "chile", "chiles": "chile", "chillies": "chile",
    "potatoes": "potato", "tomatoes": "tomato", "onions": "onion", "carrots": "carrot",
    "eggs": "egg", "pecans": "pecan", "cherries": "cherry", "apples": "apple",
    "garlic": "garlic", "ginger": "ginger", "mushrooms": "mushroom", "peas": "pea",
    "beans": "bean", "lentils": "lentil", "almonds": "almond", "walnuts": "walnut",
    "sausages": "sausage", "frankfurter": "hotdog", "frankfurters": "hotdog", "hot dog": "hotdog",
    "hot dogs": "hotdog", "wieners": "hotdog", "artichokes": "artichoke", "turkey": "turkey",
    "sirloin": "sirloin", "chuck": "chuck", "tongue": "tongue", "liver": "liver", "heart": "heart",
    "shank": "shank", "loin": "loin", "ham": "ham", "sage": "sage", "durian": "durian",
}
PREP = set("""fresh frozen thawed dried dry canned drained chopped minced sliced diced grated shredded
crushed ground cooked raw boiled roasted peeled large small medium whole fine finely coarsely
optional garnish serving taste for to of or and with into the a in about extra lean boneless skinless
softened melted packed ripe organic unsweetened sweetened plain pure""".split())
STOP = set("g kg ml oz lb tsp tbsp cup cups ready serve all grades separable fat trimmed lowfat low sodium includes foods usda programs program food distribution".split())
PRODUCT = set("""salad spread cookies cookie chips entree sandwich nectar patty candy cake pie bar bars
soup dip dressing sauce snack snacks mix beverage drink juice cereal pizza burger meal dinner
stew sticks bread muffin cracker crackers sauerkraut pudding frozen-entree""".split())
STATE = ["canned", "frozen", "dried", "dry", "cooked", "raw", "powder", "smoked", "pickled", "cured"]


def _clean(s):
    s = s.lower()
    s = re.sub(r"\([^)]*\)", lambda m: " " + m.group(0)[1:-1] + " " if False else " ", s)
    s = re.sub(r"\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", s)
    s = re.sub(r"[^a-z\s,\-']", " ", s)
    return s


def _canon(tokens):
    out = []
    i = 0
    while i < len(tokens):
        two = " ".join(tokens[i:i + 2])
        if two in ALIASES:
            out.append(ALIASES[two]); i += 2; continue
        t = tokens[i]
        t = ALIASES.get(t, t)
        if t.endswith("ies") and len(t) > 4:
            t = t[:-3] + "y"
        elif t.endswith("s") and len(t) > 3 and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
        i += 1
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        ing_main = _clean(ing.split(",")[0])
        ing_raw = _clean(ing)
        parts = [p for p in re.split(r",", _clean(usda)) if p.strip()]
        usda_head = parts[0] if parts else ""
        usda_all = " ".join(parts)

        it = [t for t in ing_main.split() if t not in PREP and t not in STOP]
        it_c = _canon(it)
        ing_full_tokens = _canon([t for t in ing_raw.split() if t not in STOP])
        uh_c = _canon([t for t in usda_head.split() if t not in STOP])
        ua_c = _canon([t for t in usda_all.replace("-", " ").split() if t not in STOP])
        if not it_c:
            return 1.0

        ua_set, uh_set = set(ua_c), set(uh_c)
        score = 0.0

        # core concept coverage: how many ingredient concept words resolve into the USDA name
        hit = [t for t in it_c if t in ua_set]
        cov = len(hit) / len(it_c)
        score += 5.0 * cov
        # head noun (last concept word of ingredient) located in USDA primary food
        head = it_c[-1]
        if head in uh_set:
            score += 2.5
        elif head in ua_set:
            score += 1.5
        else:
            score -= 1.0

        # reverse: USDA primary food words unexplained by ingredient
        ing_set = set(it_c) | set(ing_full_tokens)
        extra = [t for t in uh_c if t not in ing_set and t not in PREP]
        score -= 0.7 * min(len(extra), 4)

        # compound ingredient (two foods) vs single USDA food
        if re.search(r"\b(and|&|with)\b", ing_main) and len(it_c) >= 2:
            missing = [t for t in it_c if t not in ua_set]
            if missing:
                score -= 3.0
        # composite/processed USDA product when ingredient is not one
        prod_u = [t for t in ua_c if t in PRODUCT]
        prod_i = [t for t in it_c if t in PRODUCT]
        for p in set(prod_u):
            if p not in prod_i:
                score -= 2.0
        # head concept appears only as an ingredient of a product (not first word) while primary differs
        if head in ua_set and head not in uh_set and uh_c and uh_c[0] not in it_c:
            score -= 1.5
        # state conflicts
        il = ing_raw
        ul = usda.lower()
        for st in ("canned", "frozen", "dried", "smoked", "cooked"):
            a = st in il
            b = st in ul
            if a != b and (a or st in ("canned", "dried", "smoked")):
                score -= 1.0 if a else 1.2
        if "lean" in il and "lean" not in ul:
            score -= 1.0
        if "powder" in il and "powder" not in ul:
            score -= 1.0
        # exact-ish name match bonus
        if it_c == uh_c:
            score += 2.0
        return max(-5.0, min(12.0, score))
    except Exception:
        return 0.0
