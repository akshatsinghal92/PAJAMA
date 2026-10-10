import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ing_lower = ingredient.lower()
        usda_lower = usda_match.lower()

        # Remove gram weight prefix (e.g., "200g ")
        ing_lower = re.sub(r'^\d+g?\s+', '', ing_lower)

        # Extract core terms (remove punctuation for token comparison)
        ing_tokens = set(re.findall(r'\b[a-z]+\b', ing_lower))
        usda_tokens = set(re.findall(r'\b[a-z]+\b', usda_lower))

        # Define preparation state markers that affect culinary role
        state_markers = {
            'cooked', 'raw', 'uncooked', 'fresh', 'dried', 'frozen',
            'thawed', 'canned', 'drained', 'ground', 'whole', 'chopped',
            'sliced', 'shredded', 'minced', 'crushed', 'puree', 'pureed',
            'paste', 'diced', 'blanched', 'roasted', 'toasted', 'fried',
            'boiled', 'steamed', 'smoked', 'pickled', 'fermented'
        }

        # Identify liquid vs solid role markers
        liquid_markers = {'oil', 'sauce', 'vinegar', 'syrup', 'juice', 'milk', 'water', 'broth', 'stock'}
        solid_markers = {'paste', 'powder', 'flour', 'meal', 'flakes'}

        # Extract state markers present in each
        ing_states = ing_tokens & state_markers
        usda_states = usda_tokens & state_markers

        # Start with base score
        score = 50.0

        # Token overlap - reward shared core food terms
        common_tokens = ing_tokens & usda_tokens
        if common_tokens:
            score += len(common_tokens) * 3

        # Penalize state conflicts heavily (these break culinary role)
        conflicting_states = {
            ('raw', 'cooked'), ('fresh', 'dried'), ('fresh', 'canned'),
            ('drained', 'oil'), ('whole', 'ground'), ('whole', 'diced'),
            ('whole', 'chopped'), ('whole', 'crushed'), ('paste', 'sauce'),
            ('powder', 'paste'), ('frozen', 'cooked'), ('uncooked', 'cooked')
        }

        for state_a, state_b in conflicting_states:
            if (state_a in ing_states and state_b in usda_states) or \
               (state_b in ing_states and state_a in usda_states):
                score -= 35

        # Special handling: if ingredient specifies "drained" but USDA says "with oil/liquid"
        if 'drained' in ing_states:
            if any(term in usda_lower for term in ['with oil', 'with liquid', 'in oil', 'in brine']):
                score -= 30

        # Reward exact state match
        if ing_states and usda_states:
            matching_states = ing_states & usda_states
            score += len(matching_states) * 10

        # Penalize form mismatches (liquid vs solid)
        ing_is_liquid = bool(ing_tokens & liquid_markers)
        usda_is_liquid = bool(usda_tokens & liquid_markers)
        ing_is_solid = bool(ing_tokens & solid_markers)
        usda_is_solid = bool(usda_tokens & solid_markers)

        if (ing_is_liquid and usda_is_solid) or (ing_is_solid and usda_is_liquid):
            score -= 25

        # Check for preparation method conflicts
        # If ingredient has specific prep (e.g., "pasta") but USDA adds cooking state
        base_foods = {'pasta', 'rice', 'beans', 'lentils', 'quinoa', 'noodles'}
        for food in base_foods:
            if food in ing_tokens:
                # If ingredient doesn't specify cooked but USDA does
                if 'cooked' not in ing_states and 'cooked' in usda_states:
                    score -= 40
                # If ingredient is explicit (e.g., "dry pasta") but USDA is cooked
                if 'dry' in ing_tokens and 'cooked' in usda_states:
                    score -= 50

        # Reward if both have similar descriptors
        descriptors = {'table', 'extra', 'virgin', 'light', 'dark', 'white',
                      'red', 'black', 'green', 'yellow', 'sweet', 'spicy'}
        shared_descriptors = (ing_tokens & descriptors) & (usda_tokens & descriptors)
        score += len(shared_descriptors) * 5

        # Penalize if one has state marker but other doesn't (asymmetry)
        if ing_states and not usda_states:
            score -= 10
        elif usda_states and not ing_states:
            # More lenient - USDA can be more specific
            score -= 5

        # Check for shape conflicts (matters for texture)
        shape_terms = {'whole', 'diced', 'sliced', 'chopped', 'shredded', 'crushed', 'ground'}
        ing_shapes = ing_tokens & shape_terms
        usda_shapes = usda_tokens & shape_terms

        if ing_shapes and usda_shapes and not (ing_shapes & usda_shapes):
            # Different shapes specified
            score -= 20

        # Special case: if very high overlap but with a critical conflict
        overlap_ratio = len(common_tokens) / max(len(ing_tokens), 1)
        if overlap_ratio > 0.6 and score > 70:
            # High overlap is good, boost slightly
            score += 5

        # Normalize to 0-100 range
        score = max(0.0, min(100.0, score))

        return round(score, 2)

    except Exception:
        return 50.0
