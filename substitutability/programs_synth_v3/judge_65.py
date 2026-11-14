import re

# Culinary role lexicon: role -> keywords
ROLE_LEXICON = {
    "fat": ["oil", "butter", "lard", "shortening", "ghee", "margarine", "tallow", "drippings"],
    "protein_meat": ["beef", "pork", "chicken", "turkey", "lamb", "veal", "steak", "sirloin",
                     "brisket", "ham", "bacon", "sausage", "duck", "goat", "venison", "mince"],
    "protein_sea": ["fish", "salmon", "tuna", "cod", "shrimp", "prawn", "crab", "lobster",
                    "tilapia", "halibut", "scallop", "mussel", "clam", "anchovy", "sardine"],
    "protein_plant": ["tofu", "tempeh", "seitan", "lentil", "chickpea", "bean", "edamame"],
    "dairy_cheese": ["cheese", "cheddar", "mozzarella", "parmesan", "colby", "feta", "ricotta",
                     "cottage", "asadero", "brie", "gouda", "monterey"],
    "dairy_liquid": ["milk", "cream", "yogurt", "kefir", "buttermilk"],
    "binder": ["egg", "flaxseed", "flax", "chia", "gelatin", "breadcrumb"],
    "starch": ["flour", "rice", "pasta", "noodle", "bread", "oat", "potato", "quinoa",
               "barley", "couscous", "tortilla", "cornmeal", "polenta"],
    "thickener": ["cornstarch", "arrowroot", "tapioca", "starch", "roux", "xanthan"],
    "sweetener": ["sugar", "honey", "syrup", "molasses", "agave", "stevia", "jam", "jelly"],
    "aromatic": ["garlic", "onion", "shallot", "ginger", "leek", "scallion", "chive",
                 "lemongrass", "celery"],
    "spice": ["pepper", "cumin", "paprika", "cinnamon", "nutmeg", "spice", "spices", "salt",
              "turmeric", "oregano", "basil", "thyme", "rosemary", "cilantro", "parsley", "herb"],
    "fruit": ["apple", "applesauce", "banana", "papaya", "mango", "grape", "grapes", "berry",
              "strawberry", "blueberry", "raspberry", "watermelon", "melon", "orange",
              "lemon", "lime", "pear", "peach", "cherry", "pineapple", "plum", "kiwi"],
    "vegetable": ["green bean", "beans", "carrot", "broccoli", "spinach", "kale", "lettuce",
                  "tomato", "cucumber", "zucchini", "squash", "pepper", "cabbage",
                  "cauliflower", "eggplant", "mushroom", "corn", "pea", "peas", "asparagus"],
    "nut_seed": ["pecan", "pecans", "almond", "walnut", "cashew", "peanut", "pistachio",
                 "hazelnut", "seed", "seeds", "macadamia"],
    "liquid": ["broth", "stock", "water", "juice", "wine", "vinegar", "sauce"],
    "coconut": ["coconut"],
}

# Physical forms that alter behaviour in a recipe
FORM_GROUPS = {
    "puree": ["puree", "purée", "sauce", "applesauce", "paste", "mashed", "pureed"],
    "ground": ["ground", "minced", "mince", "crumbles", "crumbled", "powder", "powdered"],
    "whole": ["whole", "raw"],
    "liquid": ["juice", "liquid", "extract", "oil"],
    "dried": ["dried", "dehydrated", "dry"],
    "gel": ["gel", "jelly"],
}

# Extras in USDA that indicate an altered/compound product (role drift)
ADDITIVE_MARKERS = ["with ", "added", "flavored", "sweetened", "breaded", "battered",
                    "in syrup", "in oil", "candied", "frosted", "glazed", "seasoned",
                    "stuffed", "prepared", "mix", "patty", "nugget", "pie", "soup"]

NEUTRAL_MARKERS = ["raw", "nfs", "regular", "fresh", "plain", "uncooked", "cooked",
                   "frozen", "ns as to", "unprepared", "all varieties"]

DIET_MARKERS = ["dairy-free", "vegan", "gluten-free", "low-fat", "lowfat", "fat-free",
                "nonfat", "reduced", "lean", "sugar-free", "unsweetened"]

PREP_WORDS = {"shredded", "chopped", "diced", "sliced", "cubed", "cold", "warm", "hot",
              "fresh", "thawed", "frozen", "cooked", "crumbled", "grated", "minced",
              "peeled", "large", "small", "medium", "finely", "roughly", "and", "of",
              "the", "a", "to", "taste", "about", "packed", "softened", "melted"}


def _norm(text):
    text = (text or "").lower()
    text = text.replace("é", "e")
    return text


def _clean_ingredient(ing):
    s = _norm(ing)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*[\d.,/]+\s*(g|kg|ml|l|oz|lb|grams?|cups?|tbsp|tsp)?\b", " ", s)
    head, _, tail = s.partition(",")
    return head.strip(), tail.strip(), s


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and not w.endswith("ses"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s)]


def _roles(text):
    found = {}
    padded = " " + text + " "
    for role, kws in ROLE_LEXICON.items():
        for kw in kws:
            if re.search(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])", padded):
                found[role] = found.get(role, 0) + 1
    return found


def _forms(text):
    out = set()
    for f, kws in FORM_GROUPS.items():
        for kw in kws:
            if re.search(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])", text):
                out.add(f)
    return out


