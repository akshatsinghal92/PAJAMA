import re

# Form classes and the lexical cues that signal them.
_FORM_CUES = {
    "fresh":   ["fresh", "raw", "uncooked", "leaves", "leaf", "whole"],
    "frozen":  ["frozen", "thawed", "defrosted"],
    "canned":  ["canned", "tinned", "can", "drained", "jarred", "jar", "bottled", "in syrup", "in water", "in brine"],
    "dried":   ["dried", "dry", "dehydrated", "sun-dried", "mature seeds", "freeze-dried"],
    "powder":  ["powder", "powdered", "ground", "granulated", "flour", "starch", "meal"],
    "paste":   ["paste", "puree", "pureed", "concentrate", "concentrated", "pulp", "mashed"],
    "liquid":  ["juice", "nectar", "broth", "stock", "milk", "drink", "beverage", "soup", "sauce", "syrup"],
    "cooked":  ["cooked", "simmered", "boiled", "roasted", "fried", "pan-fried", "baked", "grilled",
                "braised", "steamed", "stewed", "melted", "toasted"],
    "snack":   ["chips", "crisps", "cookies", "cookie", "crackers", "bar", "candy", "cereal"],
    "zest":    ["zest", "peel", "rind"],
}

# Pairwise compatibility between forms (symmetric, 1.0 = same, 0 = incompatible).
_COMPAT = {
    ("fresh", "frozen"): 0.75,
    ("fresh", "canned"): 0.35,
    ("fresh", "dried"): 0.45,
    ("fresh", "powder"): 0.15,
    ("fresh", "paste"): 0.25,
    ("fresh", "liquid"): 0.1,
    ("fresh", "cooked"): 0.55,
    ("fresh", "snack"): 0.0,
    ("fresh", "zest"): 0.2,
    ("frozen", "canned"): 0.4,
    ("frozen", "dried"): 0.2,
    ("frozen", "cooked"): 0.5,
    ("canned", "dried"): 0.4,
    ("canned", "cooked"): 0.6,
    ("canned", "liquid"): 0.4,
    ("canned", "paste"): 0.35,
    ("dried", "powder"): 0.45,
    ("powder", "paste"): 0.3,
    ("paste", "liquid"): 0.2,
    ("cooked", "liquid"): 0.15,
    ("snack", "powder"): 0.0,
}

_STOP = set("""a an the and or of with in on for to from as by nfs ns fat eaten
g kg mg ml l oz lb tsp tbsp cup cups chopped sliced diced minced shredded grated
trimmed visible pieces piece large small medium finely roughly about plus each
separable lean only choice select prime""".split())


def _compat(a, b):
    if a == b:
        return 1.0
    return _COMPAT.get((a, b), _COMPAT.get((b, a), 0.3))


def _norm(s):
    s = (s or "").lower()
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)?\b", " ", s)
    s = s.replace("-", " - ")
    return re.sub(r"\s+", " ", s).strip()


def _forms(text):
    found = set()
    t = " " + re.sub(r"[^a-z\- ]", " ", text) + " "
    t = t.replace(" - ", "-")
    for form, cues in _FORM_CUES.items():
        for c in cues:
            if re.search(r"(?<![a-z])" + re.escape(c) + r"(?![a-z])", t):
                found.add(form)
                break
    return found


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(text):
    out = []
    for w in re.findall(r"[a-z]+", text):
        if w in _STOP or len(w) < 3:
            continue
        out.append(_stem(w))
    return out


def _trigrams(w):
    w = "^" + w + "$"
    return {w[i:i + 3] for i in range(len(w) - 2)}


def _fuzzy(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.85
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return 2.0 * len(ta & tb) / (len(ta) + len(tb))


def _anchor(ing_tokens, primary_tokens, all_tokens):
    """How well the ingredient's food identity appears in the USDA entry.
    Primary (pre-comma) segment weighs more than descriptors."""
    if not ing_tokens or not all_tokens:
        return 0.0, 0.0
    best_primary = 0.0
    total = 0.0
    for t in ing_tokens:
        bp = max((_fuzzy(t, p) for p in primary_tokens), default=0.0)
        ba = max((_fuzzy(t, p) for p in all_tokens), default=0.0)
        best_primary = max(best_primary, bp)
        total += max(ba, bp)
    coverage = total / len(ing_tokens)
    return best_primary, coverage


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient)
        usda = _norm(usda_match)
        if not ing or not usda:
            return 0.0

        # Split ingredient into body / post-comma state / parenthetical.
        paren = " ".join(re.findall(r"\(([^)]*)\)", ing))
        ing_body = re.sub(r"\([^)]*\)", " ", ing)
        ing_main, _, ing_state = ing_body.partition(",")

        usda_parts = [p.strip() for p in usda.split(",") if p.strip()]
        primary = usda_parts[0] if usda_parts else usda

        # ---- Identity gate: does the USDA entry describe the same food? ----
        form_words = set()
        for cues in _FORM_CUES.values():
            for c in cues:
                form_words.update(_stem(x) for x in c.split())
        ing_tok = [t for t in _tokens(ing_main + " " + paren) if t not in form_words] \
            or _tokens(ing_main + " " + paren)
        prim_tok = _tokens(primary)
        all_tok = _tokens(usda)
        prim_tok = prim_tok or all_tok
        best_primary, coverage = _anchor(ing_tok, prim_tok, all_tok)
        # USDA often leads with a category ("Spices", "Beef"), so coverage over
        # the whole description dominates; the primary segment is a small bonus.
        identity = 0.8 * coverage + 0.2 * best_primary
        if coverage < 0.4:
            identity *= 0.6

        # ---- Form matching ----
        ing_forms = _forms(ing_main + " " + ing_state + " " + paren)
        usda_forms = _forms(usda)

        # "thawed" means it was frozen; "melted" recoverable for cheese is not.
        if "thawed" in ing_state or "thawed" in ing_main:
            ing_forms.add("frozen")
        # Absent explicit cue, a plain ingredient is assumed fresh/whole.
        if not ing_forms:
            ing_forms = {"fresh"}
        usda_forms_eff = set(usda_forms) or {"fresh"}

        # Asymmetric best-alignment: each ingredient form finds its best partner.
        align = []
        for f in ing_forms:
            align.append(max(_compat(f, g) for g in usda_forms_eff))
        form_score = sum(align) / len(align)

        # Penalize USDA forms that the ingredient never asked for and that
        # alter concentration/handling (liquid, snack, paste, powder).
        heavy = {"liquid", "snack", "paste", "powder", "zest"}
        extra = (usda_forms - ing_forms) & heavy
        for g in extra:
            if not any(_compat(g, f) >= 0.75 for f in ing_forms):
                form_score -= 0.25
        missing = (ing_forms - usda_forms_eff) & heavy
        for f in missing:
            form_score -= 0.2
        form_score = max(0.0, min(1.0, form_score))

        # Extra unrequested additions in USDA ("with oats", "with granola").
        mods = 0.0
        if re.search(r"\bwith\b", usda) and not re.search(r"\bwith\b", ing):
            mods -= 0.15
        if re.search(r"\bwith\b", ing) and not re.search(r"\bwith\b", usda):
            mods -= 0.15

        raw = identity * (0.35 + 0.65 * form_score) + mods
        score = max(0.0, min(1.0, raw)) * 10.0
        return round(score, 4)
    except Exception:
        return 0.0
