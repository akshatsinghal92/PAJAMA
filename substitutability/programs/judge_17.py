import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).lower()
        usda_match = str(usda_match).lower()

        # Preservation and form keywords
        preservation_forms = {
            'frozen': {'frozen', 'freeze-dried', 'icy'},
            'canned': {'canned', 'tinned', 'jarred', 'bottled'},
            'dried': {'dried', 'dehydrated', 'desiccated', 'dry'},
            'fresh': {'fresh', 'raw', 'uncooked'},
            'cooked': {'cooked', 'prepared', 'heated', 'baked', 'roasted', 'fried', 'grilled'},
            'paste': {'paste', 'puree', 'mashed'},
            'powder': {'powder', 'ground', 'powdered'},
            'liquid': {'liquid', 'juice', 'broth', 'stock', 'sauce', 'oil'},
        }

        # Extract preservation tokens from ingredient
        ingredient_forms = set()
        for form_type, keywords in preservation_forms.items():
            for keyword in keywords:
                if keyword in ingredient:
                    ingredient_forms.add(form_type)

        # Extract preservation tokens from USDA match
        usda_forms = set()
        for form_type, keywords in preservation_forms.items():
            for keyword in keywords:
                if keyword in usda_match:
                    usda_forms.add(form_type)

        # Base score starts at 50
        score = 50.0

        # If both have no explicit form markers, assume compatibility
        if not ingredient_forms and not usda_forms:
            score = 70.0
        # If forms match exactly, high score
        elif ingredient_forms == usda_forms:
            score = 90.0
        # If there's overlap, good score
        elif ingredient_forms & usda_forms:
            overlap_ratio = len(ingredient_forms & usda_forms) / max(len(ingredient_forms), len(usda_forms))
            score = 60.0 + 30.0 * overlap_ratio

        # Detect incompatible state pairs
        incompatible_pairs = [
            ({'cooked'}, {'fresh', 'raw', 'uncooked'}),
            ({'cooked'}, {'frozen'}),
            ({'paste', 'liquid'}, {'dried', 'powder'}),
            ({'dried', 'powder'}, {'canned'}),
        ]

        for pair_a, pair_b in incompatible_pairs:
            if (ingredient_forms & pair_a and usda_forms & pair_b) or \
               (ingredient_forms & pair_b and usda_forms & pair_a):
                score -= 40.0

        # Check for "drained" in ingredient but not in USDA (or vice versa with oil/sauce)
        if 'drained' in ingredient:
            if 'oil' in usda_match or 'sauce' in usda_match:
                score -= 30.0

        # Check for thawed + frozen compatibility (recoverable form)
        if 'thawed' in ingredient and 'frozen' in usda_match:
            score += 20.0

        # Detect sauce vs base ingredient mismatch
        if 'sauce' in ingredient and 'sauce' not in usda_match:
            score -= 25.0
        if 'sauce' in usda_match and 'sauce' not in ingredient:
            score -= 25.0

        # Word overlap bonus (excluding common words)
        stop_words = {'the', 'a', 'an', 'with', 'from', 'in', 'of', 'to'}
        ingredient_words = set(re.findall(r'\b[a-z]{3,}\b', ingredient)) - stop_words
        usda_words = set(re.findall(r'\b[a-z]{3,}\b', usda_match)) - stop_words

        if ingredient_words and usda_words:
            word_overlap = len(ingredient_words & usda_words) / len(ingredient_words | usda_words)
            score += 10.0 * word_overlap

        # Clamp score to 0-100 range
        return max(0.0, min(100.0, score))

    except Exception:
        return 50.0
