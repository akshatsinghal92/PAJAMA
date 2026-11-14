import re

_COMPOUNDS = [
    "sweet potato", "coconut milk", "coconut cream", "coconut water", "peanut butter",
    "almond butter", "sea bass", "green tea", "black tea", "ice cream", "sour cream",
    "cream cheese", "cottage cheese", "bell pepper", "black pepper", "hot dog",
    "corn starch", "potato starch", "corn meal", "rice bran", "wheat bran", "olive oil",
    "sesame oil", "soy sauce", "fish sauce", "apple pie", "apple sauce", "sweet cherry",
    "green bean", "kidney bean", "black bean", "pinto bean", "turnip green", "ground turkey",
    "ground beef", "breakfast sausage", "breakfast bar", "cheese sauce", "pie filling",
    "potato chip", "greek yogurt", "plant based", "sports drink", "ground ginger",
    "garlic paste", "tomato paste", "tomato sauce", "baking soda", "baking powder",
    "egg white", "egg yolk", "pine nut", "water chestnut", "butternut squash",
    "olive tapenade", "bean sprout", "chicken breast", "beef kidney", "lamb liver",
]
_STOP = set("""a an the and or of with without in on for to from nfs raw cooked uncooked fresh frozen
dried dry thawed chopped sliced diced minced melted crumbled shredded grated peeled boiled
steamed roasted simmered large small medium whole skin trimmed choice separable fat lean
unprepared style type optional garnish""".split())
_SYN = {"vegan": "plantbased", "plant": "plantbased", "based": "", "maiz": "corn"}


def _st(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 4 and w[-3] in "sxzh":
        return w[:-2]
    if w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
        return w[:-1]
    return w


def _clean_tokens(s):
    return [_st(t) for t in re.findall(r"[a-z]+", s)]


def _concepts(toks):
    """Return set of compound concepts found plus residual single tokens."""
    found = set()
    text = " ".join(toks)
    for c in _COMPOUNDS:
        cs = " ".join(_st(w) for w in c.split())
        rev = " ".join(reversed(cs.split()))
        if re.search(r"\b" + cs + r"\b", text) or re.search(r"\b" + rev + r"\b", text):
            found.add(cs)
    return found


def _lcs_len(a, b):
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"\([^)]*\)", " ", ing)
        usda = re.sub(r"\([^)]*\)", " ", usda)
        ing_main = re.sub(r"^\s*\d+(\.\d+)?\s*[a-z]{0,2}\b", " ", ing.split(",")[0])
        it = _clean_tokens(ing_main)
        ut_full = _clean_tokens(usda)
        ut_primary = _clean_tokens(usda.split(",")[0])
        ic = [t for t in it if t not in _STOP]
        if not ic:
            ic = it
        if not ic:
            return 0.0
        uc_primary = [t for t in ut_primary if t not in _STOP]
        uc_full = [t for t in ut_full if t not in _STOP]

        ic_comp = _concepts(it)
        uc_comp = _concepts(ut_full)
        up_comp = _concepts(ut_primary)

        score = 5.0
        # compound concept alignment
        if ic_comp:
            kept = ic_comp & uc_comp
            lost = ic_comp - uc_comp
            score += 2.5 * len(kept) / len(ic_comp)
            score -= 3.0 * len(lost) / len(ic_comp)
        # USDA introduces compounds the ingredient does not have -> different food
        foreign = up_comp - ic_comp
        score -= 3.5 * len(foreign)
        # ordered alignment of the ingredient core against USDA tokens (sequence-aware)
        l_set = set(ic)
        lcs_p = _lcs_len(ic, uc_primary)
        lcs_f = _lcs_len(ic, uc_full)
        score += 2.5 * max(lcs_p, lcs_f * 0.8) / len(ic)
        # unordered coverage using whole description
        cov = len(l_set & set(uc_full)) / len(l_set)
        score += 2.0 * cov - 1.5 * (1 - cov)
        # leading head: the USDA description should start with the ingredient head noun
        head = ic[-1]
        if uc_primary and head in uc_primary:
            score += 1.0
        else:
            score -= 2.0
        # primary-food tokens not explained by the ingredient (partial modifiers)
        stray = [t for t in uc_primary if t not in l_set]
        score -= 1.2 * max(0, len(stray) - 1) + 0.5 * min(1, len(stray))
        # generic bucket penalty
        if "nfs" in ut_full:
            score -= 1.0
        # ingredient has a single-word core but the USDA has heterogeneous multiword name
        if len(ic) == 1 and len(uc_primary) >= 3:
            score -= 1.5
        return max(0.0, min(12.0, score))
    except Exception:
        return 0.0
