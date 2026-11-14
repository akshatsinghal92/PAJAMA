import re

# Qualifier ledger: canonical qualifier -> (regex patterns, penalty weight, synonyms that count as "stated")
_QUALIFIERS = {
    "low_sodium": ([r"\blow[\s-]*sodium\b", r"\breduced[\s-]*sodium\b", r"\bno[\s-]*salt[\s-]*added\b",
                    r"\bwithout[\s-]*(added[\s-]*)?salt\b", r"\bunsalted\b", r"\bsodium[\s-]*free\b"], 2.5,
                   ["low sodium", "reduced sodium", "unsalted", "no salt", "without salt", "sodium free", "low-sodium", "salt-free"]),
    "salted": ([r"\bwith[\s-]*salt\b", r"\bsalted\b", r"\bsalt[\s-]*added\b"], 2.0,
               ["salted", "with salt", "salt"]),
    "nonfat": ([r"\bnon[\s-]*fat\b", r"\bfat[\s-]*free\b", r"\bskim\b", r"\bnonfat\b"], 3.0,
               ["nonfat", "non-fat", "non fat", "fat free", "fat-free", "skim", "zero fat", "0%"]),
    "low_fat": ([r"\blow[\s-]*fat\b", r"\breduced[\s-]*fat\b", r"\blowfat\b", r"\b\d+%\s*(milk)?fat\b", r"\blight\b", r"\blite\b"], 2.5,
                ["low fat", "low-fat", "lowfat", "reduced fat", "reduced-fat", "light", "lite", "lean", "2%", "1%"]),
    "sweetened": ([r"\bsweetened\b", r"\bwith[\s-]*added[\s-]*sugar\b", r"\bsugared\b", r"\bin[\s-]*(heavy|light)?[\s-]*syrup\b", r"\bhoney\b"], 2.5,
                  ["sweetened", "sugar", "syrup", "honey", "candied", "sweet"]),
    "sugar_free": ([r"\bsugar[\s-]*free\b", r"\bunsweetened\b", r"\bno[\s-]*sugar[\s-]*added\b", r"\bdiet\b", r"\bartificial(ly)?[\s-]*sweeten"], 2.5,
                   ["sugar free", "sugar-free", "unsweetened", "no sugar", "diet"]),
    "flavored": ([r"\bflavou?red\b", r"\bseasoned\b", r"\bspiced\b", r"\bmarinated\b", r"\bwith[\s-]*added\b(?![\s-]*(vitamin|sugar|salt))"], 2.0,
                 ["flavored", "flavoured", "seasoned", "spiced", "marinated"]),
    "fortified": ([r"\bfortified\b", r"\benriched\b", r"\bwith[\s-]*(added[\s-]*)?vitamins?\b", r"\bvitamin\s*[a-k]\b", r"\bcalcium[\s-]*fortified\b"], 0.8,
                  ["fortified", "enriched", "vitamin"]),
    "additives": ([r"\badditives?\b", r"\bpreservatives?\b", r"\binjected\b", r"\benhanced\b", r"\bsolution\b"], 1.5,
                  ["additive", "enhanced", "injected", "brined"]),
    "imitation": ([r"\bimitation\b", r"\bsubstitute\b", r"\banalog\b", r"\bmeatless\b", r"\bvegetarian\b"], 3.0,
                  ["imitation", "substitute", "vegan", "vegetarian", "meatless", "plant-based"]),
}

_NEUTRAL = {"raw", "plain", "regular", "fresh", "nfs", "ns", "as", "to", "form", "whole", "all", "commercial",
            "prepared", "ready", "uncooked", "unprepared", "mixed", "species", "includes", "including"}

_STOP = {"and", "or", "with", "the", "of", "in", "a", "an", "for", "from", "g", "kg", "mg", "ml", "oz", "lb",
         "cup", "cups", "tbsp", "tsp", "can", "canned", "chopped", "sliced", "diced", "minced", "cubed", "cut",
         "into", "pieces", "piece", "large", "small", "medium", "about", "thawed", "drained", "rinsed"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)?\b", " ", t)
    return t


def _tokens(text):
    out = []
    for w in re.findall(r"[a-z]+", text):
        if w in _STOP or len(w) < 3:
            continue
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("es") and len(w) > 4 and w[-3] in "sxz":
            w = w[:-2]
        elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            w = w[:-1]
        out.append(w)
    return out


def _stated(ing_text, canon):
    pats, _, syns = _QUALIFIERS[canon]
    for s in syns:
        if s in ing_text:
            return True
    for p in pats:
        if re.search(p, ing_text):
            return True
    return False


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0

        # Ledger of unstated added qualifiers
        ledger = 0.0
        hits = 0
        for canon, (pats, weight, _syn) in _QUALIFIERS.items():
            present = any(re.search(p, usda) for p in pats)
            if not present:
                continue
            if _stated(ing, canon):
                continue
            # Fortification paired with a matching stated fat qualifier is less noticeable
            ledger += weight
            hits += 1
        # Diminishing compounding: each extra qualifier stacks but with decay
        penalty = ledger * (1.0 + 0.15 * max(0, hits - 1))

        # Reverse direction: ingredient states a qualifier USDA lacks (minor, asymmetric)
        missing = 0.0
        for canon, (pats, weight, _syn) in _QUALIFIERS.items():
            if canon in ("fortified", "additives"):
                continue
            if any(re.search(p, ing) for p in pats) and not any(re.search(p, usda) for p in pats):
                missing += 0.4 * weight

        # Anchor: the ingredient's core food should appear in USDA entry
        ing_tok = set(_tokens(ing))
        usda_parts = [p.strip() for p in re.sub(r"\([^)]*\)", " ", usda).split(",") if p.strip()]
        usda_tok = set(_tokens(" ".join(usda_parts)))
        head_tok = set(_tokens(usda_parts[0])) if usda_parts else set()
        head_tok |= set(_tokens(usda_parts[1])) if len(usda_parts) > 1 else set()
        content_ing = {w for w in ing_tok if w not in _NEUTRAL}
        if content_ing:
            shared = content_ing & usda_tok
            anchor = len(shared) / float(len(content_ing))
            head_hit = 1.0 if (content_ing & head_tok) else 0.0
        else:
            anchor, head_hit = 0.0, 0.0

        # Count unexplained non-neutral descriptors in USDA (mild noise penalty)
        extra = [w for w in usda_tok if w not in ing_tok and w not in _NEUTRAL]
        noise = min(1.5, 0.12 * len(extra))

        base = 3.0 + 3.5 * anchor + 1.5 * head_hit
        score = base - penalty - missing - noise
        if anchor == 0.0:
            score = min(score, 2.5)
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
