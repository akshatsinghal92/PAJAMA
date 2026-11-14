import re

_GROUPS = {
    "raw": ["raw", "uncooked", "fresh"],
    "fried": ["fried", "frying", "fry", "deep-fried", "battered", "breaded"],
    "baked": ["baked", "bake", "roasted", "roast", "toasted", "toast", "broiled", "grilled", "charbroiled"],
    "wet": ["boiled", "steamed", "simmered", "stewed", "poached", "braised", "blanched", "microwaved"],
    "smoked": ["smoked", "cured"],
    "cooked": ["cooked", "heated", "prepared"],
}

# cost of mismatch between method classes (symmetric)
_COST = {
    ("raw", "fried"): 6, ("raw", "baked"): 5, ("raw", "wet"): 4, ("raw", "smoked"): 4, ("raw", "cooked"): 3,
    ("fried", "baked"): 4, ("fried", "wet"): 5, ("fried", "smoked"): 4, ("fried", "cooked"): 2,
    ("baked", "wet"): 3, ("baked", "smoked"): 3, ("baked", "cooked"): 1.5,
    ("wet", "smoked"): 4, ("wet", "cooked"): 1.5, ("smoked", "cooked"): 2,
}

_FORMS = ["canned", "frozen", "dried", "pickled", "juice", "syrup", "sauce", "salad", "soup", "powder", "flour", "candied"]


def _strip(s):
    s = str(s or "").lower()
    s = re.sub(r"^\s*[\d./]+\s*(g|kg|mg|ml|l|oz|lb)?\b", " ", s)
    return s


def _classes(text):
    words = set(re.findall(r"[a-z\-]+", text))
    res = set()
    for k, lst in _GROUPS.items():
        for w in lst:
            if w in words:
                res.add(k)
                break
    return res


def _norm(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("es"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s"):
        return w[:-1]
    return w


def _cost(a, b):
    if a == b:
        return 0.0
    return float(_COST.get((a, b), _COST.get((b, a), 3)))


def judging_function(ingredient, usda_match):
    try:
        ing = _strip(ingredient)
        usd = _strip(usda_match)
        if not ing.strip() or not usd.strip():
            return 0.0
        ci, cu = _classes(ing), _classes(usd)

        # --- method agreement penalty ---
        if ci and cu:
            pen = min(_cost(a, b) for a in ci for b in cu)
        elif cu:  # ingredient silent -> compatible with raw / generic only
            if cu <= {"raw", "cooked"}:
                pen = 0.0 if "raw" in cu else 1.0
            else:
                pen = min(_cost("raw", b) for b in cu)
        elif ci:
            pen = 0.0 if ci <= {"raw"} else 1.5
        else:
            pen = 0.0

        # --- form / preservation penalty ---
        wi = set(_norm(w) for w in re.findall(r"[a-z]+", ing))
        wu = set(_norm(w) for w in re.findall(r"[a-z]+", usd))
        form_pen = 0.0
        for f in _FORMS:
            nf = _norm(f)
            if (nf in wi) != (nf in wu):
                form_pen += 1.0

        # --- topical overlap (what fraction of USDA head and ingredient words agree) ---
        stop = set("raw cooked fresh and with without the for from only added of or in a type style".split())
        wi -= stop
        wu -= stop
        head = set(_norm(w) for w in re.findall(r"[a-z]+", usd.split(",")[0])) - stop
        inter = wi & wu
        cov_head = len(head & wi) / float(len(head)) if head else 0.0
        cov_ing = len(inter) / float(len(wi)) if wi else 0.0
        topical = 0.5 * cov_head + 0.5 * cov_ing

        score = 4.0 * topical + 6.0 - pen - 1.2 * form_pen
        if not inter:
            score -= 4.0
        return float(score)
    except Exception:
        return 0.0
