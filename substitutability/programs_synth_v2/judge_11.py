import re

# Preparation-State Equivalence, variant 3: phrase-level regex patterns and
# a reversibility check. A state gap is acceptable when the cook can close it
# in the kitchen (raw -> chopped, frozen -> thawed, uncooked pasta -> cooked
# pasta when the recipe cooks it anyway). A gap is harmful when it cannot be
# undone (cooked -> raw, fried -> fresh, canned/creamed -> raw) or when the
# USDA product already carries a method that changes flavour/texture.

_USDA_PATTERNS = [
    (r"\bdry heat\b|\broasted\b|\bgrilled\b|\bbroiled\b", "dry_cooked"),
    (r"\bmoist heat\b|\bboiled\b|\bsteamed\b|\bstewed\b|\bbraised\b|\bpoached\b", "wet_cooked"),
    (r"\bfried\b|\bbreaded\b|\bbattered\b", "fried"),
    (r"\bbaked\b|\btoasted\b", "dry_cooked"),
    (r"\bcooked\b|\bprepared\b|\bheated\b", "wet_cooked"),
    (r"\bcanned\b|\bsolids and liquids\b|\bdrained solids\b", "canned"),
    (r"\bfrozen\b", "frozen"),
    (r"\bdried\b|\bdehydrated\b|\bpowder\b", "dried"),
    (r"\bsmoked\b|\bcured\b|\bpickled\b", "cured"),
    (r"\bcream style\b|\bcreamed\b|\bpuree\b|\bmashed\b", "pureed"),
    (r"\braw\b|\bfresh\b|\buncooked\b", "raw"),
]
_ING_PATTERNS = [
    (r"\bfried\b|\bfries\b|\bcrispy\b|\bbreaded\b", "fried"),
    (r"\broast(ed)?\b|\bgrilled\b|\bbbq\b|\bbaked\b|\btoasted\b", "dry_cooked"),
    (r"\bcooked\b|\bboiled\b|\bsteamed\b|\bleftover\b|\bstewed\b", "wet_cooked"),
    (r"\bcanned\b|\btinned\b|\bjarred\b", "canned"),
    (r"\bfrozen\b", "frozen"),
    (r"\bdried\b|\bdry\b|\bpowder(ed)?\b|\bdehydrated\b", "dried"),
    (r"\bsmoked\b|\bcured\b|\bpickled\b", "cured"),
    (r"\bcreamed\b|\bpureed?\b|\bmashed\b", "pureed"),
    (r"\braw\b|\bfresh\b|\buncooked\b|\bchopped\b|\bdiced\b|\bminced\b|\bsliced\b|\bshredded\b|\bgrated\b", "raw"),
    (r"\bthawed\b|\bdefrosted\b", "frozen"),
]

# (ingredient_state, usda_state) -> score 0..10 ; reversible gaps score high
_GAP = {
    "raw": {"raw": 10, "frozen": 7, "wet_cooked": 3, "dry_cooked": 2, "fried": 1,
            "canned": 3, "dried": 1.5, "cured": 1.5, "pureed": 2},
    "frozen": {"frozen": 10, "raw": 8.5, "wet_cooked": 4, "dry_cooked": 3, "fried": 1.5,
               "canned": 4, "dried": 2, "cured": 2, "pureed": 3},
    "wet_cooked": {"wet_cooked": 10, "dry_cooked": 6, "raw": 6, "frozen": 5.5, "fried": 3,
                   "canned": 7, "dried": 3, "cured": 3, "pureed": 5},
    "dry_cooked": {"dry_cooked": 10, "wet_cooked": 5, "raw": 5, "frozen": 4.5, "fried": 5,
                   "canned": 3, "dried": 3, "cured": 4, "pureed": 2},
    "fried": {"fried": 10, "dry_cooked": 4, "wet_cooked": 2, "raw": 2, "frozen": 2.5,
              "canned": 1, "dried": 1, "cured": 1, "pureed": 1},
    "canned": {"canned": 10, "wet_cooked": 7.5, "raw": 3, "frozen": 4, "dry_cooked": 3,
               "fried": 1, "dried": 2, "cured": 4, "pureed": 5},
    "dried": {"dried": 10, "raw": 2, "frozen": 1.5, "wet_cooked": 2, "dry_cooked": 3,
              "fried": 1, "canned": 1.5, "cured": 4, "pureed": 2},
    "cured": {"cured": 10, "raw": 2, "dry_cooked": 3, "wet_cooked": 3, "frozen": 2,
              "canned": 3, "dried": 3, "fried": 1, "pureed": 1},
    "pureed": {"pureed": 10, "canned": 6, "wet_cooked": 4, "raw": 2, "frozen": 3,
               "dry_cooked": 2, "dried": 2, "fried": 1, "cured": 1},
}


def _first_state(text, patterns):
    found = []
    for pat, label in patterns:
        m = re.search(pat, text)
        if m:
            found.append((label, m.start()))
    return found


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        ing = ing.replace("(", " ").replace(")", " ")
        i_found = _first_state(ing, _ING_PATTERNS)
        u_found = _first_state(usda, _USDA_PATTERNS)
        i_state = i_found[0][0] if i_found else "raw"
        u_state = u_found[0][0] if u_found else None

        if u_state is None:
            # USDA states nothing: treat as the as-purchased default of the item
            u_state = i_state if i_state in ("canned", "dried", "cured", "pureed") else "raw"
            score = _GAP[i_state].get(u_state, 3) - 0.5
        else:
            score = float(_GAP[i_state].get(u_state, 3))

        # uncooked starch / pasta destined to be cooked tolerates a cooked match
        if re.search(r"\buncooked\b|\bdry\b", ing) and u_state in ("wet_cooked",) and re.search(
                r"pasta|noodle|rice|gnocchi|macaroni|spaghetti|quinoa|oat", ing):
            score = max(score, 6.0)
        # conflicting multiple USDA states (e.g. "frozen, fried") compound the gap
        distinct_u = {lab for lab, _ in u_found} - {"raw"}
        if len(distinct_u) >= 2 and i_state == "raw":
            score -= 1.0
        if not i_found:
            score -= 0.5          # ingredient implicit, less certainty
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