def _role_similarity(r1, r2):
    if not r1 or not r2:
        return 0.35  # unknown role: neutral-ish
    s1, s2 = set(r1), set(r2)
    inter = s1 & s2
    union = s1 | s2
    base = len(inter) / float(len(union))
    # compatible role families (can play same function)
    compatible = [
        {"protein_meat", "protein_sea"},
        {"dairy_liquid", "coconut"},
        {"fat", "coconut"},
        {"starch", "thickener"},
        {"aromatic", "spice"},
        {"binder", "starch"},
    ]
    bonus = 0.0
    for fam in compatible:
        if (s1 & fam) and (s2 & fam) and not inter & fam:
            bonus = max(bonus, 0.3)
    return min(1.0, base + bonus)


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing_head, ing_tail, ing_full = _clean_ingredient(ingredient)
        usda = _norm(usda_match)
        usda_parts = [p.strip() for p in usda.split(",") if p.strip()]
        if not usda_parts:
            return 0.0
        usda_primary = usda_parts[0]
        usda_descs = usda_parts[1:]

        # 1. Role compatibility (dominant term)
        r_ing = _roles(ing_head)
        r_usda = _roles(usda)
        role_sim = _role_similarity(r_ing, r_usda)

        # 2. Identity anchoring: does the ingredient's core noun appear in USDA?
        ing_core = [t for t in _tokens(ing_head) if t not in PREP_WORDS and len(t) > 2]
        usda_tok = set(_tokens(usda))
        usda_primary_tok = set(_tokens(usda_primary))
        if ing_core:
            hits = sum(1 for t in ing_core if t in usda_tok or any(
                (len(t) > 4 and (t in u or u in t)) for u in usda_tok if len(u) > 4))
            anchor = hits / float(len(ing_core))
            last_noun = ing_core[-1]
            head_noun_hit = last_noun in usda_tok or any(
                len(u) > 4 and (last_noun in u or u in last_noun) for u in usda_tok)
            primary_hit = any(t in usda_primary_tok for t in ing_core)
        else:
            anchor, head_noun_hit, primary_hit = 0.3, False, False

        # 3. Form / texture behaviour
        f_ing = _forms(ing_full)
        f_usda = _forms(usda)
        form_pen = 0.0
        conflicting = [("puree", "whole"), ("ground", "whole"), ("gel", "ground"),
                       ("liquid", "whole"), ("dried", "whole"), ("puree", "dried")]
        for a, b in conflicting:
            if (a in f_ing and b in f_usda and a not in f_usda) or \
               (b in f_ing and a in f_usda and b not in f_usda):
                form_pen += 0.15
        if f_ing and f_ing & f_usda:
            form_pen -= 0.1  # explicit form preserved

        # 4. Additive / compound-product drift in USDA descriptors
        desc_text = " " + ", ".join(usda_descs) + " "
        additive_pen = 0.0
        for m in ADDITIVE_MARKERS:
            if m in desc_text and m.strip() not in ing_full:
                additive_pen += 0.18
        # primary noun of USDA being a compound product (patty, pie...) different from ingredient
        for m in ("patty", "nugget", "pie", "soup", "mix"):
            if m in usda_primary and m not in ing_full:
                additive_pen += 0.2

        # 5. Specific-variety mismatch: ingredient names a variety USDA replaces with another
        unmatched_desc = 0
        for d in usda_descs:
            dt = [t for t in _tokens(d) if len(t) > 2]
            if not dt:
                continue
            if any(n in d for n in NEUTRAL_MARKERS):
                continue
            if any(t in ing_full for t in dt):
                continue
            if re.search(r"\d", d) and ("lean" in ing_full or "fat" in ing_full):
                continue
            unmatched_desc += 1
        variety_pen = 0.0
        ing_specifiers = [t for t in ing_core[:-1]] if len(ing_core) > 1 else []
        unmatched_spec = [t for t in ing_specifiers if t not in usda_tok]
        if unmatched_spec and unmatched_desc:
            variety_pen += 0.25  # ingredient variety swapped for a different one
        elif unmatched_spec and not head_noun_hit:
            variety_pen += 0.15
        if not primary_hit and unmatched_desc and r_ing and r_usda and \
                set(r_ing) & set(r_usda):
            # same category, different specific item (e.g. asadero vs colby)
            variety_pen += 0.2
        variety_pen += 0.05 * max(0, unmatched_desc - 1)

        # 6. Dietary qualifiers that alter function (fat content, dairy-free)
        diet_pen = 0.0
        for dm in DIET_MARKERS:
            in_i = dm in ing_full
            in_u = dm.replace("-", "") in usda.replace("-", "") or dm in usda
            if in_u and not in_i:
                diet_pen += 0.08
        if "dairy-free" in ing_full and r_usda.get("dairy_liquid") and \
                "coconut" not in usda and "soy" not in usda and "almond" not in usda:
            diet_pen += 0.3

        # Combine
        score = 0.0
        score += 4.5 * role_sim
        score += 3.0 * anchor
        score += 1.0 if head_noun_hit else 0.0
        score += 0.8 if primary_hit else 0.0
        score -= 6.0 * form_pen
        score -= 5.0 * additive_pen
        score -= 5.0 * variety_pen
        score -= 4.0 * diet_pen
        if r_ing and r_usda and not (set(r_ing) & set(r_usda)) and role_sim < 0.2:
            score -= 2.5  # entirely different culinary role
        if anchor == 0 and not head_noun_hit:
            score -= 1.5

        score = (score + 3.0) / 12.3 * 10.0
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
