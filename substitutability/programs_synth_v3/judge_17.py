import re

# Preservation / physical-form lexicon: form -> trigger words
_FORM_LEXICON = {
    "fresh": ["fresh", "raw", "uncooked", "unprocessed"],
    "frozen": ["frozen", "thawed", "defrosted", "ice"],
    "canned": ["canned", "tinned", "can", "drained", "in syrup", "in water", "in oil", "in brine"],
    "dried": ["dried", "dry", "dehydrated", "sun-dried", "sundried", "desiccated", "flakes", "flaked", "slices dried"],
    "jarred": ["jarred", "jar", "pickled", "preserved", "marinated"],
    "paste": ["paste", "puree", "pureed", "concentrate", "concentrated", "tube"],
    "powder": ["powder", "powdered", "ground", "granulated", "flour", "meal", "starch"],
    "liquid": ["juice", "broth", "stock", "milk", "sauce", "syrup", "soup", "drink", "beverage", "ready-to-serve", "ready to serve"],
    "cooked": ["cooked", "boiled", "roasted", "baked", "fried", "grilled", "steamed", "smoked", "nfs"],
}

# Forms that can be recovered into one another with no change in the dish
_RECOVERABLE = {
    frozenset(["frozen", "fresh"]): 0.75,
    frozenset(["fresh", "cooked"]): 0.35,
    frozenset(["canned", "jarred"]): 0.7,
    frozenset(["paste", "liquid"]): 0.3,
    frozenset(["dried", "powder"]): 0.55,
    frozenset(["canned", "cooked"]): 0.5,
}

# Strongly incompatible form pairs (water content / concentration changes)
_HARD_CLASH = {
    frozenset(["dried", "fresh"]),
    frozenset(["powder", "fresh"]),
    frozenset(["dried", "liquid"]),
    frozenset(["powder", "liquid"]),
    frozenset(["paste", "fresh"]),
    frozenset(["dried", "frozen"]),
}

_STOP = {"and", "or", "with", "of", "the", "a", "an", "in", "for", "from", "nfs",
         "ns", "to", "as", "low", "fat", "sodium", "lean", "reduced", "plain"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)\b\.?", " ", t)
    return t


def _forms(text):
    found = {}
    padded = " " + re.sub(r"[^a-z\- ]", " ", text) + " "
    for form, words in _FORM_LEXICON.items():
        for w in words:
            if (" " + w + " ") in padded:
                found[form] = found.get(form, 0) + 1
    return found


def _tokens(text):
    toks = re.findall(r"[a-z]+", text)
    out = []
    for t in toks:
        if t in _STOP or len(t) < 3:
            continue
        if t.endswith("ies") and len(t) > 4:
            t = t[:-3] + "y"
        elif t.endswith("es") and len(t) > 4 and t[-3] in "sxz":
            t = t[:-2]
        elif t.endswith("s") and not t.endswith("ss") and len(t) > 3:
            t = t[:-1]
        out.append(t)
    return out


def _all_form_words():
    s = set()
    for ws in _FORM_LEXICON.values():
        for w in ws:
            for p in w.split():
                s.add(p)
    return s


_FORM_WORDS = _all_form_words()


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0

        # Split ingredient into head (before comma / parenthesis) and state tail
        ing_head = re.split(r"[,(]", ing, maxsplit=1)[0]
        usda_parts = [p.strip() for p in usda.split(",") if p.strip()]
        usda_primary = usda_parts[0] if usda_parts else usda

        f_ing = _forms(ing)
        f_usda = _forms(usda)

        # ---- Form agreement component (0..1) ----
        set_i, set_u = set(f_ing), set(f_usda)
        # Ignore the generic "liquid" category if it is the food itself on both sides
        if not set_i and not set_u:
            form_score = 0.7  # both default/fresh-ish; neutral-good
        elif not set_i:
            # Ingredient implies default (fresh) form
            if set_u <= {"fresh", "cooked", "liquid"}:
                form_score = 0.65 if "cooked" not in set_u else 0.4
            else:
                form_score = 0.25
            if set_u & {"dried", "powder", "paste"}:
                form_score = 0.15
        elif not set_u:
            # USDA generic; ingredient states a specific preservation
            if set_i <= {"fresh"}:
                form_score = 0.7
            elif set_i & {"dried", "powder", "paste", "canned", "jarred"}:
                form_score = 0.15
            else:
                form_score = 0.4
        else:
            inter = set_i & set_u
            union = set_i | set_u
            jacc = len(inter) / float(len(union))
            best_pair = 0.0
            clash = False
            for a in set_i:
                for b in set_u:
                    if a == b:
                        best_pair = max(best_pair, 1.0)
                        continue
                    key = frozenset([a, b])
                    if key in _HARD_CLASH:
                        clash = True
                    best_pair = max(best_pair, _RECOVERABLE.get(key, 0.0))
            form_score = 0.55 * best_pair + 0.45 * jacc
            if clash and not inter:
                form_score *= 0.3

        # ---- Food identity anchor (0..1) ----
        ing_food = [t for t in _tokens(ing_head) if t not in _FORM_WORDS]
        usda_food_primary = [t for t in _tokens(usda_primary) if t not in _FORM_WORDS]
        usda_food_all = [t for t in _tokens(usda) if t not in _FORM_WORDS]
        if not ing_food:
            ing_food = _tokens(ing_head)
        iset = set(ing_food)
        if iset:
            hit_all = len(iset & set(usda_food_all)) / float(len(iset))
            hit_primary = 1.0 if iset & set(usda_food_primary) else 0.0
            # partial prefix match (e.g. frankfurter vs frankfurters)
            fuzzy = 0.0
            for a in iset:
                for b in usda_food_all:
                    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b[:4]) and b.startswith(a[:4])):
                        fuzzy = max(fuzzy, 0.5)
            identity = max(hit_all, fuzzy) * 0.7 + hit_primary * 0.3
        else:
            identity = 0.3

        # Extra USDA food words not in ingredient indicate a different product
        extra = [t for t in set(usda_food_all) if t not in iset]
        extra_pen = min(0.3, 0.06 * len(extra))

        # Ingredient lists a compound ("x and y") but USDA names one thing
        compound_pen = 0.0
        if " and " in ing_head and " and " not in usda:
            compound_pen = 0.15

        score = 100.0 * (0.55 * form_score + 0.45 * identity) - 100.0 * (extra_pen * 0.5 + compound_pen)
        # Identity gate: form match is meaningless if foods differ entirely
        if identity < 0.15:
            score *= 0.35
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
