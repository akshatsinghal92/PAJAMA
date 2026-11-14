import re

# Qualifier ledger approach: build a ledger of "qualifier concepts" on each side,
# map surface words to canonical concepts, then reconcile the ledgers.
# Score = anchor credit - cost(extra USDA qualifiers) - cost(dropped ingredient qualifiers).

_CONCEPTS = {
    # processing / state
    "raw": "state:raw", "fresh": "state:raw", "uncooked": "state:raw",
    "dried": "state:dried", "dry": "state:dried", "dehydrated": "state:dried",
    "dehydrate": "state:dried", "sundried": "state:dried",
    "cooked": "state:cooked", "boiled": "state:cooked", "steamed": "state:cooked",
    "simmered": "state:cooked", "stewed": "state:cooked", "braised": "state:cooked",
    "poached": "state:cooked", "moist": "state:cooked",
    "roasted": "state:roasted", "baked": "state:roasted", "grilled": "state:roasted",
    "broiled": "state:roasted", "toasted": "state:roasted",
    "fried": "state:fried", "breaded": "state:fried",
    "frozen": "state:frozen", "canned": "state:canned", "jarred": "state:canned",
    "smoked": "state:smoked", "cured": "state:cured", "pickled": "state:pickled",
    "salted": "state:salted", "fermented": "state:fermented",
    # flavour / formulation modifiers diners notice
    "sweetened": "mod:sweet", "sugar": "mod:sweet", "syrup": "mod:sweet",
    "unsweetened": "mod:unsweet",
    "diet": "mod:diet", "light": "mod:diet", "lowfat": "mod:diet", "reduced": "mod:diet",
    "nonfat": "mod:diet", "fatfree": "mod:diet",
    "flavored": "mod:flavored", "seasoned": "mod:flavored", "spiced": "mod:flavored",
    "iced": "mod:beverage", "bottled": "mod:beverage", "beverage": "mod:beverage",
    "drink": "mod:beverage", "brewed": "mod:beverage", "instant": "mod:instant",
    "mix": "mod:mix", "prepared": "mod:prepared", "imitation": "mod:imitation",
    "substitute": "mod:imitation", "extra": "mod:premium", "virgin": "mod:premium",
    "organic": "mod:soft",
    # physical form / part
    "zest": "form:peel", "peel": "form:peel", "rind": "form:peel",
    "juice": "form:juice", "concentrate": "form:juice",
    "crumbs": "form:crumb", "crumb": "form:crumb", "breadcrumbs": "form:crumb",
    "powder": "form:powder", "ground": "form:powder", "flour": "form:powder",
    "paste": "form:paste", "puree": "form:paste", "sauce": "form:sauce",
    "seeds": "form:seed", "seed": "form:seed", "kernels": "form:seed",
    "skin": "form:skin", "tongue": "form:tongue", "liver": "form:liver",
    "heart": "form:heart", "kidney": "form:kidney", "tail": "form:tail",
    "tails": "form:tail", "wing": "form:wing", "wings": "form:wing",
    "breast": "form:breast", "thigh": "form:thigh", "leg": "form:leg",
    "patty": "form:patty", "sausage": "form:sausage", "oil": "form:oil",
    "chips": "form:chip", "flakes": "form:flake", "rings": "form:slice",
    "slices": "form:slice", "sliced": "form:slice",
}

# USDA filler descriptors that do not represent a diner-noticeable qualifier
_NEUTRAL = set("""
mixed species wild farmed whole all commercial grades includes include and or with
without nfs ns as to form not further specified separable lean fat trimmed
heat enriched unenriched variety meats byproducts by products regular plain
type usda commodity food service retail made from also known solids liquids
drained raw light dark choice select prime u.s. us inch the of in a for
""".split())

_PREP_WORDS = set("""
chopped minced diced sliced grated shredded thawed peeled halved quartered cubed
crushed finely roughly coarsely thinly large small medium about approximately
cup cups tbsp tsp tablespoon teaspoon g gram grams kg ml l oz lb pinch handful
to taste optional softened melted divided rinsed trimmed packed loosely firmly
room temperature cold warm hot tube from of the a an for into pieces piece
""".split())

# "dried", "fresh" etc. inside the ingredient that a diner cares about are kept via _CONCEPTS


def _norm(word):
    w = word.lower().strip()
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _words(text):
    text = text.lower().replace("-", " ")
    return re.findall(r"[a-z]+", text)


