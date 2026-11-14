import re
import math

# Variant 4: "anatomical coordinate" model.
# Each anatomical part term is placed at a point in a small 3-D space
# (kingdom-region axis, tissue axis, processing-form axis). The distance
# between the ingredient's part-cloud and the USDA entry's part-cloud gives
# a part-mismatch penalty; a character-trigram Dice coefficient on the
# primary food anchors the comparison. Final score = 100 * sigmoid(logit).

_PART_COORDS = {
    # plant parts: x in [0, 4]
    "leaf": (0.0, 0.0, 0.0), "leaves": (0.0, 0.0, 0.0), "greens": (0.0, 0.0, 0.0),
    "top": (0.0, 0.2, 0.0), "tops": (0.0, 0.2, 0.0),
    "stem": (1.0, 0.0, 0.0), "stalk": (1.0, 0.0, 0.0), "stalks": (1.0, 0.0, 0.0),
    "shoot": (1.0, 0.3, 0.0), "shoots": (1.0, 0.3, 0.0),
    "root": (2.0, 0.0, 0.0), "roots": (2.0, 0.0, 0.0), "tuber": (2.0, 0.2, 0.0),
    "bulb": (2.0, 0.5, 0.0),
    "seed": (3.0, 0.0, 0.0), "seeds": (3.0, 0.0, 0.0), "kernel": (3.0, 0.3, 0.0),
    "kernels": (3.0, 0.3, 0.0), "germ": (3.0, 0.6, 0.0), "bran": (3.0, 0.9, 0.0),
    "flower": (4.0, 0.0, 0.0), "flowers": (4.0, 0.0, 0.0), "blossom": (4.0, 0.0, 0.0),
    "blossoms": (4.0, 0.0, 0.0),
    "peel": (5.0, 2.0, 0.0), "zest": (5.0, 2.0, 0.2), "rind": (5.0, 2.2, 0.0),
    "skin": (5.0, 2.5, 0.0), "flesh": (5.0, 0.0, 0.0), "pulp": (5.0, 0.3, 0.0),
    "juice": (5.0, 0.0, 3.0),
    # egg parts
    "yolk": (7.0, 0.0, 0.0), "yolks": (7.0, 0.0, 0.0),
    "white": (7.0, 3.0, 0.0), "whites": (7.0, 3.0, 0.0),
    # poultry cuts
    "breast": (10.0, 0.0, 0.0), "tenderloins": (10.0, 0.4, 0.0),
    "thigh": (11.5, 0.0, 0.0), "thighs": (11.5, 0.0, 0.0),
    "drumstick": (12.0, 0.0, 0.0), "drumsticks": (12.0, 0.0, 0.0),
    "leg": (11.8, 0.0, 0.0), "legs": (11.8, 0.0, 0.0),
    "wing": (13.0, 0.0, 0.0), "wings": (13.0, 0.0, 0.0),
    "back": (13.5, 1.0, 0.0), "neck": (13.5, 1.2, 0.0),
    # red-meat cuts
    "loin": (20.0, 0.0, 0.0), "tenderloin": (20.0, 0.3, 0.0), "sirloin": (20.4, 0.0, 0.0),
    "ribeye": (20.6, 0.0, 0.0), "rib": (20.8, 0.4, 0.0), "ribs": (20.8, 0.4, 0.0),
    "chop": (20.2, 0.3, 0.0), "chops": (20.2, 0.3, 0.0),
    "shoulder": (22.0, 0.0, 0.0), "chuck": (22.0, 0.2, 0.0), "butt": (22.2, 0.0, 0.0),
    "brisket": (22.5, 0.5, 0.0), "shank": (23.0, 0.0, 0.0), "flank": (21.5, 0.6, 0.0),
    "belly": (21.5, 1.2, 0.0), "round": (23.3, 0.0, 0.0), "rump": (23.3, 0.2, 0.0),
    "ham": (23.5, 0.0, 0.0), "hock": (23.8, 0.5, 0.0), "trotter": (24.0, 1.0, 0.0),
    "oxtail": (24.0, 1.0, 0.0), "tail": (24.0, 1.0, 0.0), "cheek": (24.2, 1.0, 0.0),
    "stew": (22.6, 0.4, 0.0),
    # offal
    "liver": (30.0, 0.0, 0.0), "kidney": (31.0, 0.0, 0.0), "kidneys": (31.0, 0.0, 0.0),
    "heart": (32.0, 0.0, 0.0), "tongue": (33.0, 0.0, 0.0), "tripe": (34.0, 0.0, 0.0),
    "gizzard": (32.5, 0.0, 0.0), "gizzards": (32.5, 0.0, 0.0),
    "sweetbread": (35.0, 0.0, 0.0), "sweetbreads": (35.0, 0.0, 0.0),
    "marrow": (36.0, 0.0, 0.0), "bone": (36.0, 1.0, 0.0), "bones": (36.0, 1.0, 0.0),
    "giblets": (31.5, 0.5, 0.0),
    # seafood parts
    "fillet": (40.0, 0.0, 1.0), "fillets": (40.0, 0.0, 1.0), "steak": (40.0, 0.2, 1.0),
    "steaks": (40.0, 0.2, 1.0), "roe": (42.0, 0.0, 0.0), "claw": (41.0, 0.0, 0.0),
    "claws": (41.0, 0.0, 0.0),
}

