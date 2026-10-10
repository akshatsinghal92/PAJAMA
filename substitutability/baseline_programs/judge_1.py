# Baseline — Lexical/token overlap (Jaccard) of meaningful food tokens.
# Higher = more substitutable.
def judging_function(ingredient, usda_match):
    try:
        import re

        NOISE = {
            "g", "diced", "chopped", "sliced", "minced", "grated", "shredded",
            "to", "taste", "fresh", "raw", "of", "from", "tube", "a", "the",
            "ground", "whole", "large", "small", "and", "or",
        }

        def toks(text):
            text = re.sub(r"\([^)]*\)", " ", str(text).lower())
            text = re.sub(r"\d+\s*g\b", " ", text)   # drop gram weights
            text = re.sub(r"[^a-z\s]", " ", text)
            words = [w for w in text.split() if w and w not in NOISE]
            # crude singularization
            norm = []
            for w in words:
                if len(w) > 3 and w.endswith("es"):
                    w = w[:-2]
                elif len(w) > 3 and w.endswith("s"):
                    w = w[:-1]
                norm.append(w)
            return set(norm)

        a, b = toks(ingredient), toks(usda_match)
        if not a or not b:
            return 1.0
        inter = len(a & b)
        union = len(a | b)
        jaccard = inter / union if union else 0.0
        return round(10.0 * jaccard, 4)
    except Exception:
        return 1.0
