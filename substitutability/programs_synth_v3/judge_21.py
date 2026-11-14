import re
import math

# Variant 5: ordinal "physical state" axes.
# Each text is projected onto three continuous axes:
#   moisture      (0 = bone dry powder ... 1 = liquid)
#   concentration (0 = diluted/ready-to-serve ... 1 = concentrated paste/extract)
#   processing    (0 = raw/fresh ... 1 = heavily processed/shelf-stable)
# The form score is a Gaussian-kernel similarity between the two projected
# points, with "recoverable" transitions (frozen->thawed, dried->rehydrated)
# collapsing the distance. A food-identity gate keeps unrelated foods low.

_FORM_LEXICON = {
    # term: (moisture, concentration, processing, weight)
    "fresh": (0.75, 0.3, 0.0, 1.0),
    "raw": (0.75, 0.3, 0.0, 1.0),
    "frozen": (0.75, 0.3, 0.35, 1.0),
    "thawed": (0.75, 0.3, 0.35, 0.8),
    "chilled": (0.75, 0.3, 0.1, 0.5),
    "canned": (0.85, 0.25, 0.75, 1.0),
    "tinned": (0.85, 0.25, 0.75, 1.0),
    "jarred": (0.8, 0.35, 0.7, 1.0),
    "bottled": (0.9, 0.3, 0.7, 0.8),
    "pickled": (0.85, 0.4, 0.75, 1.0),
    "brined": (0.85, 0.4, 0.7, 0.9),
    "drained": (0.7, 0.3, 0.7, 0.5),
    "dried": (0.1, 0.8, 0.7, 1.0),
    "dry": (0.15, 0.7, 0.6, 0.6),
    "dehydrated": (0.05, 0.85, 0.8, 1.0),
    "freeze-dried": (0.05, 0.85, 0.85, 1.0),
    "sun-dried": (0.2, 0.8, 0.7, 1.0),
    "powder": (0.0, 0.9, 0.85, 1.0),
    "powdered": (0.0, 0.9, 0.85, 1.0),
    "ground": (0.05, 0.8, 0.75, 0.9),
    "granules": (0.0, 0.85, 0.85, 1.0),
    "flakes": (0.05, 0.8, 0.8, 0.8),
    "paste": (0.45, 1.0, 0.8, 1.0),
    "puree": (0.6, 0.7, 0.6, 0.9),
    "concentrate": (0.5, 1.0, 0.85, 1.0),
    "concentrated": (0.5, 1.0, 0.85, 1.0),
    "condensed": (0.5, 0.95, 0.85, 1.0),
    "extract": (0.6, 1.0, 0.9, 1.0),
    "evaporated": (0.7, 0.8, 0.85, 0.9),
    "juice": (1.0, 0.3, 0.5, 0.9),
    "broth": (1.0, 0.15, 0.6, 1.0),
    "stock": (1.0, 0.2, 0.6, 1.0),
    "bouillon": (0.2, 1.0, 0.9, 1.0),
    "ready-to-serve": (1.0, 0.05, 0.8, 1.0),
    "ready-to-drink": (1.0, 0.05, 0.8, 1.0),
    "prepared": (0.9, 0.15, 0.7, 0.6),
    "reconstituted": (0.9, 0.2, 0.7, 0.7),
    "syrup": (0.6, 0.85, 0.8, 0.8),
    "smoked": (0.5, 0.5, 0.65, 0.6),
    "cured": (0.45, 0.55, 0.7, 0.7),
    "roasted": (0.3, 0.5, 0.5, 0.5),
    "cooked": (0.7, 0.3, 0.4, 0.4),
    "boiled": (0.8, 0.25, 0.4, 0.4),
    "uncooked": (0.75, 0.3, 0.05, 0.4),
}

_RECOVERABLE = [
    ({"frozen"}, {"thawed", "fresh", "raw"}),
    ({"dried", "dehydrated"}, {"rehydrated", "soaked", "reconstituted"}),
    ({"concentrate", "concentrated", "condensed"}, {"reconstituted", "prepared", "diluted"}),
    ({"canned", "tinned"}, {"drained"}),
]

_STOP = {
    "g", "kg", "mg", "ml", "l", "oz", "lb", "cup", "cups", "tbsp", "tsp", "of", "and",
    "or", "with", "the", "a", "an", "to", "in", "for", "from", "fresh", "raw", "frozen",
    "thawed", "canned", "dried", "chopped", "sliced", "diced", "minced", "large", "small",
    "medium", "whole", "plain", "regular", "cooked", "uncooked", "unprepared", "prepared",
    "tube", "jar", "can", "package", "piece", "pieces", "about", "finely", "roughly",
    "peeled", "trimmed", "grated", "cut", "into", "unsalted", "salted", "added", "without",
    "salt", "ns", "as", "to", "nfs",
}


def _clean(text):
    t = str(text or "").lower()
    t = t.replace("–", "-").replace("—", "-")
    t = re.sub(r"^\s*[\d.,/]+\s*(g|kg|mg|ml|l|oz|lb|grams?)?\b", " ", t)
    t = re.sub(r"\bfreeze[\s-]dried\b", "freeze-dried", t)
    t = re.sub(r"\bsun[\s-]dried\b", "sun-dried", t)
    t = re.sub(r"\bready[\s-]to[\s-]serve\b", "ready-to-serve", t)
    t = re.sub(r"\bready[\s-]to[\s-]drink\b", "ready-to-drink", t)
    t = re.sub(r"\bpur[eé]e[sd]?\b", "puree", t)
    return t


