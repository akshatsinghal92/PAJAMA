import re
import math

# Variant 8: physical-state vector model.
# Each text is projected onto continuous axes describing how the food is
# preserved / delivered: moisture, concentration, processing intensity,
# packaging/shelf-stability, and particle form. The score is a similarity in
# that latent space, modulated by a "recoverability" credit (user transforms
# such as thawing/rehydrating that bridge a gap) and a light identity gate.

_AXES = ("moisture", "concentration", "processing", "shelf", "particle")

# cue -> partial vector (missing axes = no evidence)
_CUES = {
    "fresh":        {"moisture": 0.9, "processing": 0.0, "shelf": 0.0},
    "raw":          {"moisture": 0.85, "processing": 0.0, "shelf": 0.05},
    "frozen":       {"moisture": 0.85, "processing": 0.2, "shelf": 0.5},
    "thawed":       {"moisture": 0.85, "processing": 0.2, "shelf": 0.5},
    "chilled":      {"moisture": 0.85, "processing": 0.1, "shelf": 0.15},
    "canned":       {"moisture": 0.9, "processing": 0.6, "shelf": 0.95},
    "tinned":       {"moisture": 0.9, "processing": 0.6, "shelf": 0.95},
    "jarred":       {"moisture": 0.8, "processing": 0.55, "shelf": 0.85},
    "jar":          {"moisture": 0.8, "processing": 0.55, "shelf": 0.85},
    "bottled":      {"moisture": 0.85, "processing": 0.5, "shelf": 0.85},
    "pickled":      {"moisture": 0.8, "processing": 0.7, "shelf": 0.85, "concentration": 0.5},
    "dried":        {"moisture": 0.1, "concentration": 0.85, "processing": 0.6, "shelf": 0.9},
    "dry":          {"moisture": 0.15, "concentration": 0.7, "shelf": 0.85},
    "dehydrated":   {"moisture": 0.05, "concentration": 0.9, "processing": 0.65, "shelf": 0.95},
    "freeze":       {"moisture": 0.05, "concentration": 0.9, "processing": 0.7, "shelf": 0.95},
    "sun":          {"moisture": 0.2, "concentration": 0.8, "processing": 0.5, "shelf": 0.8},
    "powder":       {"moisture": 0.03, "concentration": 0.95, "processing": 0.8, "shelf": 0.95, "particle": 1.0},
    "powdered":     {"moisture": 0.03, "concentration": 0.95, "processing": 0.8, "shelf": 0.95, "particle": 1.0},
    "ground":       {"particle": 0.8},
    "flour":        {"moisture": 0.1, "processing": 0.7, "shelf": 0.9, "particle": 1.0},
    "meal":         {"moisture": 0.1, "processing": 0.6, "shelf": 0.85, "particle": 0.85},
    "paste":        {"moisture": 0.45, "concentration": 0.8, "processing": 0.75, "shelf": 0.75, "particle": 0.6},
    "puree":        {"moisture": 0.75, "concentration": 0.5, "processing": 0.6, "particle": 0.55},
    "pureed":       {"moisture": 0.75, "concentration": 0.5, "processing": 0.6, "particle": 0.55},
    "concentrate":  {"moisture": 0.4, "concentration": 0.95, "processing": 0.8, "shelf": 0.8},
    "concentrated": {"moisture": 0.4, "concentration": 0.95, "processing": 0.8, "shelf": 0.8},
    "condensed":    {"moisture": 0.4, "concentration": 0.9, "processing": 0.8, "shelf": 0.9},
    "evaporated":   {"moisture": 0.55, "concentration": 0.75, "processing": 0.75, "shelf": 0.9},
    "ready":        {"moisture": 0.9, "concentration": 0.2, "processing": 0.7, "shelf": 0.7},
    "rts":          {"moisture": 0.9, "concentration": 0.2, "processing": 0.7, "shelf": 0.7},
    "instant":      {"moisture": 0.05, "concentration": 0.9, "processing": 0.85, "shelf": 0.95},
    "smoked":       {"moisture": 0.6, "processing": 0.7, "shelf": 0.5, "concentration": 0.4},
    "cured":        {"moisture": 0.5, "processing": 0.75, "shelf": 0.6, "concentration": 0.5},
    "salted":       {"processing": 0.5, "shelf": 0.6},
    "cooked":       {"processing": 0.55},
    "boiled":       {"processing": 0.5, "moisture": 0.85},
    "roasted":      {"processing": 0.55, "moisture": 0.6},
    "toasted":      {"processing": 0.5, "moisture": 0.3},
    "fried":        {"processing": 0.6},
    "baked":        {"processing": 0.55},
    "shelf":        {"shelf": 0.95, "processing": 0.6},
    "stable":       {"shelf": 0.9},
    "refrigerated": {"shelf": 0.2},
    "whole":        {"particle": 0.0},
    "sliced":       {"particle": 0.2},
    "chopped":      {"particle": 0.3},
    "minced":       {"particle": 0.45},
    "flaked":       {"particle": 0.35},
    "shredded":     {"particle": 0.35},
    "grated":       {"particle": 0.5},
    "crushed":      {"particle": 0.55},
    "granules":     {"particle": 0.85, "moisture": 0.05, "concentration": 0.85, "shelf": 0.9},
    "flakes":       {"particle": 0.6, "moisture": 0.1, "concentration": 0.7, "shelf": 0.85},
    "syrup":        {"moisture": 0.35, "concentration": 0.85, "processing": 0.7, "shelf": 0.85},
    "juice":        {"moisture": 0.95, "processing": 0.4},
    "soup":         {"moisture": 0.95, "concentration": 0.15, "processing": 0.7},
    "broth":        {"moisture": 0.97, "concentration": 0.1, "processing": 0.6},
    "stock":        {"moisture": 0.97, "concentration": 0.15, "processing": 0.6},
    "bouillon":     {"moisture": 0.05, "concentration": 0.98, "processing": 0.85, "shelf": 0.95},
    "cube":         {"particle": 0.2},
    "spices":       {"moisture": 0.05, "concentration": 0.9, "shelf": 0.95},
    "spice":        {"moisture": 0.05, "concentration": 0.9, "shelf": 0.95},
    "uncooked":     {"processing": 0.1},
    "unprepared":   {"concentration": 0.6},
    "prepared":     {"concentration": 0.3, "processing": 0.6},
    "mix":          {"moisture": 0.05, "concentration": 0.8, "processing": 0.85, "shelf": 0.9},
}

