import re

_ALIAS = {"filbert": "hazelnut", "clementine": "tangerine", "mandarin": "tangerine", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "pinon": "pine", "para": "brazil", "linseed": "flaxseed", "bison": "buffalo", "dehydrated": "dried", "uncooked": "raw", "unroasted": "raw", "plant": "vegan", "cos": "romaine", "granada": "pomegranate"}
_DROP = set("raw nfs regular plain type separable lean fat only trimmed choice select grade all meat mature whole variety flavor other than not eaten fresh drained of and or the a with in for from to into without salt added free range farmed wild mixed species chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot steak fillet seed segment floret slice piece strong brewed round bone toasted".split())
_TAXON = set("fish beef pork lamb veal chicken turkey duck nut cheese lettuce crustacean cereal fruit vegetable sausage game variety mollusk".split())
_FORM = {"oil", "juice", "syrup", "sauce", "soup", "pudding", "cookie", "cake", "candy", "jerky", "flour", "snack", "taco", "sandwich", "entree", "spice", "stew", "nectar"}
_MOD = set("lowfat nonfat reduced low light diet sodium decaffeinated unsweetened lactose vegetable oat imported hydrogenated fortified prepackaged deli luncheon crumble patty breaded battered beaked mountain zealand hawaii cooked fried dried canned smoked pickled sweetened ground".split())

def _t(s):
    r = []
    for w in re.findall(r"[a-zé]+", s):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        r.append(_ALIAS.get(w, w))
    return r

def _lcs(a, b):
    n, m = len(a), len(b)
    if not n or not m:
        return 0
    prev = [0] * (m + 1)
    for i in range(1, n + 1):
        cur = [0] * (m + 1)
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
            else:
                cur[j] = max(prev[j], cur[j - 1])
        prev = cur
    return prev[m]

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        main = [w for w in _t(ing.split(",")[0]) if w not in _DROP]
        tail = _t(",".join(ing.split(",")[1:]))
        usegs = [[w for w in _t(s) if w not in _DROP] for s in u.split(",") if s.strip()]
        if not main or not usegs:
            return 0.0
        # two orderings of USDA tokens: as-written and hierarchy reversed (generic first -> generic last)
        fwd = [w for s in usegs for w in s]
        rev = [w for s in reversed(usegs) for w in s]
        best_l = max(_lcs(main, fwd), _lcs(main, rev))
        # also segment-local: best single segment
        seg_l = max(_lcs(main, s) for s in usegs)
        l = max(best_l, seg_l)
        rec = l / float(len(main))
        # coverage as set (order-free)
        uset = set(fwd)
        setcov = sum(1 for w in main if w in uset) / float(len(main))
        # specificity gap: USDA content words beyond the ingredient's, excluding taxonomy words in segment 0
        first = usegs[0]
        iset = set(main) | set(tail)
        extra_first = [w for w in first if w not in iset and w not in _TAXON]
        extra_tail = [w for w in fwd[len(first):] if w not in iset and w not in _TAXON]
        spec_pen = 0.9 * len(extra_first) + 0.25 * min(len(extra_tail), 4)
        # forms and modifiers
        form_pen = 3.0 if (set(first) & _FORM) - iset else 0.0
        mod_pen = 0.0
        for w in set(fwd) & _MOD:
            if w not in iset:
                mod_pen += 0.9
        for w in iset & _MOD:
            if w not in uset and w not in ("ground", "cooked"):
                mod_pen += 0.6
        # head noun check
        head_ok = 1.5 if main[-1] in uset else -1.0
        score = 4.0 * rec + 2.5 * setcov + head_ok - spec_pen - form_pen - min(mod_pen, 3.0)
        # dropped qualifier: ingredient has 2+ core words but USDA covers only head
        if len(main) >= 2 and setcov < 0.6:
            score -= 1.0
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
