import re

# Each axis: (name, weight, negative-pole patterns, positive-pole patterns)
# Negative patterns are checked first so "skin not eaten" is not read as "skin".
_AXES = [
    ("skin", 3.0,
     [r"\bskinless\b", r"\bskin[- ]?off\b", r"\bskin not eaten\b", r"\bwithout skin\b",
      r"\bno skin\b", r"\bskin removed\b", r"\bpeeled\b"],
     [r"\bskin[- ]?on\b", r"\bwith skin\b", r"\bmeat and skin\b", r"\bskin and\b",
      r"\bskin eaten\b", r"\bunpeeled\b", r"\bskin\b"]),
    ("bone", 3.0,
     [r"\bboneless\b", r"\bdeboned\b", r"\bbone removed\b", r"\bwithout bones?\b", r"\bfillets?\b"],
     [r"\bbone[- ]?in\b", r"\bwith bones?\b", r"\bbones? included\b"]),
    ("salt", 2.5,
     [r"\bunsalted\b", r"\bno salt\b", r"\bwithout salt\b", r"\bsalt[- ]?free\b",
      r"\bno added salt\b", r"\blow sodium\b", r"\bsodium[- ]?free\b", r"\breduced sodium\b"],
     [r"\bsalted\b", r"\bwith salt\b", r"\bsalt added\b", r"\bbrined\b"]),
    ("sugar", 2.5,
     [r"\bunsweetened\b", r"\bno sugar\b", r"\bsugar[- ]?free\b", r"\bwithout sugar\b",
      r"\bno added sugar\b", r"\bnot sweetened\b"],
     [r"\bsweetened\b", r"\bwith sugar\b", r"\bsugar added\b", r"\bheavy syrup\b",
      r"\blight syrup\b", r"\bcandied\b"]),
    ("fat", 2.5,
     [r"\bno added fat\b", r"\bwithout fat\b", r"\bfat[- ]?free\b", r"\bnonfat\b",
      r"\bnon[- ]fat\b", r"\bskim\b", r"\bwithout added fat\b"],
     [r"\bfat added\b", r"\bwith added fat\b", r"\bwhole milk\b", r"\bfull[- ]fat\b",
      r"\bwith fat\b"]),
    ("hull", 2.0,
     [r"\bhulled\b", r"\bshelled\b", r"\bdehulled\b", r"\bkernels?\b"],
     [r"\bunhulled\b", r"\bin shell\b", r"\bin the shell\b", r"\bwith shells?\b", r"\bunshelled\b"]),
    ("seed", 2.0,
     [r"\bseedless\b", r"\bseeded\b", r"\bwithout seeds\b", r"\bpitted\b", r"\bno seeds\b"],
     [r"\bwith seeds\b", r"\bunpitted\b", r"\bseeds included\b"]),
    ("caffeine", 3.0,
     [r"\bdecaf\w*\b", r"\bcaffeine[- ]?free\b", r"\bwithout caffeine\b"],
     [r"\bcaffeinated\b", r"\bregular\b", r"\bwith caffeine\b"]),
    ("cooked", 1.5,
     [r"\buncooked\b", r"\braw\b", r"\bunbaked\b", r"\bunprepared\b"],
     [r"\bcooked\b", r"\broasted\b", r"\bbaked\b", r"\bfried\b", r"\bboiled\b",
      r"\bgrilled\b", r"\bprepared\b", r"\bsteamed\b"]),
    ("frozen", 1.0,
     [r"\bunfrozen\b", r"\bthawed\b", r"\bnot frozen\b"],
     [r"\bfrozen\b"]),
    ("alcohol", 2.5,
     [r"\bnon[- ]?alcoholic\b", r"\balcohol[- ]?free\b"],
     [r"\balcoholic\b", r"\bwith alcohol\b"]),
    ("lean", 1.0,
     [r"\blean only\b"],
     [r"\blean and fat\b"]),
]

_COMPILED = [(n, w, [re.compile(p) for p in neg], [re.compile(p) for p in pos])
             for (n, w, neg, pos) in _AXES]

_STOP = {"and", "or", "with", "the", "a", "of", "in", "for", "from", "to", "raw", "fresh",
         "cooked", "g", "sliced", "chopped", "diced", "drained", "store", "bought", "all",
         "varieties", "not", "no", "without", "ready", "serve"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(?:\.\d+)?\s*(?:g|kg|mg|ml|l|oz|lb)?\b", " ", t)
    t = t.replace("_", " ")
    return re.sub(r"\s+", " ", t).strip()


def _state(text, neg, pos):
    """Return -1 (negative pole), +1 (positive pole), 0 (silent). Negations mask text."""
    work = text
    hit_neg = False
    for rx in neg:
        if rx.search(work):
            hit_neg = True
            work = rx.sub(" ", work)
    hit_pos = any(rx.search(work) for rx in pos)
    if hit_neg and not hit_pos:
        return -1
    if hit_pos and not hit_neg:
        return 1
    return 0


def _tokens(text):
    out = set()
    for w in re.findall(r"[a-z]+", text):
        if len(w) < 3 or w in _STOP:
            continue
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("es") and len(w) > 4 and not w.endswith("ses"):
            w = w[:-2]
        elif w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out


def judging_function(ingredient, usda_match):
    try:
        a = _clean(ingredient)
        b = _clean(usda_match)
        if not a or not b:
            return 0.0

        # Polarity vectors over all attribute axes.
        conflict = 0.0
        agree = 0.0
        for name, weight, neg, pos in _COMPILED:
            sa = _state(a, neg, pos)
            sb = _state(b, neg, pos)
            if sa != 0 and sb != 0:
                if sa * sb < 0:
                    conflict += weight
                else:
                    agree += weight * 0.25

        # Weak lexical anchor so the score is not flat when no polarity is stated.
        ta, tb = _tokens(a), _tokens(b)
        anchor = 0.0
        if ta and tb:
            inter = len(ta & tb)
            anchor = inter / float(min(len(ta), len(tb)))
            # partial prefix matches (e.g. frankfurter / frankfurters)
            if inter == 0:
                for x in ta:
                    for y in tb:
                        if len(x) >= 4 and len(y) >= 4 and (x.startswith(y[:4]) and y.startswith(x[:4])):
                            anchor = max(anchor, 0.3)

        score = 5.0 + 2.5 * anchor + min(agree, 1.5)
        # Contradictions dominate: multiplicative decay plus subtractive penalty.
        if conflict > 0:
            score = score * (0.5 ** (conflict / 3.0)) - conflict * 0.5
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 5.0
