import re
import math


_NOTE_PHRASES = [
    "to taste", "for garnish", "for serving", "optional", "as needed", "if desired",
    "divided", "plus more", "or more", "about", "approximately", "roughly",
]

_FILLER = {
    "a", "an", "the", "and", "or", "of", "with", "in", "into", "for", "from", "to",
    "on", "at", "by", "g", "gram", "grams", "kg", "ml", "piece", "pieces", "cup",
    "cups", "tbsp", "tsp", "large", "small", "medium", "some", "few", "fine",
    "finely", "coarsely", "roughly", "thinly", "freshly", "lightly", "well",
    "tube", "jar", "can", "pack", "package", "bag", "inch", "nfs", "ns", "type",
    "mixed", "species", "made", "prepared", "style", "brand", "plain", "regular",
}

# Concept groups: tokens in the same group are treated as covering each other.
_EQUIV = [
    {"wrap", "wraps", "tortilla", "tortillas"},
    {"glass", "cellophane", "vermicelli"},
    {"poultry", "chicken", "broiler", "broilers", "fryer", "fryers"},
    {"shungiku", "chrysanthemum"},
    {"veggie", "vegetable", "vegetables", "meatless", "no meat"},
    {"dumpling", "dumplings", "wonton", "potsticker", "pot sticker"},
    {"cracker", "crackers"},
    {"skin-on", "skin"},
    {"cubed", "stew", "diced", "chunk", "chunks"},
    {"melted", "oil"},
    {"whole grain", "wheat", "whole wheat"},
    {"fresh", "raw"},
    {"ground", "minced", "mince"},
    {"dried", "dehydrated", "dry"},
    {"lean", "lowfat", "low fat"},
    {"patty", "patties"},
    {"fillet", "fillets", "filet"},
    {"noodle", "noodles"},
]

# State families: a qualifier from one family contradicts a qualifier from another family
_STATE_FAMILIES = {
    "raw": {"raw", "fresh", "uncooked"},
    "cooked": {"cooked", "boiled", "simmered", "broiled", "roasted", "baked",
               "fried", "grilled", "stewed", "braised", "steamed", "dry heat",
               "microwaved", "poached", "sauteed"},
    "dried": {"dried", "dehydrated", "dry"},
    "frozen": {"frozen"},
    "canned": {"canned"},
    "smoked": {"smoked"},
}

# Material qualifiers that, when present only on the USDA side, signal a modified product.
_MATERIAL_EXTRAS = {
    "lowfat": 1.6, "low fat": 1.6, "nonfat": 1.6, "fat free": 1.6, "reduced fat": 1.4,
    "low sodium": 1.5, "no salt": 1.4, "unsalted": 0.8, "sodium": 0.6,
    "lactose": 1.6, "lactose reduced": 1.6, "sugar free": 1.5, "sweetened": 0.8,
    "unsweetened": 0.8, "with vegetables": 1.8, "with fruit": 1.6, "fortified": 0.6,
    "greek": 1.4, "muscadine": 2.0, "mountain": 1.6, "hawaii": 1.0,
    "from dried": 1.4, "no added fat": 1.2, "added fat": 1.0, "fat": 0.5,
    "milkfat": 1.0, "%": 0.9, "imitation": 2.0, "substitute": 1.8,
    "diet": 1.4, "light": 1.0, "dry heat": 0.4,
}

# Words in the ingredient that are almost never material (preparation actions).
_PREP_ONLY = {"thawed", "chopped", "sliced", "cut", "pieces", "rinsed", "drained",
              "peeled", "trimmed", "washed", "softened", "beaten", "crushed",
              "torn", "halved", "quartered", "pitted", "seeded", "shredded",
              "grated", "packed", "room", "temperature", "paste"}


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"^\s*\d+(?:[.,]\d+)?\s*(?:g|grams?|kg|ml|oz|lb)?\b", " ", t)
    t = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:g|grams?|kg|ml|oz|lb)\b", " ", t)
    for p in _NOTE_PHRASES:
        t = t.replace(p, " ")
    return t


def _clean_usda(text):
    t = text.lower()
    t = re.sub(r"\(([^)]*)\)", r", \1", t)
    return t


def _phrases_present(text, vocab):
    found = []
    padded = " " + re.sub(r"[^a-z0-9%\- ]", " ", text) + " "
    for v in vocab:
        if v == "%":
            if "%" in text:
                found.append(v)
            continue
        if re.search(r"(?<![a-z])" + re.escape(v) + r"(?![a-z])", padded):
            found.append(v)
    return found


def _words(text):
    return [w for w in re.findall(r"[a-z][a-z\-]*", text) if w not in _FILLER and len(w) > 1]


def _stem(w):
    w = w.strip("-")
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            return w[:-len(suf)]
    return w


def _trigrams(w):
    p = "##" + w + "#"
    return {p[i:i + 3] for i in range(len(p) - 2)}


def _dice(a, b):
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return 2.0 * len(ta & tb) / (len(ta) + len(tb))


def _concept_ids(word, full_text):
    ids = set()
    for i, grp in enumerate(_EQUIV):
        for member in grp:
            if " " in member:
                if member in full_text and word in member.split():
                    ids.add(i)
            elif _stem(member) == _stem(word):
                ids.add(i)
    return ids


