import re

_PREP = set("""fresh frozen thawed chopped diced sliced minced grated shredded ground dried canned cooked raw
large small medium big whole boneless skinless trimmed peeled optional garnish strong brewed soft hot cold
finely roughly coarsely crushed melted softened packed fillet fillets slices slice pieces piece flaked
of and or with for from the a an to taste plain regular refined organic unsalted salted sweet light dark
extra virgin lean fat free low reduced""".split())
_CATS = set("""fish cheese nuts spices beef pork lamb veal chicken turkey duck oil oils seeds cereals cereal
vegetables fruits fruit candies beverages babyfood snacks soup soups sauce sauces game bread breads
crackers cookie cookies cake cakes pie pies milk yogurt egg eggs salad dressing""".split())
_MOD_FOODS = set("""milk soup pie sauce cookie cookies cake cakes bread candies candy relish juice drink
dressing butter oil syrup jam jelly pudding cereal bar chips flavored ice cream paste powder""".split())


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w


def _toks(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = ing.split(",")[0]
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb)?\b", " ", ing)
        ing_t = [t for t in _toks(ing) if t not in _PREP and t not in ("g",)]
        usda = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        segs = [s.strip() for s in usda.split(",") if s.strip()]
        if not ing_t or not segs:
            return 0.0
        seg_t = [_toks(s) for s in segs]
        head = seg_t[0]
        # pick the "food segment": skip a generic category lead if next segment exists
        food_idx = 0
        if len(segs) > 1 and len(head) == 1 and head[0] in _CATS and head[0] not in ing_t:
            food_idx = 1
        elif len(segs) > 1 and len(head) == 1 and head[0] in _CATS:
            food_idx = 0
        food = seg_t[food_idx]
        flat = [t for st in seg_t for t in st]
        ing_head = ing_t[-1]  # head noun of recipe phrase
        score = 0.0
        # 1. ingredient head noun position
        if food and ing_head == food[-1]:
            score += 4.0
        elif ing_head in food:
            score += 2.5
        elif ing_head in head:
            score += 2.0
        elif ing_head in flat:
            pos = min(i for i, st in enumerate(seg_t) if ing_head in st)
            score += 1.0 if pos <= 1 else 0.3
        # 2. ingredient coverage by food segment
        cov = sum(1 for t in ing_t if t in food or t in head) / float(len(ing_t))
        score += 3.0 * cov
        # 3. demotion: usda lead is a different dish-type word, ingredient only a modifier
        if food_idx == 0 and ing_head in head and head[-1] != ing_head and head[-1] in _MOD_FOODS \
                and head[-1] not in ing_t:
            score -= 4.0
        if food and food[-1] in _MOD_FOODS and food[-1] not in ing_t:
            score -= 3.0
        # ingredient is product of the food (butter/sauce) but usda is the plain base
        if ing_t[-1] in _MOD_FOODS and ing_t[-1] not in flat:
            score -= 2.5
        # 4. extra food words in the usda head not in ingredient
        extra = [t for t in food if t not in ing_t]
        score -= 0.5 * min(len(extra), 3)
        # 5. ingredient tokens absent from usda altogether
        miss = [t for t in ing_t if t not in flat]
        score -= 1.0 * min(len(miss), 3)
        # 6. unrelated usda leading food when ingredient not present at all
        if not any(t in flat for t in ing_t):
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
