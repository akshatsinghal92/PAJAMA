import re

_BRAND_WORDS = {"lifeway", "kraft", "heinz", "oreo", "nabisco", "kellogg", "kelloggs", "pillsbury",
                "campbell", "campbells", "nestle", "hershey", "hersheys", "general", "mills",
                "quaker", "betty", "crocker", "mcdonalds", "burger", "king", "wendys", "subway",
                "starbucks", "pepsi", "coca", "cola", "gatorade", "snickers", "twix", "mars",
                "pringles", "doritos", "cheetos", "fritos", "lays", "ritz", "triscuit",
                "keebler", "cadbury", "godiva", "hormel", "oscar", "mayer", "jimmy", "dean",
                "tyson", "perdue", "gerber", "ensure", "slimfast", "boost", "yoplait", "dannon",
                "chobani", "silk", "ben", "jerry", "haagen", "dazs", "stouffers", "lean",
                "cuisine", "kashi", "clif", "luna", "powerbar", "tofutti", "morningstar",
                "boca", "gardein", "beyond", "impossible", "pizza", "hut", "taco", "bell",
                "arbys", "kfc", "dominos", "applebees", "chilis", "dennys", "denny", "olive garden"}

_VARIANT_WORDS = {"vegan", "plant", "plantbased", "dairy-free", "dairyfree", "imitation", "substitute",
                  "flavored", "flavoured", "vanilla", "strawberry", "chocolate", "banana", "blueberry",
                  "peach", "cherry", "raspberry", "lemon", "caramel", "mocha", "coffee", "mint",
                  "maple", "cinnamon", "honey", "ranch", "bbq", "barbecue", "spicy", "sweetened",
                  "unsweetened", "lowfat", "nonfat", "reduced", "light", "lite", "diet", "sugarfree",
                  "free", "low", "fat", "soy", "almond", "oat", "coconut", "rice", "meatless",
                  "analog", "fortified", "restaurant", "fast", "babyfood", "baby", "infant",
                  "formula", "supplement", "bar", "bars"}

_STOP = {"and", "or", "of", "the", "a", "with", "in", "from", "for", "to", "raw", "fresh", "style",
         "all", "varieties", "type", "made", "g", "oz", "cup", "cups", "tbsp", "tsp", "no", "added"}


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0

        ing_raw = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|oz|ml|lb)?\s+", "", ing.strip(), flags=re.I)

        # brand markers in the USDA entry: ALL-CAPS tokens (len>=3) and known brand words
        caps = [t for t in re.findall(r"\b[A-Z][A-Z&']{2,}\b", usda)]
        usda_l = usda.lower()
        ing_l = ing_raw.lower()
        usda_words = set(re.findall(r"[a-z]+", usda_l))
        ing_words = set(re.findall(r"[a-z]+", ing_l))
        brand_u = {w for w in usda_words if w in _BRAND_WORDS} - ing_words
        brand_i = {w for w in ing_words if w in _BRAND_WORDS}
        caps_unmatched = [c for c in caps if c.lower() not in ing_words]
        # Registered/trademark symbols or parenthetical in the USDA entry
        tm = len(re.findall(r"[®™©]", usda))
        paren_brand = 0
        for p in re.findall(r"\(([^)]*)\)", usda):
            if re.search(r"[A-Z]{2,}|[A-Z][a-z]+\s[A-Z]", p):
                paren_brand += 1

        # core content similarity
        it = [t for t in _tokens(ing_raw.split(",")[0]) if t not in _STOP and len(t) > 1]
        head = usda.split(",")[0]
        ut_head = [t for t in _tokens(head) if t not in _STOP and len(t) > 1]
        ut_all = [t for t in _tokens(usda) if t not in _STOP and len(t) > 1]
        if not it or not ut_all:
            return 0.0
        iset, uset, hset = set(it), set(ut_all), set(ut_head)
        cover = len(iset & uset) / len(iset)
        precision = len(iset & uset) / len(uset)
        head_hit = len(iset & hset) / max(1, len(hset))

        # variant words introduced by USDA entry but absent in the ingredient (changes flavor/base)
        iv = {_stem(w) for w in ing_words}
        extra_var = [w for w in uset if w in {_stem(v) for v in _VARIANT_WORDS} and w not in iv]
        # variant words in the ingredient not reflected by the USDA entry (e.g., vegan, coconut)
        missing_var = [w for w in iset if w in {_stem(v) for v in _VARIANT_WORDS} and w not in uset]

        score = 10.0 * (0.55 * cover + 0.25 * head_hit + 0.20 * precision)
        score -= 2.5 * len(missing_var)
        score -= 1.0 * min(3, len(extra_var))
        score -= 3.0 * len(caps_unmatched)
        score -= 2.0 * len(brand_u)
        score -= 1.5 * tm + 1.0 * paren_brand
        # brand in both ingredient and USDA: standard example, reward
        if brand_i and (brand_i & usda_words):
            score += 1.5
        # little overlap overall => hard cap
        if cover < 0.34:
            score = min(score, 2.0)
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
