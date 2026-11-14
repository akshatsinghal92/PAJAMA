import re

# Concept families: each family lists surface patterns (regex) and a severity
# (how noticeable it is to a diner when the ingredient never asked for it).
_FAMILIES = {
    "sodium_low":   (r"\b(low|reduced|less|no|lower)[\s-]*(sodium|salt)\b|\bsodium[\s-]*free\b|\bunsalted\b|\bwithout salt( added)?\b|\bno salt added\b", 14),
    "salted":       (r"\bwith (added )?salt\b|\bsalted\b|\bsalt added\b", 14),
    "fat_none":     (r"\b(fat|non)[\s-]*free\b|\bnon[\s-]*fat\b|\bskim\b|\b0%\b", 18),
    "fat_low":      (r"\b(low|reduced|less|lite|light)[\s-]*fat\b|\b(1|2)%\b|\blean\b", 14),
    "light":        (r"\blight\b|\blite\b", 10),
    "sweetened":    (r"\bsweetened\b|\bwith (added )?sugar\b|\bsugared\b|\bhoney[\s-]*coated\b|\bfrosted\b|\bcandied\b", 16),
    "sugar_none":   (r"\bsugar[\s-]*free\b|\bunsweetened\b|\bno sugar added\b|\b(low|reduced)[\s-]*sugar\b|\bdiet\b|\bartificial(ly)? sweeten", 16),
    "flavored":     (r"\bflavou?red\b|\bwith flavou?r", 12),
    "fortified":    (r"\benriched\b|\bfortified\b|\bwith added (vitamin|calcium|iron|nutrient)s?\b|\bvitamin [a-z0-9]+ added\b|\bcalcium[\s-]*fortified\b", 6),
    "decaf":        (r"\bdecaf(feinated)?\b|\bcaffeine[\s-]*free\b", 15),
    "smoked":       (r"\bsmoked\b", 12),
    "toasted":      (r"\btoasted\b|\broasted\b|\bdry roasted\b", 8),
    "gluten_free":  (r"\bgluten[\s-]*free\b", 10),
    "breaded":      (r"\bbreaded\b|\bbattered\b|\bcoated\b", 12),
    "sauce":        (r"\bsauce\b|\bgravy\b|\bin syrup\b|\bheavy syrup\b|\blight syrup\b", 12),
    "spiced":       (r"\bspiced\b|\bseasoned\b|\bspicy\b|\bhot\b", 8),
}

# Pairs where the ingredient stating one makes the USDA stating the other a clash.
_OPPOSITES = [
    ("sodium_low", "salted"),
    ("fat_none", "fat_low"),
    ("sweetened", "sugar_none"),
]

# Words that count as stating a family even without the exact USDA phrase.
_STATED_HINTS = {
    "sodium_low": ["unsalted", "low sodium", "low-sodium", "no salt", "salt free", "reduced sodium"],
    "salted": ["salted", "salt"],
    "fat_none": ["nonfat", "non-fat", "fat free", "fat-free", "skim", "0%"],
    "fat_low": ["low fat", "low-fat", "reduced fat", "lean", "2%", "1%", "light"],
    "light": ["light", "lite"],
    "sweetened": ["sweetened", "sweet", "sugar", "honey", "frosted", "candied", "chocolate", "vanilla"],
    "sugar_none": ["unsweetened", "sugar free", "sugar-free", "diet"],
    "flavored": ["flavored", "flavoured", "vanilla", "chocolate", "strawberry", "peach", "berry", "lemon", "cherry", "coco"],
    "fortified": ["enriched", "fortified"],
    "decaf": ["decaf"],
    "smoked": ["smoked", "smoky"],
    "toasted": ["toasted", "roasted"],
    "gluten_free": ["gluten"],
    "breaded": ["breaded", "battered", "coated", "crumbed"],
    "sauce": ["sauce", "gravy", "syrup", "relish", "melted"],
    "spiced": ["spiced", "seasoned", "spicy", "hot"],
}

_NEUTRAL = {"raw", "plain", "regular", "nfs", "ns", "fresh", "whole", "dry", "dried",
            "canned", "frozen", "cooked", "uncooked", "drained", "solids", "prepared"}

_STOP = {"and", "or", "with", "of", "the", "a", "an", "in", "for", "from", "to", "type",
         "style", "g", "kg", "mg", "ml", "oz", "lb", "cup", "cups", "tbsp", "tsp"}


def _clean_ingredient(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)\b\.?", " ", t)
    paren = " ".join(re.findall(r"\(([^)]*)\)", t))
    t = re.sub(r"\([^)]*\)", " ", t)
    full = (t + " " + paren).replace(",", " ")
    full = re.sub(r"\s+", " ", full).strip()
    return full


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(text):
    return {_stem(w) for w in re.findall(r"[a-z]+", text) if w not in _STOP and len(w) > 1}


def _families_in(text):
    found = set()
    for fam, (pat, _) in _FAMILIES.items():
        if re.search(pat, text):
            found.add(fam)
    return found


def _stated(fam, ing_text):
    for h in _STATED_HINTS.get(fam, []):
        if re.search(r"(?<![a-z])" + re.escape(h) + r"(?![a-z])", ing_text):
            return True
    return False


def judging_function(ingredient, usda_match):
    try:
        ing = _clean_ingredient(ingredient)
        usda = re.sub(r"\s+", " ", str(usda_match or "").lower()).strip()
        if not ing or not usda:
            return 0.0

        # --- Qualifier ledger: start from a full budget and deduct ---
        score = 100.0
        usda_fams = _families_in(usda)
        ing_fams = _families_in(ing)

        unstated = 0
        for fam in usda_fams:
            if fam in ing_fams or _stated(fam, ing):
                continue
            sev = _FAMILIES[fam][1]
            # Escalate each further unstated qualifier (compounding noticeability).
            score -= sev * (1.0 + 0.25 * unstated)
            unstated += 1

        # Direct clash: the ingredient asked for the opposite qualifier.
        for a, b in _OPPOSITES:
            if (a in ing_fams and b in usda_fams) or (b in ing_fams and a in usda_fams):
                score -= 20.0

        # Qualifier the ingredient stated but USDA dropped (smoked, toasted, etc.).
        for fam in ing_fams:
            if fam not in usda_fams and fam in ("smoked", "toasted", "decaf", "fat_none",
                                                 "sugar_none", "sodium_low", "sweetened"):
                score -= 10.0

        # --- Anchor gate: a qualifier check is meaningless if the food differs ---
        ing_tok = _tokens(ing) - _NEUTRAL
        segs = [s.strip() for s in usda.split(",") if s.strip()]
        head_tok = _tokens(segs[0]) if segs else set()
        all_tok = _tokens(usda)
        if ing_tok:
            head_hit = len(ing_tok & head_tok)
            any_hit = len(ing_tok & all_tok)
            cover = any_hit / float(len(ing_tok))
            if head_hit == 0 and any_hit == 0:
                gate = 0.25
            elif head_hit == 0:
                gate = 0.55 + 0.3 * cover
            else:
                gate = 0.75 + 0.25 * cover
        else:
            gate = 0.5

        # Neutral-only descriptor bonus: rewards entries that add nothing notable.
        neutral_bonus = 0.0
        if not usda_fams:
            tail = segs[1:]
            if all(_tokens(s) <= (_NEUTRAL | ing_tok) for s in tail):
                neutral_bonus = 8.0

        final = (max(score, 0.0) + neutral_bonus) * gate
        return round(max(0.0, min(100.0, final)), 3)
    except Exception:
        return 0.0
