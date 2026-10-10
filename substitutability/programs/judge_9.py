import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = ingredient.strip().lower()
        usda_match = usda_match.strip().lower()

        # Remove gram weights like "200g", "30g"
        ingredient = re.sub(r'^\d+g?\s*', '', ingredient)

        # Remove parentheticals from ingredient
        ingredient = re.sub(r'\([^)]*\)', '', ingredient)

        # Trivial preparation states (can be ignored/applied easily)
        trivial_states = {
            'raw', 'fresh', 'chopped', 'diced', 'minced', 'sliced',
            'shredded', 'thawed', 'frozen', 'whole', 'halved', 'quartered',
            'peeled', 'unpeeled', 'crushed', 'ground', 'dried', 'grated'
        }

        # Significant states (change cooking/outcome)
        significant_states = {
            'cooked', 'fried', 'roasted', 'baked', 'boiled', 'steamed',
            'grilled', 'sauteed', 'braised', 'toasted', 'blanched'
        }

        # State modifiers that add complexity
        problematic_modifiers = {
            'with oil', 'with sauce', 'with butter', 'with cream',
            'in oil', 'in sauce', 'in brine', 'in syrup',
            'seasoned', 'marinated', 'breaded', 'battered'
        }

        # Extract tokens from both
        ing_tokens = set(re.findall(r'\b\w+\b', ingredient))
        usda_tokens = set(re.findall(r'\b\w+\b', usda_match))

        # Check for problematic modifiers (substring check)
        has_problematic = any(mod in usda_match for mod in problematic_modifiers)

        # Find state differences
        ing_trivial = ing_tokens & trivial_states
        ing_significant = ing_tokens & significant_states
        usda_trivial = usda_tokens & trivial_states
        usda_significant = usda_tokens & significant_states

        # Extract core food words (non-state words)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'from', 'of', 'for'}
        all_state_words = trivial_states | significant_states | stop_words

        ing_core = ing_tokens - all_state_words
        usda_core = usda_tokens - all_state_words

        # Core food overlap (Jaccard similarity)
        if ing_core or usda_core:
            core_overlap = len(ing_core & usda_core) / len(ing_core | usda_core)
        else:
            core_overlap = 0.0

        # Start with base score from core overlap
        score = core_overlap * 50.0

        # Preparation state analysis
        # If both have same significant states, neutral
        # If USDA has significant state not in ingredient, penalize heavily
        # If only trivial differences, reward

        usda_extra_significant = usda_significant - ing_significant
        ing_extra_significant = ing_significant - usda_significant

        if usda_extra_significant:
            # USDA has cooking state not in ingredient (bad)
            score -= len(usda_extra_significant) * 25.0

        if ing_extra_significant and not usda_significant:
            # Ingredient has cooking state but USDA doesn't (less critical)
            score -= len(ing_extra_significant) * 15.0

        # Problematic modifiers check
        if has_problematic:
            score -= 30.0

        # If no significant state differences and good core overlap, reward
        if not usda_extra_significant and not ing_extra_significant and core_overlap > 0.5:
            score += 30.0

        # Trivial state differences are okay, slight bonus
        trivial_diff = (ing_trivial | usda_trivial) - (ing_trivial & usda_trivial)
        if trivial_diff and not usda_extra_significant:
            score += 5.0

        # Clamp score to reasonable range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 0.0
