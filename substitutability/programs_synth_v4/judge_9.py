import re

# Form/preservation state lexicon: state -> trigger words
_FORM_LEXICON = {
    "fresh": ["fresh", "raw", "uncooked"],
    "frozen": ["frozen"],
    "canned": ["canned", "tinned", "can"],
    "dried": ["dried", "dehydrated", "dry", "chips", "sun-dried", "freeze-dried", "jerky"],
    "pickled": ["pickled", "brined", "marinated", "jarred", "jar"],
    "smoked": ["smoked", "cured", "kippered"],
    "paste": ["paste", "puree", "pureed", "concentrate", "concentrated"],
    "powder": ["powder", "powdered", "ground", "granulated"],
    "cooked": ["cooked", "baked", "roasted", "boiled", "braised", "fried", "grilled",
               "broiled", "steamed", "stewed", "dry heat", "moist heat", "pan-broiled",
               "simmered", "microwaved", "leftover"],
    "liquid": ["broth", "stock", "juice", "soup", "ready-to-serve", "prepared", "reconstituted"],
}

# Pairs of forms that are recoverable / compatible (symmetric)
_COMPATIBLE = {
    frozenset(["fresh", "frozen"]): 0.75,
    frozenset(["cooked", "fresh"]): 0.15,
    frozenset(["cooked", "frozen"]): 0.25,
    frozenset(["smoked", "pickled"]): 0.2,
    frozenset(["paste", "liquid"]): 0.35,
    frozenset(["powder", "dried"]): 0.6,
    frozenset(["canned", "pickled"]): 0.5,
    frozenset(["canned", "cooked"]): 0.45,
}

_STOP = set("""and or with without of the a an for in on to from plain optional serving
garnish nfs ns other style type made added salt sodium low lean fat fresh frozen raw
cooked whole large small medium piece pieces sliced diced chopped cubed minced
leaves leaf fillets fillet segments""".split())


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)\b", " ", t)
    t = t.replace("-", " - ").replace("/", " ")
    return t


def _ingredient_parts(ing):
    t = _clean(ing)
    paren = " ".join(re.findall(r"\(([^)]*)\)", t))
    t = re.sub(r"\([^)]*\)", " ", t)
    head, _, tail = t.partition(",")
    return head.strip(), tail.strip(), paren.strip()


def _forms(text):
    found = set()
    padded = " " + re.sub(r"[^a-z0-9% \-]", " ", text) + " "
    padded = padded.replace(" - ", "-")
    for state, words in _FORM_LEXICON.items():
        for w in words:
            if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", padded):
                found.add(state)
                break
    return found


def _tokens(text):
    words = re.findall(r"[a-z]+", text)
    out = set()
    for w in words:
        if len(w) < 3 or w in _STOP:
            continue
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("es") and len(w) > 4 and w[-3] in "sxz":
            w = w[:-2]
        elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            w = w[:-1]
        out.add(w)
    return out


def _form_pair_score(a, b):
    if a == b:
        return 1.0
    return _COMPATIBLE.get(frozenset([a, b]), 0.0)


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        head, tail, paren = _ingredient_parts(ingredient)
        usda = _clean(usda_match)
        usda_segs = [s.strip() for s in usda.split(",") if s.strip()]
        if not usda_segs:
            return 0.0
        primary = usda_segs[0]

        # --- Identity anchor: does the food itself line up? ---
        ing_tok = _tokens(head)
        usda_tok = _tokens(usda)
        prim_tok = _tokens(primary)
        if not ing_tok:
            ing_tok = _tokens(tail)
        shared = ing_tok & usda_tok
        identity = len(shared) / max(1, len(ing_tok))
        primary_hit = 1.0 if (ing_tok & prim_tok) else 0.0
        if not shared:
            # no recognisable food overlap: form matching is moot
            return round(5.0 * min(1.0, 0.0), 3)

        # --- Form/preservation states ---
        # Ingredient "native" form comes from the head; post-comma "thawed",
        # "drained" etc. describe recovery, not the purchased form.
        ing_forms = _forms(head + " " + paren)
        tail_forms = _forms(tail)
        if "thawed" in tail and "frozen" not in ing_forms:
            ing_forms.add("frozen")
        if "cooked" in tail_forms and not ing_forms:
            ing_forms.add("cooked")
        usda_forms = _forms(" ".join(usda_segs[1:]) + " " + primary)

        # "raw or frozen" style entries cover both states
        if "fresh" in usda_forms and "frozen" in usda_forms:
            usda_forms_eff = usda_forms | {"fresh", "frozen"}
        else:
            usda_forms_eff = usda_forms

        if not ing_forms and not usda_forms_eff:
            form_score = 0.85
        elif not ing_forms:
            # unspecified ingredient -> assume default purchase state (fresh/raw)
            if usda_forms_eff <= {"fresh", "frozen", "powder", "liquid"}:
                form_score = 0.8
            elif "cooked" in usda_forms_eff:
                form_score = 0.35
            else:
                form_score = 0.45
        elif not usda_forms_eff:
            form_score = 0.6 if ing_forms <= {"fresh", "powder", "liquid"} else 0.4
        else:
            # best-match alignment: each ingredient form finds its best USDA form
            per = []
            for f in ing_forms:
                per.append(max(_form_pair_score(f, g) for g in usda_forms_eff))
            form_score = sum(per) / len(per)
            # penalise extra USDA processing states the ingredient didn't ask for
            extra = usda_forms_eff - ing_forms
            heavy = extra & {"cooked", "pickled", "smoked", "dried", "canned"}
            if heavy and not ("thawed" in tail and heavy == set()):
                form_score *= 0.6 ** len(heavy)

        # concentration-altering mismatches (broth vs soup, herb vs dried spice)
        if ("broth" in head or "stock" in head) and "soup" in usda:
            form_score *= 0.4
        if "fresh" in ing_forms and "spices" in primary:
            form_score *= 0.3

        score = 10.0 * (0.55 * form_score + 0.3 * identity + 0.15 * primary_hit)
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
