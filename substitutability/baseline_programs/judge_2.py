# Baseline — Core food head match: does the ingredient's head food noun appear
# in the USDA entry's primary food (text before the first comma)? Higher = more substitutable.
def judging_function(ingredient, usda_match):
    try:
        import re

        NOISE = {
            "g", "diced", "chopped", "sliced", "minced", "grated", "shredded",
            "to", "taste", "fresh", "raw", "of", "from", "tube", "ground",
            "whole", "large", "small", "and", "or", "thawed", "frozen", "canned",
            "dried", "melted",
        }

        def clean(text):
            text = re.sub(r"\([^)]*\)", " ", str(text).lower())
            text = re.sub(r"\d+\s*g\b", " ", text)
            text = re.sub(r"[^a-z\s]", " ", text)
            return [w for w in text.split() if w and w not in NOISE]

        ing_tokens = clean(ingredient)
        # USDA primary food = text before first comma
        primary = str(usda_match).split(",")[0]
        usda_tokens = set(clean(primary))
        usda_all = set(clean(usda_match))
        if not ing_tokens or not usda_all:
            return 1.0

        # The ingredient head is usually the last meaningful token (pre-comma region).
        ing_pre = str(ingredient).split(",")[0]
        ing_pre_tokens = clean(ing_pre)
        head = ing_pre_tokens[-1] if ing_pre_tokens else ing_tokens[-1]

        score = 0.0
        if head in usda_tokens:
            score += 7.0           # head food is the USDA primary food
        elif head in usda_all:
            score += 3.5           # head appears only as a USDA descriptor
        # small bonus for any additional shared token
        shared = len(set(ing_tokens) & usda_all)
        score += min(3.0, shared)
        return round(min(10.0, score), 4)
    except Exception:
        return 1.0
