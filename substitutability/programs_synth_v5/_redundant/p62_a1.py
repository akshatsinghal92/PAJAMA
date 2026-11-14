import re
import math


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0

        # clean ingredient: drop weight prefix, parentheticals
        ing = re.sub(r"\([^)]*\)", " ", ing)
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb)?\b", " ", ing)
        usda = re.sub(r"\([^)]*\)", " ", usda)

        # ingredient core = text before first comma; usda primary = before first comma
        ing_core = ing.split(",")[0]
        usda_parts = [p.strip() for p in usda.split(",")]
        usda_primary = usda_parts[0] if usda_parts else usda

        stop = {"fresh", "frozen", "raw", "cooked", "chopped", "sliced", "diced", "minced",
                "ground", "dried", "optional", "serving", "garnish", "the", "of", "a", "for",
                "plain", "large", "small", "fillet", "fillets", "boneless", "skinless",
                "shredded", "grated", "cubed", "thawed", "warmed", "to", "taste"}

        def toks(s):
            out = []
            for w in re.findall(r"[a-z]+", s):
                if w in stop or len(w) < 2:
                    continue
                if len(w) > 3 and w.endswith("ies"):
                    w = w[:-3] + "y"
                elif len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
                    w = w[:-2]
                elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
                    w = w[:-1]
                out.append(w)
            return out

        dish_words = {"salad", "soup", "casserole", "sandwich", "mix", "blend", "dinner",
                      "prepared", "stuffed", "sauce", "stew", "pie", "pizza", "taco",
                      "burrito", "entree", "meal", "pasta", "dish", "combo", "filling",
                      "stir-fry", "kabob", "burger", "topped", "breaded", "patty", "dressing"}
        connectors = {"with", "and", "in", "or", "stuffed", "topped", "over", "plus"}

        def composite_level(raw, primary):
            ws = re.findall(r"[a-z\-]+", raw)
            c = 0.0
            c += 1.0 * sum(1 for w in ws if w in ("with", "and", "stuffed", "topped", "plus"))
            c += 1.0 * sum(1 for w in ws if w in dish_words and w not in ("dressing", "patty", "sauce"))
            c += 0.5 * sum(1 for w in ws if w in ("sauce", "patty"))
            c += 0.5 * (len(re.findall(r"\bin\b", raw)))
            return c

        ing_comp = composite_level(ing_core, ing_core)
        usda_comp = composite_level(usda, usda_primary)

        # same-dish exception: dish word shared by both sides
        it = toks(ing_core)
        ut_all = toks(usda)
        ut_primary = toks(usda_primary)
        iset, uset = set(it), set(ut_all)

        shared_dish = [w for w in dish_words if w in ing_core.split() and w in usda.split()]
        asym = abs(ing_comp - usda_comp)
        if shared_dish:
            asym = max(0.0, asym - 1.0 * len(shared_dish))

        # component counting: number of distinct food nouns joined by 'and'
        ing_units = 1 + len(re.findall(r"\band\b|\bwith\b", ing_core))
        usda_units = 1 + len(re.findall(r"\band\b|\bwith\b", usda_primary + " " + " ".join(usda_parts[1:2])))
        unit_gap = abs(ing_units - usda_units)

        # content overlap
        if iset:
            cover = len(iset & uset) / float(len(iset))
        else:
            cover = 0.0
        prim_cover = len(iset & set(ut_primary)) / float(max(1, len(set(ut_primary))))
        extra = len(uset - iset)

        score = 5.0 * cover + 2.0 * prim_cover
        score -= 2.5 * asym
        score -= 1.5 * unit_gap
        score -= 0.25 * min(extra, 6)

        # extra-state descriptors in USDA that imply processing/addition
        if re.search(r"fat added|salt added|sauce|breaded|battered|fried|canned|condensed|nfs", usda) and \
           not re.search(r"fat added|sauce|breaded|battered|fried|canned|condensed|nfs", ing):
            score -= 1.0

        if cover == 0:
            score -= 2.0
        return float(score)
    except Exception:
        return 0.0
