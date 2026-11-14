import re
import math

CATS = {
    "dairy": "milk cream cheese yogurt yoghurt butter buttermilk kefir whey curd ghee custard cheddar mozzarella parmesan ricotta feta",
    "poultry": "chicken turkey duck goose quail hen poultry",
    "redmeat": "beef pork lamb veal mutton ham bacon sausage steak venison goat bison rabbit salami chorizo meat",
    "seafood": "fish salmon tuna cod shrimp prawn crab lobster crayfish swordfish tilapia trout oyster clam mussel squid scallop anchovy sardine mackerel crustaceans mollusks seafood eel",
    "grain": "bread rice wheat flour oat oats barley corn cornmeal pasta noodle noodles cereal rye quinoa couscous gnocchi cracker tortilla bagel bun roll dough millet bulgur flakes",
    "legume": "bean beans lentil lentils chickpea chickpeas pea peas soy tofu tempeh edamame legumes hummus",
    "nut": "nut nuts almond almonds walnut walnuts pecan cashew pistachio hazelnut hazelnuts peanut peanuts brazil macadamia seed seeds sesame flaxseed sunflower chia pumpkin",
    "spice": "spice spices pepper cinnamon cumin paprika turmeric ginger oregano basil thyme rosemary parsley cilantro dill mint sage clove nutmeg cardamom coriander herb herbs saffron vanilla garlic powder",
    "oil": "oil oils lard shortening margarine fat tallow",
    "sweetener": "sugar honey syrup molasses sweetener stevia candy jam jelly chocolate cocoa",
    "condiment": "sauce ketchup mustard mayonnaise vinegar dressing salsa condiment relish paste miso pickle pickles marinade broth stock soup gravy",
    "fruit": "apple banana orange lemon lime berry berries blackberry strawberry blueberry raspberry grape grapes mango pineapple peach pear plum cherry melon watermelon pomegranate durian fig date dates apricot kiwi papaya avocado fruit coconut cranberry juice",
    "veg": "tomato potato onion carrot celery lettuce spinach cabbage broccoli cauliflower cucumber zucchini squash chard kale mushroom mushrooms eggplant beet radish turnip leek pepper peppers asparagus vegetable vegetables cassava yam",
    "egg": "egg eggs yolk",
}
WORD2CAT = {}
for c, ws in CATS.items():
    for w in ws.split():
        WORD2CAT.setdefault(w, []).append(c)

STOP = set("of the and with in for or a an to from raw fresh cooked dried frozen canned ready serve serving optional ground whole chopped sliced diced minced large small medium thawed boneless lean only separable fat skin not eaten all varieties commercially prepared plain".split())


def _tokens(s):
    s = s.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|oz|lb|ml|l)\b", " ", s)
    return re.findall(r"[a-z]+", s)


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w


def _catvec(tokens, head_weight):
    v = {}
    n = len(tokens)
    for i, t in enumerate(tokens):
        for w in (t, _stem(t)):
            if w in WORD2CAT:
                wt = 1.0 + (head_weight if i == 0 else 0.0)
                for c in WORD2CAT[w]:
                    v[c] = v.get(c, 0.0) + wt
                break
    return v


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        it = _tokens(re.split(",", ing)[0] if ing.count(",") and len(_tokens(re.split(",", ing)[0])) else ing)
        ut_full = _tokens(usda)
        # USDA primary food is the first comma segment
        first = _tokens(usda.split(",")[0])
        ut = ut_full
        if not it or not ut:
            return 0.0
        # ingredient head noun = last content word; usda head = first segment
        ihead = [t for t in it if t not in STOP]
        iv = _catvec(ihead[-2:] if ihead else it, 0.0)
        for t in ihead[-1:]:
            for c in WORD2CAT.get(t, []) + WORD2CAT.get(_stem(t), []):
                iv[c] = iv.get(c, 0.0) + 1.5
        uv = _catvec(first, 1.5)
        for c, w in _catvec(ut_full[len(first):], 0.0).items():
            uv[c] = uv.get(c, 0.0) + 0.3 * w
        if not iv or not uv:
            cat_score = 0.4
        else:
            dot = sum(iv[c] * uv.get(c, 0.0) for c in iv)
            ni = math.sqrt(sum(x * x for x in iv.values()))
            nu = math.sqrt(sum(x * x for x in uv.values()))
            cat_score = dot / (ni * nu) if ni and nu else 0.4
        # top category agreement
        if iv and uv:
            ti = max(iv, key=iv.get)
            tu = max(uv, key=uv.get)
            top = 1.0 if ti == tu else 0.0
        else:
            top = 0.4
        # content token overlap (stems)
        ic = set(_stem(t) for t in it if t not in STOP)
        uc = set(_stem(t) for t in ut_full if t not in STOP)
        if ic and uc:
            ov = len(ic & uc) / float(len(ic))
            extra = len(uc - ic) / float(len(uc))
        else:
            ov, extra = 0.0, 0.0
        score = 4.0 * cat_score + 2.5 * top + 3.0 * ov - 1.5 * extra
        return max(0.0, min(10.0, score + 1.0))
    except Exception:
        return 0.0
