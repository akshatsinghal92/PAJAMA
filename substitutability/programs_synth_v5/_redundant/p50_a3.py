import re
import math

# token-level qualifier lexicon with per-token cost (taste/composition impact)
_COST = {
    "low": 1.0, "reduced": 1.0, "lowfat": 1.5, "nonfat": 2.0, "skim": 1.5, "free": 1.0,
    "light": 1.0, "lite": 1.0, "diet": 1.5, "sweetened": 1.5, "unsweetened": 1.5,
    "salted": 1.2, "unsalted": 1.2, "flavored": 1.5, "flavoured": 1.5, "enriched": 1.0,
    "fortified": 1.2, "imitation": 2.0, "artificial": 1.5, "decaffeinated": 1.5,
    "seasoned": 1.2, "sodium": 0.6, "sugar": 0.6, "fat": 0.4, "added": 0.5, "vitamin": 0.8,
    "substitute": 1.5, "dietetic": 1.5,
}
_FILLER = {"raw", "plain", "regular", "whole", "fresh", "and", "or", "of", "the", "with",
           "a", "in", "for", "from", "all", "types", "ns", "as", "g", "gram", "grams"}


def _words(s):
    s = str(s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|oz|ml|grams?)?\b", " ", s)
    s = s.replace("low-fat", "lowfat").replace("low fat", "lowfat")
    s = s.replace("non-fat", "nonfat").replace("non fat", "nonfat").replace("fat-free", "nonfat").replace("fat free", "nonfat")
    s = s.replace("sugar-free", "sugar free")
    out = []
    for w in re.findall(r"[a-z]+", s):
        if len(w) > 3 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def judging_function(ingredient, usda_match):
    try:
        iw = _words(ingredient)
        uw = _words(usda_match)
        if not iw or not uw:
            return 0.0
        iset, uset = set(iw), set(uw)

        # unstated qualifier cost: only tokens in USDA not stated by the ingredient
        added = 0.0
        for w in uset:
            c = _COST.get(w)
            if c and w not in iset:
                added += c
        # a percent-fat figure like 1% / 2% milkfat is also a qualifier
        if re.search(r"\d\s*%", str(usda_match or "")) and not re.search(r"\d\s*%", str(ingredient or "")):
            added += 1.0
        # qualifier mentioned in ingredient but dropped by USDA (reverse direction, mild)
        dropped = 0.0
        for w in iset:
            c = _COST.get(w)
            if c and w not in uset:
                dropped += 0.3 * c

        # relevance: fraction of content tokens of ingredient found in usda and vice versa
        icont = [w for w in iset if w not in _FILLER and w not in _COST]
        ucont = [w for w in uset if w not in _FILLER and w not in _COST]
        if not icont or not ucont:
            rel = 0.3
        else:
            inter = len(set(icont) & set(ucont))
            rel = inter / float(len(icont))
            prec = inter / float(len(ucont))
            rel = 0.7 * rel + 0.3 * prec

        # multiplicative: relevance gates, qualifiers decay
        score = 10.0 * (0.15 + 0.85 * rel) * math.exp(-0.45 * (added + dropped))
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
