import re

# Concept table: each concept lists surface forms (single words or phrases) that name the same culinary item.
_CONCEPTS = {
    "tangerine": ["clementine", "mandarin", "tangerine", "satsuma"],
    "hazelnut": ["hazelnut", "filbert", "cobnut"],
    "pinenut": ["pine nut", "pinyon", "pinon", "pignoli", "pine kernel"],
    "flax": ["flaxseed", "linseed", "flax"],
    "brazilnut": ["brazil nut", "para nut"],
    "broadbean": ["broadbean", "fava", "faba", "broad bean"],
    "chickpea": ["chickpea", "garbanzo"],
    "buffalo": ["bison", "buffalo"],
    "crayfish": ["crayfish", "crawfish", "crawdad"],
    "shrimp": ["shrimp", "prawn"],
    "pomegranate": ["pomegranate", "granada"],
    "romaine": ["romaine", "cos lettuce", "cos"],
    "applesauce": ["applesauce", "apple puree", "apple sauce", "apple purée"],
    "cornflakes": ["corn flakes", "maize flakes"],
    "cellophane": ["glass noodle", "cellophane noodle", "bean thread", "long rice"],
    "halfandhalf": ["half and half", "equal parts milk and cream", "half & half"],
    "vegan_mayo": ["vegan mayonnaise", "plant-based mayonnaise", "mayonnaise made with tofu", "eggless mayonnaise"],
    "thuringer": ["cervelat", "thuringer", "summer sausage"],
    "tamarind": ["tamarind", "indian date"],
    "javaplum": ["jamun", "java plum", "java-plum", "jambolan"],
    "queso": ["asadero", "queso asadero"],
    "mungtofu": ["sufu", "fermented tofu", "fuyu"],
    "cocoabutter": ["cocoa butter"],
    "chrysanthemum": ["shungiku", "chrysanthemum", "garland chrysanthemum"],
    "poultry": ["poultry", "chicken"],
}
_SURF = []
for _c, _fs in _CONCEPTS.items():
    for _f in _fs:
        _SURF.append((_f, _c))
_SURF.sort(key=lambda x: -len(x[0]))

_COOK = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "grilled", "sauteed", "poached", "stewed"}
_SKIPW = set("fresh thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten lean free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american bing golden navel meat by product fat without salt added dry heat moist steak chop fillet heart tail neck wing breast thigh leg shank loin roast rib flat segment floret slice piece strip wedge chunk cube rind kernel".split())
_DIETW = {"lowfat": 1.4, "nonfat": 1.4, "reduced": 1.4, "light": 1.0, "diet": 1.0, "lactose": 1.3, "sodium": 1.0, "decaffeinated": 1.3, "skim": 1.4, "sweetened": 1.4, "flavored": 1.2, "breaded": 2.0, "battered": 2.0, "seasoned": 1.5, "prepared": 1.0, "mix": 1.4, "deli": 1.2, "luncheon": 1.2, "prepackaged": 1.0, "beaked": 1.5, "mountain": 1.5, "hawaii": 1.2, "fortified": 0.6, "hydrogenated": 1.4, "oat": 1.0, "vegetable": 1.0, "strawberry": 1.4, "peach": 1.2, "chocolate": 1.2}
_FORMNOUN = set("oil juice flour jerky nectar soup stew candy cake pudding snack spice sandwich taco entree cookie syrup sauce frankfurter".split())

def _tag(s):
    """replace known surface forms by concept tokens like 'c_flax'"""
    s = " " + re.sub(r"[^a-zé&\- ]", " ", s.lower()) + " "
    found = set()
    for f, c in _SURF:
        pat = " " + f + " "
        pat2 = " " + f + "s "
        if pat in s or pat2 in s:
            found.add(c)
            s = s.replace(pat2, " ").replace(pat, " ")
    return s, found

def _w(s):
    out = []
    for t in re.findall(r"[a-zé]+", s):
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out

def _nobrand(raw):
    return " ".join(t for t in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", t)) >= 3 and re.sub(r"[^A-Za-z]", "", t).isupper()))

def judging_function(ingredient, usda_match):
    try:
        raw_u = _nobrand(str(usda_match or ""))
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", raw_u.lower())
        i_rest, i_conc = _tag(ing.split(",")[0])
        _, i_conc_all = _tag(ing)
        u_rest, u_conc = _tag(u)
        main = _w(i_rest)
        ut = _w(u_rest)
        first = _w(_tag(u.split(",")[0])[0])
        iall = set(_w(_tag(ing)[0]))
        uset = set(ut)
        if not main and not i_conc:
            return 0.0
        score = 0.0
        # concept channel
        if i_conc:
            score += 6.0 if (i_conc & u_conc) else -1.0
        core = [t for t in main if t not in _SKIPW and t not in _COOK and t not in _DIETW and t not in ("raw", "dried", "canned", "frozen", "smoked", "pickled", "fried", "ground", "whole", "seed")]
        if core:
            cov = sum(1 for t in core if t in uset) / float(len(core))
            w = 4.5 if not i_conc else 1.5
            score += w * cov
            score += 1.3 if core[-1] in uset else (-1.5 if not i_conc else 0.0)
        elif not i_conc:
            score -= 1.0
        # events
        if (set(first) & _FORMNOUN) - iall:
            score -= 3.0
        if (iall & _FORMNOUN) - uset:
            score -= 1.5
        ic = bool(iall & _COOK)
        uc = bool(uset & _COOK) or "heat" in uset
        if uc and not ic and "raw" not in uset:
            score -= 2.0
        if ic and not uc:
            score -= 1.4
        for st, pen in (("dried", 2.2), ("pickled", 2.0), ("smoked", 2.0), ("canned", 1.2), ("fried", 1.3)):
            if (st in iall) != (st in uset):
                if st == "fried" and ic and uc:
                    continue
                score -= pen
        if first and first[0] in ("frozen", "dried", "canned", "smoked") and first[0] not in iall:
            score -= 2.3
        for t in ("leaf", "leave", "bone", "peel", "stem", "skin"):
            if (t in iall) != (t in uset):
                score -= 1.8
        if "ground" in iall != ("ground" in uset):
            score -= 1.3
        d = sum(c for t, c in _DIETW.items() if t in uset and t not in iall) + 0.5 * sum(c for t, c in _DIETW.items() if t in iall and t not in uset)
        score -= min(d, 3.5)
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.5
        return float(score + 2.0)
    except Exception:
        return 0.0
