import re

# Attribute polarity lexicon: attribute -> (negative-pole patterns, positive-pole patterns)
_POLARITY_AXES = {
    "fat": (
        [r"\bno (?:added )?fat\b", r"\bfat[- ]free\b", r"\bnonfat\b", r"\bnon[- ]fat\b",
         r"\bwithout (?:added )?fat\b", r"\bskim(?:med)?\b"],
        [r"\bfat added\b", r"\bwith (?:added )?fat\b", r"\bfull[- ]fat\b", r"\bwhole milk\b"],
    ),
    "salt": (
        [r"\bunsalted\b", r"\bwithout salt\b", r"\bno salt(?: added)?\b", r"\bsalt[- ]free\b",
         r"\blow sodium\b", r"\bsodium[- ]free\b"],
        [r"(?<!un)\bsalted\b", r"\bwith salt\b", r"\bsalt added\b", r"\bbrined\b"],
    ),
    "sugar": (
        [r"\bunsweetened\b", r"\bno sugar(?: added)?\b", r"\bsugar[- ]free\b",
         r"\bwithout (?:added )?sugar\b", r"\bdiet\b"],
        [r"(?<!un)\bsweetened\b", r"\bsugar added\b", r"\bwith (?:added )?sugar\b",
         r"\bsyrup\b", r"\bsweet\b", r"\bcandied\b", r"\bnectar\b", r"\bhoney\b"],
    ),
    "skin": (
        [r"\bskinless\b", r"\bwithout skin\b", r"\bskin removed\b", r"\bpeeled\b", r"\bmeat only\b"],
        [r"\bwith skin\b", r"\bskin[- ]on\b", r"\bunpeeled\b", r"\bmeat and skin\b"],
    ),
    "bone": (
        [r"\bboneless\b", r"\bdeboned\b", r"\bwithout bone\b", r"\bfillets?\b"],
        [r"\bbone[- ]in\b", r"\bwith bone\b", r"\bbones? included\b"],
    ),
    "hull": (
        [r"\bhulled\b", r"\bshelled\b", r"\bkernels?\b", r"\bwithout shell\b"],
        [r"\bunhulled\b", r"\bin shell\b", r"\bwith shell\b", r"\bunshelled\b"],
    ),
    "seed": (
        [r"\bseedless\b", r"\bseeded\b", r"\bwithout seeds\b", r"\bpitted\b"],
        [r"\bwith seeds\b", r"\bseeds? in\b", r"\bunpitted\b", r"\bwith pits?\b"],
    ),
    "caffeine": (
        [r"\bdecaf(?:feinated)?\b", r"\bcaffeine[- ]free\b", r"\bwithout caffeine\b"],
        [r"\bregular\b(?=.*\b(?:coffee|tea|cola)\b)", r"\bcaffeinated\b", r"\bwith caffeine\b"],
    ),
    "cook": (
        [r"\braw\b", r"\buncooked\b", r"\bfresh\b"],
        [r"\bcooked\b", r"\bboiled\b", r"\broasted\b", r"\btoasted\b", r"\bfried\b",
         r"\bbaked\b", r"\bgrilled\b", r"\bsmoked\b"],
    ),
    "moisture": (
        [r"\bdried\b", r"\bdry\b", r"\bdehydrated\b", r"\bpowder(?:ed)?\b"],
        [r"\bliquid\b", r"\bfluid\b", r"\bjuice\b", r"\bnectar\b", r"\bcream\b(?! powder)"],
    ),
    "calorie": (
        [r"\breduced calorie\b", r"\blight\b", r"\blite\b", r"\blow[- ]?calorie\b", r"\blow[- ]?fat\b"],
        [r"\bregular\b", r"\bfull\b", r"\bwhole\b"],
    ),
}

# Weight of a contradiction per axis (core axes named in the rubric weigh more)
_AXIS_WEIGHT = {
    "fat": 3.0, "salt": 3.0, "sugar": 3.0, "skin": 3.0, "bone": 3.0, "hull": 2.5,
    "seed": 2.5, "caffeine": 3.0, "cook": 1.5, "moisture": 2.0, "calorie": 2.0,
}

_STOP = {"and", "or", "with", "without", "of", "the", "a", "in", "for", "from", "nfs", "ns",
         "raw", "fresh", "to", "as", "on", "g", "kg", "ml"}


def _normalize(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(?:\.\d+)?\s*(?:g|kg|ml|l|oz|lb)\b\.?", " ", t)
    paren = " ".join(re.findall(r"\(([^)]*)\)", t))
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t + " " + paren
    t = re.sub(r"[^a-z0-9\s\-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _poles(text):
    """Return dict axis -> set of poles ('neg'/'pos') present in the text."""
    found = {}
    for axis, (neg, pos) in _POLARITY_AXES.items():
        hit = set()
        for p in neg:
            if re.search(p, text):
                hit.add("neg")
                break
        for p in pos:
            if re.search(p, text):
                hit.add("pos")
                break
        if hit:
            found[axis] = hit
    return found


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(text):
    return {_stem(w) for w in re.findall(r"[a-z]+", text) if w not in _STOP and len(w) > 2}


def judging_function(ingredient, usda_match):
    try:
        ing = _normalize(ingredient)
        usd = _normalize(usda_match)
        if not ing or not usd:
            return 0.0

        # --- Polarity analysis (primary signal) ---
        ip = _poles(ing)
        up = _poles(usd)
        conflict = 0.0
        agreement = 0.0
        for axis in set(ip) & set(up):
            a, b = ip[axis], up[axis]
            w = _AXIS_WEIGHT.get(axis, 2.0)
            if a == b and len(a) == 1:
                agreement += 0.4 * w
            elif not (a & b):
                conflict += w           # fully opposite poles
            else:
                conflict += 0.4 * w     # mixed / ambiguous
        # Explicit negation-prefix pairs not in the lexicon (e.g. "unsmoked" vs "smoked")
        iw = set(re.findall(r"[a-z]+", ing))
        uw = set(re.findall(r"[a-z]+", usd))
        for w in iw:
            if w.startswith("un") and len(w) > 5 and w[2:] in uw:
                conflict += 2.0
            if w.startswith("non") and len(w) > 6 and w[3:] in uw:
                conflict += 2.0
        for w in uw:
            if w.startswith("un") and len(w) > 5 and w[2:] in iw:
                conflict += 2.0
            if w.startswith("non") and len(w) > 6 and w[3:] in iw:
                conflict += 2.0

        # --- Identity anchor (secondary signal so unrelated foods do not score high) ---
        it = _tokens(ing)
        ut = _tokens(usd)
        head = _tokens(usd.split(",")[0]) if "," in str(usda_match) else ut
        overlap = len(it & ut) / max(1, len(it))
        head_hit = 1.0 if (head & it) else 0.0
        anchor = 4.0 * overlap + 2.0 * head_hit   # 0..6

        score = 4.0 + anchor + agreement - 2.2 * conflict
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