# Transforms a cook can apply in the recipe that move an item along an axis.
_RECOVERY = {
    "thawed": ("frozen",),
    "defrosted": ("frozen",),
    "rehydrated": ("dried", "dehydrated", "dry"),
    "soaked": ("dried", "dehydrated", "dry"),
    "reconstituted": ("dried", "dehydrated", "powder", "concentrate", "condensed"),
    "diluted": ("concentrate", "condensed", "concentrated"),
    "drained": ("canned", "jarred", "tinned"),
    "rinsed": ("canned", "tinned"),
}

_STOP = {
    "g", "kg", "mg", "ml", "l", "oz", "lb", "lbs", "cup", "cups", "tbsp", "tsp",
    "of", "and", "or", "with", "the", "a", "an", "in", "for", "to", "from",
    "large", "small", "medium", "inch", "pieces", "piece", "lean", "soft",
    "regular", "plain", "style", "type", "brand", "all", "purpose", "tube",
    "boneless", "skinless", "choice", "select", "prime", "ns", "nfs", "as",
    "to", "made", "added", "without", "w",
}

# Form cues that are also the food's identity noun (kept for identity matching).
_NOUN_CUES = {"flour", "meal", "paste", "puree", "concentrate", "syrup", "juice",
              "soup", "broth", "stock", "bouillon", "powder", "mix", "flakes",
              "granules", "cube"}


def _tokens(text):
    text = text.lower()
    text = re.sub(r"\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb|lbs)\b", " ", text)
    text = re.sub(r"[^a-z\s\-]", " ", text)
    text = text.replace("-", " ")
    return [t for t in text.split() if t]


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _project(tokens):
    """Average the evidence on each axis; return (vector, confidence per axis)."""
    sums = {a: 0.0 for a in _AXES}
    counts = {a: 0 for a in _AXES}
    toks = list(tokens)
    joined = " ".join(toks)
    if "ready to serve" in joined or "ready to eat" in joined:
        toks.append("rts")
    if "freeze dried" in joined:
        toks.append("freeze")
    for t in toks:
        cue = _CUES.get(t)
        if cue is None:
            cue = _CUES.get(_stem(t))
        if not cue:
            continue
        for a, v in cue.items():
            sums[a] += v
            counts[a] += 1
    vec = {}
    for a in _AXES:
        vec[a] = sums[a] / counts[a] if counts[a] else None
    return vec


def _default_vec():
    # A plain unqualified food is presumed fresh / minimally processed.
    return {"moisture": 0.8, "concentration": 0.3, "processing": 0.15,
            "shelf": 0.2, "particle": 0.1}


_AXIS_WEIGHT = {"moisture": 1.6, "concentration": 1.4, "processing": 0.8,
                "shelf": 0.6, "particle": 1.0}


