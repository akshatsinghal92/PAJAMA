import re

# broad culinary alias groups (regional / common / scientific names); first item is the canonical form
_GROUPS = """
eggplant|aubergine|brinjal|melongene
zucchini|courgette|marrow|summer squash
chickpea|garbanzo|chick pea|ceci|bengal gram
scallion|green onion|spring onion|salad onion
cilantro|coriander leaf|chinese parsley|coriander
arugula|rocket|roquette
bell pepper|capsicum|sweet pepper
rutabaga|swede|neep
beet|beetroot|red beet
corn|maize|sweet corn
cornstarch|corn flour|cornflour|maize starch
powdered sugar|confectioners sugar|icing sugar|confectioner's sugar
granulated sugar|caster sugar|castor sugar|superfine sugar|white sugar
molasses|treacle
shrimp|prawn
crayfish|crawfish|crawdad|langoustine
squid|calamari
cod|codfish
hazelnut|filbert|cobnut
pine nut|pinyon|pignoli|pinon|pine kernel
brazil nut|para nut|cream nut
flaxseed|linseed|flax seed
sesame|benne|gingelly
tangerine|clementine|mandarin|satsuma|mandarin orange
grapefruit|pomelo|pummelo
papaya|pawpaw|papaw
pomegranate|granada
cantaloupe|rockmelon|muskmelon
watermelon|water melon
potato|spud
sweet potato|kumara|yam
yam|name|igname
cassava|manioc|tapioca root|yuca|yucca
taro|dasheen|eddo|cocoyam
broadbean|fava bean|fava|faba bean|broad bean
lima bean|butter bean|butterbean
navy bean|haricot|pea bean
mung bean|green gram|moong
adzuki|azuki|red bean
edamame|green soybean
tofu|bean curd|soybean curd
fermented tofu|sufu|fuyu|tofu cheese
bison|buffalo
mutton|sheep
veal|calf
beef tongue|ox tongue|beef variety meat tongue
organ meat|variety meats|offal|innards|giblets
pork rind|chicharron|cracklings
ground beef|minced beef|hamburger
ground pork|minced pork
bacon|streaky bacon|rasher
cervelat|thuringer|summer sausage
frankfurter|hot dog|wiener|wienerwurst
half and half|half-and-half
heavy cream|double cream|whipping cream
light cream|single cream|coffee cream
sour cream|soured cream|creme fraiche
yogurt|yoghurt|yogourt
cottage cheese|farmer cheese
cream cheese|philadelphia
asadero|queso asadero|oaxaca cheese
queso fresco|fresh cheese
ricotta|requeson
parmesan|parmigiano|parmigiano reggiano
mayonnaise|mayo
catsup|ketchup|tomato ketchup
marinara|pasta sauce|spaghetti sauce|tomato sauce
applesauce|apple sauce|apple puree
vegetable shortening|crisco|shortening
canola oil|rapeseed oil
sunflower oil|safflower oil
cocoa|cacao|cocoa powder
cocoa butter|theobroma oil
cornmeal|polenta|maize meal
cream of wheat|farina|semolina cereal
rolled oats|oatmeal|porridge oats|old fashioned oats
all-purpose flour|plain flour|white flour
whole wheat flour|wholemeal flour|graham flour
glass noodle|cellophane noodle|bean thread|vermicelli bean|long rice
rice vermicelli|rice noodle|rice stick
ramen|instant noodle
tortilla|wrap|flatbread
chrysanthemum|shungiku|tong ho|garland chrysanthemum
bok choy|pak choi|chinese cabbage|pak choy
napa cabbage|chinese leaf|celery cabbage
daikon|mooli|white radish|chinese radish
rapini|broccoli raab|broccoli rabe
tamarind|indian date
jujube|chinese date|red date
java plum|jamun|jambolan|black plum
durian|king of fruits
lychee|litchi|lichee
cranberry|lingonberry
currant|ribes
marmalade|orange jam
tomatillo|husk tomato|mexican green tomato
jicama|yam bean|mexican turnip
nopal|nopales|prickly pear pad|cactus pad
okra|lady finger|ladies fingers|gumbo
collard|collards|collard greens
kale|borecole
spinach|palak
chard|swiss chard|silverbeet
romaine|cos|cos lettuce
iceberg|crisphead
endive|chicory|witloof
radicchio|italian chicory
fennel|finocchio|florence fennel
leek|poireau
ginger|ginger root
turmeric|curcuma|haldi
cardamom|elaichi
fenugreek|methi
paneer|indian cheese
ghee|clarified butter
jaggery|gur|panela|piloncillo
tahini|sesame paste
hummus|chickpea dip
miso|soybean paste
kefir|cultured milk
buttermilk|cultured buttermilk
""".strip().split("\n")

_CANON = {}
for _g in _GROUPS:
    _items = [x.strip() for x in _g.split("|") if x.strip()]
    _can = _items[0]
    for _x in _items:
        _CANON.setdefault(_x, set()).add(_can)
_PHRASES = sorted(_CANON, key=lambda x: -len(x))

