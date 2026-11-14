import re

_NOTES = {"optional", "taste", "garnish", "serving", "needed", "about", "approximately", "fresh",
          "large", "small", "medium", "big", "of", "and", "or", "with", "without", "the", "a", "an",
          "for", "to", "from", "in", "into", "plus", "extra", "good", "quality", "pieces", "piece",
          "nfs", "type", "style", "made", "pack", "solids", "liquids", "equal", "parts", "part"}
_STATE_GROUPS = {
    "canned": {"canned", "can", "tinned"},
    "frozen": {"frozen", "thawed"},
    "dried": {"dried", "dry", "dehydrated"},
    "cooked": {"cooked", "boiled", "baked", "roasted", "steamed", "fried", "grilled", "simmered"},
    "raw": {"raw", "uncooked"},
    "toasted": {"toasted"},
    "ground": {"ground", "powder", "powdered", "meal"},
    "juice": {"juice"},
    "sauce": {"sauce"},
    "pie": {"pie", "filling"},
    "syrup": {"syrup"},
    "pickled": {"pickled", "brined"},
    "smoked": {"smoked"},
    "candied": {"candied", "sweetened", "glazed"},
}
_TOKEN_TO_STATE = {}
for _k, _v in _STATE_GROUPS.items():
    for _t in _v:
        _TOKEN_TO_STATE[_t] = _k
_NEUTRAL_STATES = {"raw"}
_SYN = {"pinyon": "pine", "jamun": "jambolan", "yoghurt": "yogurt", "nonfat": "fat", "lowfat": "fat"}


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 3 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            if suf == "es" and not w.endswith(("ches", "shes", "oes")):
                continue
            return w[:-len(suf)] if suf != "es" else w[:-2]
    return w


def _tokens(s):
    s = s.lower()
    s = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|oz|lb|lbs|ml|l|cups?|tbsp|tsp)\b", " ", s)
    s = re.sub(r"[^a-z\s]", " ", s)
    out = []
    for w in s.split():
        w = _SYN.get(w, w)
        w = _stem(w)
        if w and w not in _NOTES:
            out.append(w)
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        it = _tokens(ing)
        ut = _tokens(usda)
        if not it or not ut:
            return 0.0
        uset = set(ut)
        iset = set(it)

        # head noun of ingredient: last token before first comma/paren; USDA head: first segment
        ing_main = re.split(r"[,(]", ing)[0]
        ihead = _tokens(ing_main)
        usda_first = _tokens(usda.split(",")[0])
        head_hit = 0.0
        if ihead:
            h = ihead[-1]
            if h in uset:
                head_hit = 1.0
            elif usda_first and any(h in t or t in h for t in usda_first if len(t) > 3):
                head_hit = 0.6
        if ihead and usda_first and ihead[-1] in usda_first:
            head_hit = 1.0

        # weighted coverage: tokens in the ingredient earlier = food, later = qualifiers
        cov_w, tot_w = 0.0, 0.0
        for i, t in enumerate(it):
            w = 2.0 if t in ihead[-2:] else 1.0
            tot_w += w
            if t in uset:
                cov_w += w
            elif any(len(t) > 4 and len(u) > 4 and (t[:5] == u[:5]) for u in uset):
                cov_w += 0.6 * w
        coverage = cov_w / tot_w if tot_w else 0.0

        # state contradictions / unaccounted
        istates = {_TOKEN_TO_STATE[t] for t in it if t in _TOKEN_TO_STATE}
        ustates = {_TOKEN_TO_STATE[t] for t in ut if t in _TOKEN_TO_STATE}
        # canned in ingredient text comes from word "canned" too
        penalty = 0.0
        for s in istates - ustates:
            if s not in _NEUTRAL_STATES:
                penalty += 0.8
        for s in ustates - istates:
            if s in ("canned", "pie", "sauce", "syrup", "juice", "pickled", "candied", "smoked", "frozen", "dried"):
                penalty += 1.5
            elif s == "raw":
                penalty += 0.0
            else:
                penalty += 0.3
        if "raw" in istates and "cooked" in ustates:
            penalty += 1.0
        if "cooked" in istates and "raw" in ustates:
            penalty += 0.5
        if "canned" in istates and "canned" in ustates:
            penalty -= 0.5

        # extra USDA content words that the ingredient never mentions
        extra = [t for t in ut if t not in iset and t not in _TOKEN_TO_STATE
                 and len(t) > 2 and t not in {"raw", "whole", "brand", "usda", "commodity", "choice", "separable", "lean", "fat"}]
        extra_ratio = len(extra) / float(len(ut))
        # brand-like uppercase tokens are ignored
        brands = set(re.findall(r"\b[A-Z]{3,}\b", usda))
        if brands:
            extra = [t for t in extra if t.upper() not in brands]
            extra_ratio = len(extra) / float(len(ut))

        score = 5.0 * coverage + 3.0 * head_hit - 1.6 * penalty - 2.0 * extra_ratio
        if head_hit == 0.0:
            score -= 2.0
        return float(score)
    except Exception:
        return 0.0
