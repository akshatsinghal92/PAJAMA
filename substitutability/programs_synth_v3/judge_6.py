import re
import math

_SYNONYMS = {
    "maize": "corn", "ox": "beef", "cow": "beef", "steer": "beef", "veal": "beef",
    "aubergine": "eggplant", "courgette": "zucchini", "coriander": "cilantro",
    "prawn": "shrimp", "prawns": "shrimp", "rocket": "arugula", "capsicum": "pepper",
    "mince": "ground", "minced": "ground", "scallion": "onion", "scallions": "onion",
    "spring onion": "onion", "garbanzo": "chickpea", "chickpeas": "chickpea",
    "icing": "powdered", "caster": "granulated", "lunch": "luncheon",
    "beetroot": "beet", "swede": "rutabaga", "mangetout": "pea", "hogget": "lamb",
    "mutton": "lamb", "flax": "flaxseed", "linseed": "flaxseed",
}

_FILLER = {
    "fresh", "frozen", "thawed", "dried", "raw", "cooked", "sliced", "chopped", "diced",
    "minced", "grated", "large", "small", "medium", "whole", "fine", "finely", "roughly",
    "boneless", "skinless", "organic", "dairy", "free", "dairy-free", "plain", "chunks",
    "chunk", "pieces", "piece", "of", "the", "a", "an", "for", "with", "from", "tube",
    "jar", "can", "canned", "tin", "tinned", "packet", "pack", "prepackaged", "or", "deli",
    "unsalted", "salted", "lean", "extra", "virgin", "baby", "ripe", "and", "in", "to",
    "taste", "peeled", "trimmed", "separable", "fat", "boiled", "uncooked", "regular",
    "100", "style", "type", "brand", "pure", "natural", "homemade", "store", "bought",
}

_FORM_SHIFT = {
    "juice", "powder", "paste", "sauce", "oil", "extract", "syrup", "flour", "jam",
    "jelly", "chips", "soup", "drink", "beverage", "milk", "cheese", "butter", "bar",
    "candy", "cereal", "flakes", "seed", "seeds", "bone", "skin", "germ", "bran",
    "mix", "blend", "dressing", "spread", "concentrate", "nectar", "dried", "patty",
    "sausage", "nugget", "nuggets", "broth", "stock", "cake", "bread", "pie",
}


def _norm_word(w):
    w = w.lower().strip("-'")
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return _SYNONYMS.get(w, w)


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.split(",")[0]
    t = re.sub(r"^\s*[\d./]+\s*(g|kg|ml|l|oz|lb|grams?|cups?|tbsp|tsp)?\b", " ", t)
    for k, v in _SYNONYMS.items():
        if " " in k:
            t = t.replace(k, v)
    words = re.findall(r"[a-z][a-z'-]*", t)
    out = []
    for w in words:
        if w in _FILLER:
            continue
        for part in w.split("-"):
            if part and part not in _FILLER:
                out.append(_norm_word(part))
    return out


def _usda_segments(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", lambda m: m.group(0)[1:-1], t)
    segs = []
    for s in t.split(","):
        ws = [_norm_word(w) for w in re.findall(r"[a-z][a-z'-]*", s)]
        ws = [w for w in ws if w not in _FILLER]
        if ws:
            segs.append(ws)
    return segs


def _trigrams(word):
    p = "  " + word + " "
    return {p[i:i + 3] for i in range(len(p) - 2)}


def _word_sim(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.85
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    j = len(ta & tb) / float(len(ta | tb))
    return j if j >= 0.45 else 0.0


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = _clean_ingredient(str(ingredient))
        segs = _usda_segments(str(usda_match))
        if not ing or not segs:
            return 0.0

        head = ing[-1]
        modifiers = ing[:-1]

        # Position-decayed alignment: each USDA segment carries less identity weight
        # the further it sits from the primary (first) food slot.
        def best_hit(word):
            best, pos = 0.0, None
            for si, seg in enumerate(segs):
                decay = 1.0 / (1.0 + 0.35 * si)
                for w in seg:
                    s = _word_sim(word, w) * decay
                    if s > best:
                        best, pos = s, si
            return best, pos

        head_score, head_pos = best_hit(head)

        mod_scores = [best_hit(m)[0] for m in modifiers]
        mod_cov = sum(mod_scores) / len(mod_scores) if mod_scores else 0.6

        # Primary USDA food identity: is the USDA head word explained by the ingredient?
        primary = segs[0]
        prim_cov = 0.0
        for pw in primary:
            prim_cov = max(prim_cov, max(_word_sim(pw, iw) for iw in ing))
        prim_words_unmatched = [pw for pw in primary
                                if max(_word_sim(pw, iw) for iw in ing) < 0.45]

        # Form-shift penalty: USDA introduces a substance word the ingredient lacks
        # (e.g. 'juice' for watermelon) or vice versa.
        ing_set = set(ing)
        usda_all = [w for s in segs[:2] for w in s]
        shift_pen = 0.0
        for w in usda_all:
            if w in _FORM_SHIFT and w not in ing_set and w != head:
                shift_pen += 1.0
        for w in ing:
            if w in _FORM_SHIFT and max(_word_sim(w, u) for s in segs for u in s) < 0.45:
                shift_pen += 1.2
        shift_pen = min(shift_pen, 3.0)

        # Composite ingredient ("X and Y mix") only partially covered.
        raw_l = str(ingredient).lower()
        compound_pen = 0.0
        if re.search(r"\b(and|&|mix|blend|medley)\b", raw_l):
            uncovered = [m for m, s in zip(modifiers, mod_scores) if s < 0.3]
            compound_pen = 1.5 + 0.5 * len(uncovered)

        score = 0.0
        score += 5.0 * head_score
        score += 2.0 * prim_cov
        score += 1.5 * mod_cov
        score -= 0.6 * min(len(prim_words_unmatched), 3) if head_score < 0.8 else 0.0
        score -= 1.3 * shift_pen
        score -= compound_pen
        if head_score < 0.3 and prim_cov < 0.3:
            score -= 2.0
        score = 1.5 + score
        if math.isnan(score):
            return 0.0
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