_COOK = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "grilled", "sauteed", "poached", "stewed", "heat"}
_BENIGN = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american bing navel meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart seed delicious golden".split())
_FORMS = set("oil juice flour jerky nectar soup stew candy cake pudding snack spice sandwich taco entree cookie syrup sauce frankfurter loaf".split())
_DIETW = set("lowfat nonfat reduced light lite skim lactose sodium decaffeinated diet sweetened unsweetened flavored fortified hydrogenated".split())
_TAXA = set("fish beef pork lamb veal chicken turkey duck nut cheese lettuce crustacean cereal fruit vegetable sausage game mollusk".split())

def _stem(t):
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t

def _norm_text(s):
    s = " " + re.sub(r"[^a-zé\- ]", " ", s.lower()).replace("-", " ") + " "
    return re.sub(r"\s+", " ", s)

def _canon_set(text):
    """return (set of canonical ids found, remaining text with matched phrases removed)"""
    s = _norm_text(text)
    # light singularisation of whole phrase words
    found = set()
    for ph in _PHRASES:
        p = " " + ph.replace("-", " ") + " "
        for cand in (p, p[:-1] + "s "):
            if cand in s:
                found |= _CANON[ph]
                s = s.replace(cand, " ")
                break
    return found, s

def _nobrand(raw):
    return " ".join(t for t in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", t)) >= 3 and re.sub(r"[^A-Za-z]", "", t).isupper()))

def _toks(s):
    return [_stem(t) for t in re.findall(r"[a-zé]+", s)]

def judging_function(ingredient, usda_match):
    try:
        ing_raw = str(ingredient or "").lower()
        ing_raw = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing_raw)
        ing_main_raw = re.sub(r"\([^)]*\)", " ", ing_raw).split(",")[0]
        usda_nb = _nobrand(str(usda_match or ""))
        # USDA parentheses carry aliases: keep them for canonical lookup
        u_all = usda_nb.lower()
        i_ids, i_rest = _canon_set(ing_main_raw)
        i_ids_all, _ = _canon_set(ing_raw)
        u_ids, _u1 = _canon_set(u_all)
        u_first_ids, _u2 = _canon_set(re.sub(r"\([^)]*\)", " ", u_all).split(",")[0])
        u_clean = re.sub(r"\([^)]*\)", " ", u_all)
        main = _toks(ing_main_raw)
        it = _toks(re.sub(r"\([^)]*\)", " ", ing_raw))
        segs = [_toks(s) for s in u_clean.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        ut = [t for s in segs for t in s]
        iset, uset, first = set(it), set(ut), segs[0]
        core = [t for t in _toks(i_rest) if t not in _BENIGN and t not in _COOK and t not in _DIETW and t not in ("dried", "canned", "frozen", "smoked", "pickled", "fried", "ground", "powdered", "batter", "puree")]
        if not core:
            core = [t for t in main if t not in _BENIGN] or main
        # ---- alias channel
        score = 0.0
        alias_hit = bool(i_ids & u_ids)
        alias_conflict = bool(i_ids and u_first_ids and not (i_ids & u_ids))
        if alias_hit:
            score += 6.5
        elif alias_conflict:
            score -= 2.5
        # ---- lexical channel (reduced weight when alias resolved)
        wl = 1.2 if alias_hit else 4.5
        cov = sum(1 for t in core if t in uset) / float(len(core)) if core else 0.0
        if not alias_hit or core:
            score += wl * cov
        if core and core[-1] in uset:
            score += 1.4
        elif not alias_hit:
            score -= 1.2
        # ---- events
        if (set(first) & _FORMS) - iset:
            score -= 3.2
        if (iset & _FORMS) - uset:
            score -= 1.4
        if first and first[0] in ("frozen", "dried", "canned", "smoked") and first[0] not in iset:
            score -= 2.5
        ic, uc = bool(iset & _COOK), bool(uset & _COOK)
        if uc and not ic and "raw" not in uset:
            score -= 2.0
        if ic and not uc:
            score -= 1.3
        if ("dried" in iset and not ic) != ("dried" in uset and "from" not in uset):
            score -= 2.4
        for st, p in (("pickled", 2.4), ("smoked", 2.4), ("canned", 2.0)):
            if (st in iset) != (st in uset):
                score -= p
        if ("ground" in iset) != ("ground" in uset) or ("powdered" in iset) != ("powdered" in uset):
            score -= 1.2
        if {"leaf", "leave", "bone", "peel", "stem", "shell"} & (iset ^ uset):
            score -= 2.5
        score -= 0.9 * min(len((uset & _DIETW) - iset) + 0.5 * len((iset & _DIETW) - uset), 3.0)
        extra = [t for t in first if t not in iset and t not in _BENIGN and t not in _DIETW and t not in core and t not in _TAXA and t not in _COOK and t not in ("dried", "canned", "frozen", "smoked", "pickled", "fried", "ground")]
        if not alias_hit:
            score -= 0.55 * min(len(extra), 3)
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_all):
            score -= 3.5
        return float(score + 1.0)
    except Exception:
        return 0.0
