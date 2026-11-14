import re
import math

# Each physical form is embedded as a point in a 4-D "form space":
#   (moisture, concentration, processing, temperature_handling)
# moisture: 0 = bone dry .. 1 = liquid
# concentration: 0 = diluted .. 1 = highly concentrated
# processing: 0 = raw/whole .. 1 = heavily prepared/composite
# temperature_handling: 0 = ambient shelf .. 1 = frozen
_FORM_SPACE = {
    "fresh":     (0.70, 0.30, 0.00, 0.30),
    "raw":       (0.70, 0.30, 0.00, 0.30),
    "frozen":    (0.70, 0.30, 0.15, 1.00),
    "thawed":    (0.70, 0.30, 0.15, 0.60),
    "canned":    (0.80, 0.30, 0.45, 0.00),
    "jarred":    (0.75, 0.40, 0.45, 0.00),
    "pickled":   (0.80, 0.50, 0.55, 0.00),
    "dried":     (0.10, 0.80, 0.40, 0.00),
    "powder":    (0.02, 0.95, 0.60, 0.00),
    "paste":     (0.40, 0.85, 0.60, 0.10),
    "puree":     (0.75, 0.55, 0.50, 0.10),
    "juice":     (0.95, 0.40, 0.50, 0.20),
    "concentrate": (0.60, 1.00, 0.70, 0.40),
    "condensed": (0.65, 0.95, 0.75, 0.00),
    "soup":      (0.95, 0.20, 0.95, 0.10),
    "broth":     (0.98, 0.15, 0.55, 0.10),
    "cooked":    (0.65, 0.35, 0.40, 0.30),
    "smoked":    (0.50, 0.50, 0.55, 0.20),
    "cured":     (0.40, 0.60, 0.60, 0.10),
}

_LEXICON = [
    (r"\bfresh(ly)?\b", "fresh"),
    (r"\braw\b|\buncooked\b", "raw"),
    (r"\bfrozen\b|\bfreeze\b", "frozen"),
    (r"\bthaw(ed)?\b|\bdefrost(ed)?\b", "thawed"),
    (r"\bcann?ed\b|\btinned\b|\bcan\b|\bdrained solids\b", "canned"),
    (r"\bjar(red)?\b|\bbottled\b", "jarred"),
    (r"\bpickled?\b|\bbrined?\b", "pickled"),
    (r"\bdried\b|\bdry\b|\bdehydrated\b|\bsun-dried\b|\bflakes?\b|\bleaves,? dried\b", "dried"),
    (r"\bpowder(ed)?\b|\bground\b(?!\s+(beef|pork|turkey|chicken|lamb|meat))", "powder"),
    (r"\bpaste\b|\btube\b", "paste"),
    (r"\bpur[eé]e[ed]?\b|\bmashed\b", "puree"),
    (r"\bjuice\b", "juice"),
    (r"\bconcentrate[d]?\b", "concentrate"),
    (r"\bcondensed\b", "condensed"),
    (r"\bsoup\b|\bchowder\b|\bbisque\b|\bready-to-serve\b", "soup"),
    (r"\bbroth\b|\bstock\b|\bbouillon\b", "broth"),
    (r"\bcooked\b|\bboiled\b|\bbraised\b|\broasted\b|\bbaked\b|\bgrilled\b|\bfried\b|\bsteamed\b", "cooked"),
    (r"\bsmoked\b", "smoked"),
    (r"\bcured\b|\bsalted\b", "cured"),
]

_HERB_WORDS = {"sage", "basil", "thyme", "rosemary", "oregano", "parsley", "cilantro",
               "dill", "mint", "tarragon", "chives", "marjoram", "coriander", "ginger",
               "garlic", "bay"}

_STOP = {"g", "kg", "ml", "l", "oz", "lb", "and", "or", "of", "the", "a", "with", "to",
         "chopped", "sliced", "diced", "minced", "shredded", "optional", "large", "small",
         "medium", "whole", "ns", "as", "fat", "eaten", "only", "separable", "lean",
         "drained", "solids", "taste", "for", "from", "into", "pieces", "piece", "cut",
         "finely", "roughly", "grated", "peeled", "trimmed", "new", "imported"}


