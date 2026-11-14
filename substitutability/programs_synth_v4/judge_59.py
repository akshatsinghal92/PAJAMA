import re
import math

# Variant 3: segment-level brand classification + character trigram coverage.
# Each USDA comma segment is classified as BRAND (all-caps / trademark-like) or GENERIC.
# Generic segments are matched to the ingredient by character trigram Dice similarity;
# brand segments are scanned for variant-implying cues that the ingredient never asked for.

_VARIANT_CUES = {
    "flavored", "flavoured", "flavor", "flavour", "vanilla", "chocolate", "strawberry",
    "honey", "cinnamon", "maple", "berry", "lemon", "lime", "orange", "mint", "caramel",
    "plant", "vegan", "almond", "soy", "oat", "coconut", "rice", "veggie", "meatless",
    "light", "lite", "lowfat", "diet", "zero", "sugarfree", "reduced", "fat-free",
    "spicy", "hot", "bbq", "barbecue", "ranch", "garlic", "cheddar", "nacho", "sweetened",
    "unsweetened", "glutenfree", "gluten-free", "decaf", "organic", "whole", "protein",
}

_TM_RE = re.compile(r"(®|™|\(r\)|\(tm\)|\btm\b|!|')")
_STOP = {"and", "or", "with", "the", "a", "of", "in", "for", "to", "nfs", "ns", "raw",
         "fresh", "plain", "from", "style", "type", "made"}


def _norm(s):
    s = re.sub(r"\(.*?\)", " ", s.lower())
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)\b", " ", s)
    s = re.sub(r"[^a-z\s-]", " ", s)
    return " ".join(w for w in s.split() if w not in _STOP)


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _grams(text):
    out = set()
    for w in text.split():
        w = "#" + _stem(w) + "#"
        for i in range(len(w) - 2):
            out.add(w[i:i + 3])
    return out


def _is_brand_segment(raw):
    letters = re.sub(r"[^A-Za-z]", "", raw)
    if not letters:
        return False
    caps_words = [w for w in re.findall(r"[A-Za-z][A-Za-z'!&.-]*", raw) if len(w) >= 2]
    upper = [w for w in caps_words if w.isupper()]
    if caps_words and len(upper) >= max(1, math.ceil(0.5 * len(caps_words))):
        return True
    if _TM_RE.search(raw):
        return True
    return False


def judging_function(ingredient, usda_match):
    try:
        ing_raw = str(ingredient or "")
        usda_raw = str(usda_match or "")
        if not ing_raw.strip() or not usda_raw.strip():
            return 0.0

        # Brand mentioned in the ingredient's parentheticals also counts as brand intent
        ing_paren = " ".join(re.findall(r"\((.*?)\)", ing_raw)).lower()
        ing_main = _norm(ing_raw.split(",")[0])
        ing_full = _norm(ing_raw) + " " + re.sub(r"[^a-z\s]", " ", ing_paren)
        ing_words = set(_stem(w) for w in ing_full.split())
        ing_grams = _grams(ing_main) or _grams(ing_full)

        segments = [s.strip() for s in usda_raw.split(",") if s.strip()]
        usda_parens = re.findall(r"\((.*?)\)", usda_raw)

        generic, brands = [], []
        for idx, seg in enumerate(segments):
            if idx > 0 and _is_brand_segment(seg):
                brands.append(seg)
            else:
                generic.append(seg)
        for p in usda_parens:
            if _is_brand_segment(p):
                brands.append(p)

        gen_text = _norm(" ".join(generic))
        gen_grams = _grams(gen_text)
        if not ing_grams or not gen_grams:
            return 1.0

        inter = len(ing_grams & gen_grams)
        coverage = inter / float(len(ing_grams))          # how much of the ingredient is explained
        dice = 2.0 * inter / (len(ing_grams) + len(gen_grams))
        base = 0.65 * coverage + 0.35 * dice

        # Primary food (first segment) must relate to the ingredient
        head_hit = 0.0
        for seg in generic[:3]:
            hg = _grams(_norm(seg))
            if hg:
                head_hit = max(head_hit, len(hg & ing_grams) / float(len(hg)))
        if head_hit < 0.4:
            base *= 0.5

        # Brand analysis
        brand_penalty = 0.0
        brand_bonus = 0.0
        for b in brands:
            btoks = set(_stem(w) for w in re.sub(r"[^a-z\s-]", " ", b.lower()).split())
            unasked = [t for t in btoks if t in _VARIANT_CUES and t not in ing_words]
            if unasked:
                brand_penalty += 0.18 * min(3, len(unasked))
            else:
                # Brand is just a commercial label for the same generic product
                brand_bonus += 0.03

        # Variant cues in generic part not requested by ingredient (brand-like flavoured product)
        gen_words = set(_stem(w) for w in gen_text.split())
        gen_unasked = [t for t in gen_words if t in _VARIANT_CUES and t not in ing_words]
        if brands and gen_unasked:
            brand_penalty += 0.08 * min(2, len(gen_unasked))

        # Ingredient specifies a variant cue the entry lacks entirely
        ing_cues = [t for t in ing_words if t in _VARIANT_CUES]
        all_usda_words = set(_stem(w) for w in re.sub(r"[^a-z\s-]", " ", usda_raw.lower()).split())
        missing_cues = [t for t in ing_cues if t not in all_usda_words]
        brand_penalty += 0.12 * min(2, len(missing_cues))

        score = base + brand_bonus - brand_penalty
        score = max(0.0, min(1.0, score))
        return round(score * 10.0, 4)
    except Exception:
        return 0.0
