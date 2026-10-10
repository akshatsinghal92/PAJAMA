import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize inputs
        ing_lower = ingredient.lower().strip()
        usda_lower = usda_match.lower().strip()

        # Remove gram weights like "300g", "20g" from ingredient
        ing_lower = re.sub(r'^\d+g?\s*', '', ing_lower)

        # Remove parentheticals
        ing_lower = re.sub(r'\([^)]*\)', '', ing_lower)
        usda_lower = re.sub(r'\([^)]*\)', '', usda_lower)

        # Trivial prep states that don't affect substitutability
        trivial_states = {
            'raw', 'fresh', 'chopped', 'diced', 'minced', 'sliced',
            'shredded', 'thawed', 'frozen', 'whole', 'halved', 'quartered',
            'cubed', 'grated', 'peeled', 'unpeeled', 'trimmed'
        }

        # Problem states that indicate preparation level differences
        problem_states = {
            'cooked', 'fried', 'baked', 'roasted', 'grilled', 'boiled',
            'steamed', 'sauteed', 'braised', 'simmered', 'toasted',
            'blanched', 'poached', 'smoked', 'cured', 'pickled', 'fermented'
        }

        # Extract words from both strings
        ing_words = set(re.findall(r'\b[a-z]+\b', ing_lower))
        usda_words = set(re.findall(r'\b[a-z]+\b', usda_lower))

        # Identify states present in each
        ing_trivial = ing_words & trivial_states
        usda_trivial = usda_words & trivial_states
        ing_problem = ing_words & problem_states
        usda_problem = usda_words & problem_states

        # Remove state words to get core food terms
        ing_core = ing_words - trivial_states - problem_states
        usda_core = usda_words - trivial_states - problem_states

        # Remove common non-food words
        stop_words = {'and', 'or', 'with', 'from', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of'}
        ing_core -= stop_words
        usda_core -= stop_words

        # Calculate base score from core term overlap
        if not ing_core and not usda_core:
            return 50.0

        overlap = ing_core & usda_core
        union = ing_core | usda_core

        if not union:
            base_score = 0.0
        else:
            # Jaccard similarity with bonus for high overlap
            jaccard = len(overlap) / len(union)
            base_score = jaccard * 100

        # Preparation state penalty system
        penalty = 0.0

        # Check for incompatible preparation states
        # Case 1: One has cooking state, other doesn't (or has raw/fresh)
        if ing_problem and not usda_problem:
            # Ingredient is cooked, USDA is not
            penalty += 40.0
        elif usda_problem and not ing_problem:
            # USDA is cooked, ingredient is not (or is raw/fresh)
            if 'raw' in ing_trivial or 'fresh' in ing_trivial or not ing_problem:
                penalty += 40.0
        elif ing_problem and usda_problem:
            # Both have cooking states - check if they match
            if ing_problem != usda_problem:
                penalty += 30.0

        # Case 2: Check for specific incompatible modifiers
        # "drained" vs "with oil" or "cooked"
        has_drained = 'drained' in ing_lower
        has_oil = 'oil' in usda_lower and 'with' in usda_lower
        has_cooked = 'cooked' in usda_lower

        if has_drained and (has_oil or has_cooked):
            penalty += 35.0

        # Case 3: "sauce" vs base ingredient mismatch
        ing_has_sauce = 'sauce' in ing_lower
        usda_has_sauce = 'sauce' in usda_lower
        if ing_has_sauce != usda_has_sauce:
            # One is sauce, other is not
            penalty += 35.0

        # Case 4: "paste" vs non-paste
        ing_has_paste = 'paste' in ing_lower
        usda_has_paste = 'paste' in usda_lower
        if ing_has_paste != usda_has_paste:
            penalty += 25.0

        # Case 5: canned presence check
        ing_canned = 'canned' in ing_lower
        usda_canned = 'canned' in usda_lower
        if ing_canned and usda_canned:
            # Both canned - check for state conflicts
            if has_drained and has_cooked:
                penalty += 30.0

        # Bonus for trivial state differences (these are OK)
        if ing_trivial and usda_trivial:
            # Having trivial states on both sides is fine
            bonus = 5.0
        elif (ing_trivial or usda_trivial) and not (ing_problem or usda_problem):
            # One has trivial state, other doesn't, but no problem states
            bonus = 10.0
        else:
            bonus = 0.0

        # Calculate final score
        final_score = max(0.0, min(100.0, base_score + bonus - penalty))

        return final_score

    except Exception:
        return 0.0
