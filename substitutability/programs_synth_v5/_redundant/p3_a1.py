import re

_PREP = set("""fresh frozen canned dried raw cooked chopped sliced diced minced grated shredded cubed
ground crushed thawed drained optional garnish leftover store bought storebought homemade toasted
roasted smoked pickled large small medium whole skin on off for frying of and or with the a an
to taste from tube cup slices leaves leaf boneless skinless peeled pitted halved flaked
ripe organic plain unsalted salted warm cold hot extra virgin finely roughly thinly""".split())
_CATEGORY = set("""oil fish flour sauce spices seeds seed nuts nut cheese beef pork lamb chicken turkey duck
juice milk candies cereals beverages soup snacks sausage ham bread cake cookies crackers syrup
vinegar butter cream egg eggs beans bean pasta rice squash apples apple""".split())

def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            if suf == "ies":
                return w[:-3] + "y"
            if suf == "es" and not w.endswith(("oes", "ches", "shes", "sses", "xes")):
                continue
            return w[:-len(suf)] if suf != "es" else w[:-2]
    return w

def _toks(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s.lower())]

def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        ing = re.sub(r"\([^)]*\)", " ", ing)
        ing = re.sub(r"^\s*[\d.,/]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        ing_main = ing.split(",")[0]
        usda = re.sub(r"\([^)]*\)", " ", usda)
        segs = [s for s in usda.split(",") if s.strip()]
        if not ing_main.strip() or not segs:
            return 0.0
        iw = [w for w in _toks(ing_main)]
        core = [w for w in iw if w not in {_stem(p) for p in _PREP}]
        if not core:
            core = iw
        if not core:
            return 0.0
        head = core[-1]
        # USDA head: first segment tokens; if generic category, include second segment
        u1 = _toks(segs[0])
        u1c = [w for w in u1 if w not in _PREP]
        uhead_set = set(u1c)
        usd_all = set()
        for s in segs[:3]:
            usd_all.update(_toks(s))
        if len(u1c) <= 1 and u1c and u1c[0] in {_stem(c) for c in _CATEGORY} and len(segs) > 1:
            uhead_set.update(_toks(segs[1]))
        usd_head_last = u1c[-1] if u1c else ""
        score = 0.0
        # head noun identity
        if head in uhead_set:
            score += 5.0
            if head == usd_head_last:
                score += 1.0
        elif head in usd_all:
            score += 2.5
        # core word coverage of ingredient (head identity of all content words)
        cov = sum(1 for w in core if w in usd_all) / float(len(core))
        score += 3.0 * cov
        # substance conflict: USDA primary words absent from ingredient
        ing_all = set(iw)
        extra = [w for w in u1c if w not in ing_all]
        if head not in uhead_set:
            score -= 1.0 * min(len(extra), 3)
        else:
            score -= 0.5 * min(len(extra), 3)
        # ingredient modifiers not in usda (e.g. 'oat', 'coconut', 'vanilla') break identity
        miss = [w for w in core[:-1] if w not in usd_all]
        score -= 0.7 * min(len(miss), 3)
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
