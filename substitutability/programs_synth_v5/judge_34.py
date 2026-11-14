import re

ROLES = {
    'fat': {'oil', 'butter', 'lard', 'shortening', 'margarine', 'ghee', 'tallow', 'fat'},
    'dairy': {'milk', 'cream', 'cheese', 'yogurt', 'yoghurt', 'curd', 'whey'},
    'meat': {'beef', 'pork', 'lamb', 'veal', 'chicken', 'turkey', 'duck', 'ham', 'bacon', 'sausage', 'meat', 'goose', 'venison', 'game'},
    'seafood': {'fish', 'shrimp', 'crab', 'crayfish', 'crawfish', 'crustaceans', 'salmon', 'tuna', 'mollusks', 'oyster', 'clam', 'squid'},
    'nut': {'nut', 'nuts', 'almond', 'almonds', 'pecan', 'pecans', 'walnut', 'walnuts', 'peanut', 'cashew', 'pistachio', 'seeds', 'seed', 'flaxseed', 'sesame'},
    'fruit': {'apple', 'apples', 'orange', 'oranges', 'lemon', 'lime', 'berries', 'berry', 'grape', 'grapes', 'banana', 'tangerines', 'kumquats', 'peach', 'pear', 'cherries', 'plum', 'mango'},
    'veg': {'onion', 'onions', 'carrot', 'carrots', 'tomato', 'tomatoes', 'pepper', 'peppers', 'cabbage', 'spinach', 'lettuce', 'potato', 'potatoes', 'seaweed', 'mushroom', 'mushrooms', 'beans', 'peas'},
    'grain': {'flour', 'bread', 'rice', 'wheat', 'oats', 'corn', 'cornmeal', 'pasta', 'crumbs', 'cereal', 'noodles', 'cornbread'},
    'sweet': {'sugar', 'honey', 'syrup', 'molasses', 'sweetener'},
    'drink': {'tea', 'coffee', 'juice', 'wine', 'beer', 'water', 'beverage'},
    'spice': {'spices', 'spice', 'ginger', 'garlic', 'cinnamon', 'herbs', 'basil', 'oregano', 'paprika', 'salt', 'vinegar'},
    'soy': {'tofu', 'soy', 'tempeh', 'miso', 'natto'},
}
WORD2ROLE = {}
for r, ws in ROLES.items():
    for w in ws:
        WORD2ROLE[w] = r

# state/form modifiers that change texture/behaviour in a dish
FORMS = {
    'dry': {'dried', 'dry', 'dehydrated', 'powdered', 'powder', 'instant', 'freeze-dried'},
    'zest': {'zest', 'peel', 'rind'},
    'toasted': {'toasted', 'roasted', 'dry-roasted', 'smoked'},
    'cooked': {'cooked', 'boiled', 'baked', 'fried', 'braised', 'steamed', 'grilled'},
    'canned': {'canned', 'bottled', 'jarred'},
    'frozen': {'frozen'},
    'raw': {'raw', 'fresh', 'uncooked'},
    'lean': {'lean', 'lowfat', 'low-fat', 'nonfat', 'fat-free', 'reduced', 'skim', 'diet', 'light'},
    'ground': {'ground', 'minced', 'grated', 'crumbs', 'crumbled', 'meal'},
    'mix': {'mix', 'mixed', 'prepared', 'imitation', 'substitute', 'flavored', 'sweetened', 'unsweetened', 'lactose'},
}
W2F = {}
for f, ws in FORMS.items():
    for w in ws:
        W2F[w] = f
STOP = {'and', 'or', 'of', 'the', 'a', 'with', 'in', 'for', 'to', 'from', 'only', 'not', 'optional', 'g', 'kg', 'oz', 'ml', 'cup', 'tbsp', 'tsp', 'type', 'includes', 'cut', 'sliced', 'chopped', 'cubed', 'diced', 'thawed', 'drained', 'whole', 'all', 'separable', 'choice', 'new', 'zealand', 'imported', 'by-products', 'variety', 'products'}

def _stem(w):
    for suf in ('ies', 'es', 's'):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w

def _toks(s):
    s = re.sub(r'^\s*\d+(\.\d+)?\s*(g|kg|oz|ml|lb)?\b', ' ', s.lower())
    s = re.sub(r'[^a-z\- ]', ' ', s.replace(',', ' , '))
    return s.split()

def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or '')
        usd = str(usda_match or '')
        if not ing.strip() or not usd.strip():
            return 0.0
        it = [t for t in _toks(ing)]
        ut = [t for t in _toks(usd)]
        # primary food of usda = tokens before first comma
        primary = _toks(usd.split(',')[0])
        icore = [_stem(t) for t in it if t not in STOP and t not in W2F]
        ucore = [_stem(t) for t in ut if t not in STOP and t not in W2F and t != ',']
        pcore = [_stem(t) for t in primary if t not in STOP and t not in W2F]
        iset, uset, pset = set(icore), set(ucore), set(pcore)

        # 1. role compatibility
        iroles = {WORD2ROLE[w] for w in it if w in WORD2ROLE} | {WORD2ROLE[w] for w in icore if w in WORD2ROLE}
        proles = {WORD2ROLE[w] for w in ut if w in WORD2ROLE} | {WORD2ROLE[w] for w in ucore if w in WORD2ROLE}
        if iroles and proles:
            role = 1.0 if iroles & proles else -0.2
        else:
            role = 0.4

        # 2. content coverage: how much of ingredient's identity is in usda
        if iset:
            cover = len(iset & uset) / float(len(iset))
        else:
            cover = 0.0
        # head word of ingredient (last core token) found in usda
        head = icore[-1] if icore else ''
        head_hit = 1.0 if head and head in uset else 0.0
        # specificity: extra identity words in usda primary not in ingredient
        extra = len(pset - iset)
        extra_pen = min(extra, 3) * 0.12

        # 3. form agreement (texture / behaviour)
        iforms = {W2F[t] for t in it if t in W2F}
        uforms = {W2F[t] for t in ut if t in W2F}
        form_pen = 0.0
        for f in ('dry', 'zest', 'toasted', 'lean', 'mix', 'canned', 'frozen', 'cooked'):
            if (f in iforms) != (f in uforms):
                form_pen += 0.18 if f in ('dry', 'zest', 'lean', 'mix', 'toasted') else 0.08
        if 'raw' in iforms and 'cooked' in uforms:
            form_pen += 0.1
        if 'cooked' in iforms and 'raw' in uforms:
            form_pen += 0.1
        if 'ground' in iforms and 'ground' not in uforms:
            form_pen += 0.05

        # 4. empty-bonus: ingredient says nothing special and usda is plain
        plain = 0.1 if not (iforms - {'raw'}) and not (uforms - {'raw'}) else 0.0

        score = 4.0 * cover + 2.0 * head_hit + 2.5 * role + plain * 5
        score -= 4.0 * extra_pen + 5.0 * form_pen
        # fuzzy char-trigram fallback for synonyms/misspellings
        a = ' '.join(icore)
        b = ' '.join(pcore)
        tri = lambda s: {s[i:i + 3] for i in range(max(len(s) - 2, 0))}
        ta, tb = tri(a), tri(b)
        if ta and tb:
            score += 1.5 * len(ta & tb) / float(len(ta | tb))
        return float(score)
    except Exception:
        return 0.0
