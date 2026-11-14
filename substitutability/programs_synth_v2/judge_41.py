import re

# Lexical and Token Overlap, variant 1: role-weighted Jaccard.
# After stripping amounts, units and noise words, each content token gets a
# role weight: FOOD tokens (nouns that name a food) weigh 3, other content
# tokens 1, and known modifier tokens (cooking, fat level, size) 0.4. The
# weighted Jaccard of the two token sets is the base score, so overlap that
# comes only from modifiers counts little. A bonus is given when the
# ingredient's head token is shared.

_NOISE = set("""g gram grams kg ml l oz lb lbs cup cups tbsp tsp teaspoon tablespoon pinch
to taste from tube jar can pack package optional about approx divided plus more for
serving garnish and or of with without the a an in as into fresh chopped diced
minced sliced shredded grated thawed segmented peeled drained rinsed cubed halved
finely roughly coarsely thinly large small medium nfs ns""".split())
_MODIFIERS = set("""raw cooked boiled baked roasted fried grilled broiled steamed frozen
canned dried low fat lowfat nonfat reduced calorie sodium light lean salted unsalted
sweetened unsweetened whole plain regular prepared ready eat heat dry moist skin
not eaten only meat style type made commercial added""".split())
_FOODS = set("""oil olive chicken breast turkey beef pork fish swordfish salmon tuna
shrimp egg cheese cottage milk yogurt cream butter rice pasta bread flour oat cereal
corn potato gnocchi bean lentil pea tomato onion garlic ginger spinach lettuce kale
carrot broccoli pepper mushroom fruit apple banana berry blueberry orange guava ugli
juice nut almond peanut seed chia flaxseed sugar honey syrup chocolate dressing sauce
paste soup broth stock vanilla italian salad spice patty grain""".split())


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _tokens(text, is_ing):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    if is_ing:
        t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", t)
    t = re.sub(r"[^a-z\s]", " ", t)
    toks = [_sing(w) for w in t.split() if w not in _NOISE and len(w) > 1]
    return toks


def _weight(tok):
    if tok in _MODIFIERS:
        return 0.4
    if tok in _FOODS:
        return 3.0
    return 1.0


def judging_function(ingredient, usda_match):
    try:
        it = _tokens(str(ingredient or ""), True)
        ut = _tokens(str(usda_match or ""), False)
        if not it or not ut:
            return 0.0
        si, su = set(it), set(ut)
        inter = si & su
        union = si | su
        wi = sum(_weight(t) for t in inter)
        wu = sum(_weight(t) for t in union)
        jac = wi / wu if wu else 0.0
        # head token of the ingredient (last non-modifier token)
        content = [t for t in it if t not in _MODIFIERS] or it
        head = content[-1]
        head_bonus = 0.25 if head in su else 0.0
        # overlap only through modifiers is discounted further
        if inter and all(t in _MODIFIERS for t in inter):
            jac *= 0.3
        score = 10.0 * min(1.0, 0.75 * jac + head_bonus)
        return round(score, 3)
    except Exception:
        return 0.0
