import re

ALIASES = {
    'aubergine': 'eggplant', 'brinjal': 'eggplant',
    'garbanzo': 'chickpea', 'chickpeas': 'chickpea', 'chana': 'chickpea',
    'scallion': 'onion', 'scallions': 'onion', 'spring onion': 'onion',
    'courgette': 'zucchini', 'marrow': 'zucchini',
    'coriander': 'cilantro', 'rocket': 'arugula', 'arugula': 'arugula',
    'granada': 'pomegranate', 'mandarin': 'clementine', 'tangerine': 'clementine',
    'prawn': 'shrimp', 'prawns': 'shrimp', 'capsicum': 'pepper',
    'beetroot': 'beet', 'swede': 'rutabaga', 'maize': 'corn', 'sweetcorn': 'corn',
    'cilantro': 'cilantro', 'icing': 'powdered', 'caster': 'sugar',
    'mince': 'ground', 'minced': 'ground', 'biscuit': 'cookie',
    'chips': 'fries', 'aubergines': 'eggplant', 'zucchini': 'zucchini',
    'yoghurt': 'yogurt', 'curd': 'yogurt', 'fries': 'fries',
    'cornflour': 'cornstarch', 'garbanzos': 'chickpea', 'pinenut': 'pine',
    'squash': 'squash', 'pumpkin': 'pumpkin', 'cos': 'romaine', 'romaine': 'romaine',
    'filbert': 'hazelnut', 'hazelnuts': 'hazelnut', 'groundnut': 'peanut',
    'bream': 'seabream', 'seabass': 'bass',
}
STOP = set("""a an the of and or with without in on for to from as at by into
fresh raw cooked baked roasted fried boiled steamed grilled chopped sliced diced minced
shredded grated melted cubed crushed ground whole large small medium thin thick soaked
overnight thawed frozen canned dried drained peeled pitted halved ripe optional about
g kg ml oz lb lbs cup cups tbsp tsp piece pieces slice slices cut finely roughly
type style regular commercial prepared unsalted salted ns eaten fat nfs""".split())

def _sing(w):
    if len(w) > 4 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 4 and w.endswith('oes'):
        return w[:-2]
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss') and not w.endswith('us'):
        return w[:-1]
    return w

def _canon(text):
    out = []
    for w in re.findall(r"[a-z]+", text.lower()):
        w = _sing(w)
        w = ALIASES.get(w, w)
        w = _sing(w) if w not in ALIASES.values() else w
        out.append(w)
    return out

def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or '').lower()
        usda = str(usda_match or '').lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r'^\s*[\d.,/]+\s*(g|kg|ml|oz|lb)?\b', '', ing)
        paren_ing = ' '.join(re.findall(r'\(([^)]*)\)', ing))
        paren_usda = ' '.join(re.findall(r'\(([^)]*)\)', usda))
        ing_main = re.sub(r'\([^)]*\)', ' ', ing)
        usda_main = re.sub(r'\([^)]*\)', ' ', usda)
        ing_head_part = ing_main.split(',')[0]
        ing_state = ' '.join(ing_main.split(',')[1:])
        segs = [s for s in usda_main.split(',')]
        usda_primary = segs[0]
        usda_rest = ' '.join(segs[1:])

        ic = [w for w in _canon(ing_head_part) if w not in STOP and len(w) > 1]
        ic_all = set(ic) | set(w for w in _canon(paren_ing) if w not in STOP)
        up = [w for w in _canon(usda_primary) if w not in STOP and len(w) > 1]
        ur = [w for w in _canon(usda_rest + ' ' + paren_usda) if w not in STOP and len(w) > 1]
        uset = set(up) | set(ur)
        if not ic:
            return 0.0

        # Coverage of ingredient food words by USDA entry (aliases resolved)
        cov = sum(1 for w in ic if w in uset) / float(len(ic))
        # Head noun: last word of ingredient core should appear in USDA
        head = ic[-1]
        head_hit = 1.0 if head in uset else 0.0
        # Primary food match: ingredient words in USDA primary segment
        prim = sum(1 for w in ic if w in set(up)) / float(len(ic))
        # Extra USDA descriptors/food words not in ingredient (different food signals)
        extra_p = [w for w in up if w not in ic_all]
        extra_pen = len(extra_p) / float(max(1, len(up)))
        # Descriptor conflicts: USDA words that name a different variety/form
        conflict_words = set("""reduced low light nonfat lowfat soup stew entree pudding juice sauce powder
            butter oil flour candy cake cereal babyfood infant imitation substitute pork beef chicken
            kernel dry mix""".split())
        ing_set = set(_canon(ing_main + ' ' + paren_ing))
        conf = sum(1 for w in uset if w in conflict_words and w not in ing_set)
        # Reverse: ingredient has form words missing in USDA
        form_words = set("butter oil flour powder juice paste sauce milk cream seed".split())
        missing_form = sum(1 for w in ic if w in form_words and w not in uset)

        score = 4.0 * cov + 2.5 * head_hit + 2.0 * prim - 2.0 * extra_pen - 1.2 * min(conf, 3) - 2.0 * missing_form
        if cov == 0:
            score -= 2.0
        return float(max(-5.0, min(10.0, score)))
    except Exception:
        return 0.0
