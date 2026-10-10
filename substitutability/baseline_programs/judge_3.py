# Baseline — Processing/additive mismatch penalty. Starts from shared-token credit,
# then penalizes USDA entries that introduce a compound/processed form (sauce, paste,
# sweetened, seasoning, soup, fried) absent from the plain ingredient. Higher = more substitutable.
def judging_function(ingredient, usda_match):
    try:
        import re

        PROCESS = {
            "sauce", "paste", "soup", "sweetened", "seasoning", "mix", "fried",
            "breaded", "pickled", "canned", "imitation", "dressing", "bouillon",
            "roasted", "cooked", "powder",
        }

        def words(text):
            text = re.sub(r"\([^)]*\)", " ", str(text).lower())
            text = re.sub(r"\d+\s*g\b", " ", text)
            text = re.sub(r"[^a-z\s]", " ", text)
            return [w for w in text.split() if w]

        ing_w = set(words(ingredient))
        usda_w = set(words(usda_match))
        if not ing_w or not usda_w:
            return 5.0

        content = (ing_w & usda_w) - {"of", "the", "a", "and", "or"}
        base = min(6.0, 2.0 * len(content))

        # Processing terms present in USDA but not implied by the ingredient -> penalty.
        added_process = (usda_w & PROCESS) - ing_w
        penalty = 2.5 * len(added_process)

        # Reward neutral baseline so a plain-vs-plain match sits mid-high.
        score = 4.0 + base - penalty
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 5.0
