import re

_PREP = set("""fresh frozen thawed cooked raw dried dry chopped sliced diced minced melted crumbled
ground shredded grated peeled boiled steamed roasted smoked simmered large small medium
lean skin on off boneless skinless whole organic ripe finely coarsely optional extra
for garnish and or of the a with plain unsalted salted powdered canned lowfat low fat
diet""".split())
_KEEP_STATE = set(["ground", "dried", "dry", "smoked", "frozen", "powdered", "whole"])
_NOISE = set("nfs raw cooked unprepared fresh with without and or of the in type style".split())
_FORM_WORDS = set("""sauce pie filling chips chip bar soup juice oil paste powder zest candy cake
bread cookie cookies cracker crackers salad dressing syrup jam jelly snack drink beverage
flour starch extract seasoning mix tapenade spread""".split())


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"\([^)]*\)", " ", ing)
        ing = ing.split(",")[0]
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        raw_ing = re.findall(r"[a-z]+", ing)
        core = [_stem(t) for t in raw_ing if t not in _PREP]
        if not core:
            core = [_stem(t) for t in raw_ing]
        if not core:
            return 0.0
        usda_clean = re.sub(r"\([^)]*\)", " ", usda)
        parts = [p.strip() for p in usda_clean.split(",")]
        primary = _tokens(parts[0])
        all_u = _tokens(usda_clean)
        uset = set(all_u)
        head = core[-1]
        score = 0.0
        # head noun of compound must be found, ideally in primary
        if head in primary:
            score += 3.0
        elif head in uset:
            score += 1.5
        else:
            return 0.5 * len(set(core) & uset) / len(core)
        # modifier coverage (compound intactness)
        mods = core[:-1]
        if mods:
            hit = sum(1 for m in mods if m in uset)
            score += 3.5 * hit / len(mods)
            # adjacency of compound words in USDA, any order
            adj = 0
            pairs = list(zip(core, core[1:]))
            for a, b in pairs:
                for i in range(len(all_u) - 1):
                    if (all_u[i], all_u[i + 1]) in ((a, b), (b, a)):
                        adj += 1
                        break
            score += 1.5 * adj / len(pairs)
        else:
            score += 4.5
        # penalty: extra modifier/form words in USDA primary that form a different food
        extra = [t for t in primary if t not in core and t not in _NOISE]
        form_extra = [t for t in extra if t in _FORM_WORDS and t not in core]
        score -= 2.5 * len(form_extra)
        # extra words in primary beyond a plain match: mild penalty
        score -= 0.4 * max(0, len(extra) - len(form_extra) - 1)
        # ingredient has a form word that USDA primary lacks (e.g. starch vs chips)
        miss_form = [t for t in core if t in _FORM_WORDS and t not in uset]
        score -= 2.0 * len(miss_form)
        # ingredient asks for a distinct part (zest, bone, bran) absent in USDA
        if "nfs" in uset and len(core) > 1:
            score -= 1.0
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