def _state_distance(vi, vu):
    base = _default_vec()
    total = 0.0
    wsum = 0.0
    evidence = 0
    for a in _AXES:
        xi, xu = vi[a], vu[a]
        if xi is None and xu is None:
            continue
        evidence += 1
        # Missing side falls back to the prior, but with reduced weight.
        w = _AXIS_WEIGHT[a]
        if xi is None or xu is None:
            w *= 0.55
        xi = base[a] if xi is None else xi
        xu = base[a] if xu is None else xu
        total += w * (xi - xu) ** 2
        wsum += w
    if wsum == 0:
        return 0.0, 0
    return math.sqrt(total / wsum), evidence


def _identity_overlap(ing_toks, usda_toks):
    def keep(t):
        return t not in _STOP and len(t) > 2 and (t not in _CUES or t in _NOUN_CUES)
    ing = {_stem(t) for t in ing_toks if keep(t)}
    usda = [_stem(t) for t in usda_toks if keep(t)]
    if not ing or not usda:
        return 0.0, 0.0
    uset = set(usda)
    inter = ing & uset
    recall = len(inter) / len(ing)
    # USDA head noun: first non-generic token ("Spices, ginger" -> ginger).
    generic = {"spice", "spices", "fish", "soup", "oil", "beverage", "candy"}
    heads = [u for u in usda if u not in generic] or usda
    head_hit = 1.0 if (usda[0] in ing or heads[0] in ing) else 0.0
    return recall, head_hit


def judging_function(ingredient, usda_match):
    try:
        ing = "" if ingredient is None else str(ingredient)
        usd = "" if usda_match is None else str(usda_match)
        if not ing.strip() or not usd.strip():
            return 0.0

        # Separate parentheticals: they often name the actual form.
        paren = " ".join(re.findall(r"\(([^)]*)\)", ing))
        ing_main = re.sub(r"\([^)]*\)", " ", ing)
        ing_toks = _tokens(ing_main) + _tokens(paren)
        usda_toks = _tokens(usd)
        if not ing_toks or not usda_toks:
            return 0.0

        vi = _project(ing_toks)
        vu = _project(usda_toks)

        # Recoverability: a stated transform in the recipe means the USDA form
        # (before transform) is what was actually bought.
        recovered = 0.0
        ing_set = set(ing_toks)
        usda_set = {_stem(t) for t in usda_toks} | set(usda_toks)
        for verb, sources in _RECOVERY.items():
            if verb in ing_set and any(s in usda_set for s in sources):
                recovered = 1.0
                # project ingredient back to its source state
                src = _project([s for s in sources if s in usda_set])
                for a in _AXES:
                    if src[a] is not None:
                        vi[a] = src[a]
                break

        dist, evidence = _state_distance(vi, vu)
        form_sim = math.exp(-4.0 * dist * dist)  # 1.0 identical, ~0 far apart

        # Hard form clashes that change the dish regardless of axis averaging.
        clash = 0.0
        liquid_i = any(t in ing_set for t in ("broth", "stock"))
        soup_u = "soup" in usda_set
        if liquid_i and soup_u:
            clash += 0.35
        fresh_i = "fresh" in ing_set
        dried_u = any(t in usda_set for t in ("dried", "dehydrated", "spice", "spices", "powder"))
        if fresh_i and dried_u:
            clash += 0.4
        powder_u = any(t in usda_set for t in ("powder", "flour", "meal"))
        paste_i = "paste" in ing_set
        if paste_i and powder_u:
            clash += 0.3
        multi_i = " and " in (" " + ing_main.lower() + " ")
        if multi_i:
            clash += 0.25

        recall, head_hit = _identity_overlap(ing_toks, usda_toks)
        identity = 0.6 * recall + 0.4 * head_hit

        # Composite: identity establishes the candidate, form refines it.
        form_term = form_sim * (1.0 + 0.1 * min(evidence, 4) / 4.0)
        score = 55.0 * identity + 40.0 * form_term * (0.3 + 0.7 * identity)
        score += 6.0 * recovered * identity
        score *= max(0.0, 1.0 - clash)
        if identity <= 0.0:
            score = min(score, 15.0)

        # Small bonus when explicit form words literally coincide.
        shared_cues = {t for t in ing_set if t in _CUES} & {t for t in usda_toks if t in _CUES}
        score += 2.0 * min(len(shared_cues), 2) * (1.0 if identity > 0 else 0.0)

        if math.isnan(score) or math.isinf(score):
            return 0.0
        return round(max(0.0, min(100.0, score)), 4)
    except Exception:
        return 0.0
