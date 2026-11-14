import re

_PREP = set("""sliced chopped diced minced grated shredded crushed ground fresh frozen thawed cooked raw
roasted grilled baked fried boiled steamed simmered peeled boneless skinless lean fat large small medium
whole dried canned store bought storebought homemade mixed finely coarsely thinly optional extra
fillet fillets cut cubed halved quartered toasted ripe plain unsalted salted low reduced free the a an of
and or with from for in to into only about equal parts part pieces piece leaves leaf""".split())

_COLOR_MOD = set("sweet sour hot green red black white yellow brown wild sea sour dark light cream".split())

_SYN = {
    "tortilla": "wrap", "wraps": "wrap", "wrap": "wrap",
    "peas": "pea", "olives": "olive", "nuts": "nut", "beans": "bean",
}


def _stem(w):
    w = _SYN.get(w, w)
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _core(text):
    t = (text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.split(",")[0]
    t = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb|mg|l)?\b", " ", t)
    toks = re.findall(r"[a-z]+", t)
    return [_stem(w) for w in toks if w not in _PREP]


def judging_function(ingredient, usda_match):
    try:
        ing = _core(ingredient)
        if not ing:
            return 0.0
        raw_u = (usda_match or "").lower()
        u_all = [_stem(w) for w in re.findall(r"[a-z]+", raw_u)]
        if not u_all:
            return 0.0
        u_set = set(u_all)
        u_first_seg = [_stem(w) for w in re.findall(r"[a-z]+", raw_u.split(",")[0])]
        u_head_set = set(u_first_seg)

        head = ing[-1]
        mods = ing[:-1]
        score = 0.0

        # head noun presence
        if head in u_set:
            score += 3.0
            if head in u_head_set:
                score += 1.0
        # modifiers kept
        if mods:
            kept = sum(1 for m in mods if m in u_set)
            score += 4.0 * kept / len(mods)
            # adjacent compound intact in USDA (either order)
            ul = u_all
            adj = 0
            for i in range(len(ing) - 1):
                a, b = ing[i], ing[i + 1]
                for j in range(len(ul) - 1):
                    if (ul[j] == a and ul[j + 1] == b) or (ul[j] == b and ul[j + 1] == a):
                        adj += 1
                        break
            score += 1.5 * adj / max(1, len(ing) - 1)
        else:
            score += 3.0 if head in u_set else 0.0

        # penalty: USDA primary food words absent from ingredient (different food)
        extra_primary = [w for w in u_first_seg if w not in set(ing) and len(w) > 2 and w not in _PREP]
        for w in extra_primary:
            score -= 1.2
        # penalty: compound-forming modifier in USDA that ingredient lacks (e.g. peanut butter vs butter)
        ing_set = set(ing)
        if head in u_set and mods == []:
            others = [w for w in u_first_seg if w != head and w not in _PREP and len(w) > 2]
            score -= 1.5 * min(2, len(others))
        # penalty: head word is missing entirely
        if head not in u_set and not any(m in u_set for m in mods):
            score -= 2.0

        # ordering of dropped modifiers (ingredient modifiers not in USDA)
        if mods:
            lost = [m for m in mods if m not in u_set]
            score -= 1.0 * len(lost)

        return max(0.0, min(10.0, score + 1.0))
    except Exception:
        return 0.0