def _token_coverage(word, usda_words, usda_text, ing_text):
    """Best coverage strength in [0,1] for one ingredient word."""
    sw = _stem(word)
    best = 0.0
    for u in usda_words:
        su = _stem(u)
        if su == sw:
            return 1.0
        if len(sw) >= 4 and len(su) >= 4 and (su.startswith(sw) or sw.startswith(su)):
            best = max(best, 0.9)
        d = _dice(sw, su)
        if d >= 0.6:
            best = max(best, d)
    cid = _concept_ids(word, ing_text)
    if cid:
        for u in usda_words:
            if cid & _concept_ids(u, usda_text):
                best = max(best, 0.85)
                break
    return best


def _state_set(text):
    fams = set()
    for fam, words in _STATE_FAMILIES.items():
        if _phrases_present(text, words):
            fams.add(fam)
    return fams


def judging_function(ingredient, usda_match):
    try:
        if not isinstance(ingredient, str) or not isinstance(usda_match, str):
            return 0.0
        if not ingredient.strip() or not usda_match.strip():
            return 0.0

        ing = _clean_ingredient(ingredient)
        usd = _clean_usda(usda_match)

        # Split ingredient into a main phrase and trailing qualifier phrases.
        main = re.sub(r"\([^)]*\)", " ", ing).split(",")[0]
        ing_flat = re.sub(r"[(),]", " ", ing)

        ing_words = _words(ing_flat)
        usda_words = _words(usd)
        if not ing_words or not usda_words:
            return 0.0

        main_words = set(_words(main))
        # Head noun heuristic: last content word of the main phrase.
        main_list = [w for w in _words(main) if w not in _PREP_ONLY]
        head = main_list[-1] if main_list else ing_words[-1]

        # USDA primary food (first comma segment)
        usda_primary_words = _words(usd.split(",")[0])

        # ---- Weighted ingredient-side coverage ----
        total_w = 0.0
        covered_w = 0.0
        missed_material = 0
        for w in ing_words:
            if w in _PREP_ONLY:
                weight = 0.25
            elif w == head:
                weight = 3.0
            elif w in main_words:
                weight = 1.5
            else:
                weight = 1.0  # post-comma or parenthetical qualifier
            cov = _token_coverage(w, usda_words, usd, ing_flat)
            total_w += weight
            covered_w += weight * cov
            if cov < 0.5 and weight >= 1.0 and w != head:
                missed_material += 1
        coverage = covered_w / total_w if total_w else 0.0

        head_cov = _token_coverage(head, usda_words, usd, ing_flat)
        head_in_primary = _token_coverage(head, usda_primary_words, usd, ing_flat) >= 0.85

        # ---- State contradiction analysis ----
        ing_states = _state_set(ing_flat)
        usda_states = _state_set(usd)
        state_penalty = 0.0
        if ing_states and usda_states:
            if not (ing_states & usda_states):
                # dried vs "from dried" cooked, fresh vs cooked etc.
                state_penalty = 1.8
            elif usda_states - ing_states - {"smoked"}:
                state_penalty = 0.6
        elif ing_states and not usda_states:
            state_penalty = 0.4
        # "dried X" against "from dried" (i.e. cooked from dry) is a contradiction
        if "dried" in ing_states and "from dried" in usd:
            state_penalty = max(state_penalty, 1.6)

        # ---- USDA-only material qualifiers ----
        extra_penalty = 0.0
        for ph in _phrases_present(usd, _MATERIAL_EXTRAS.keys()):
            if ph == "%":
                if "%" not in ing:
                    extra_penalty += _MATERIAL_EXTRAS[ph]
                continue
            if ph in ing_flat:
                continue
            # if covered via equivalence group (e.g. lean ~ lowfat), soften
            toks = ph.split()
            if any(_token_coverage(t, ing_words, ing_flat, usd) >= 0.85 for t in toks):
                extra_penalty += _MATERIAL_EXTRAS[ph] * 0.5
            else:
                extra_penalty += _MATERIAL_EXTRAS[ph]
        extra_penalty = min(extra_penalty, 4.0)

        # Unexplained USDA words (beyond known descriptors) as mild noise.
        generic_usda = {"raw", "cooked", "meat", "only", "separable", "lean", "choice",
                        "select", "all", "grades", "fish", "spices", "oil", "cheese",
                        "beans", "noodles", "crackers", "fresh", "frozen", "unprepared",
                        "uncooked", "boneless", "skinless", "whole", "parts"}
        unexplained = 0
        for u in usda_words:
            if u in generic_usda:
                continue
            if _token_coverage(u, ing_words, ing_flat, usd) < 0.6:
                unexplained += 1
        noise = math.log1p(unexplained) * 0.35

        # ---- Combine ----
        score = 10.0 * coverage
        if head_cov < 0.5:
            score *= 0.35
        elif head_in_primary:
            score += 1.0
        score -= 0.9 * missed_material
        score -= state_penalty
        score -= extra_penalty
        score -= noise
        score += 1.5  # shift into positive range

        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
