import re

# Segment-ledger approach: the USDA description is split into comma segments,
# each segment is classified as COVERED (implied by ingredient), NEUTRAL
# (a diner would not notice), or EXTRA (an unimplied, noticeable qualifier).
# Ingredient qualifiers are likewise tallied as KEPT or DROPPED.
# Final score is a ledger balance mapped onto 0-100.

_NEUTRAL_SEGMENTS = {
    "raw", "fresh", "ns as to fat eaten", "ns as to form", "variety meats and by-products",
    "imported", "new zealand", "australian", "mature seeds", "separable lean and fat",
    "choice", "select", "all grades", "regular", "plain", "crude", "whole",
    "unprepared", "uncooked", "not further specified", "nfs", "commercial",
    "includes foods for usda's food distribution program", "edible portion",
    "bulk", "prepared", "lean and fat", "unenriched", "enriched",
}

_NEUTRAL_WORDS = {
    "raw", "fresh", "ns", "as", "to", "fat", "eaten", "and", "by", "products",
    "variety", "meats", "imported", "new", "zealand", "mature", "seeds", "separable",
    "lean", "choice", "select", "trimmed", "of", "or", "the", "with", "a", "in",
    "regular", "plain", "crude", "whole", "uncooked", "unprepared", "includes",
    "foods", "for", "usda", "usda's", "distribution", "program", "nfs", "grades",
    "all", "edible", "portion", "commercial", "s",
}

# qualifiers a diner would notice if added or dropped
_NOTICEABLE = {
    "cooked", "boiled", "roasted", "fried", "baked", "simmered", "braised", "grilled",
    "stewed", "steamed", "canned", "frozen", "dried", "dry", "dehydrated", "smoked",
    "sweetened", "unsweetened", "salted", "unsalted", "lowfat", "nonfat", "fat-free",
    "reduced", "light", "lite", "diet", "skim", "tart", "sour", "sweet", "spicy",
    "mix", "flavored", "breaded", "battered", "stuffed", "marinated", "pickled",
    "creamed", "instant", "powdered", "concentrate", "juice", "syrup", "crackers",
    "chips", "candied", "glazed", "with", "skin", "muscadine", "kidney", "red", "white",
    "black", "green", "yellow", "extra", "virgin", "greek", "oats", "oat", "milkfat",
    "patty", "sauce", "soup", "added", "from", "alkali", "hi-fat", "breakfast",
}

_PREP_WORDS = {
    "sliced", "diced", "chopped", "minced", "cubed", "crumbled", "grated", "shredded",
    "thawed", "soaked", "overnight", "trimmed", "visible", "divided", "optional",
    "peeled", "halved", "quartered", "rinsed", "drained", "packed", "loosely",
    "finely", "roughly", "coarsely", "thinly", "large", "small", "medium", "piece",
    "pieces", "leaves", "about", "plus", "more", "taste", "for", "serving", "of",
    "and", "or", "to", "a", "the", "into", "cut", "torn", "washed", "room",
    "temperature", "softened", "melted", "beaten", "at", "tube", "jar", "can",
}

# ingredient adjectives that imply a USDA qualifier (alias -> implied tokens)
_IMPLIES = {
    "dutch-process": {"alkali", "processed"},
    "dutch": {"alkali", "processed"},
    "sirloin": {"steak"},
    "chuck": {"roast", "pot"},
    "brie": {"cheese"},
    "cottage": {"cheese"},
    "cheddar": {"cheese"},
    "sausage": {"pork"},
    "kidneys": {"kidney"},
    "breast": {"chicken"},
}


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _words(text):
    return [w for w in re.findall(r"[a-z][a-z'\-]*", text.lower())]


def _clean_ingredient(ing):
    s = ing.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*[\d.,/]+\s*(g|kg|mg|ml|l|oz|lb|grams?)?\b", " ", s)
    s = re.sub(r"\b\d+[\d./]*\s*(g|kg|mg|ml|oz|lb)\b", " ", s)
    head, _, tail = s.partition(",")
    return head, tail


def _bigrams(w):
    w = "#" + w + "#"
    return {w[i:i + 2] for i in range(len(w) - 1)}


