import re

_DROP = set("""fresh frozen thawed chopped diced sliced minced grated shredded dried canned cooked raw large small
medium whole boneless skinless trimmed peeled optional garnish of and or with for from the a an to taste
fillet fillets slices pieces flaked g kg ml oz lb nfs regular plain crude separable lean fat select dry heat
braised roasted baked boiled steamed unprepared prepared variety meats by products""".split())
_CLASS = set("""fish cheese nuts spices beef pork lamb veal chicken turkey duck oil seeds cereals vegetables fruit
babyfood snacks candies sauce soup beverages""".split())


def _key(w):
    return w[:4] if len(w) > 4 else w


def _words(s):
    return [w for w in re.findall(r"[a-z]+", s) if w not in _DROP]


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower()).split(",")[0]
        ing = re.sub(r"\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        iw = _words(ing)
        us = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        segs = [_words(s) for s in us.split(",")]
        segs = [s for s in segs if s]
        if not iw or not segs:
            return 0.0
        ik = [_key(w) for w in iw]
        iset = set(ik)
        # Rebuild a natural-language reading of the USDA entry by reversing the comma order
        # ("Cheese, brie" -> "brie cheese") and treat its LAST word as the true head noun.
        qual = [w for s in segs[1:3] for w in s]
        lead = segs[0]
        # class-style lead (single generic word) with specifier following: head is the specifier
        if len(segs) > 1 and len(lead) == 1 and lead[0] in _CLASS and segs[1]:
            u_head = segs[1][-1]
            u_mods = lead + segs[1][:-1] + [w for s in segs[2:3] for w in s]
        else:
            u_head = lead[-1]
            u_mods = lead[:-1] + qual
        uk_head = _key(u_head)
        uk_mods = set(_key(w) for w in u_mods)
        i_head = ik[-1]
        score = 5.0
        # head noun agreement
        if uk_head == i_head:
            score += 3.0
        elif uk_head in iset:
            score += 0.5      # usda head is only a modifier in the recipe phrase
        else:
            score -= 2.5
        # recipe head demoted: occurs in usda mods but is not the usda head
        if i_head != uk_head and i_head in uk_mods:
            score -= 2.5
        # contradiction: recipe modifiers vs usda modifiers that do not match (duck vs chicken)
        i_mods = set(ik[:-1])
        if uk_head == i_head or uk_head in iset:
            miss_i = len([m for m in i_mods if m not in uk_mods and m != uk_head])
            extra_u = len([m for m in uk_mods if m not in iset])
            if miss_i and extra_u:
                score -= 2.0 * min(miss_i, extra_u)
            elif miss_i:
                score -= 0.7 * min(miss_i, 3)
            elif extra_u:
                score -= 0.3 * min(extra_u, 3)
        # shared modifiers reward
        score += 0.8 * len(i_mods & uk_mods)
        return float(max(-5.0, min(10.0, score)))
    except Exception:
        return 0.0
