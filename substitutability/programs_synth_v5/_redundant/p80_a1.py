import re

_PREP = set("""fresh frozen canned dried dry cooked raw chopped diced sliced minced ground crushed grated shredded
peeled cubed crumbled drained thawed large small medium whole fine finely thinly roughly boneless skinless
bagged mixed packed ripe optional plain regular for the of and with from in a an to or into style
cut pieces piece segmented softened melted toasted""".split())
_GENERIC = set("raw cooked regular commercial nfs all varieties variety types type prepared plain without with and or of for the in a made".split())
_COMPOUND_MODS = set("""sweet coconut peanut sea green black white red yellow sour hot cream sauce juice oil flour paste
powder milk butter cheese soup broth stock bean nut seed water vinegar syrup candy cake bread loaf stew sausage
patty snack imitation substitute flavored""".split())


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            if suf == "ies":
                return w[:-3] + "y"
            if suf == "es" and not w.endswith(("ches", "shes", "oes", "xes", "sses")):
                return w[:-1]
            return w[:-len(suf)] if suf != "es" else w[:-2]
    return w


def _toks(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"\([^)]*\)", " ", ing)
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|oz|ml|l|lb)?\b", " ", ing)
        ing = ing.split(",")[0]
        ing = ing.replace("-", " ")
        usda = re.sub(r"\([^)]*\)", " ", usda).replace("-", " ")
        core = [t for t in _toks(ing) if t not in _PREP and len(t) > 1]
        if not core:
            core = _toks(ing)
        if not core:
            return 0.0
        segs = [_toks(s) for s in usda.split(",")]
        segs = [s for s in segs if s]
        if not segs:
            return 0.0
        utoks = [t for s in segs for t in s]
        uset = set(utoks)
        primary = segs[0]

        # 1. head-weighted coverage of compound tokens
        n = len(core)
        weights = [1.0] * n
        weights[-1] = 2.0
        cov = sum(w for t, w in zip(core, weights) if t in uset) / sum(weights)

        # 2. compound bigram integrity: adjacent ingredient pairs found adjacent in same USDA segment (either order)
        pairs = list(zip(core, core[1:]))
        if pairs:
            ok = 0
            for a, b in pairs:
                for s in segs:
                    if any((s[i] == a and s[i + 1] == b) or (s[i] == b and s[i + 1] == a) for i in range(len(s) - 1)):
                        ok += 1
                        break
            integrity = ok / len(pairs)
        else:
            integrity = 1.0 if core[0] in uset else 0.0

        # 3. head noun position: head should be in primary food, or primary token appears in ingredient
        head_in_primary = 1.0 if core[-1] in primary else (0.5 if core[-1] in uset else 0.0)
        prim_in_ing = 1.0 if any(t in core for t in primary) else 0.0

        # 4. extra modifiers in USDA that form a different compound
        cs = set(core)
        extra_primary = [t for t in primary if t not in cs and t not in _GENERIC and len(t) > 2]
        pen = 0.0
        for t in extra_primary:
            pen += 1.5 if t in _COMPOUND_MODS else 0.6
        # other segments modifiers that are compound-forming and absent
        for s in segs[1:]:
            for t in s:
                if t in _COMPOUND_MODS and t not in cs and t not in _GENERIC:
                    pen += 0.5
        pen = min(pen, 5.0)

        score = 4.0 * cov + 2.5 * integrity + 1.5 * head_in_primary + 1.5 * prim_in_ing - pen
        if cov == 0:
            score -= 2.0
        return max(-5.0, min(10.0, score))
    except Exception:
        return 0.0
