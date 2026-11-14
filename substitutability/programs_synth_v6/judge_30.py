import re

_FOODNOUNS = set("""beef pork lamb veal ham bacon sausage chicken turkey duck goose buffalo liver kidney tongue heart fish salmon tuna cod shrimp crab lobster cheese yogurt kefir milk cream butter egg
bean lentil pea chickpea tofu soy flour bread cracker tortilla cereal oat granola bran pasta noodle rice quinoa wheat corn nut almond walnut pecan hazelnut peanut seed sesame
lettuce spinach kale cabbage potato yam carrot beet radish onion garlic tomato pepper cucumber squash olive broccoli celery mushroom apple pear peach plum berry grape cherry orange lemon lime mango papaya banana coconut
oil sugar honey syrup salt vinegar sauce gravy chocolate cocoa vanilla cinnamon ginger herb spice marinara ketchup mustard mayonnaise vegetable fruit strawberry""".split())
_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "linseed": "flaxseed", "bison": "buffalo", "dehydrated": "dried", "granada": "pomegranate", "cos": "romaine", "uncooked": "raw", "poultry": "chicken", "plant": "vegan"}
_REMOVAL = set("lowfat nonfat reduced low light diet lactose decaffeinated sodium skim fat-free".split())
_PROCESS = set("breaded battered fried candied glazed marinated seasoned flavored sweetened fortified enriched hydrogenated prepared mix canned pickled smoked cured".split())
_STATE_OK = set("raw cooked boiled baked braised simmered broiled roasted steamed toasted dried frozen ground whole".split())
_NEUTRAL = set("fresh thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten without salt added lean free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american bing golden navel meat".split())

def _w(s):
    out = []
    for t in re.findall(r"[a-zé]+", s):
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(_SYN.get(t, t))
    return out

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        it = _w(ing)
        main = _w(ing.split(",")[0])
        ut = _w(u)
        uf = _w(u.split(",")[0])
        if not main or not ut:
            return 0.0
        iset, uset = set(it), set(ut)
        # food nouns on each side = ingredient composition
        fn_i = iset & _FOODNOUNS
        fn_u = uset & _FOODNOUNS
        added = fn_u - fn_i
        dropped = set(t for t in main if t in _FOODNOUNS) - fn_u
        # 'main' food noun of USDA (first segment) cannot be penalised as additions: only later foods
        first_fn = set(uf) & _FOODNOUNS
        added_tail = added - first_fn
        added_first = added & first_fn
        pen = 1.6 * len(added_first) + 0.9 * len(added_tail)
        pen += 2.0 * len(dropped)
        # processing markers
        proc_u = (uset & _PROCESS) - iset
        proc_i = (iset & _PROCESS) - uset
        pen += 1.3 * len(proc_u) + 1.0 * len(proc_i)
        # removals (lowfat etc) are processing too
        rem_u = (uset & _REMOVAL) - iset
        pen += 1.2 * min(len(rem_u), 2)
        # fat / sodium added statements
        if re.search(r"fat added|added fat|salt added|sugar added|added sugar|with added|made with|prepared with|prepared from", u) and not re.search(r"added|made with|prepared", ing):
            pen += 1.2
        # core identity
        core = [t for t in main if t not in _NEUTRAL and t not in _STATE_OK and t not in _PROCESS]
        if not core:
            core = [t for t in main if t not in _NEUTRAL] or main
        cov = sum(1 for t in core if t in uset) / float(len(core))
        head = 1.5 if core[-1] in uset else -1.0
        # state conflicts
        cookfam = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted"}
        si, su = iset & _STATE_OK, uset & _STATE_OK
        d = (si ^ su) - {"raw", "whole", "frozen"}
        if si & cookfam and su & cookfam:
            d = d - cookfam
        pen += 1.1 * len(d)
        if (set(uf) & {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "spice", "sandwich", "taco", "entree", "cookie"}) - iset:
            pen += 2.5
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            pen += 3.0
        return float(5.0 * cov + head - pen + 2.0)
    except Exception:
        return 0.0
