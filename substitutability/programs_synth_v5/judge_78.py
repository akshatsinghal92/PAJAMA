import re

_FAMILIES = {
    "poultry": "turkey chicken duck goose quail hen poultry",
    "redmeat": "beef lamb pork veal mutton goat venison bison ham bacon",
    "offal": "liver kidney tongue giblet heart tripe brain",
    "sausage": "sausage frankfurter hotdog salami bologna",
    "fish": "salmon tuna cod bass trout fish shrimp crab lobster tilapia",
    "dairy": "milk cheese yogurt cream butter whey kefir",
    "egg": "egg",
    "legume": "bean pea lentil chickpea blackeye soybean tofu",
    "tuber": "potato yam cassava taro",
    "fruit": "apple cherry kumquat papaya orange lemon lime grape berry banana mango peach pear plum fig date coconut",
    "veg": "chrysanthemum turnip spinach kale carrot onion garlic tomato pepper cabbage lettuce squash pumpkin celery olive",
    "grain": "rice corn wheat oat barley flour meal bran maize",
    "nut": "almond walnut pecan peanut cashew pistachio nut",
    "oil": "oil",
    "spice": "ginger cinnamon cumin paprika spice turmeric",
    "bev": "beverage drink juice tea coffee soda",
}
_WORD2FAM = {}
for _f, _ws in _FAMILIES.items():
    for _w in _ws.split():
        _WORD2FAM.setdefault(_w, _f)

# product-form markers: each marks a distinct manufactured food type
_FORMS = {
    "sauce": "sauce", "pie": "pie", "filling": "pie", "chip": "chip", "bar": "bar",
    "tapenade": "spread", "spread": "spread", "patty": "patty", "nugget": "patty",
    "soup": "soup", "powder": "powder", "starch": "starch", "bran": "bran", "meal": "meal",
    "flour": "flour", "zest": "zest", "peel": "zest", "bone": "bone", "juice": "juice",
    "cream": "cream", "butter": "butter", "milk": "milk", "oil": "oil", "paste": "paste",
    "leaf": "leaf", "green": "leaf", "giblet": "giblet", "liver": "liver", "kidney": "kidney",
}
_NEUTRAL = set("raw cooked fresh frozen dried dry nfs unprepared whole the and or of with".split())


def _n(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
        return w[:-1]
    return w


def _fams(words):
    out = []
    for w in words:
        f = _WORD2FAM.get(w)
        if f:
            out.append(f)
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"\([^)]*\)", " ", ing).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        usda = re.sub(r"\([^)]*\)", " ", usda)
        iw = [_n(w) for w in re.findall(r"[a-z]+", ing)]
        uparts = usda.split(",")
        up = [_n(w) for w in re.findall(r"[a-z]+", uparts[0])]
        ua = [_n(w) for w in re.findall(r"[a-z]+", usda)]
        if not iw or not ua:
            return 0.0

        # 1) food-family agreement (what kind of food is it)
        fi = _fams(iw)
        fu_p = _fams(up)
        fu_a = _fams(ua)
        score = 5.0
        if fi and fu_p:
            if fi[-1] == fu_p[0] or fi[-1] in fu_p:
                score += 2.0
            elif set(fi) & set(fu_a):
                score += 0.0
            else:
                score -= 4.0
        elif fi and not fu_a:
            score -= 1.0
        # Both families mentioned in ingredient but one lost
        for f in set(fi):
            if f not in fu_a:
                score -= 1.5

        # 2) product-form agreement: forms in USDA primary but not in ingredient = new product
        form_i = {_FORMS[w] for w in iw if w in _FORMS}
        form_u = {_FORMS[w] for w in up if w in _FORMS}
        form_all = {_FORMS[w] for w in ua if w in _FORMS}
        score -= 2.0 * len(form_u - form_i)
        score -= 2.0 * len(form_i - form_all)
        score += 1.0 * len(form_i & form_all)

        # 3) head-noun identity: last ingredient content word vs USDA primary
        content_i = [w for w in iw if w not in _NEUTRAL]
        if content_i:
            h = content_i[-1]
            if h in up:
                score += 1.5
            elif h in ua:
                score += 0.5
            else:
                score -= 1.5
            share = len(set(content_i) & set(ua)) / len(set(content_i))
            score += 2.0 * share
        # 4) the primary segment should not be longer than ingredient by a lot
        extra = [w for w in up if w not in iw and w not in _NEUTRAL and w not in _FORMS]
        if len(extra) >= 2:
            score -= 1.0 * (len(extra) - 1)
        if "nfs" in ua:
            score -= 1.0
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
