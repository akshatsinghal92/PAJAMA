import re

ROLES = {
    "fat": {"oil", "butter", "lard", "shortening", "ghee", "margarine", "tallow", "fat"},
    "sweetener": {"sugar", "sugars", "honey", "syrup", "molasses", "sweetener", "agave"},
    "liquid": {"milk", "juice", "broth", "stock", "water", "wine", "vinegar", "cream", "beer"},
    "protein": {"chicken", "beef", "pork", "turkey", "lamb", "bison", "buffalo", "veal", "sausage",
                "bacon", "ham", "steak", "fish", "salmon", "tuna", "cod", "herring", "shrimp", "egg", "eggs", "tofu"},
    "nut": {"nut", "nuts", "almond", "almonds", "walnut", "walnuts", "pecan", "pecans", "hazelnut",
            "hazelnuts", "cashew", "cashews", "peanut", "pistachio", "seed", "seeds"},
    "starch": {"flour", "rice", "pasta", "bread", "oats", "oat", "grain", "wheat", "corn", "cornstarch",
               "starch", "bran", "barley", "quinoa", "amaranth", "spaghetti", "noodles"},
    "legume": {"beans", "bean", "lentils", "lentil", "peas", "pea", "chickpeas"},
    "produce": {"onion", "garlic", "carrot", "potato", "tomato", "pepper", "cucumber", "radish",
                "turnip", "spinach", "cabbage", "apple", "grapes", "grape", "papaya", "durian",
                "pomegranate", "peach", "banana", "berries", "orange", "lemon", "greens"},
    "spice": {"ginger", "cinnamon", "paprika", "cumin", "salt", "spice", "spices", "oregano", "basil"},
}
TOKEN_ROLE = {}
for r, ws in ROLES.items():
    for w in ws:
        TOKEN_ROLE[w] = r

# words that signal a changed dish / role (composite or different product form)
FORM_WORDS = {"juice", "salad", "entree", "sauce", "soup", "pie", "cake", "dessert", "candy",
              "snack", "dinner", "sandwich", "pickled", "canned", "mix", "dressing", "drink",
              "beverage", "cereal", "bar", "patty", "nuggets", "smoothie", "powder", "extract",
              "frozen", "dried", "dehydrated", "cooked", "raw", "pickles", "luncheon", "prepackaged",
              "deli", "baked", "smoked", "roasted", "boiled", "fried", "toasted"}
# states that are genuinely incompatible with each other
STATE_GROUPS = [
    {"raw", "fresh", "uncooked", "unprepared"},
    {"cooked", "baked", "boiled", "roasted", "fried", "grilled", "braised", "steamed"},
    {"dried", "dehydrated", "dry"},
    {"canned"},
    {"frozen"},
    {"pickled"},
    {"smoked", "cured"},
]
STOP = {"the", "a", "an", "of", "and", "or", "with", "in", "for", "from", "to", "g", "kg", "oz", "ml",
        "fresh", "fine", "finely", "chopped", "sliced", "diced", "minced", "ground", "large", "small",
        "medium", "ripe", "whole", "optional", "taste", "thawed", "peeled", "cubed", "soaked",
        "overnight", "garnish", "tube", "crude", "free", "added", "no", "not", "mature", "seeds",
        "meat", "or", "type", "style", "100", "brand"}


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxzh":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _toks(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s.lower())]


def _state(tokens):
    st = set()
    for i, g in enumerate(STATE_GROUPS):
        gs = {_stem(x) for x in g}
        if any(t in gs for t in tokens):
            st.add(i)
    return st


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"^\s*[\d.,/]+\s*(g|kg|ml|oz|lb)?\s*", "", ing)
        paren = " ".join(re.findall(r"\(([^)]*)\)", ing))
        ing = re.sub(r"\([^)]*\)", " ", ing)
        usda = re.sub(r"\([^)]*\)", " ", usda)
        parts = ing.split(",", 1)
        ing_main = parts[0]
        ing_post = parts[1] if len(parts) > 1 else ""
        uparts = [p.strip() for p in usda.split(",")]
        u_head = uparts[0]
        u_desc = " ".join(uparts[1:])

        it = [t for t in _toks(ing_main) if t not in STOP]
        it_all = _toks(ing_main + " " + ing_post + " " + paren)
        uh = [t for t in _toks(u_head) if t not in STOP]
        ud = _toks(u_desc)
        u_all = uh + ud
        if not it or not u_all:
            return 0.0

        score = 0.0

        # 1. Function-bearing core: last meaningful token of ingredient (head noun)
        i_head = it[-1]
        u_set = set(u_all)
        if i_head in set(uh):
            score += 3.0
        elif i_head in u_set:
            score += 2.0
        else:
            # role-level fallback
            ri = TOKEN_ROLE.get(i_head)
            ru = {TOKEN_ROLE.get(t) for t in uh} - {None}
            if ri and ri in ru:
                score += 0.8

        # 2. Coverage of ingredient content words by the USDA description
        cov = sum(1 for t in it if t in u_set) / float(len(it))
        score += 3.0 * cov

        # 3. Extra unexplained content in USDA primary food (composite dish / other item)
        extra_head = [t for t in uh if t not in set(it_all)]
        score -= 1.2 * min(len(extra_head), 4) * (1.0 if len(uh) > 1 else 0.5)
        # ingredient modifiers the USDA lacks (variety/species change)
        missing = [t for t in it if t not in u_set]
        score -= 1.5 * min(len(missing), 3)

        # 4. Role compatibility: roles of both sides
        ri = {TOKEN_ROLE[t] for t in it if t in TOKEN_ROLE}
        ru = {TOKEN_ROLE[t] for t in uh if t in TOKEN_ROLE}
        if ri and ru:
            if ri & ru:
                score += 1.0
            else:
                score -= 2.0

        # 5. Form words in USDA that change behaviour and that ingredient does not name
        ing_set = set(it_all)
        for w in uh + ud:
            if w in ("juice", "salad", "entree", "sauce", "soup", "dessert", "candy", "snack",
                     "dinner", "sandwich", "dressing", "drink", "beverage", "cereal", "pickled",
                     "luncheon", "prepackaged", "deli", "pie", "cake", "mix", "powder", "extract",
                     "patty", "nugget", "smoothie"):
                if w not in ing_set:
                    score -= 2.0
        # ingredient names a form the USDA lacks (e.g. juice, sauce, milk, butter)
        for w in it:
            if w in ("juice", "sauce", "milk", "butter", "oil", "paste", "powder", "flour",
                     "vinegar", "syrup", "broth", "stock") and w not in u_set:
                score -= 2.0

        # 6. Preparation-state compatibility
        si = _state(it_all)
        su = _state(u_all)
        if si and su:
            if si & su:
                score += 1.0
            else:
                score -= 1.5
        elif si and not su:
            # ingredient specifies state, USDA silent: mild risk
            if 1 in si or 2 in si or 5 in si:
                score -= 0.8
        elif su and not si:
            # USDA specifies a state the recipe did not
            if su & {2, 3, 5, 6}:
                score -= 1.0

        # 7. Preserving shape / ingredient says dried but USDA is from-dried reconstituted
        if ("from" in ud and "dried" in ud) and 2 in si:
            score -= 1.0

        return float(score)
    except Exception:
        return 0.0