def _clean_ingredient(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*[\d.,/]+\s*(g|kg|mg|ml|l|oz|lb|grams?)?\b", " ", t)
    t = re.sub(r"\d+(\.\d+)?", " ", t)
    return t


def _concept_ledger(words):
    ledger = set()
    for w in words:
        c = _CONCEPTS.get(w) or _CONCEPTS.get(_norm(w))
        if c:
            ledger.add(c)
    return ledger


def _cost(concept, side):
    kind = concept.split(":", 1)[0]
    if concept == "mod:soft":
        return 0.3
    if side == "extra":
        # qualifier USDA adds that the ingredient never asked for
        return {"mod": 2.6, "form": 2.4, "state": 1.3}.get(kind, 1.0)
    # qualifier the ingredient specified that the USDA entry drops
    return {"mod": 1.8, "form": 3.0, "state": 1.1}.get(kind, 1.0)


_STATE_COMPAT = {
    frozenset(["state:raw", "state:frozen"]),
    frozenset(["state:cooked", "state:roasted"]),
    frozenset(["state:salted", "state:fermented"]),
    frozenset(["state:salted", "state:cured"]),
    frozenset(["state:smoked", "state:cured"]),
    frozenset(["form:slice", "state:dried"]),
}


def judging_function(ingredient, usda_match):
    try:
        ing_raw = str(ingredient or "")
        usda_raw = str(usda_match or "")
        if not ing_raw.strip() or not usda_raw.strip():
            return 0.0

        ing_text = _clean_ingredient(ing_raw)
        ing_main, _, ing_state = ing_text.partition(",")
        ing_words_all = _words(ing_text)
        ing_core = [w for w in _words(ing_main) if w not in _PREP_WORDS]
        if not ing_core:
            ing_core = [w for w in ing_words_all if w not in _PREP_WORDS]
        if not ing_core:
            return 0.0

        usda_clean = re.sub(r"\([^)]*\)", " ", usda_raw.lower())
        segments = [s.strip() for s in usda_clean.split(",") if s.strip()]
        if not segments:
            return 0.0
        usda_words = _words(usda_clean)
        usda_norm = set(_norm(w) for w in usda_words)
        paren = " ".join(re.findall(r"\(([^)]*)\)", usda_raw.lower()))
        paren_norm = set(_norm(w) for w in _words(paren))

        # ---- anchor: does the ingredient's head noun appear in USDA? ----
        ing_concept_words = set(w for w in ing_core if _CONCEPTS.get(w) or _CONCEPTS.get(_norm(w)))
        nouns = [w for w in ing_core if w not in ing_concept_words] or ing_core
        head = _norm(nouns[-1])
        noun_norms = [_norm(w) for w in nouns]

        def present(tok):
            if tok in usda_norm or tok in paren_norm:
                return True
            for u in usda_norm | paren_norm:
                if len(tok) >= 4 and len(u) >= 4 and (u.startswith(tok[:5]) or tok.startswith(u[:5])):
                    return True
            return False

        head_hit = present(head)
        noun_hits = sum(1 for t in noun_norms if present(t))
        primary_words = set(_norm(w) for w in _words(segments[0]))
        head_in_primary = head in primary_words or any(
            len(head) >= 4 and (p.startswith(head[:5]) or head.startswith(p[:5])) for p in primary_words if len(p) >= 4
        )
        any_primary = any(t in primary_words for t in noun_norms) or head_in_primary

        if head_hit and (head_in_primary or any_primary):
            anchor = 5.0
        elif head_hit:
            anchor = 3.8
        elif noun_hits:
            anchor = 2.0 + 0.8 * noun_hits / max(1, len(noun_norms))
        else:
            anchor = 0.3

        # ---- qualifier ledgers ----
        ing_ledger = _concept_ledger(ing_words_all)
        usda_ledger = _concept_ledger(usda_words)
        # concepts that are just the head noun itself (e.g. "oil" in "olive oil") are not qualifiers
        head_concept = _CONCEPTS.get(head)
        if head_concept:
            ing_ledger.discard(head_concept)
            usda_ledger.discard(head_concept)
        # raw/fresh is the USDA default; an unstated state on the ingredient implies raw
        if not any(c.startswith("state:") for c in ing_ledger):
            ing_ledger.add("state:raw")

        extra = usda_ledger - ing_ledger
        dropped = ing_ledger - usda_ledger

        # forgive compatible state pairs
        for a in list(extra):
            for b in list(dropped):
                if frozenset([a, b]) in _STATE_COMPAT:
                    extra.discard(a)
                    dropped.discard(b)
                    break

        # USDA silently omits "raw" often; dropping raw is very cheap
        penalty = 0.0
        for c in extra:
            penalty += _cost(c, "extra")
        for c in dropped:
            penalty += 0.2 if c == "state:raw" else _cost(c, "dropped")

        # ---- unknown residual descriptors in USDA (generic vs specific) ----
        ing_norm_all = set(_norm(w) for w in ing_words_all)
        residual = 0
        for seg in segments[1:]:
            seg_words = [_norm(w) for w in _words(seg)]
            if not seg_words:
                continue
            if all(w in _NEUTRAL or w in ing_norm_all or
                   (_CONCEPTS.get(w)) for w in seg_words):
                continue
            residual += 1
        specificity_cost = 0.35 * max(0, residual - 1)

        # ingredient specifies a variant word (non-head noun) that USDA lacks
        variant_missing = sum(1 for t in noun_norms[:-1] if not present(t) and t not in _NEUTRAL)
        variant_cost = 0.9 * variant_missing

        # alignment bonus: USDA echoes ingredient's own qualifiers
        echoed = len(ing_ledger & usda_ledger - {"state:raw"})
        bonus = 0.6 * echoed

        score = anchor + bonus - penalty - specificity_cost - variant_cost
        if anchor < 1.0:
            score = min(score, 1.0)
        score = max(0.0, min(10.0, score * 1.6 + 1.0))
        return round(score, 4)
    except Exception:
        return 0.0
