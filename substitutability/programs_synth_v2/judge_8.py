import re

# Variant 8: phonetic-skeleton + word-sequence LCS.
# 1) Convert the USDA description into a natural English noun phrase by
#    reading its fields in reverse order of specificity
#    ("Cheese, cottage, low fat" -> "cottage cheese").
# 2) Encode every word with a Soundex-like phonetic code, which tolerates
#    spelling variants (yoghurt/yogurt, chili/chile) but keeps different
#    substances apart (garlic G642 vs guava G100).
# 3) Score = longest common subsequence of phonetic codes (order matters:
#    head noun must line up at the end) blended with exact head agreement.

_IGNORE = set("""fresh frozen canned raw cooked uncooked chopped diced sliced minced
grated shredded large small medium thawed drained peeled nfs ns and or of
with without the a an in for from to plain prepared""".split())

_SOUNDEX = {}
for _letters, _digit in (("bfpv", "1"), ("cgjkqsxz", "2"), ("dt", "3"),
                         ("l", "4"), ("mn", "5"), ("r", "6")):
    for _c in _letters:
        _SOUNDEX[_c] = _digit


def _code(word):
    w = word.rstrip("s") if len(word) > 3 else word
    if not w:
        return ""
    out = w[0]
    last = _SOUNDEX.get(w[0], "")
    for c in w[1:]:
        d = _SOUNDEX.get(c, "")
        if d and d != last:
            out += d
        if c not in "hw":
            last = d
    return (out + "000")[:4]


def _ing_phrase(text):
    t = re.sub(r"\([^)]*\)", " ", text.lower()).split(",")[0]
    t = re.sub(r"\d+(\.\d+)?", " ", t)
    return [w for w in re.findall(r"[a-z]+", t) if w not in _IGNORE and w not in ("g", "ml", "kg", "oz")]


def _usda_phrase(text):
    t = re.sub(r"\([^)]*\)", " ", text.lower())
    fields = []
    for f in t.split(","):
        ws = [w for w in re.findall(r"[a-z]+", f) if w not in _IGNORE]
        if ws:
            fields.append(ws)
    if not fields:
        return [], []
    if len(fields[0]) == 1 and len(fields) > 1:
        phrase = fields[1] + fields[0]          # qualifier + category noun
    else:
        phrase = list(fields[0])
    extra = [w for f in fields[2:] for w in f] if len(fields[0]) == 1 else [w for f in fields[1:] for w in f]
    return phrase, extra


def _lcs(a, b):
    if not a or not b:
        return 0
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[-1][-1]


def judging_function(ingredient, usda_match):
    try:
        ip = _ing_phrase(str(ingredient or ""))
        up, extra = _usda_phrase(str(usda_match or ""))
        if not ip or not up:
            return 0.0
        ic = [_code(w) for w in ip]
        uc = [_code(w) for w in up]
        ec = [_code(w) for w in extra]

        l = _lcs(ic, uc)
        lcs_score = 2.0 * l / (len(ic) + len(uc))

        head_same = ic[-1] == uc[-1]
        head_in = ic[-1] in uc
        head_in_extra = ic[-1] in ec

        score = 55.0 * lcs_score
        if head_same:
            score += 45.0
        elif head_in:
            score += 28.0
        elif head_in_extra:
            score += 10.0
        else:
            score *= 0.5
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
