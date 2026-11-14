import re

# Modifier and Qualifier Consistency, variant 3: head-slot alignment.
# The most discriminating qualifier usually sits right next to the head
# noun: the word before the head in a recipe phrase ("RED bell pepper",
# "WHOLE milk", "chicken BREAST" where the head is the part) and, in USDA
# style, the first descriptor field after the primary noun ("Peppers,
# SWEET, red", "Milk, WHOLE", "Chicken, broilers, BREAST").
# We locate the shared head noun, extract the ordered qualifier slots on
# each side (nearest first), and align them:
#   same word in aligned slots            -> agreement
#   both slots filled with discriminating
#   words of the same kind (via a small
#   kind lexicon, or both unknown)        -> contradiction
#   one side empty                        -> tolerated
# Neutral words (raw, fresh, cooked, NFS, sizes) never fill a slot.

_NEUTRAL = set("""raw fresh frozen canned cooked uncooked boiled baked roasted fried
grilled steamed drained chopped diced minced sliced shredded grated thawed
segmented peeled large small medium nfs ns regular prepared plain with without
and or of the a an in to from not eaten only meat broilers fryers broiler fryer
mature commercial heat dry moist solids liquids style type made g kg ml oz""".split())
_KIND = {}
for _k, _ws in {
    "colour": "red green yellow orange white black brown purple golden pink",
    "fat": "whole skim nonfat lowfat reduced lean fat free full light",
    "sweet": "sweet sweetened unsweetened semisweet bittersweet dark",
    "part": "breast thigh wing drumstick leg loin tenderloin rib shoulder brisket liver skin back neck",
    "plantpart": "leaf leaves root seed seeds stem stalk peel zest juice bulb",
    "flavour": "vanilla chocolate strawberry honey cinnamon maple lemon coffee peach",
    "cheese": "cheddar cottage mozzarella swiss parmesan feta ricotta brie gouda",
    "dressing": "italian ranch caesar french",
    "pepper": "bell jalapeno serrano habanero poblano chipotle",
}.items():
    for _w in _ws.split():
        _KIND[_w] = _k


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _ing_slots(words, head):
    """Qualifiers ordered nearest-to-head first (pre-head adjectives)."""
    if head in words:
        idx = len(words) - 1 - words[::-1].index(head)
        pre = words[:idx][::-1]
        post = words[idx + 1:]
    else:
        pre, post = words[:-1][::-1], []
    return [w for w in pre + post if w not in _NEUTRAL]


def _usda_slots(fields, head):
    slots = []
    for fi, f in enumerate(fields):
        if head in f:
            idx = f.index(head)
            slots.extend(w for w in f[:idx][::-1])
            slots.extend(f[idx + 1:])
        else:
            slots.extend(f)
    return [w for w in slots if w not in _NEUTRAL and w != head]


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing).split(",")[0]
        iw = [_sing(w) for w in re.findall(r"[a-z]+", ing)]
        fields = [[_sing(w) for w in re.findall(r"[a-z]+", f)] for f in str(usda_match or "").lower().split(",")]
        fields = [f for f in fields if f]
        if not iw or not fields:
            return 0.0
        content = [w for w in iw if w not in _NEUTRAL] or iw
        u_all = {w for f in fields for w in f}
        # head: last ingredient content word found in the USDA entry, else last word
        head = next((w for w in reversed(content) if w in u_all), content[-1])
        si = _ing_slots(content, head)
        su = _usda_slots(fields, head)
        score = 8.0
        su_set = set(su)
        used = set()
        for rank, q in enumerate(si[:3]):
            weight = 1.0 / (1 + rank)            # nearest qualifier matters most
            if q in su_set:
                score += 1.2 * weight
                used.add(q)
                continue
            kind = _KIND.get(q)
            rivals = [u for u in su if u not in used and _KIND.get(u) == kind and kind]
            if rivals:
                score -= 3.0 * weight            # contradicted known qualifier
            elif kind is None and su and su[0] not in si and _KIND.get(su[0]) is None and rank == 0:
                score -= 1.0 * weight            # two unknown qualifiers in the same slot
            else:
                score -= 0.4 * weight            # simply unspecified in USDA
        # discriminating USDA qualifiers of a known kind that the ingredient never set
        for u in su[:3]:
            if u not in si and _KIND.get(u) in ("fat", "flavour", "part", "colour", "sweet") \
                    and not any(_KIND.get(q) == _KIND.get(u) for q in si):
                score -= 0.5
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
