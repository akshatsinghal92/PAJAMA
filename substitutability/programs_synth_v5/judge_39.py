import re

# Attribute lexicons. Each attribute extracted from both texts; a multiplicative
# compatibility probability is built from per-attribute agreement.
_ATTRS = {
    "state": ({"raw", "fresh"}, {"cooked", "boiled", "roasted", "baked", "fried", "grilled", "steamed", "toasted"},
              {"canned", "bottled", "jarred"}, {"frozen"}, {"dried", "dehydrated", "dry"}, {"pickled", "brined"}, {"smoked", "cured"}),
    "sweet": ({"sweetened", "sugared"}, {"unsweetened"}),
    "salt": ({"salted"}, {"unsalted", "salt-free"}),
    "fat": ({"whole", "full-fat"}, {"skim", "nonfat", "fat-free"}, {"lowfat", "low-fat", "reduced", "light", "lite", "2", "1"}),
    "color": ({"red"}, {"green"}, {"yellow"}, {"white"}, {"black"}, {"brown"}, {"purple"}, {"orange"}),
    "part": ({"breast"}, {"thigh"}, {"wing"}, {"drumstick", "leg"}, {"liver"}, {"shank"}, {"loin", "tenderloin"}, {"rib", "ribs"},
             {"leaf", "leave"}, {"seed"}, {"root"}, {"stem"}, {"bran"}, {"hearts", "heart"}, {"skin"}),
    "species": ({"beef"}, {"pork"}, {"lamb"}, {"chicken", "broiler", "fryer"}, {"turkey"}, {"veal"}, {"duck"}, {"goat"}, {"fish"}),
    "bean": ({"pinto"}, {"kidney"}, {"navy"}, {"lima"}, {"garbanzo", "chickpea"}, {"soy", "soybean"}),
    "form": ({"sauce"}, {"relish"}, {"oil"}, {"flour"}, {"starch"}, {"cracker", "crackers"}, {"cereal"}, {"juice"}, {"syrup"},
             {"patty"}, {"ball"}, {"souffle"}, {"paste"}, {"butter"}, {"powder"}, {"cream"}, {"milk"}, {"cheese"}, {"tea"}),
}
_NOISE = {"the", "a", "an", "and", "or", "of", "with", "in", "for", "to", "from", "only", "optional", "divided",
          "g", "kg", "oz", "ml", "nfs", "separable", "imported", "choice", "crude", "style", "mixed", "thawed",
          "trimmed", "visible", "fat", "lean", "chopped", "sliced", "diced", "minced", "peeled", "rinsed", "soaked",
          "overnight", "drained", "solids", "cos", "mature", "seeds"}


def _clean(s):
    s = (s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*[\d.]+\s*(g|kg|oz|ml|lb|mg)?\s+", " ", s)
    return s


def _words(s):
    ws = []
    for w in re.findall(r"[a-z\-]+", s):
        if len(w) > 3 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        ws.append(w)
    return ws


def _extract(words, attr):
    found = set()
    for i, grp in enumerate(_ATTRS[attr]):
        g = {x[:-1] if x.endswith("s") and len(x) > 3 else x for x in grp}
        if g & set(words):
            found.add(i)
    return found


def _head(s, pre_comma_last):
    seg = s.split(",")
    seg = seg[0] if seg else s
    ws = [w for w in _words(seg) if w not in _NOISE]
    if not ws:
        return None, set()
    return (ws[-1] if pre_comma_last else ws[0]), set(ws)


def judging_function(ingredient, usda_match):
    try:
        ic, uc = _clean(ingredient), _clean(usda_match)
        if not ic.strip() or not uc.strip():
            return 0.0
        iw, uw = _words(ic), _words(uc)
        # ingredient head: last noun of main clause; usda head: first word (primary food)
        ing_seg = ic.split(",")[0]
        ing_main = [w for w in _words(ing_seg) if w not in _NOISE]
        u_main_seg = [w for w in _words(uc.split(",")[0]) if w not in _NOISE]
        if not ing_main or not u_main_seg:
            return 0.5
        ing_heads = set(ing_main)
        u_heads = set(u_main_seg)

        # Head-noun agreement probability (multiplicative base).
        p = 1.0
        ing_last = ing_main[-1]
        # any of USDA primary-food words equal to the ingredient's final noun, or ingredient words
        if ing_last in uw or (u_heads & ing_heads):
            base_ok = True
        else:
            base_ok = False
        if not base_ok:
            # prefix/substring tolerance (e.g. pecan/pecans, radish/horseradish counts as weak)
            weak = any(len(a) > 4 and (a in b or b in a) for a in ing_heads for b in u_heads)
            p *= 0.35 if weak else 0.08
        # USDA primary food words unexplained by ingredient
        unexplained = [w for w in u_main_seg if w not in set(iw)]
        p *= 0.75 ** min(len(unexplained), 3)
        # Ingredient content words absent in USDA entirely
        missing = [w for w in ing_main if w not in set(uw)]
        p *= 0.8 ** min(len(missing), 3)

        # Attribute-wise compatibility.
        for attr in _ATTRS:
            a = _extract(iw, attr)
            b = _extract(uw, attr)
            if a and b:
                if a & b:
                    p *= 1.0
                else:
                    p *= 0.3 if attr in ("part", "species", "bean", "form", "color", "sweet") else 0.45
            elif a and not b:
                # ingredient specifies, USDA silent
                p *= 0.6 if attr in ("part", "form", "bean") else 0.9
            elif b and not a:
                # USDA specifies something the recipe didn't: tolerate raw/fat, punish form/part
                if attr in ("form", "part", "sweet"):
                    p *= 0.55
                elif attr == "state":
                    p *= 0.85 if b <= {0} else 0.7
                else:
                    p *= 0.9
        return round(10.0 * max(0.0, min(1.0, p)), 4)
    except Exception:
        return 0.0
