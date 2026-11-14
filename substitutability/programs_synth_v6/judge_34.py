import re

_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "linseed": "flaxseed", "bison": "buffalo", "dehydrated": "dried", "granada": "pomegranate", "cos": "romaine", "uncooked": "raw", "poultry": "chicken", "purée": "puree", "para": "brazil", "concord": "grape"}
_COOK = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "grilled", "sauteed", "poached", "stewed"}
_SKIPW = set("fresh thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten lean free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american bing golden navel meat by product fat without salt added dry heat moist steak chop fillet heart tail neck wing breast thigh leg shank loin roast rib flat segment floret slice piece strip wedge chunk cube rind".split())
_TAXON = set("fish beef pork lamb veal chicken turkey duck nut cheese lettuce crustacean cereal fruit vegetable sausage game mollusk seed".split())
_FORMNOUN = set("oil juice flour jerky nectar soup stew candy cake pudding snack spice sandwich taco entree cookie syrup sauce frankfurter".split())
_DIET = set("lowfat nonfat reduced light diet lactose sodium decaffeinated skim sweetened salted flavored breaded battered seasoned prepared mix deli luncheon prepackaged imported beaked mountain zealand hawaii fortified hydrogenated strawberry peach chocolate oat vegetable".split())

def _w(s):
    out = []
    for t in re.findall(r"[a-zé]+", s):
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(_SYN.get(t, t))
    return out

def _nobrand(raw):
    return " ".join(t for t in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", t)) >= 3 and re.sub(r"[^A-Za-z]", "", t).isupper()))

def _events(ing, u, main, it, ut, segs):
    """Return list of (severity, label) mismatch events; fewer/lower = better."""
    ev = []
    iset, uset = set(it), set(ut)
    first = segs[0]
    ident = [t for t in main if t not in _SKIPW and t not in _COOK and t not in _DIET and t not in ("raw", "dried", "canned", "frozen", "smoked", "pickled", "fried", "ground", "whole", "seed")]
    if not ident:
        ident = [t for t in main if t not in _SKIPW] or main
    head = ident[-1]
    if head not in uset:
        ev.append((4.0, "head_missing"))
    for t in ident[:-1]:
        if t not in uset:
            ev.append((2.2, "modifier_missing"))
    # form noun introduced
    if (set(first) & _FORMNOUN) - iset:
        ev.append((3.2, "form_noun"))
    if (iset & _FORMNOUN) - uset:
        ev.append((2.0, "form_noun_lost"))
    # cooking: ingredient unmarked but USDA cooked (and no raw)
    ic = bool(iset & _COOK)
    uc = bool(uset & _COOK) or "heat" in uset
    if uc and not ic and "raw" not in uset:
        ev.append((2.2, "usda_cooked"))
    if ic and not uc:
        ev.append((1.6 if "raw" not in uset else 2.0, "ing_cooked"))
    # dried
    id_, ud_ = "dried" in iset, "dried" in uset
    if id_ != ud_:
        ev.append((2.4, "dried"))
    # pickled/smoked
    for st in ("pickled", "smoked", "canned"):
        if (st in iset) != (st in uset):
            ev.append((1.5 if st == "canned" else 2.2, st))
    if first and first[0] in ("frozen", "dried", "canned", "smoked") and first[0] not in iset:
        ev.append((2.5, "front_state"))
    # frying
    if ("fried" in iset) != ("fried" in uset) and not (ic and uc):
        ev.append((1.5, "fried"))
    # grind / shape
    if ("ground" in iset or "ground" in uset) and ("ground" in iset) != ("ground" in uset):
        ev.append((1.4, "ground"))
    # parts
    for t in ("leaf", "leave", "bone", "peel", "stem", "skin"):
        if (t in iset) != (t in uset):
            ev.append((2.0, "part_" + t))
    # descriptor words
    for t in (uset & _DIET) - iset:
        ev.append((1.1, "diet_" + t))
    for t in (iset & _DIET) - uset:
        ev.append((0.6, "ing_desc_" + t))
    # extra identity words in USDA first segment
    for t in first:
        if t not in iset and t not in _SKIPW and t not in _COOK and t not in _TAXON and t not in _DIET and t not in _FORMNOUN and t not in ("raw", "dried", "canned", "frozen", "smoked", "pickled", "fried", "ground", "whole", "seed") and t not in ident:
            ev.append((0.8, "extra_first"))
    if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
        ev.append((3.5, "brand"))
    return ev

def judging_function(ingredient, usda_match):
    try:
        raw_u = _nobrand(str(usda_match or ""))
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", raw_u.lower())
        main = _w(ing.split(",")[0])
        it = _w(ing)
        ut = _w(u)
        segs = [_w(s) for s in u.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        ev = _events(ing, u, main, it, ut, segs)
        total = sum(s for s, _ in ev)
        # saturating: the more events, diminishing marginal damage
        total = min(total, 6.0) + 0.3 * max(0.0, total - 6.0)
        return float(10.0 - total)
    except Exception:
        return 0.0
