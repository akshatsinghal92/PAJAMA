import re

_STOP = set("of the and with in a an for from or to on style fresh whole cold warm warmed hot thawed frozen chopped diced sliced minced cubed crumbled strong large small medium optional serving serve skin eaten nfs".split())
_FLAVORS = set("chocolate vanilla strawberry blueberry blackberry raspberry cherry peach banana mango lemon lime orange caramel mocha coffee cinnamon maple honey peanut almond coconut mint apple".split())
_ALT = set("substitute imitation analog alternative vegan soy almond oat rice plant meatless dairy-free artificial flavored flavoured sweetened".split())
_COOK = set("cooked roasted baked boiled fried broiled grilled steamed canned stewed pan-broiled braised".split())
_RAW = set("raw fresh uncooked".split())
_PROC = set("entree patty patties formed chopped snacks mix dessert sauce soup babyfood".split())

def _clean(s):
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b", " ", s or "", flags=re.I)
    return s

def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w

def judging_function(ingredient, usda_match):
    try:
        ing_raw = _clean(str(ingredient))
        usda_raw = str(usda_match or "")
        # brand tokens: all-caps words (len>=3) in USDA text, not in ingredient
        brand = [t for t in re.findall(r"[A-Z][A-Z0-9'\-]{2,}", usda_raw)
                 if not re.fullmatch(r"\d+%?|NFS", t)]
        ing_low = ing_raw.lower()
        usda_low = usda_raw.lower()
        paren = re.findall(r"\(([^)]*)\)", ing_low)
        ing_main = re.sub(r"\([^)]*\)", " ", ing_low)
        ing_main = ing_main.split(",")[0] if len(ing_main.split(",")[0].strip()) > 2 else ing_main
        tok = lambda s: [_stem(w) for w in re.findall(r"[a-z]+", s) if w not in _STOP and len(w) > 1]
        it = tok(ing_main)
        ut_all = tok(re.sub(r"[A-Z][A-Z0-9'\-]{2,}", " ", usda_raw).lower())
        brand_l = set(_stem(b.lower()) for b in brand)
        if not it or not ut_all:
            return 0.0
        uset = set(ut_all)
        iset = set(it)
        # coverage of ingredient words by usda (brand words counted as weak coverage)
        cov = sum(1 for w in iset if w in uset or w in brand_l) / len(iset)
        # head: first usda segment
        first = tok(usda_low.split(",")[0])
        head_hit = 1.0 if (set(first) & iset) else 0.0
        # last ingredient word as head noun
        head_ing = it[-1]
        noun_hit = 1.0 if head_ing in uset or head_ing in brand_l else 0.0
        score = 4.0 * cov + 2.0 * head_hit + 2.0 * noun_hit
        # extra usda words not in ingredient (dilution)
        extra = [w for w in uset if w not in iset and w not in _COOK and w not in _RAW]
        score -= min(2.0, 0.25 * len(extra))
        # brand logic
        if brand:
            flav_u = (set(ut_all) | brand_l) & _FLAVORS
            flav_i = iset & _FLAVORS
            if flav_u - flav_i - {"honey"}:
                score -= 1.5
            elif flav_i and flav_i <= flav_u:
                score += 1.0   # branded entry carrying same flavour: standard example
            if cov >= 0.6:
                score += 0.7
        else:
            if "commercial" in usda_low or "regular" in usda_low or "plain" in usda_low:
                score += 0.5
        # alternative / plant-based base
        alt_u = set(re.findall(r"[a-z\-]+", usda_low)) & _ALT
        alt_i = set(re.findall(r"[a-z\-]+", ing_low)) & _ALT
        if alt_u - alt_i:
            score -= 3.0
        # state mismatch
        wu = set(re.findall(r"[a-z\-]+", usda_low))
        wi = set(re.findall(r"[a-z\-]+", ing_low))
        if (wu & _COOK) and not (wi & _COOK) and "canned" not in wi:
            score -= 1.5
        if (wi & _COOK) and (wu & _RAW) and not (wu & _COOK):
            score -= 1.0
        if (wu & _PROC) - wi:
            score -= 1.5
        if paren:
            score -= 0.5
        # lean/fat qualifiers conflicting
        if ("lowfat" in usda_low or "nonfat" in usda_low or "low sodium" in usda_low) and not re.search(r"low|non|skim|light", ing_low):
            score -= 1.5
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
