import re

# Variant 2: character-trigram profile comparison between the ingredient's
# head phrase and every "natural reading" of the USDA primary food
# (e.g. "Cheese, cottage" -> "cottage cheese").

_PREP = re.compile(
    r"\b(fresh|frozen|canned|chopped|diced|sliced|minced|uncooked|cooked|raw|"
    r"large|small|medium|thawed|drained|peeled|organic|boneless|skinless|"
    r"finely|roughly|lightly|packed|heaping|about)\b"
)


def _ingredient_phrase(s):
    s = s.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.split(",")[0]
    s = re.sub(r"^\s*[\d./]+\s*(g|gram|grams|kg|ml|l|oz|lb)?\b", " ", s)
    s = _PREP.sub(" ", s)
    s = re.sub(r"[^a-z ]", " ", s)
    return " ".join(s.split())


def _usda_readings(s):
    s = s.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    segs = [" ".join(re.sub(r"[^a-z ]", " ", x).split()) for x in s.split(",")]
    segs = [x for x in segs if x]
    if not segs:
        return []
    readings = [segs[0]]
    if len(segs) >= 2:
        readings.append(segs[1] + " " + segs[0])
        readings.append(segs[0] + " " + segs[1])
    if len(segs) >= 3:
        readings.append(segs[2] + " " + segs[1] + " " + segs[0])
    return readings


def _trigrams(text):
    padded = "  " + text.replace(" ", "_") + " "
    grams = {}
    for i in range(len(padded) - 2):
        g = padded[i:i + 3]
        grams[g] = grams.get(g, 0) + 1
    return grams


def _dice(a, b):
    ga, gb = _trigrams(a), _trigrams(b)
    if not ga or not gb:
        return 0.0
    inter = sum(min(v, gb.get(k, 0)) for k, v in ga.items())
    return 2.0 * inter / (sum(ga.values()) + sum(gb.values()))


def _last_word(text):
    w = text.split()
    return w[-1] if w else ""


def _word_sim(a, b):
    if not a or not b:
        return 0.0
    a, b = a.rstrip("s"), b.rstrip("s")
    if a == b:
        return 1.0
    return _dice(a, b)


def judging_function(ingredient, usda_match):
    try:
        phrase = _ingredient_phrase(str(ingredient or ""))
        readings = _usda_readings(str(usda_match or ""))
        if not phrase or not readings:
            return 0.0

        best_phrase = max(_dice(phrase, r) for r in readings)

        # Head-noun comparison: the ingredient head vs the USDA primary head
        ing_head = _last_word(phrase)
        primary = readings[0]
        head_sims = [_word_sim(ing_head, w) for w in primary.split()]
        # a category-style primary ("Cheese, cottage") puts the identity in seg 2
        if len(readings) > 1:
            head_sims += [_word_sim(ing_head, w) for w in readings[1].split()]
        head = max(head_sims) if head_sims else 0.0

        # Core substance check: does the USDA primary head appear in the ingredient?
        usda_head = _last_word(primary)
        reverse = max([_word_sim(usda_head, w) for w in phrase.split()] or [0.0])

        score = 45.0 * head + 35.0 * best_phrase + 20.0 * reverse
        # Hard penalty when neither direction finds the core noun
        if head < 0.5 and reverse < 0.5:
            score *= 0.4
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
