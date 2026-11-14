import re

# Processing-level lexicon: each cue contributes to a "processing level" for a text.
LEVELS = {
    'raw': -1, 'fresh': -1, 'plain': -1, 'unsweetened': -1, 'unsalted': -1, 'without': -1,
    'dried': 1, 'dry': 1, 'frozen': 1, 'canned': 1, 'cooked': 1, 'roasted': 1, 'toasted': 1,
    'ground': 1, 'powder': 1, 'powdered': 1, 'dehydrated': 1,
    'salted': 2, 'salt': 2, 'smoked': 2, 'cured': 2, 'pickled': 2, 'flavored': 2, 'flavor': 2,
    'sweetened': 3, 'sugar': 2, 'syrup': 3, 'honey': 2, 'vanilla': 1, 'chocolate': 2,
    'breaded': 4, 'battered': 4, 'fried': 3, 'glazed': 3, 'candied': 4, 'marinated': 3,
    'seasoned': 3, 'seasoning': 3, 'mix': 4, 'blend': 3, 'sauce': 4, 'dressing': 4,
    'frosting': 4, 'coating': 3, 'filled': 3, 'stuffed': 3, 'creamed': 3, 'dessert': 4,
    'prepared': 3, 'instant': 3, 'fortified': 2, 'candies': 4, 'soup': 4, 'pie': 4,
    'cookie': 4, 'cake': 4, 'palm': 1, 'oil': 1,
}
SKIP = set('the a an of and or with in for from to on g kg ml oz lb sliced diced chopped minced '
           'cubed drained thawed trimmed sifted skin bagged type style whole separable lean fat '
           'choice grade nfs ns as major regular made large small medium boneless usda'.split())


def _words(s):
    s = s.lower().replace("'", '')
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'\b\d+(?:\.\d+)?\s*(?:g|kg|ml|oz|lb)?\b', ' ', s)
    return re.findall(r'[a-z]+', s)


def _root(w):
    if len(w) > 4 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w


def _level_profile(words):
    lv = 0
    cues = 0
    for w in words:
        if w in LEVELS:
            lv += LEVELS[w]
            cues += 1
    return lv, cues


def judging_function(ingredient, usda_match):
    try:
        iw = _words(str(ingredient or ''))
        uw = _words(str(usda_match or ''))
        if not iw or not uw:
            return 0.0
        i_foods = [_root(w) for w in iw if w not in SKIP and w not in LEVELS]
        u_foods = [_root(w) for w in uw if w not in SKIP and w not in LEVELS]
        if not i_foods or not u_foods:
            return 1.0

        # The ingredient's head noun is typically its last food word.
        head_i = i_foods[-1]
        u_set = set(u_foods)
        first_u = u_foods[0]
        # Position of head noun inside the USDA description (earlier = primary food)
        if head_i in u_set:
            pos = u_foods.index(head_i)
            ident = 6.0 - 0.7 * min(pos, 4)
        else:
            others = [w for w in i_foods if w in u_set]
            ident = 2.5 * len(others) / float(len(i_foods)) if others else 0.0
        # secondary food words of the ingredient also present
        ci = sum(1 for w in set(i_foods) if w in u_set) / float(len(set(i_foods)))
        ident += 1.5 * ci
        # the USDA entry should not be dominated by foods the ingredient lacks
        foreign = sum(1 for w in set(u_foods) if w not in set(i_foods)) / float(len(set(u_foods)))
        ident -= 1.0 * foreign

        li, ci_cues = _level_profile(iw)
        lu, cu_cues = _level_profile(uw)
        # added processing counts more than missing processing
        diff = lu - li
        proc_pen = 0.8 * diff if diff > 0 else 0.5 * (-diff)
        # extra cues (compound features) in USDA
        proc_pen += 0.3 * max(0, cu_cues - ci_cues)

        score = 2.0 + ident - proc_pen
        if ident < 2.0:
            score = min(score, 2.0)
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
