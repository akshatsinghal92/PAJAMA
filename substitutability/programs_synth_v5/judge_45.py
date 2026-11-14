import re

_PREP = set("""fresh frozen chopped diced sliced minced ground grated shredded crushed cooked raw plain thawed
dried large small medium whole boneless skinless trimmed peeled optional fine finely coarsely roughly
leaves leaf fillets fillet seeds seed organic lean extra of and or with the a an for to in from
g kg oz lb lbs ml cup cups tbsp tsp pinch mix flakes""".split())
_MODIFIER_FOODS = set("""soup pie milk juice sauce cake cookie cookies candy cereal bar bars drink beverage
dressing flavored flavor yogurt ice cream pudding jam jelly syrup snack muffin bread chips""".split())
_STATE_BAD = set("canned syrup sweetened flavored strawberry vanilla chocolate nfs".split())


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            if suf == "ies":
                return w[:-3] + "y"
            if suf == "es" and not w.endswith(("ches", "shes", "oes", "ses", "xes")):
                continue
            return w[:-len(suf)] if suf != "es" else w[:-2]
    return w


def _tokens(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = ing.split(",")[0]
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*[a-z]*\s", " ", ing)
        usda = str(usda_match or "").lower()
        usda_nop = re.sub(r"\([^)]*\)", " ", usda)
        segs = [s.strip() for s in usda_nop.split(",") if s.strip()]
        if not segs:
            return 0.0
        itoks = [t for t in _tokens(ing) if t not in _PREP and t not in {_stem(p) for p in _PREP}]
        if not itoks:
            itoks = _tokens(ing)
        if not itoks:
            return 0.0
        head = itoks[-1]  # head noun of ingredient
        iset = set(itoks)
        seg0 = _tokens(segs[0])
        seg0set = set(seg0)
        rest = set()
        for s in segs[1:]:
            rest.update(_tokens(s))
        allu = seg0set | rest

        score = 0.0
        # head food in first segment
        if head in seg0set:
            score += 4.0
            # position within first segment: head noun last = plain food, else modifier
            if seg0 and seg0[-1] == head:
                score += 1.5
            elif seg0 and seg0[0] == head:
                score += 1.0
            else:
                score -= 1.0
        elif head in rest:
            score += 1.5
        # coverage of ingredient content words in the primary segment
        cov0 = len(iset & seg0set) / float(len(iset))
        covall = len(iset & allu) / float(len(iset))
        score += 2.0 * cov0 + 1.0 * covall
        # penalty if first segment holds extra foods not in the ingredient
        extra0 = [t for t in seg0 if t not in iset and t not in _PREP]
        score -= 0.8 * min(len(extra0), 3)
        # modifier demotion: ingredient food followed by a different head food
        if head in seg0set and seg0 and seg0[-1] != head and seg0[-1] in _MODIFIER_FOODS and seg0[-1] not in iset:
            score -= 3.0
        # ingredient food appearing only in later segments after a different primary food
        if head not in seg0set and head in rest:
            score -= 1.0
        # unmatched state words in descriptors
        bad = (allu & {_stem(b) for b in _STATE_BAD}) - iset
        score -= 0.7 * len(bad)
        # primary segment of usda is a different category word with no overlap
        if not (iset & allu):
            score -= 3.0
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