def _close(a, b):
    if a == b:
        return True
    sa, sb = _stem(a), _stem(b)
    if sa == sb:
        return True
    if len(sa) >= 5 and len(sb) >= 5 and (sa.startswith(sb) or sb.startswith(sa)):
        return True
    ba, bb = _bigrams(sa), _bigrams(sb)
    if not ba or not bb:
        return False
    return (2.0 * len(ba & bb) / (len(ba) + len(bb))) >= 0.8 and min(len(sa), len(sb)) >= 5


def _any_close(w, pool):
    for p in pool:
        if _close(w, p):
            return True
    return False


def judging_function(ingredient, usda_match):
    try:
        if not isinstance(ingredient, str) or not isinstance(usda_match, str):
            return 0.0
        if not ingredient.strip() or not usda_match.strip():
            return 0.0

        head, tail = _clean_ingredient(ingredient)
        head_words = [w for w in _words(head) if w not in _PREP_WORDS]
        tail_words = [w for w in _words(tail) if w not in _PREP_WORDS]
        if not head_words:
            head_words = _words(head)
        if not head_words:
            return 0.0

        # implied vocabulary from the ingredient
        ing_vocab = set(head_words) | set(tail_words)
        for w in list(ing_vocab):
            for k, v in _IMPLIES.items():
                if _close(w, k):
                    ing_vocab |= v
        ing_vocab_stems = {_stem(w) for w in ing_vocab}

        usda_text = re.sub(r"\([^)]*\)", " ", usda_match.lower())
        segments = [seg.strip() for seg in usda_text.split(",") if seg.strip()]
        if not segments:
            return 0.0

        covered = 0.0
        neutral = 0.0
        extra = 0.0
        usda_all_words = []
        for idx, seg in enumerate(segments):
            seg_words = _words(seg)
            usda_all_words.extend(seg_words)
            # lead segment is the primary food: weighted more
            weight = 1.6 if idx == 0 else 1.0
            if seg in _NEUTRAL_SEGMENTS:
                neutral += 1.0
                continue
            content = [w for w in seg_words if w not in _NEUTRAL_WORDS]
            if not content:
                neutral += 1.0
                continue
            hits = sum(1 for w in content if _stem(w) in ing_vocab_stems or _any_close(w, ing_vocab))
            frac = hits / float(len(content))
            if frac >= 0.5:
                covered += weight * frac
            else:
                noticeable = sum(1 for w in content
                                 if w in _NOTICEABLE and not (_stem(w) in ing_vocab_stems))
                # unmatched segment: added qualifier. heavier if noticeable
                penalty = weight * (1.0 - frac) * (1.0 + 0.9 * noticeable)
                if idx == 0:
                    penalty *= 1.5
                extra += penalty

        # how many ingredient head qualifiers survive in USDA
        usda_set = set(usda_all_words)
        kept = 0
        dropped = 0.0
        core = head_words[-1]
        core_found = _any_close(core, usda_set)
        for w in head_words:
            if _any_close(w, usda_set):
                kept += 1
            else:
                implied = False
                for k, v in _IMPLIES.items():
                    if _close(w, k) and any(_any_close(x, usda_set) for x in v):
                        implied = True
                        break
                if implied:
                    kept += 1
                else:
                    dropped += 1.3 if w in _NOTICEABLE else 1.0
        # tail state qualifiers (post-comma) matter less, but noticeable ones count
        for w in tail_words:
            if w in _NOTICEABLE and not _any_close(w, usda_set):
                dropped += 0.6

        n_head = float(len(head_words))
        keep_ratio = kept / n_head

        # state conflict: fresh/raw ingredient vs cooked entry, dried vs not
        state_pen = 0.0
        ing_low = ingredient.lower()
        cooked_terms = {"cooked", "boiled", "roasted", "simmered", "braised", "stewed", "fried", "baked"}
        if usda_set & cooked_terms and not (set(_words(ing_low)) & cooked_terms):
            state_pen += 1.2
        if ("dried" in ing_low or "dry" in _words(ing_low)) and "from dried" in usda_text:
            state_pen += 1.0

        balance = (
            3.0 * keep_ratio
            + 1.2 * covered
            + 0.15 * neutral
            - 1.1 * extra
            - 1.4 * dropped
            - state_pen
        )
        if not core_found:
            balance -= 2.5
        score = 50.0 + 12.0 * balance
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
