import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        ingredient = str(ingredient).lower().strip()
        usda_match = str(usda_match).lower().strip()

        # Remove gram weights like "200g" from ingredient
        ingredient = re.sub(r'^\d+g?\s*', '', ingredient)

        # Define trivial prep states that don't affect substitutability
        trivial_states = {
            'raw', 'fresh', 'chopped', 'diced', 'minced', 'sliced',
            'shredded', 'thawed', 'whole', 'crushed', 'ground',
            'peeled', 'cubed', 'halved', 'quartered', 'julienned',
            'grated', 'torn', 'trimmed', 'cleaned', 'washed'
        }

        # Define significant states that change the food substantially
        significant_states = {
            'cooked', 'fried', 'baked', 'roasted', 'grilled', 'boiled',
            'steamed', 'sauteed', 'sautéed', 'toasted', 'smoked', 'cured',
            'pickled', 'fermented', 'dried', 'freeze-dried', 'dehydrated',
            'blanched', 'poached', 'braised', 'stewed'
        }

        # Define preparation-level modifiers
        preparation_modifiers = {
            'with oil', 'with butter', 'with salt', 'with sugar',
            'in oil', 'in brine', 'in syrup', 'in water', 'in sauce',
            'seasoned', 'marinated', 'breaded', 'battered'
        }

        # Extract words from both strings
        ingredient_words = set(re.findall(r'\b\w+\b', ingredient))
        usda_words = set(re.findall(r'\b\w+\b', usda_match))

        # Check for multi-word preparation modifiers in both
        ingredient_text = ingredient
        usda_text = usda_match

        ing_has_prep_modifier = any(mod in ingredient_text for mod in preparation_modifiers)
        usda_has_prep_modifier = any(mod in usda_text for mod in preparation_modifiers)

        # Extract state descriptors
        ing_trivial = ingredient_words & trivial_states
        ing_significant = ingredient_words & significant_states
        usda_trivial = usda_words & trivial_states
        usda_significant = usda_words & significant_states

        # Base score starts at 100
        score = 100.0

        # PENALTY 1: Asymmetric significant states (one has it, other doesn't)
        if ing_significant and not usda_significant:
            score -= 40.0
        elif usda_significant and not ing_significant:
            score -= 40.0

        # PENALTY 2: Different significant states
        if ing_significant and usda_significant:
            if ing_significant != usda_significant:
                score -= 35.0

        # PENALTY 3: Preparation modifier mismatch (one has "with oil", other doesn't)
        if ing_has_prep_modifier != usda_has_prep_modifier:
            score -= 30.0

        # BONUS 1: Both have same trivial states (shows alignment)
        matching_trivial = ing_trivial & usda_trivial
        if matching_trivial:
            score += len(matching_trivial) * 5.0

        # BONUS 2: Core food term overlap (non-state words)
        non_state_ing = ingredient_words - trivial_states - significant_states
        non_state_usda = usda_words - trivial_states - significant_states

        # Filter out common non-food words
        stopwords = {'from', 'tube', 'can', 'jar', 'frozen', 'canned',
                    'drained', 'the', 'and', 'or', 'in', 'of', 'with'}
        non_state_ing = non_state_ing - stopwords
        non_state_usda = non_state_usda - stopwords

        if non_state_ing and non_state_usda:
            overlap = non_state_ing & non_state_usda
            overlap_ratio = len(overlap) / max(len(non_state_ing), len(non_state_usda))
            score += overlap_ratio * 20.0

        # PENALTY 4: "sauce" vs base ingredient mismatch
        ing_has_sauce = 'sauce' in ingredient_words or 'paste' in ingredient_words
        usda_has_sauce = 'sauce' in usda_words or 'paste' in usda_words
        if ing_has_sauce != usda_has_sauce:
            score -= 25.0

        # PENALTY 5: "canned" + "drained" in ingredient but USDA has extra descriptors
        if 'canned' in ingredient_words and 'drained' in ingredient_words:
            # Check if USDA has cooking states that weren't drained away
            if usda_significant or usda_has_prep_modifier:
                score -= 20.0

        # Normalize to 0-100 range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 50.0
