import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize inputs
        ing_lower = ingredient.lower()
        usda_lower = usda_match.lower()

        # Remove gram weights (e.g., "200g", "30 g")
        ing_lower = re.sub(r'\b\d+\s*g\b', '', ing_lower).strip()

        # Remove parentheticals
        ing_lower = re.sub(r'\([^)]*\)', '', ing_lower).strip()
        usda_lower = re.sub(r'\([^)]*\)', '', usda_lower).strip()

        # Trivial prep states that don't change substitutability
        trivial_states = {
            'raw', 'fresh', 'chopped', 'diced', 'minced', 'sliced',
            'shredded', 'thawed', 'grated', 'cubed', 'whole', 'halved',
            'quartered', 'peeled', 'trimmed', 'cut', 'crushed'
        }

        # Non-trivial states that change the food significantly
        cooking_states = {
            'cooked', 'fried', 'baked', 'roasted', 'grilled', 'boiled',
            'steamed', 'sauteed', 'braised', 'stewed', 'toasted'
        }

        # Extraction methods that change composition
        process_modifiers = {
            'with oil', 'with butter', 'with salt', 'with sauce',
            'in oil', 'in brine', 'in syrup', 'sweetened', 'salted',
            'seasoned', 'flavored', 'marinated'
        }

        # Form differences that matter
        form_words = {
            'sauce', 'paste', 'powder', 'juice', 'puree', 'concentrate',
            'extract', 'syrup', 'broth', 'stock'
        }

        # Base score starts at 50
        score = 50.0

        # Extract tokens from both
        ing_tokens = set(re.findall(r'\b\w+\b', ing_lower))
        usda_tokens = set(re.findall(r'\b\w+\b', usda_lower))

        # Find prep states in each
        ing_trivial = ing_tokens & trivial_states
        usda_trivial = usda_tokens & trivial_states
        ing_cooking = ing_tokens & cooking_states
        usda_cooking = usda_tokens & cooking_states

        # Check for form differences
        ing_form = ing_tokens & form_words
        usda_form = usda_tokens & form_words

        # MAJOR PENALTY: Incompatible cooking states
        if ing_cooking != usda_cooking:
            # One is cooked, other is not
            if (ing_cooking and not usda_cooking) or (usda_cooking and not ing_cooking):
                score -= 35

        # MAJOR PENALTY: Different forms (sauce vs base ingredient)
        if ing_form != usda_form:
            if bool(ing_form) != bool(usda_form):
                score -= 40
            elif ing_form and usda_form and not ing_form.intersection(usda_form):
                score -= 30

        # PENALTY: Process modifiers that change composition
        for modifier in process_modifiers:
            ing_has = modifier in ing_lower
            usda_has = modifier in usda_lower
            if ing_has != usda_has:
                score -= 25

        # Special case: "drained" vs ingredients with liquids/oils
        if 'drained' in ing_lower:
            if any(phrase in usda_lower for phrase in ['with oil', 'with butter', 'in oil', 'in brine']):
                score -= 30

        # REWARD: Only trivial prep differences
        if ing_trivial or usda_trivial:
            # If only trivial states differ, that's good
            if not (ing_cooking or usda_cooking):
                score += 20

        # REWARD: Both have no cooking states (both raw/fresh)
        if not ing_cooking and not usda_cooking:
            score += 15

        # REWARD: Exact cooking state match
        if ing_cooking and usda_cooking and ing_cooking == usda_cooking:
            score += 10

        # Check for core food overlap
        # Remove all prep/cooking/form words
        all_modifiers = trivial_states | cooking_states | form_words
        ing_core = ing_tokens - all_modifiers - {'canned', 'frozen', 'dried', 'the', 'a', 'an', 'and', 'or'}
        usda_core = usda_tokens - all_modifiers - {'canned', 'frozen', 'dried', 'the', 'a', 'an', 'and', 'or'}

        # Core word overlap bonus
        if ing_core and usda_core:
            overlap = len(ing_core & usda_core)
            overlap_ratio = overlap / max(len(ing_core), len(usda_core))
            score += overlap_ratio * 15

        # Clamp to 0-100 range
        return max(0.0, min(100.0, score))

    except Exception:
        # Fallback on any error
        return 25.0
