import re

# Lexical and Token Overlap, variant 6: Greedy String Tiling on the
# space-free content strings.
# Food names are often written as compounds in one source and split in the
# other (flaxseed / flax seed, cornmeal / corn meal, peanut butter /
# peanutbutter). Greedy String Tiling (as used in plagiarism detection)
# finds maximal non-overlapping common substrings ("tiles") of a minimum
# length, independent of order. We tile the content-token sequences of both
# texts (joined without spaces, tokens sorted so word order does not matter),
# and score 2*tiled/(|a|+|b|). Tiles that cover the ingredient head noun
# earn extra credit; tiles built only from modifier words are discounted.

_NOISE = set("""g gram grams kg ml oz lb cup cups tbsp tsp to taste from tube jar can
optional about divided and or of with without the a an in as for fresh chopped diced
minced sliced shredded grated thawed segmented peeled drained rinsed cubed finely
roughly large small medium nfs ns""".split())
_MODS = set("""raw cooked boiled baked roasted fried grilled steamed frozen canned dried
low fat lowfat nonfat reduced calorie sodium light lean salted sweetened whole plain
regular prepared heat dry skin not eaten only meat style made""".split())
_MIN_TILE = 4


def _content(text, is_ing):
    t = re.sub(r"\([^)]*\)", " ", text.lower())
    if is_ing:
        t = t.split(",")[0]
        t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", t)
    return [w for w in re.findall(r"[a-z]+", t) if w not in _NOISE and len(w) > 1]


def _gst(a, b, min_len):
    """Greedy String Tiling. Returns list of (start_a, start_b, length)."""
    marked_a = [False] * len(a)
    marked_b = [False] * len(b)
    tiles = []
    while True:
        max_len = min_len - 1
        matches = []
        for i in range(len(a)):
            if marked_a[i]:
                continue
            for j in range(len(b)):
                if marked_b[j]:
                    continue
                k = 0
                while (i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]
                       and not marked_a[i + k] and not marked_b[j + k]):
                    k += 1
                if k > max_len:
                    max_len = k
                    matches = [(i, j, k)]
                elif k == max_len and k >= min_len:
                    matches.append((i, j, k))
        if max_len < min_len:
            break
        for i, j, k in matches:
            if any(marked_a[i:i + k]) or any(marked_b[j:j + k]):
                continue
            for x in range(k):
                marked_a[i + x] = True
                marked_b[j + x] = True
            tiles.append((i, j, k))
    return tiles, marked_a


def judging_function(ingredient, usda_match):
    try:
        iw = _content(str(ingredient or ""), True)
        uw = _content(str(usda_match or ""), False)
        if not iw or not uw:
            return 0.0
        head = iw[-1]
        food_i = [w for w in iw if w not in _MODS] or iw
        food_u = [w for w in uw if w not in _MODS] or uw
        a = "".join(sorted(food_i))
        b = "".join(sorted(food_u))
        tiles, marked_a = _gst(a, b, _MIN_TILE)
        tiled = sum(k for _, _, k in tiles)
        sim = 2.0 * tiled / (len(a) + len(b)) if (a or b) else 0.0

        # head coverage: fraction of the head's characters inside tiles
        pos = a.find(head.rstrip("s")[:max(_MIN_TILE, len(head) - 1)])
        head_cov = 0.0
        if pos >= 0:
            span = marked_a[pos:pos + len(head)]
            head_cov = sum(span) / float(max(1, len(span)))
        # modifier-only agreement adds a little
        mods_i = set(iw) & _MODS
        mods_u = set(uw) & _MODS
        mod_bonus = 0.05 * len(mods_i & mods_u)
        score = 10.0 * min(1.0, 0.6 * sim + 0.4 * head_cov + mod_bonus)
        return round(max(0.0, score), 3)
    except Exception:
        return 0.0
