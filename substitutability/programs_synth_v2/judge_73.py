import re

# Modifier and Qualifier Consistency, variant 1: mutually-exclusive value
# groups and contradiction counting.
# Discriminating qualifiers are organised into exclusive groups: a food can
# be only one colour, one fat level, one sweetness, one animal part, one
# plant part, one variety. For every group we read the value asserted by
# each side:
#   both assert, same value      -> agreement (small reward)
#   both assert, different value -> contradiction (penalty by noticeability)
#   only one side asserts        -> unspecified, tolerated (tiny cost)
# Nested values are treated as compatible (e.g. "lean" vs "extra lean").

_GROUPS = {
    "colour": (2.0, {"red": "red", "green": "green", "yellow": "yellow", "orange": "orange",
                     "white": "white", "black": "black", "brown": "brown", "purple": "purple",
                     "golden": "yellow", "pink": "pink"}),
    "fat": (2.2, {"whole": "full", "full fat": "full", "regular": "full", "2%": "reduced",
                  "reduced fat": "reduced", "low fat": "low", "lowfat": "low", "1%": "low",
                  "light": "low", "skim": "none", "nonfat": "none", "fat free": "none",
                  "lean": "lean", "extra lean": "lean"}),
    "sweet": (2.0, {"sweetened": "sweet", "sweet": "sweet", "unsweetened": "unsweet",
                    "sugar free": "unsweet", "no sugar added": "unsweet", "semisweet": "semi",
                    "bittersweet": "bitter", "dark": "bitter"}),
    "animal_part": (2.5, {"breast": "breast", "thigh": "thigh", "wing": "wing", "drumstick": "leg",
                          "leg": "leg", "loin": "loin", "tenderloin": "loin", "rib": "rib",
                          "shoulder": "shoulder", "brisket": "brisket", "light meat": "light",
                          "dark meat": "dark", "liver": "liver", "skin": "skin", "ground": "ground",
                          "white meat": "light"}),
    "plant_part": (2.0, {"leaf": "leaf", "leaves": "leaf", "root": "root", "seed": "seed",
                         "seeds": "seed", "stem": "stem", "stalk": "stem", "bulb": "bulb",
                         "peel": "peel", "zest": "peel", "juice": "juice", "flower": "flower"}),
    "variety": (1.8, {"bell": "bell", "jalapeno": "jalapeno", "chipotle": "chipotle", "russet": "russet",
                      "red skin": "red", "yukon": "yukon", "basmati": "basmati", "jasmine": "jasmine",
                      "arborio": "arborio", "roma": "roma", "cherry": "cherry", "granny smith": "granny",
                      "fuji": "fuji", "gala": "gala", "navel": "navel", "valencia": "valencia",
                      "cheddar": "cheddar", "cottage": "cottage", "mozzarella": "mozzarella",
                      "swiss": "swiss", "parmesan": "parmesan", "feta": "feta", "italian": "italian",
                      "ranch": "ranch", "caesar": "caesar", "french": "french"}),
    "cut_size": (0.8, {"baby": "baby", "jumbo": "large", "large": "large", "small": "small",
                       "medium": "medium", "mini": "small"}),
    "flavour": (2.0, {"vanilla": "vanilla", "chocolate": "chocolate", "strawberry": "strawberry",
                      "plain": "plain", "original": "plain", "honey": "honey", "cinnamon": "cinnamon",
                      "garlic": "garlic", "lemon": "lemon", "maple": "maple"}),
}


def _values(text):
    t = " " + re.sub(r"[^a-z0-9% ]", " ", text.lower()) + " "
    t = re.sub(r"\s+", " ", t)
    found = {}
    for g, (_w, table) in _GROUPS.items():
        for phrase in sorted(table, key=len, reverse=True):
            if " " + phrase + " " in t:
                found.setdefault(g, set()).add(table[phrase])
                t = t.replace(" " + phrase + " ", " ")
    return found


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or ""))
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing, flags=re.I).split(",")[0]
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        vi, vu = _values(ing), _values(usda)
        # "skin not eaten" / "without skin" negates skin
        if re.search(r"skin not eaten|without skin|skinless", usda.lower()):
            vu.get("animal_part", set()).discard("skin")
        score = 8.5
        for g in set(vi) | set(vu):
            w = _GROUPS[g][0]
            a, b = vi.get(g, set()), vu.get(g, set())
            if a and b:
                if a & b:
                    score += 0.4 * w
                    if a - b:
                        score -= 0.6 * w      # extra asserted part not matched
                else:
                    score -= 1.5 * w
            elif a:
                score -= 0.25 * w            # USDA silent on a qualifier the recipe named
            else:
                score -= 0.15 * w            # USDA adds an unrequested qualifier
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
