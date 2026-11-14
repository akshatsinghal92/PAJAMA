import re
import math

# Culinary role lexicon: each keyword votes for one or more functional roles.
_ROLE_LEXICON = {
    "fat": ["oil", "butter", "lard", "shortening", "ghee", "margarine", "tallow", "drippings"],
    "dairy": ["milk", "cream", "yogurt", "yoghurt", "kefir", "cheese", "cottage", "ricotta",
              "buttermilk", "curd", "whey", "souffle"],
    "muscle_meat": ["chicken", "turkey", "beef", "pork", "lamb", "veal", "duck", "ham", "bacon",
                    "steak", "breast", "thigh", "ground", "mince", "minced", "sausage", "patty"],
    "organ": ["liver", "livers", "gizzard", "gizzards", "giblets", "tongue", "kidney", "heart",
              "tripe", "blood", "pate", "variety", "by-products"],
    "seafood": ["fish", "lobster", "crayfish", "shrimp", "prawn", "crab", "salmon", "tuna",
                "cod", "clam", "mussel", "oyster", "squid"],
    "fruit": ["apple", "grape", "grapes", "plum", "pomegranate", "arils", "berry", "berries",
              "jamun", "java-plum", "jambolan", "carissa", "mango", "banana", "orange", "lemon",
              "cherry", "peach", "pear", "fruit"],
    "nut_seed": ["nut", "nuts", "peanut", "peanuts", "hazelnut", "almond", "walnut", "cashew",
                 "pecan", "seed", "seeds", "chia", "flax", "sesame", "coconut"],
    "legume": ["pea", "peas", "bean", "beans", "lentil", "lentils", "chickpea", "blackeye"],
    "grain": ["flour", "tortilla", "bread", "rice", "oat", "oats", "cereal", "cereals", "pasta",
              "noodle", "noodles", "cheerios", "wheat", "corn"],
    "sauce": ["sauce", "marinara", "ketchup", "salsa", "gravy", "dressing", "paste", "puree"],
    "beverage": ["juice", "drink", "beverage", "nectar", "soda"],
    "sweetener": ["sugar", "honey", "syrup", "molasses", "vanilla"],
    "aromatic": ["garlic", "onion", "ginger", "spice", "spices", "herb", "pepper", "shallot"],
}

_WORD_TO_ROLES = {}
for _role, _words in _ROLE_LEXICON.items():
    for _w in _words:
        _WORD_TO_ROLES.setdefault(_w, set()).add(_role)

# Physical form groups: forms in different groups behave differently in a recipe.
_FORM_GROUPS = {
    "liquid": ["juice", "oil", "liquid", "milk", "syrup", "drink", "beverage", "expressed", "melted"],
    "powder": ["powder", "powdered", "ground", "flour", "dried", "dry", "dehydrated"],
    "paste": ["paste", "pate", "puree", "spread", "mashed"],
    "whole": ["whole", "arils", "raw", "fresh", "tails", "slices", "sliced", "diced", "chopped"],
    "preserved": ["canned", "jarred", "syrup", "pack", "pickled", "solids"],
}

# Descriptors that signal a formulation change the eater would notice.
_ALTERING = {
    "lowfat", "low-fat", "nonfat", "non-fat", "fat-free", "reduced", "lactose", "sodium",
    "low", "light", "lite", "sweetened", "unsweetened", "heavy", "syrup", "salted",
    "unsalted", "milkfat", "added", "diet", "imitation", "substitute", "fried", "roasted",
    "dry", "smoked", "canned", "baked",
}

# Cooking-method words: a mismatch here changes texture/taste.
_METHODS = {"fried", "roasted", "dry", "baked", "boiled", "grilled", "smoked", "steamed",
            "broiled", "pan-fried", "pan-broiled", "oil-roasted", "braised", "stewed", "raw",
            "cooked"}

_IGNORE = {"g", "kg", "mg", "ml", "of", "and", "or", "the", "a", "an", "for", "from", "into",
           "with", "in", "to", "garnish", "leftover", "tube", "ready-to-serve", "ready-to-eat",
           "nfs", "ns", "as", "to", "prepared", "plain"}

_PREP_ONLY = {"diced", "minced", "sliced", "chopped", "crumbled", "melted", "thawed",
              "frozen", "cooked", "toasted", "grated", "shredded", "cubed", "peeled"}


def _tokens(text):
    text = text.lower()
    text = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|ml|oz|lb)\b", " ", text)
    text = re.sub(r"\d+%?", " ", text)
    toks = re.findall(r"[a-z][a-z\-/]*", text)
    out = []
    for t in toks:
        for p in t.split("/"):
            if p and p not in _IGNORE:
                out.append(p)
    return out


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _role_vector(toks):
    vec = {}
    for t in toks:
        roles = _WORD_TO_ROLES.get(t) or _WORD_TO_ROLES.get(_stem(t))
        if not roles:
            for part in t.split("-"):
                roles = _WORD_TO_ROLES.get(part) or _WORD_TO_ROLES.get(_stem(part))
                if roles:
                    break
        if roles:
            w = 1.0 / len(roles)
            for r in roles:
                vec[r] = vec.get(r, 0.0) + w
    return vec


