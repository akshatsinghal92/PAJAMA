import re

_CATS = {
    'dairy': "milk cheese cheddar mozzarella parmesan yogurt yoghurt butter cream custard whey ricotta cottage feta brie".split(),
    'poultry': "chicken turkey duck goose quail hen giblets wing drumstick".split(),
    'meat': "beef pork lamb veal ham bacon sausage steak mutton venison liver kidney kidneys salami meat brisket".split(),
    'fish': "fish salmon tuna cod shrimp prawn crab lobster trout sardine anchovy whitefish mackerel tilapia squid oyster clam".split(),
    'grain': "rice wheat oat oats flour bread pasta spaghetti noodle noodles cereal barley corn cornmeal rye quinoa couscous tortilla cracker".split(),
    'legume': "bean beans pea peas lentil lentils chickpea chickpeas soybean tofu pinto lupin".split(),
    'nutseed': "almond walnut pecan cashew peanut hazelnut pistachio seed seeds sesame sunflower pumpkin nuts nut".split(),
    'spice': "spice spices pepper cinnamon ginger cumin paprika turmeric oregano basil thyme parsley cilantro rosemary sage herb herbs garlic clove nutmeg dill mint".split(),
    'oil': "oil oils shortening lard margarine tallow fat".split(),
    'sweet': "sugar syrup honey molasses sweetener sweeteners candy caramel".split(),
    'condiment': "sauce ketchup mustard mayonnaise vinegar dressing salsa paste relish gravy marinade soy".split(),
    'fruit': "apple apples orange banana berry berries strawberry blueberry grape grapes lemon lime mango peach pear plum cherry melon watermelon clementine mandarin pineapple raisin fruit coconut avocado".split(),
    'veg': "tomato tomatoes onion carrot broccoli potato yam spinach lettuce cabbage celery cucumber artichoke artichokes squash zucchini mushroom mushrooms eggplant beet kale cauliflower vegetable vegetables pepper".split(),
    'beverage': "tea coffee juice beverage wine beer soda water".split(),
}
_W2C = {}
for _c, _ws in _CATS.items():
    for _w in _ws:
        _W2C.setdefault(_w, _c)

_FORM = "juice sauce spread salad substitute powder dried dehydrated canned frozen smoked cooked raw flavored mix dressing soup".split()
_STOP = set("the a an of and or with without in from for to style whole fresh raw cooked boiled drained added no salt nfs low fat free reduced g kg ml oz".split())


def _toks(s):
    s = re.sub(r'\([^)]*\)', ' ', s.lower())
    return re.findall(r"[a-z]+", s)


def _cats(tokens, weights=None):
    out = {}
    for i, t in enumerate(tokens):
        for v in (t, t[:-1] if t.endswith('s') else t, t[:-2] if t.endswith('es') else t):
            c = _W2C.get(v)
            if c:
                w = 1.0 if weights is None else weights[i]
                out[c] = out.get(c, 0) + w
                break
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r'^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\s+', '', (ingredient or '').lower())
        ing_main = ing.split(',')[0]
        parts = (usda_match or '').lower().split(',')
        u_head = parts[0]
        it = _toks(ing_main)
        ut = _toks(usda_match or '')
        uh = _toks(u_head)
        if not it or not ut:
            return 0.0
        # category profiles: last words of ingredient (head noun) weigh more
        iw = [1.0 + (1.0 if i >= len(it) - 2 else 0.0) for i in range(len(it))]
        ic = _cats(it, iw)
        uw = [2.0] * len(uh) + [0.5] * (len(ut) - len(uh))
        uc = _cats(ut, uw)
        if not ic or not uc:
            cat_score = 3.0
        else:
            itop = max(ic, key=ic.get)
            utop = max(uc, key=uc.get)
            if itop == utop:
                cat_score = 6.0
            elif itop in uc:
                cat_score = 4.0
            else:
                cat_score = 0.5
            # penalty when the USDA entry has a strong second category (e.g. sauce over fruit)
            shared = set(ic) & set(uc)
            cat_score += min(len(shared), 2) * 0.5
        # content overlap
        ci = set(t for t in it if t not in _STOP)
        cu = set(t for t in ut if t not in _STOP)
        stem = lambda w: w[:-1] if w.endswith('s') and len(w) > 3 else w
        ci = {stem(w) for w in ci}
        cu = {stem(w) for w in cu}
        ov = len(ci & cu) / float(len(ci) or 1)
        extra = len(cu - ci) / float(len(cu) or 1)
        score = cat_score + 3.0 * ov - 1.5 * extra
        # form mismatch penalty: form word on exactly one side
        for f in _FORM:
            if (f in ci) != (f in cu) and f in ("juice", "sauce", "spread", "salad", "substitute", "powder", "soup", "mix", "dressing"):
                score -= 1.5
        # head noun match
        if stem(it[-1]) in cu:
            score += 1.5
        return max(0.0, min(15.0, score))
    except Exception:
        return 0.0
