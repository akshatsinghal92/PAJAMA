import re

_STOP = set("a an the and or of with in from for to as g kg oz lb ml cup cups tbsp tsp fresh raw nfs type all grades".split())

# attribute -> (positive cue patterns, negative cue patterns)
_ATTRS = {
    "salt": ([r"\bsalted\b", r"\bwith salt\b", r"\bsalt added\b"], [r"\bunsalted\b", r"\bno salt\b", r"\bwithout salt\b", r"\bsalt[- ]free\b", r"\bno added salt\b", r"\blow sodium\b", r"\bsodium[- ]free\b"]),
    "sugar": ([r"\bsweetened\b", r"\bwith sugar\b", r"\bsugar added\b"], [r"\bunsweetened\b", r"\bno sugar\b", r"\bwithout sugar\b", r"\bsugar[- ]free\b", r"\bno added sugar\b"]),
    "skin": ([r"\bwith skin\b", r"\bskin[- ]on\b", r"\bskin\b(?!less)"], [r"\bskinless\b", r"\bwithout skin\b", r"\bskin removed\b", r"\bpeeled\b"]),
    "bone": ([r"\bbone[- ]in\b", r"\bwith bone\b", r"\bbone\b(?!less)"], [r"\bboneless\b", r"\bwithout bone\b", r"\bbone removed\b"]),
    "seed": ([r"\bwith seeds?\b", r"\bseeded\b"], [r"\bseedless\b", r"\bwithout seeds?\b", r"\bseeds? removed\b"]),
    "hull": ([r"\bunhulled\b", r"\bin shell\b", r"\bwith shell\b", r"\bwith hulls?\b"], [r"\bhulled\b", r"\bshelled\b", r"\bdehulled\b"]),
    "caf": ([r"\bcaffeinated\b", r"\bregular\b", r"\bwith caffeine\b"], [r"\bdecaf\w*\b", r"\bdecaffeinated\b", r"\bcaffeine[- ]free\b", r"\bwithout caffeine\b"]),
    "fat": ([r"\bfat added\b", r"\bwith added fat\b", r"\bseparable lean and fat\b", r"\bfull[- ]fat\b", r"\bwhole\b", r"\bregular fat\b"],
            [r"\bno added fat\b", r"\bfat[- ]free\b", r"\bnonfat\b", r"\bnon-fat\b", r"\bseparable lean only\b", r"\bwithout fat\b", r"\bfat removed\b", r"\blean\b", r"\blow[- ]?fat\b", r"\breduced fat\b", r"\bskim\b", r"\btrimmed\b"]),
    "cal": ([r"\bregular\b"], [r"\breduced calorie\b", r"\blow calorie\b", r"\bdiet\b", r"\blight\b", r"\blite\b"]),
    "cook": ([r"\bcooked\b", r"\bbaked\b", r"\bfried\b", r"\broasted\b", r"\btoasted\b", r"\bboiled\b", r"\bgrilled\b", r"\bsteamed\b", r"\bpan-fried\b"], [r"\braw\b", r"\buncooked\b", r"\bfresh\b"]),
    "freeze": ([r"\bfrozen\b"], [r"\bfresh\b", r"\bthawed\b", r"\bunfrozen\b"]),
    "dry": ([r"\bdried\b", r"\bdry\b", r"\bdehydrated\b"], [r"\bwet\b", r"\bfresh\b", r"\bcanned\b"]),
    "gluten": ([r"\bwith gluten\b"], [r"\bgluten[- ]free\b", r"\bwithout gluten\b"]),
}
_STRONG = {"salt": 1.0, "sugar": 1.0, "skin": 1.0, "bone": 1.0, "seed": 1.0, "hull": 1.0, "caf": 1.0,
           "fat": 0.6, "cal": 0.6, "cook": 0.5, "freeze": 0.3, "dry": 0.4, "gluten": 1.0}


def _clean(s):
    s = str(s or "").lower()
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|oz|lb|ml)?\b", " ", s)
    s = s.replace("’", "'")
    return s


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(s):
    ws = re.findall(r"[a-z]+", s)
    return [_stem(w) for w in ws if w not in _STOP and len(w) > 1]


def _polarity(text, attr):
    pos, neg = _ATTRS[attr]
    n = any(re.search(p, text) for p in neg)
    p_txt = text
    for p in neg:
        p_txt = re.sub(p, " ", p_txt)
    p = any(re.search(q, p_txt) for q in pos)
    if n and not p:
        return -1
    if p and not n:
        return 1
    return 0


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usd = _clean(usda_match)
        if not ing.strip() or not usd.strip():
            return 0.0
        # --- behavior / polarity component ---
        pen = 0.0
        agree = 0.0
        for a in _ATTRS:
            pi, pu = _polarity(ing, a), _polarity(usd, a)
            if pi != 0 and pu != 0:
                if pi != pu:
                    pen += _STRONG[a]
                else:
                    agree += 0.3 * _STRONG[a]
        # --- similarity component ---
        ing_main = re.sub(r"\([^)]*\)", " ", ing).split(",")[0]
        ti = set(_tokens(ing_main)) | set(_tokens(ing))
        head_i = _tokens(ing_main)
        usd_parts = usd.split(",")
        tu = set(_tokens(usd))
        tu_head = set(_tokens(usd_parts[0]))
        if not ti or not tu:
            return 0.0
        inter = ti & tu
        recall = len(inter) / len(ti)
        prec = len(inter) / len(tu)
        # head noun of ingredient (last token of main phrase) should appear in usda
        head = head_i[-1] if head_i else None
        head_hit = 1.0 if head and head in tu else 0.0
        first_hit = 1.0 if head and head in tu_head else 0.0
        # ingredient first noun in USDA head?
        any_head = 1.0 if (set(head_i) & tu_head) else 0.0
        sim = 4.0 * recall + 1.5 * prec + 2.0 * head_hit + 1.0 * first_hit + 1.0 * any_head
        # extra USDA qualifiers absent from the ingredient (mild)
        extra = [w for w in tu - ti]
        flag = {"vegetable", "blend", "imported", "flavored", "sweet", "mixed", "fortified"}
        extra_pen = 0.15 * len([w for w in extra if w in flag])
        # state words in ingredient demanded but absent in usda
        missing_state = 0.0
        for w in ("toasted", "lean", "ground", "smoked", "pickled", "roasted"):
            if re.search(r"\b" + w + r"\b", ing) and not re.search(r"\b" + w + r"\b", usd):
                missing_state += 0.5
        score = sim + agree - 3.0 * pen - extra_pen - missing_state
        return float(score)
    except Exception:
        return 0.0
