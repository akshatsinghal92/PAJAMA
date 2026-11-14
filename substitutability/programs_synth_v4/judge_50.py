import re
import math


# Each qualifier family: (name, severity, usda-side regex, ingredient-side regexes that "license" it)
_FAMILIES = [
    ("sodium", 2.2,
     r"\b(low|reduced|less|no|lower)[\s-]*(sodium|salt)\b|\bsodium[\s-]*(free|reduced)\b|\bunsalted\b|\bwithout salt\b|\bno salt added\b",
     [r"\b(low|reduced|less|no|lower)[\s-]*(sodium|salt)\b", r"\bunsalted\b", r"\bsodium\b", r"\bno[\s-]*salt\b"]),
    ("salted", 1.4,
     r"\bwith (added )?salt\b|\bsalted\b",
     [r"\bsalted\b", r"\bsalt\b", r"\bbrined\b", r"\bcured\b"]),
    ("fat", 2.4,
     r"\b(fat[\s-]*free|nonfat|non-fat|low[\s-]*fat|lowfat|reduced[\s-]*fat|less fat|lean|light|lite|skim|\d+%\s*(milk)?fat|part[\s-]*skim|extra lean)\b",
     [r"\b(fat[\s-]*free|nonfat|non-fat|low[\s-]*fat|lowfat|reduced[\s-]*fat|light|lite|skim|lean|part[\s-]*skim|\d+%)\b", r"\bdiet\b"]),
    ("sugar", 2.2,
     r"\b(sugar[\s-]*free|no sugar added|unsweetened|reduced sugar|low sugar|artificially sweetened|sweetened with|diet)\b",
     [r"\b(sugar[\s-]*free|no sugar|unsweetened|reduced sugar|low sugar|diet|artificial)\b"]),
    ("sweetened", 1.8,
     r"\b(sweetened|with sugar|sugar added|honey|candied|syrup pack|heavy syrup|light syrup|glazed|frosted)\b",
     [r"\b(sweet\w*|sugar\w*|honey|candied|syrup|glazed|frosted)\b"]),
    ("flavored", 1.6,
     r"\b(flavored|flavoured|with (added )?flavou?r\w*|seasoned|spiced|smoked flavou?r)\b",
     [r"\b(flavou?r\w*|seasoned|spiced|herbed)\b"]),
    ("fortified", 1.0,
     r"\b(enriched|fortified|with added (vitamin|calcium|iron|nutrient)s?\w*|vitamin [a-z0-9]+ added|calcium[\s-]*fortified|added (vitamins?|calcium|iron))\b",
     [r"\b(enriched|fortified|vitamin|calcium|iron)\b"]),
    ("decaf", 1.2,
     r"\b(decaffeinated|decaf|caffeine[\s-]*free)\b",
     [r"\b(decaf\w*|caffeine)\b"]),
    ("lactose", 1.2,
     r"\b(lactose[\s-]*free|lactose[\s-]*reduced|gluten[\s-]*free)\b",
     [r"\b(lactose|gluten)\b"]),
]

_COMPILED = [(n, s, re.compile(u), [re.compile(p) for p in lic]) for (n, s, u, lic) in _FAMILIES]

_NEUTRAL = set("""raw plain regular fresh whole all varieties mixed species ns as to form
unprepared prepared ready-to-eat commercial includes include not specified usda commodity
uncooked boiled cooked drained solids liquids unheated solid pack edible portion meat only
year round average""".split())

_UNITS_RE = re.compile(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb|grams?)\b\.?\s*", re.I)


def _clean_ing(text):
    t = str(text or "").lower()
    t = _UNITS_RE.sub("", t)
    t = t.replace("(", " ").replace(")", " ")
    return re.sub(r"\s+", " ", t).strip()


def _segments(usda):
    return [s.strip() for s in str(usda or "").lower().split(",") if s.strip()]


def _words(s):
    return re.findall(r"[a-z]+", s)


def judging_function(ingredient, usda_match):
    try:
        ing = _clean_ing(ingredient)
        segs = _segments(usda_match)
        if not ing or not segs:
            return 0.0
        usda_full = " , ".join(segs)

        # 1) Qualifier families: a penalty mass that accumulates for unlicensed qualifiers.
        penalty_mass = 0.0
        licensed_hits = 0
        for name, sev, urx, lic in _COMPILED:
            found = urx.findall(usda_full)
            if not found:
                continue
            if any(p.search(ing) for p in lic):
                licensed_hits += 1
            else:
                # extra hits in the same family add diminishing extra weight
                penalty_mass += sev * (1.0 + 0.25 * math.log(len(found)))

        # 2) Segment-level classification of descriptors after the primary food.
        ing_words = set(_words(ing))
        tail = segs[1:]
        neutral_segs = 0
        echoed_segs = 0
        foreign_segs = 0
        for seg in tail:
            ws = [w for w in _words(seg) if len(w) > 1]
            if not ws:
                continue
            if all(w in _NEUTRAL for w in ws):
                neutral_segs += 1
            elif any(w in ing_words or w.rstrip("s") in ing_words for w in ws):
                echoed_segs += 1
            else:
                foreign_segs += 1

        # 3) Primary-food anchoring: does the head segment overlap the ingredient?
        head = [w for w in _words(segs[0]) if len(w) > 2]
        if head:
            anchor = sum(1 for w in head if w in ing_words or w.rstrip("s") in ing_words
                         or any(iw.startswith(w[:4]) for iw in ing_words if len(w) >= 4)) / len(head)
        else:
            anchor = 0.0
        if anchor == 0.0:
            # allow ingredient words appearing anywhere in usda
            usda_words = set(_words(usda_full))
            anchor = 0.5 if ing_words & {w for w in usda_words if len(w) > 3} else 0.0

        # Score: base logistic over a linear evidence sum, then exponential decay by penalty.
        evidence = (1.6 * anchor
                    + 0.35 * neutral_segs
                    + 0.45 * echoed_segs
                    + 0.5 * licensed_hits
                    - 0.3 * foreign_segs)
        base = 1.0 / (1.0 + math.exp(-(evidence - 0.6) * 2.0))
        decay = math.exp(-0.55 * penalty_mass)
        score = 100.0 * base * decay
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