def _cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b.get(k, 0.0) for k in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _forms(toks):
    found = set()
    for t in toks:
        for g, ws in _FORM_GROUPS.items():
            if t in ws or any(p in ws for p in t.split("-")):
                found.add(g)
    return found


def _primary_of_usda(usda):
    first = usda.split(",")[0].strip().lower()
    return set(_stem(t) for t in _tokens(first))


def judging_function(ingredient, usda_match):
    try:
        ing = "" if ingredient is None else str(ingredient)
        usda = "" if usda_match is None else str(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0

        # Split ingredient into core and qualifiers (parentheticals, post-comma state).
        ing_core = re.sub(r"\([^)]*\)", " ", ing)
        ing_main = ing_core.split(",")[0]
        ing_toks = _tokens(ing_main)
        ing_all_toks = _tokens(ing_core)
        usda_toks = _tokens(re.sub(r"\([^)]*\)", " ", usda))
        usda_paren = " ".join(re.findall(r"\(([^)]*)\)", usda))
        usda_toks_full = usda_toks + _tokens(usda_paren)

        if not ing_toks or not usda_toks:
            return 1.0

        ing_stems = set(_stem(t) for t in ing_all_toks)
        usda_stems = set(_stem(t) for t in usda_toks_full)

        # 1. Functional role similarity (0..1).
        role_sim = _cosine(_role_vector(ing_all_toks), _role_vector(usda_toks_full))

        # 2. Head-noun anchoring: does the ingredient's head (last content word) appear
        #    in the USDA primary segment, or vice versa?
        content = [t for t in ing_toks if t not in _PREP_ONLY]
        head = _stem(content[-1]) if content else _stem(ing_toks[-1])
        primary = _primary_of_usda(usda)
        head_in_primary = head in primary or any(head in p or p in head for p in primary if len(p) > 3)
        head_anywhere = head in usda_stems
        # Modifier words of the ingredient (non-head content words) covered by USDA.
        mods = [_stem(t) for t in content[:-1]]
        mod_cov = (sum(1 for m in mods if m in usda_stems or any(m in u for u in usda_stems if len(m) > 3))
                   / len(mods)) if mods else 1.0

        # Ingredient identity hit: if the primary USDA noun refers to something the
        # ingredient only uses as a modifier (hazelnut -> oil, hazelnut), role changed.
        primary_is_mod_only = bool(primary & ing_stems) and not head_in_primary

        # 3. Form compatibility.
        f_ing = _forms(ing_all_toks)
        f_usda = _forms(usda_toks_full)
        # melted fat is still fat: treat 'liquid' from melting as compatible with oil
        form_pen = 0.0
        if f_ing and f_usda and not (f_ing & f_usda):
            form_pen = 0.35
        elif not f_ing and ("liquid" in f_usda or "powder" in f_usda or "paste" in f_usda):
            # USDA introduces a form shift the ingredient never asked for.
            form_pen = 0.3
        if "preserved" in f_usda and "preserved" not in f_ing:
            form_pen += 0.2
        if "paste" in f_usda and "paste" not in f_ing and "liquid" not in f_ing:
            form_pen += 0.1

        # 4. Formulation changes: altering descriptors present in USDA but absent from ingredient.
        extra_alter = [t for t in usda_toks_full
                       if (t in _ALTERING or _stem(t) in _ALTERING) and _stem(t) not in ing_stems
                       and t not in ing_stems]
        alter_pen = min(0.45, 0.12 * len(set(extra_alter)))

        # 5. Cooking method conflict.
        m_ing = set()
        for t in ing_all_toks:
            for p in [t] + t.split("-"):
                if p in _METHODS:
                    m_ing.add(p)
        m_usda = set()
        for t in usda_toks_full:
            for p in [t] + t.split("-"):
                if p in _METHODS:
                    m_usda.add(p)
        method_pen = 0.0
        strong = {"fried", "roasted", "baked", "smoked", "grilled", "boiled", "dry", "oil"}
        if (m_ing & strong) and (m_usda & strong) and not (m_ing & m_usda & strong):
            method_pen = 0.25

        # 6. Specificity loss: ingredient names a specific variety the USDA doesn't carry.
        uncovered = [t for t in content if _stem(t) not in usda_stems
                     and not any(_stem(t) in u or u in _stem(t) for u in usda_stems if len(u) > 3)]
        spec_pen = min(0.4, 0.15 * len(uncovered))

        # Combine into a 0..10 score.
        base = 0.0
        base += 3.5 * role_sim
        base += 3.0 if head_in_primary else (1.2 if head_anywhere else 0.0)
        base += 1.5 * mod_cov
        base += 1.0 if not primary_is_mod_only else -1.0
        # Brevity of USDA tail: fewer extra descriptors -> closer to a generic swap.
        tail = [t for t in usda_toks_full if _stem(t) not in ing_stems]
        base += 1.0 * math.exp(-0.35 * len(tail))

        penalty = form_pen + alter_pen + method_pen + spec_pen
        score = base * (1.0 - min(0.85, penalty))
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
