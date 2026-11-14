import re

# Each axis maps to (negative-pole regexes, positive-pole regexes, weight).
# A side's state on an axis is -1 (negative pole), +1 (positive pole), or 0 (unstated).
_AXES = {
    "sweet": ([r"\bunsweetened\b", r"\bno sugar added\b", r"\bsugar[- ]free\b", r"\bwithout (added )?sugar\b",
               r"\bno added sugar\b", r"\bdiet\b"],
              [r"\bsweetened\b", r"\bsugar added\b", r"\bwith (added )?sugar\b", r"\bin (heavy|light) syrup\b",
               r"\bhoney[- ]?(roasted|glazed)\b", r"\bcandied\b", r"\bnectar\b"], 3.0),
    "salt": ([r"\bunsalted\b", r"\bno salt( added)?\b", r"\bsalt[- ]free\b", r"\bwithout salt\b",
              r"\blow sodium\b", r"\bsodium[- ]free\b", r"\bno sodium\b"],
             [r"\bsalted\b", r"\bwith salt\b", r"\bsalt added\b", r"\bbrined\b"], 3.0),
    "fat_added": ([r"\bno (added )?fat\b", r"\bwithout (added )?fat\b", r"\bfat not added\b"],
                  [r"\bfat added\b", r"\bwith (added )?fat\b", r"\bwith (butter|oil|margarine)\b"], 2.5),
    "fat_level": ([r"\bnon[- ]?fat\b", r"\bfat[- ]free\b", r"\bskim\b", r"\breduced[- ]fat\b", r"\blow[- ]?fat\b",
                   r"\blight\b", r"\blite\b", r"\b\d%\s*milkfat\b", r"\blean\b"],
                  [r"\bfull[- ]fat\b", r"\bwhole milk\b", r"\bregular fat\b", r"\bfull cream\b", r"\b4%\s*milkfat\b"], 2.0),
    "skin": ([r"\bskinless\b", r"\bwithout skin\b", r"\bno skin\b", r"\bmeat only\b", r"\bskin removed\b", r"\bpeeled\b"],
             [r"\bwith skin\b", r"\bskin[- ]on\b", r"\bskin only\b", r"\bmeat and skin\b", r"\bunpeeled\b",
              r"\bpoultry skin\b", r"\bskin\b"], 2.5),
    "bone": ([r"\bboneless\b", r"\bdeboned\b", r"\bwithout bones?\b", r"\bfillets?\b"],
             [r"\bbone[- ]in\b", r"\bwith bones?\b", r"\bbones? included\b"], 2.5),
    "hull": ([r"\bhulled\b", r"\bshelled\b", r"\bkernels?\b", r"\bdehulled\b", r"\bpearled\b"],
             [r"\bunhulled\b", r"\bin shell\b", r"\bwith shells?\b", r"\bin-shell\b", r"\bwhole seeds?\b"], 2.0),
    "seed": ([r"\bseedless\b", r"\bseeds? removed\b", r"\bpitted\b", r"\bwithout (seeds|pits?)\b"],
             [r"\bwith seeds\b", r"\bseeded\b", r"\bwith pits?\b", r"\bunpitted\b"], 2.0),
    "caffeine": ([r"\bdecaf(feinated)?\b", r"\bcaffeine[- ]free\b", r"\bwithout caffeine\b"],
                 [r"\bcaffeinated\b", r"\bregular\b", r"\bwith caffeine\b"], 2.5),
    "dairy": ([r"\bvegan\b", r"\bdairy[- ]free\b", r"\bnon[- ]?dairy\b", r"\blactose[- ]free\b", r"\bplant[- ]based\b",
               r"\btofu\b", r"\bsoy\b"],
              [r"\bwith (milk|cream|butter)\b", r"\bdairy\b", r"\bmade with (milk|egg)s?\b"], 1.5),
    "gluten": ([r"\bgluten[- ]free\b", r"\bwithout gluten\b"], [r"\bwheat\b", r"\bwith gluten\b"], 1.5),
    "alcohol": ([r"\bnon[- ]?alcoholic\b", r"\balcohol[- ]free\b"], [r"\balcoholic\b", r"\bwith alcohol\b"], 2.0),
    "cooked": ([r"\braw\b", r"\buncooked\b", r"\bfresh\b"],
               [r"\bcooked\b", r"\bboiled\b", r"\broasted\b", r"\bfried\b", r"\bbaked\b", r"\bgrilled\b",
                r"\bsteamed\b", r"\bbraised\b", r"\bmoist heat\b", r"\bdry heat\b"], 1.5),
}

