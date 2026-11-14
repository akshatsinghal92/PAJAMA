import re
import math

_CATS = {
    'dairy': 'milk cream cheese butter yogurt yoghurt whey curd kefir queso paneer ricotta mozzarella cheddar parmesan custard ghee buttermilk',
    'poultry': 'chicken turkey duck goose poultry hen quail giblets',
    'redmeat': 'beef pork lamb veal mutton ham bacon sausage steak sirloin chuck liver venison bison salami cervelat roast ribs brisket',
    'seafood': 'fish salmon tuna cod herring pollock shrimp crab lobster crayfish oyster clam squid trout tilapia sardine anchovy mackerel scallop',
    'grain': 'rice wheat flour bread pasta oat oats barley rye corn cornmeal noodle spaghetti cereal quinoa amaranth couscous cracker crackers bagel tortilla starch semolina',
    'legume': 'bean beans lentil lentils chickpea chickpeas pea peas soy tofu tempeh legume lupin',
    'nutseed': 'almond pecan pecans walnut cashew peanut peanuts pistachio hazelnut flaxseed flax sesame sunflower chia seed seeds nut nuts',
    'produce': 'squash tomato potato onion carrot spinach lettuce escarole cabbage broccoli apple banana orange lemon berry berries pepper cucumber celery mushroom garlic kale zucchini grape mango fruit vegetable asparagus eggplant pumpkin',
    'spice': 'spice spices ginger cinnamon cumin paprika oregano basil thyme pepper turmeric clove nutmeg herb herbs parsley cilantro dill rosemary sage vanilla',
    'oil': 'oil oils lard shortening margarine tallow fat',
    'sweet': 'sugar honey syrup molasses sweetener sucralose stevia agave candy chocolate cocoa',
    'condiment': 'sauce dressing ketchup mustard mayonnaise vinegar salsa gravy paste condiment marinade',
    'dish': 'soup entree dinner meal sandwich pizza burrito casserole stew mix frozen',
    'beverage': 'tea coffee juice beverage wine beer soda water',
    'egg': 'egg eggs yolk',
}
_W = {}
for _c, _s in _CATS.items():
    for _w in _s.split():
        _W.setdefault(_w, []).append(_c)

_PREP = set('chopped diced sliced minced shredded grated crushed fresh whole large small medium optional divided cooked raw toasted trimmed thawed drained packed finely roughly cut of and or the a with from for to into plus more lean'.split())

def _toks(s):
    s = s.lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    return re.findall(r'[a-z]+', s)

def _norm(w):
    if len(w) > 3 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w

def _catvec(tokens, weights):
    v = {}
    for t, wt in zip(tokens, weights):
        for key in (t, _norm(t)):
            if key in _W:
                for c in _W[key]:
                    v[c] = v.get(c, 0.0) + wt
                break
    return v

def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or '')
        usda = str(usda_match or '')
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r'^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b', ' ', ing.lower())
        main_ing = ing.split(',')[0]
        it = _toks(main_ing)
        ut_full = _toks(usda)
        usda_head = usda.split(',')[0]
        ut = _toks(usda_head)
        ut_rest = _toks(','.join(usda.split(',')[1:]))
        if not it or not ut_full:
            return 0.0
        # weights: later words in ingredient (head noun) matter more; USDA first words matter more
        iw = [0.5 + i / max(1, len(it) - 1) if len(it) > 1 else 1.0 for i in range(len(it))]
        uw = [1.5] * len(ut) + [0.6] * len(ut_rest)
        ut_all = ut + ut_rest
        iv = _catvec(it, iw)
        uv = _catvec(ut_all, uw)
        dot = sum(iv[c] * uv.get(c, 0) for c in iv)
        ni = math.sqrt(sum(x * x for x in iv.values()))
        nu = math.sqrt(sum(x * x for x in uv.values()))
        if ni == 0 or nu == 0:
            cat = 0.4  # unknown category: neutral
        else:
            cat = dot / (ni * nu)
        # core word overlap
        ic = set(_norm(t) for t in it if t not in _PREP)
        uc = set(_norm(t) for t in ut_all if t not in _PREP)
        ov = len(ic & uc) / max(1, len(ic)) if ic else 0.0
        uhead_cov = len(ic & set(_norm(t) for t in ut)) / max(1, len(set(_norm(t) for t in ut) - set(_PREP)))
        score = 4.0 * cat + 3.5 * ov + 1.0 * min(1.0, uhead_cov)
        # penalties: processed/dish USDA entry for simple ingredient
        dishy = set(['soup', 'entree', 'dinner', 'sandwich', 'crackers', 'cracker', 'mix', 'sauce', 'dressing'])
        if (set(ut) & dishy) and not (set(it) & dishy):
            score -= 2.0
        # extra USDA words not in the ingredient dilute match
        extra = len(uc - ic)
        score -= 0.25 * min(extra, 6)
        # form mismatches
        forms = [('ground', 'whole'), ('butter', 'nut'), ('flour', 'whole')]
        for a in ('ground', 'powder', 'butter', 'flour', 'juice', 'dried', 'canned', 'frozen'):
            if (a in ut_full) != (a in it):
                score -= 0.5
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
