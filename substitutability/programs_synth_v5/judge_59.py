import re
import math

_NOISE = {'and', 'or', 'of', 'the', 'a', 'with', 'for', 'in', 'from', 'to', 'nfs', 'ns',
          'g', 'kg', 'oz', 'ml', 'lb', 'fresh', 'cold', 'warm', 'warmed', 'ripe', 'cubed',
          'sliced', 'chopped', 'diced', 'thawed', 'drained', 'serving', 'by', 'type',
          'raw', 'cooked', 'frozen', 'canned', 'whole', 'large', 'small', 'medium',
          'fine', 'finely', 'minced', 'grated', 'peeled', 'solids', 'liquid', 'trimmed',
          'separable', 'lean', 'choice', 'only', 'all', 'grades', 'salad', 'cooking'}
# words that change what the food IS when present on just one side
_SHIFT = {'vanilla', 'chocolate', 'strawberry', 'coconut', 'almond', 'soy', 'oat',
          'vegan', 'imitation', 'substitute', 'artificial', 'powdered', 'powder',
          'dehydrated', 'butter', 'oil', 'milk', 'cream', 'seeds', 'seed', 'juice',
          'flour', 'paste', 'syrup', 'extract', 'chips', 'sauce', 'balsamic', 'smoked',
          'flavored', 'diet', 'sugar', 'dried', 'dry', 'sweetened', 'unsweetened',
          'butter', 'cocoa', 'heart', 'tongue', 'liver', 'skin', 'bone', 'shell',
          'tofu', 'yogurt', 'cheese', 'ricotta', 'cottage', 'palm', 'plant', 'based'}


def _stem(w):
    if len(w) > 4 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 4 and w.endswith('es') and w[-3] in 'sxzh':
        return w[:-2]
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w


def _words(s):
    return [_stem(w) for w in re.findall(r"[a-z]+", s.lower())]


def _grams(s, n=3):
    s = '^' + s + '$'
    return set(s[i:i + n] for i in range(max(1, len(s) - n + 1)))


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or '')
        usda = str(usda_match or '')
        if not ing.strip() or not usda.strip():
            return 0.0

        # ---- brand / commercial signature of the USDA entry
        caps = re.findall(r"\b[A-Z][A-Z0-9'!&\.\-]{2,}\b", usda)
        paren_in_usda = len(re.findall(r"\([^)]*\)", usda))
        segs = [s.strip() for s in usda.split(',') if s.strip()]
        usda_plain = re.sub(r"\b[A-Z][A-Z0-9'!&\. \-]{2,}\b", ' ', usda)
        usda_plain = re.sub(r"\([^)]*\)", ' ', usda_plain)

        ing_noparen = re.sub(r"\([^)]*\)", ' ', ing)
        ing_main = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|oz|ml|lb)?\b", ' ', ing_noparen.lower())
        ing_has_caps = bool(re.search(r"\b[A-Z]{3,}\b", ing))

        iw = [w for w in _words(ing_main) if w not in _NOISE]
        # post-comma prep words are noise: keep only pre-comma if available
        pre = ing_main.split(',')[0]
        iw_pre = [w for w in _words(pre) if w not in _NOISE]
        if iw_pre:
            iw = iw_pre
        uw = [w for w in _words(usda_plain) if w not in _NOISE]
        if not iw or not uw:
            return 0.0

        # ---- feature 1: character-trigram dice on the joined core strings
        ga, gb = _grams(' '.join(iw)), _grams(' '.join(uw))
        dice = 2.0 * len(ga & gb) / (len(ga) + len(gb))

        # ---- feature 2: ordered alignment of the ingredient's last word
        # (head noun) against the USDA leading segment
        lead = [w for w in _words(segs[0]) if w not in _NOISE] if segs else uw
        head_in_lead = 1.0 if iw[-1] in lead or iw[-1] in uw[:2] else 0.0
        anyhit = 1.0 if (set(iw) & set(uw)) else 0.0

        # ---- feature 3: unmatched shift words (asymmetric difference)
        si, su = set(iw), set(uw)
        shift_i = (si - su) & _SHIFT
        shift_u = (su - si) & _SHIFT
        shift_cost = len(shift_i) * 1.0 + len(shift_u) * 0.8

        # ---- feature 4: brand evidence classification
        brand_evidence = len(caps) + 0.4 * paren_in_usda
        if brand_evidence > 0:
            if shift_u or shift_i:
                brand_adj = -0.7 * brand_evidence          # brand implies a different variant
            elif dice > 0.45:
                brand_adj = 0.6                            # standard example of the product
            else:
                brand_adj = -0.3
        else:
            brand_adj = 0.0
        if ing_has_caps and caps:
            brand_adj += 0.4

        # ---- feature 5: leftover size of the ingredient not explained by USDA
        unexplained = len(si - su) / float(len(si))

        z = -1.2 + 5.0 * dice + 2.0 * head_in_lead + 1.0 * anyhit \
            - 1.6 * shift_cost - 1.5 * unexplained + brand_adj
        # squash to 0-100
        return round(100.0 / (1.0 + math.exp(-z / 1.5)), 2)
    except Exception:
        return 0.0