def _words(t):
    out = []
    for w in re.findall(r"[a-z][a-z\-]*", t):
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("oes") and len(w) > 4:
            w = w[:-2]
        elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            w = w[:-1]
        out.append(w)
    return out


def _form_terms(t):
    found = set()
    for term in _FORM_LEXICON:
        if re.search(r"(?<![a-z\-])" + re.escape(term) + r"(?![a-z\-])", t):
            found.add(term)
    if "freeze-dried" in found:
        found.discard("dried")
    if "sun-dried" in found:
        found.discard("dried")
    return found


def _project(terms):
    if not terms:
        return None
    sm = sc = sp = sw = 0.0
    for term in terms:
        m, c, p, w = _FORM_LEXICON[term]
        sm += m * w
        sc += c * w
        sp += p * w
        sw += w
    if sw <= 0:
        return None
    return (sm / sw, sc / sw, sp / sw)


def _recoverable(a, b):
    for src, dst in _RECOVERABLE:
        if (a & src and b & (src | dst)) or (b & src and a & (src | dst)):
            if (a & src and b & dst) or (b & src and a & dst):
                return True
    return False


def _identity(ing_t, usda_t):
    iw = [w for w in _words(re.sub(r"\(.*?\)", " ", ing_t.split(",")[0])) if w not in _STOP]
    uw_all = _words(usda_t)
    uw = [w for w in uw_all if w not in _STOP]
    if not iw or not uw:
        return 0.3
    iset, uset = set(iw), set(uw)
    head = set(_words(usda_t.split(",")[0])) - _STOP
    hit = 0.0
    for w in iset:
        if w in uset:
            hit += 1.0
        elif any(len(w) >= 4 and (u.startswith(w[:4]) and abs(len(u) - len(w)) <= 3) for u in uset):
            hit += 0.6
    recall = hit / len(iset)
    head_hit = 1.0 if (head & iset) else 0.0
    if not head_hit and head:
        for h in head:
            if any(len(h) >= 4 and w.startswith(h[:4]) for w in iset):
                head_hit = 0.6
                break
    precision = len(iset & uset) / max(1, len(uset))
    return max(0.0, min(1.0, 0.5 * recall + 0.35 * head_hit + 0.15 * min(1.0, precision * 2)))


def judging_function(ingredient, usda_match):
    try:
        ing_t = _clean(ingredient)
        usda_t = _clean(usda_match)
        if not ing_t.strip() or not usda_t.strip():
            return 0.0

        ident = _identity(ing_t, usda_t)

        fi = _form_terms(ing_t)
        fu = _form_terms(usda_t)
        pi = _project(fi)
        pu = _project(fu)

        if pi is None and pu is None:
            form = 0.8
        elif pi is None or pu is None:
            # one side silent about form: default ingredient is "fresh-ish"
            other = pu if pi is None else pi
            ref = (0.75, 0.3, 0.1)
            d2 = sum((x - y) ** 2 for x, y in zip(other, ref))
            form = 0.45 + 0.4 * math.exp(-d2 / 0.18)
        else:
            weights = (1.6, 1.3, 0.6)
            d2 = sum(w * (x - y) ** 2 for w, x, y in zip(weights, pi, pu))
            if _recoverable(fi, fu):
                d2 *= 0.15
            form = math.exp(-d2 / 0.12)
            # explicit hard conflicts on water content / delivery
            if ({"powder", "powdered", "granules", "dried", "dehydrated", "bouillon"} & fi) and \
               ({"broth", "stock", "juice", "ready-to-serve"} & fu):
                form *= 0.4
            if ({"broth", "stock", "juice"} & fi) and ({"powder", "powdered", "bouillon", "concentrate", "paste"} & fu):
                form *= 0.4
            if fi & fu:
                form = min(1.0, form + 0.1 * len(fi & fu))

        # oil-roasted vs dry roasted style method conflicts
        if re.search(r"\boil[\s-]roasted\b", ing_t) and re.search(r"\bdry[\s-]roasted\b", usda_t):
            form *= 0.35
        if re.search(r"\bdry[\s-]roasted\b", ing_t) and re.search(r"\boil[\s-]roasted\b", usda_t):
            form *= 0.35

        # fresh herb vs ground spice
        if "spices" in usda_t and ("fresh" in fi or not fi) and not ({"ground", "dried", "powder"} & fi):
            if re.search(r"\b(basil|parsley|cilantro|thyme|rosemary|dill|mint|sage|oregano|ginger|garlic|tarragon|chive)", ing_t):
                form *= 0.45

        # soup vs broth
        if re.search(r"\b(broth|stock)\b", ing_t) and re.search(r"\bsoup\b", usda_t) and "broth" not in usda_t:
            form *= 0.5

        score = 100.0 * (ident ** 1.3) * (0.35 + 0.65 * form)
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