# Processing/form axis: these modify the z coordinate of whatever part co-occurs
_FORM_Z = {
    "ground": 2.0, "minced": 2.0, "mince": 2.0, "whole": 0.0,
    "boneless": 0.5, "bone-in": 0.5, "skinless": 0.4,
    "butter": 4.0, "paste": 3.0, "powder": 3.5, "flour": 3.5, "meal": 3.2,
    "oil": 4.5, "crumbs": 3.4, "sauce": 4.0, "puree": 2.5,
}

# Parts that a USDA entry may state when the recipe is silent; when the recipe
# names a specific part and USDA a different one, distance drives the penalty.
_STOP = set("""
g kg mg ml l oz lb lbs cup cups tbsp tsp of and or the a an with without for to
fresh freshly raw cooked chopped diced sliced cubed shredded grated optional
large small medium ripe dried dry frozen thawed into in about plus finely
roughly thinly cut pieces piece garnish taste nfs ns all commercial varieties
""".split())


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)?\b", " ", t)
    t = re.sub(r"[^a-z\- ]", " ", t)
    return t


def _tokens(text):
    return [w for w in _clean(text).replace("-", " ").split() if w]


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _part_cloud(text):
    raw = _clean(text)
    toks = raw.split()
    parts = []
    zshift = 0.0
    for w in toks:
        if w in _FORM_Z:
            zshift = max(zshift, _FORM_Z[w])
    for w in toks:
        if w in _PART_COORDS:
            x, y, z = _PART_COORDS[w]
            parts.append((x, y, z + zshift))
    return parts, zshift


def _trigrams(s):
    s = "  " + s + " "
    return {s[i:i + 3] for i in range(len(s) - 2)}


def _dice(a, b):
    if not a or not b:
        return 0.0
    ta, tb = _trigrams(a), _trigrams(b)
    inter = len(ta & tb)
    return 2.0 * inter / (len(ta) + len(tb))


def _cloud_distance(pa, pb):
    # symmetric average nearest-neighbour distance
    def one_way(src, dst):
        tot = 0.0
        for p in src:
            tot += min(math.sqrt(sum((p[i] - q[i]) ** 2 for i in range(3))) for q in dst)
        return tot / len(src)
    return 0.5 * (one_way(pa, pb) + one_way(pb, pa))


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usd = str(usda_match or "")
        if not ing.strip() or not usd.strip():
            return 0.0

        # Recipe head: drop post-comma state
        ing_head = ing.split(",")[0]
        ing_toks = [_stem(w) for w in _tokens(ing_head) if w not in _STOP]
        usd_segments = [s for s in usd.split(",") if s.strip()]
        primary = " ".join(_stem(w) for w in _tokens(usd_segments[0]) if w not in _STOP) if usd_segments else ""
        usd_toks = [_stem(w) for w in _tokens(usd) if w not in _STOP]

        if not ing_toks:
            ing_toks = [_stem(w) for w in _tokens(ing_head)]
        if not usd_toks:
            return 5.0

        ing_str = " ".join(ing_toks)
        usd_set = set(usd_toks)
        ing_set = set(ing_toks)

        # --- identity anchor ---
        # best per-token trigram similarity of each recipe token into USDA tokens
        per_tok = []
        for t in ing_set:
            per_tok.append(max(_dice(t, u) for u in usd_set))
        coverage = sum(per_tok) / len(per_tok) if per_tok else 0.0
        primary_sim = _dice(ing_str, primary) if primary else 0.0
        # does the recipe's main noun (last token) appear in the USDA primary segment?
        head_noun = ing_toks[-1]
        head_in_primary = 1.0 if primary and any(_dice(head_noun, p) > 0.7 for p in primary.split()) else 0.0
        anchor = 0.55 * coverage + 0.25 * primary_sim + 0.20 * head_in_primary

        # --- anatomical part distance ---
        pa, za = _part_cloud(ing_head)
        pb, zb = _part_cloud(usd)
        if pa and pb:
            dist = _cloud_distance(pa, pb)
            part_term = 1.6 - 1.1 * math.log1p(dist)
        elif pa and not pb:
            # recipe names a part the USDA entry leaves unspecified
            part_term = 0.2 - 0.25 * za
        elif pb and not pa:
            # USDA specifies a part, recipe silent: mild penalty if it's an
            # unusual part (offal/peel/greens), neutral otherwise
            unusual = any(p[0] >= 30 or p[0] in (0.0, 5.0) for p in pb)
            part_term = -0.6 if unusual else 0.1
        else:
            part_term = 0.3

        # processed-form mismatch (whole vs butter/paste/powder/ground)
        form_gap = abs(za - zb)
        form_term = -0.55 * form_gap

        # dish/composite signals in USDA that don't appear in recipe
        composite = 0
        for kw in ("entree", "with", "dinner", "mix", "cookies", "chips", "sandwich", "meal"):
            if kw in usd.lower() and kw not in ing.lower():
                composite += 1
        composite_term = -0.9 * composite

        logit = -2.4 + 5.2 * anchor + part_term + form_term + composite_term
        score = 100.0 / (1.0 + math.exp(-logit))
        if score != score:
            return 0.0
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
