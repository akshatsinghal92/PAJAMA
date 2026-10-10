import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize inputs
        ing_lower = ingredient.lower().strip()
        usda_lower = usda_match.lower().strip()

        # Remove gram weights (e.g., "300g", "40 g")
        ing_lower = re.sub(r'^\d+\s*g\s+', '', ing_lower)
        ing_lower = re.sub(r'^\d+\s*grams?\s+', '', ing_lower)

        # Remove parentheticals
        ing_lower = re.sub(r'\([^)]*\)', '', ing_lower)
        usda_lower = re.sub(r'\([^)]*\)', '', usda_lower)

        # Trivial prep states that don't affect substitutability
        trivial_states = {
            'raw', 'fresh', 'chopped', 'diced', 'minced', 'sliced',
            'shredded', 'grated', 'thawed', 'whole', 'halved', 'quartered',
            'peeled', 'unpeeled', 'crushed', 'ground', 'cubed'
        }

        # Significant prep states that affect substitutability
        significant_states = {
            'cooked', 'fried', 'baked', 'roasted', 'grilled', 'boiled',
            'steamed', 'sauteed', 'toasted', 'blanched', 'caramelized',
            'with oil', 'in oil', 'with sauce', 'in sauce', 'breaded',
            'marinated', 'seasoned', 'spiced'
        }

        # Extract tokens from both strings
        ing_tokens = set(re.findall(r'\b\w+\b', ing_lower))
        usda_tokens = set(re.findall(r'\b\w+\b', usda_lower))

        # Find core food words (excluding numbers and common prep words)
        stopwords = {'and', 'or', 'the', 'a', 'an', 'from', 'with', 'without', 'tube'}
        ing_core = ing_tokens - trivial_states - significant_states - stopwords
        usda_core = usda_tokens - trivial_states - significant_states - stopwords

        # Remove numeric tokens
        ing_core = {t for t in ing_core if not t.isdigit()}
        usda_core = {t for t in usda_core if not t.isdigit()}

        # Calculate core overlap score (Jaccard similarity)
        if not ing_core or not usda_core:
            core_similarity = 0.0
        else:
            intersection = len(ing_core & usda_core)
            union = len(ing_core | usda_core)
            core_similarity = intersection / union if union > 0 else 0.0

        # Detect trivial state differences
        ing_trivial = ing_tokens & trivial_states
        usda_trivial = usda_tokens & trivial_states
        trivial_diff = len(ing_trivial ^ usda_trivial)  # symmetric difference

        # Detect significant state differences
        ing_significant = ing_tokens & significant_states
        usda_significant = usda_tokens & significant_states

        # Check for multi-word significant states
        for state in significant_states:
            if ' ' in state:
                if state in ing_lower:
                    ing_significant.add(state.replace(' ', '_'))
                if state in usda_lower:
                    usda_significant.add(state.replace(' ', '_'))

        significant_diff = len(ing_significant ^ usda_significant)

        # Check for "sauce" vs base ingredient mismatch
        sauce_penalty = 0.0
        if 'sauce' in ing_tokens and 'sauce' not in usda_tokens:
            sauce_penalty = 3.0
        elif 'sauce' in usda_tokens and 'sauce' not in ing_tokens:
            sauce_penalty = 3.0

        # Check for "canned" + "drained" vs "with oil" type mismatches
        drain_mismatch = 0.0
        if 'drained' in ing_tokens:
            if any(oil_word in usda_lower for oil_word in ['with oil', 'in oil', 'oiled']):
                drain_mismatch = 4.0

        # Pasta special case: raw pasta vs cooked pasta is NOT substitutable
        pasta_penalty = 0.0
        if 'pasta' in ing_core or 'penne' in ing_core or 'spaghetti' in ing_core:
            if 'cooked' in usda_tokens and 'cooked' not in ing_tokens:
                pasta_penalty = 5.0
            elif 'cooked' in ing_tokens and 'cooked' not in usda_tokens:
                pasta_penalty = 5.0

        # Base score from core similarity (0-50 points)
        base_score = core_similarity * 50.0

        # Penalty for trivial differences (minor, -0.5 per difference)
        trivial_penalty = trivial_diff * 0.5

        # Heavy penalty for significant state differences (-5 per difference)
        significant_penalty = significant_diff * 5.0

        # Calculate final score
        final_score = (
            base_score
            - trivial_penalty
            - significant_penalty
            - sauce_penalty
            - drain_mismatch
            - pasta_penalty
        )

        # Bonus for very high core similarity with no significant differences
        if core_similarity > 0.7 and significant_diff == 0:
            final_score += 10.0

        # Ensure score is in reasonable range [0, 60]
        final_score = max(0.0, min(60.0, final_score))

        return final_score

    except Exception:
        return 0.0