_COMPILED = {k: ([re.compile(p) for p in neg], [re.compile(p) for p in pos], w)
             for k, (neg, pos, w) in _AXES.items()}

# Generic un-/non- prefix pairing, catches words outside the explicit table.
_PREFIX_RE = re.compile(r"\b(un|non[- ]?)([a-z]{4,})\b")


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)\b\.?", " ", t)
    t = t.replace("(", " ").replace(")", " ")
    t = re.sub(r"[^a-z0-9%\s,\-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _state(text, neg_pats, pos_pats):
    # Negative-pole patterns are checked first and their spans are blanked so that,
    # e.g., "unsweetened" does not also fire the positive "sweetened" pattern.
    neg_hits = 0
    scratch = text
    for p in neg_pats:
        if p.search(scratch):
            neg_hits += 1
            scratch = p.sub(" ", scratch)
    pos_hits = sum(1 for p in pos_pats if p.search(scratch))
    if neg_hits and not pos_hits:
        return -1
    if pos_hits and not neg_hits:
        return 1
    if neg_hits and pos_hits:
        return -1 if neg_hits >= pos_hits else 1
    return 0


def _prefix_conflicts(a, b):
    # Find words like "unhulled"/"hulled", "nonalcoholic"/"alcoholic" appearing in opposite forms.
    conflicts = 0
    a_words = set(re.findall(r"[a-z]+", a))
    b_words = set(re.findall(r"[a-z]+", b))
    for src, other_words, other in ((a, b_words, b), (b, a_words, a)):
        for m in _PREFIX_RE.finditer(src):
            root = m.group(2)
            if root in other_words and not re.search(r"\b(un|non[- ]?)" + re.escape(root) + r"\b", other):
                conflicts += 1
    return conflicts


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usd = _clean(usda_match)
        if not ing or not usd:
            return 0.0

        contradiction = 0.0
        agreement = 0.0
        one_sided = 0
        for name, (neg, pos, w) in _COMPILED.items():
            si = _state(ing, neg, pos)
            su = _state(usd, neg, pos)
            if si and su:
                if si * su < 0:
                    contradiction += w
                else:
                    agreement += w
            elif si or su:
                one_sided += 1

        contradiction += 2.0 * _prefix_conflicts(ing, usd)

        # Light anchor on the primary food so polarity checks are about the same thing.
        ing_tokens = set(t for t in re.findall(r"[a-z]{3,}", ing))
        head = usd.split(",")[0].strip()
        head_tokens = set(re.findall(r"[a-z]{3,}", head))
        stem = lambda w: w[:-1] if w.endswith("s") and len(w) > 3 else w
        ing_st = set(stem(t) for t in ing_tokens)
        head_st = set(stem(t) for t in head_tokens)
        anchor = (len(ing_st & head_st) / len(head_st)) if head_st else 0.0
        all_st = set(stem(t) for t in re.findall(r"[a-z]{3,}", usd))
        overall = (len(ing_st & all_st) / len(ing_st)) if ing_st else 0.0

        # Multiplicative penalty: each unit of contradiction shrinks the score geometrically.
        base = 4.0 + 3.0 * anchor + 2.0 * overall
        score = base * (0.55 ** contradiction) + 0.4 * min(agreement, 5.0) - 0.05 * one_sided
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
