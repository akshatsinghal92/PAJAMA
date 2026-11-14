import re

# (regex, weight) qualifiers that a diner could notice if added silently
_QUALIFIERS = [
    (r"\b(low|reduced|less)[- ]?(sodium|salt)\b|\bunsalted\b|\bno salt\b", "sodium", 3.0),
    (r"\b(fat[- ]?free|non[- ]?fat|skim)\b", "nofat", 3.0),
    (r"\b(low[- ]?fat|reduced[- ]?fat|lowfat|part[- ]skim|lite|light)\b", "lowfat", 2.5),
    (r"\b(sugar[- ]?free|no sugar|unsweetened|reduced sugar|low sugar)\b", "nosugar", 3.0),
    (r"\b(sweetened|with sugar|added sugar|candied|glazed)\b", "sweet", 2.5),
    (r"\b(with salt|salted|added salt|brine|brined)\b", "salt", 2.5),
    (r"\b(flavored|flavoured|seasoned|spiced|smoked|marinated|barbecue|bbq)\b", "flavor", 2.0),
    (r"\b(enriched|fortified|with added|added vitamin|vitamin [a-d]\b)", "fortify", 1.0),
    (r"\b(additives|preservative|artificial|imitation|substitute|reduced calorie|diet)\b", "additive", 2.0),
    (r"\b(shelf stable|ready[- ]to|instant|dehydrated|canned|frozen|dried|dry)\b", "proc", 0.8),
]
_NEUTRAL = {"raw", "plain", "regular", "whole", "fresh", "nfs", "ns", "as", "to", "specified",
            "all", "types", "commercial", "unprepared", "mature", "seeds", "mixed", "species"}

def _clean(s):
    s = (s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|oz|lb|ml|l)\b", " ", s)
    return s

def _quals(text):
    found = {}
    for pat, name, w in _QUALIFIERS:
        if re.search(pat, text):
            found[name] = w
    return found

def judging_function(ingredient, usda_match):
    try:
        ing_raw = ingredient or ""
        usda_raw = usda_match or ""
        ing = _clean(ing_raw)
        # keep parenthetical of usda too for qualifiers (additives etc.)
        usda_full = re.sub(r"[()]", " ", usda_raw.lower())
        usda = _clean(usda_raw)
        ing_full = re.sub(r"[()]", " ", ing_raw.lower())
        iq = _quals(ing_full)
        uq = _quals(usda_full)
        # asymmetric: only qualifiers present in usda but not stated (or opposite stated) are penalized
        penalty = 0.0
        for name, w in uq.items():
            if name in iq:
                continue
            # a related stated qualifier softens the penalty
            related = {"nofat": "lowfat", "lowfat": "nofat", "nosugar": "sweet", "sweet": "nosugar"}
            if related.get(name) in iq:
                penalty += w * 0.4
            else:
                penalty += w
        # stated qualifier that usda lacks is a mild issue
        for name, w in iq.items():
            if name not in uq and name in ("sodium", "nofat", "lowfat", "nosugar", "salt", "sweet"):
                penalty += w * 0.5
        # coverage of ingredient content words by usda text
        tok = lambda t: [x for x in re.findall(r"[a-z]+", t) if len(x) > 2]
        stop = {"and", "the", "with", "for", "from", "only", "fresh", "cooked", "chopped", "sliced",
                "diced", "cubed", "ground", "shredded", "ripe", "large", "small", "thawed", "whole"}
        it = [t for t in tok(ing) if t not in stop]
        ut = set(tok(usda))
        def stem(t):
            return t[:-1] if t.endswith("s") and len(t) > 3 else t
        us = {stem(t) for t in ut}
        if it:
            cov = sum(1 for t in it if stem(t) in us) / float(len(it))
        else:
            cov = 0.0
        # extra usda descriptors that are not neutral and not in ingredient
        ist = {stem(t) for t in tok(ing_full)}
        extras = [t for t in ut if stem(t) not in ist and t not in _NEUTRAL]
        extra_pen = min(len(extras), 8) * 0.15
        score = 10.0 * cov - penalty - extra_pen
        if cov == 0:
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