def _norm(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*[\d.,/]+\s*(g|kg|ml|l|oz|lb|grams?)?\b", " ", t)
    return t


def _forms(text):
    found = []
    for pat, label in _LEXICON:
        try:
            if re.search(pat, text):
                found.append(label)
        except re.error:
            continue
    return found


def _centroid(labels):
    if not labels:
        return None
    acc = [0.0, 0.0, 0.0, 0.0]
    for lab in labels:
        v = _FORM_SPACE.get(lab)
        if v is None:
            continue
        for i in range(4):
            acc[i] += v[i]
    n = float(len(labels))
    return tuple(a / n for a in acc)


def _tokens(text):
    toks = re.findall(r"[a-z]+", text)
    out = set()
    for w in toks:
        if w in _STOP or len(w) < 3:
            continue
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("es") and len(w) > 4 and w[-3] in "sxz":
            w = w[:-2]
        elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            w = w[:-1]
        out.add(w)
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient)
        usd = _norm(usda_match)
        if not ing.strip() or not usd.strip():
            return 0.0

        # Separate ingredient body from parenthetical notes (they still carry form hints)
        paren = " ".join(re.findall(r"\(([^)]*)\)", ing))
        ing_body = re.sub(r"\([^)]*\)", " ", ing)

        ing_forms = _forms(ing_body + " " + paren)
        usd_forms = _forms(usd)

        # Identity anchor: forms only matter if the foods are the same thing.
        ti, tu = _tokens(ing_body), _tokens(usd)
        if ti and tu:
            inter = ti & tu
            # USDA primary food (first comma segment) gets special weight
            head = _tokens(usd.split(",")[0])
            head_hit = 1.0 if (head & ti) else 0.0
            anchor = 0.6 * (len(inter) / float(len(ti))) + 0.4 * head_hit
            if not inter:
                # allow prefix/substring matches (asadero vs queso asadero etc.)
                for a in ti:
                    for b in tu:
                        if len(a) >= 4 and len(b) >= 4 and (a in b or b in a):
                            anchor = max(anchor, 0.5)
        else:
            anchor = 0.0

        # Form-space distance
        ci = _centroid(ing_forms)
        cu = _centroid(usd_forms)
        weights = (1.3, 1.1, 0.8, 0.6)
        if ci is None and cu is None:
            form_sim = 0.8  # neither side specifies form: implicitly the default
        else:
            if ci is None:
                ci = _FORM_SPACE["fresh"]
            if cu is None:
                cu = _FORM_SPACE["fresh"]
            d = math.sqrt(sum(w * (a - b) ** 2 for w, a, b in zip(weights, ci, cu)))
            dmax = math.sqrt(sum(weights))
            form_sim = math.exp(-3.0 * d / dmax)

        # Specific hazard: fresh/unspecified herb in recipe vs ground/dried spice in USDA
        herb_penalty = 0.0
        if (ti & _HERB_WORDS) and ("powder" in usd_forms or "dried" in usd_forms
                                   or usd.startswith("spices")):
            if not ({"powder", "dried"} & set(ing_forms)):
                herb_penalty = 0.35

        # Composite-dish hazard: USDA is soup/condensed while ingredient isn't
        composite_penalty = 0.0
        if ({"soup", "condensed"} & set(usd_forms)) and not ({"soup", "condensed"} & set(ing_forms)):
            composite_penalty = 0.3

        # Exact label agreement bonus (e.g. canned↔canned, cooked/braised↔cooked/braised)
        shared_labels = set(ing_forms) & set(usd_forms)
        label_bonus = min(0.15, 0.08 * len(shared_labels))

        form_score = max(0.0, min(1.0, form_sim + label_bonus - herb_penalty - composite_penalty))

        # Combine multiplicatively: form only rescues when identity is plausible
        score = 10.0 * (0.25 * form_score + 0.75 * form_score * min(1.0, anchor + 0.15)) \
            * (0.35 + 0.65 * min(1.0, anchor))
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
