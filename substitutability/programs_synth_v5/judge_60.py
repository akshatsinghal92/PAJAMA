import re

_STOP = set("""a an and or of the with without to taste from in for fresh freshly fillets fillet
chopped sliced diced minced grated shredded crushed warmed thawed drained rinsed peeled large small medium
whole raw cooked boiled toasted frozen canned dried pack solids liquids g kg ml oz lb cup cups tbsp tsp pieces
piece leaves leaf style type brand optional extra""".split())

_VARIANT = ["vanilla", "chocolate", "strawberry", "flavored", "flavor", "sweetened", "unsweetened",
            "soy", "almond", "oat", "coconut", "rice", "plant", "vegan", "imitation", "substitute",
            "reduced", "lowfat", "low", "nonfat", "fat-free", "light", "lite", "diet", "sugar-free",
            "smoked", "cured", "breaded", "stuffed", "fried", "babyfood", "infant", "formula", "mix",
            "dehydrated", "powder", "powdered", "cream", "soup", "sauce", "candy", "cake", "pie", "chips",
            "peanut", "pecan", "almond", "cashew", "butter", "margarine", "juice", "syrup", "salad", "dressing"]
_BRANDWORDS = {"kraft", "nabisco", "oreo", "heinz", "kellogg", "kelloggs", "campbell", "campbells",
               "mcdonalds", "burger", "king", "pillsbury", "hershey", "hersheys", "nestle", "pepsi", "coca",
               "cola", "gatorade", "starbucks", "snickers", "mars", "tabasco", "pizza", "hut", "wendys",
               "subway", "ocean", "spray", "land", "lakes", "pete", "texas", "yoplait", "oscar", "mayer",
               "jimmy", "dean", "smucker", "smuckers", "quaker", "general", "mills", "keebler", "pringles",
               "lays", "doritos", "fritos", "cheerios", "trix", "kashi", "cadbury", "godiva", "mccormick"}


def _norm(s):
    s = str(s or "")
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", s.lower().strip(), flags=re.I)
    return s


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _toks(s):
    return [_stem(w) for w in re.findall(r"[a-z][a-z\-]+", s) if w not in _STOP]


def judging_function(ingredient, usda_match):
    try:
        ing_raw = str(ingredient or "")
        usda_raw = str(usda_match or "")
        if not ing_raw.strip() or not usda_raw.strip():
            return 0.0
        ing_n = _norm(ing_raw)
        usda_n = _norm(usda_raw)
        ing_main = re.sub(r"\([^)]*\)", " ", ing_n).split(",")[0]
        ing_t = _toks(re.sub(r"\([^)]*\)", " ", ing_n))
        ing_core = _toks(ing_main) or ing_t
        usda_parts = [p.strip() for p in usda_n.split(",")]
        usda_t = _toks(usda_n)
        if not ing_core or not usda_t:
            return 0.0
        uset = set(usda_t)
        iset = set(ing_core)
        iset_all = set(ing_t)

        # (1) core coverage with weight on primary food
        primary = set(_toks(usda_parts[0])) if usda_parts else set()
        cov = sum(1.0 for w in iset if w in uset) / len(iset)
        prim_hit = 1.0 if (primary and (primary & iset_all)) else 0.0
        prim_full = 1.0 if (primary and primary <= iset_all) else 0.0
        # (2) how much of usda is explained by the ingredient (extra descriptors)
        extra = [w for w in usda_t if w not in iset_all]
        extra_ratio = len(extra) / float(len(usda_t))

        # (3) brand / commercial detection
        raw_tokens = re.findall(r"[A-Za-z!']+", usda_raw)
        caps = [w for w in raw_tokens if len(w) > 2 and w.isupper()]
        brand_hit = [w for w in re.findall(r"[a-z]+", usda_n) if w in _BRANDWORDS]
        has_brand = bool(caps or brand_hit or re.search(r"[A-Z]{2,}[ !]", usda_raw))
        ing_has_brand = bool(re.search(r"\b[A-Z]{2,}\b", ing_raw) or
                             any(w in _BRANDWORDS for w in re.findall(r"[a-z]+", ing_n)))
        brand_pen = 0.0
        if has_brand:
            # standard example of product: ingredient fully covered -> mild/no penalty
            brand_pen = 0.3 if cov >= 0.99 else 1.5
            if ing_has_brand:
                brand_pen *= 0.3

        # (4) variant conflicts: variant word on one side only
        ing_all_words = set(re.findall(r"[a-z\-]+", ing_n))
        usda_all_words = set(re.findall(r"[a-z\-]+", usda_n))
        conflicts = 0
        for v in _VARIANT:
            a = v in ing_all_words
            b = v in usda_all_words
            if a != b:
                conflicts += 1
        # words in usda primary not present in ingredient
        prim_foreign = len(primary - iset_all)
        # unmatched core ingredient words
        miss = len([w for w in iset if w not in uset])

        # (5) state agreement (cooked vs raw)
        state_pen = 0.0
        if ("cooked" in ing_all_words or "boiled" in ing_all_words) != ("cooked" in usda_all_words or "boiled" in usda_all_words):
            if not ("raw" in usda_all_words and "cooked" not in ing_all_words and "boiled" not in ing_all_words):
                state_pen = 1.0
        if "canned" in usda_all_words and "canned" not in ing_all_words:
            state_pen += 0.8

        score = 10.0 * cov * (0.5 + 0.5 * prim_hit) + 2.0 * prim_full
        score -= 6.0 * extra_ratio
        score -= 1.5 * conflicts
        score -= 2.5 * prim_foreign
        score -= 1.5 * miss
        score -= brand_pen
        score -= state_pen
        if usda_n.strip() == ing_main.strip():
            score += 2.0
        return float(max(-10.0, min(15.0, score)))
    except Exception:
        return 0.0
