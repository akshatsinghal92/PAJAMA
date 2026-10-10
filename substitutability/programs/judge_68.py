import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize inputs
        ingredient = ingredient.lower().strip()
        usda_match = usda_match.lower().strip()

        # Remove gram weights from ingredient (e.g., "300g penne pasta" -> "penne pasta")
        ingredient = re.sub(r'^\d+g\s+', '', ingredient)

        # Extract core food name by removing parentheticals and post-comma details from ingredient
        ingredient_core = re.sub(r'\([^)]*\)', '', ingredient)
        ingredient_core = ingredient_core.split(',')[0].strip()

        # Define culinary role markers
        # Cooking state markers
        cooking_states = {
            'raw': ['raw', 'uncooked', 'fresh'],
            'cooked': ['cooked', 'baked', 'fried', 'roasted', 'grilled', 'boiled', 'steamed'],
            'frozen': ['frozen'],
            'canned': ['canned'],
            'dried': ['dried', 'dehydrated']
        }

        # Physical form markers (affect texture/function in dish)
        form_markers = {
            'whole': ['whole'],
            'diced': ['diced', 'cubed', 'chopped'],
            'ground': ['ground', 'minced'],
            'shredded': ['shredded', 'grated'],
            'sliced': ['sliced'],
            'paste': ['paste'],
            'sauce': ['sauce'],
            'powder': ['powder']
        }

        # Liquid/texture modifiers that change culinary behavior
        liquid_modifiers = ['drained', 'with oil', 'in water', 'in brine', 'in juice', 'with liquid']

        def extract_markers(text, marker_dict):
            """Extract which marker categories are present in text"""
            found = set()
            for category, keywords in marker_dict.items():
                if any(kw in text for kw in keywords):
                    found.add(category)
            return found

        def has_liquid_modifier(text):
            """Check if text has liquid-related modifiers"""
            return any(mod in text for mod in liquid_modifiers)

        # Extract markers from both texts
        ing_cooking = extract_markers(ingredient, cooking_states)
        usda_cooking = extract_markers(usda_match, cooking_states)

        ing_form = extract_markers(ingredient, form_markers)
        usda_form = extract_markers(usda_match, form_markers)

        ing_has_liquid = has_liquid_modifier(ingredient)
        usda_has_liquid = has_liquid_modifier(usda_match)

        # Calculate base similarity using word overlap
        ing_words = set(re.findall(r'\b\w+\b', ingredient_core))
        usda_words = set(re.findall(r'\b\w+\b', usda_match))

        # Remove common stopwords
        stopwords = {'the', 'and', 'or', 'with', 'without', 'from', 'to'}
        ing_words -= stopwords
        usda_words -= stopwords

        if not ing_words or not usda_words:
            return 10.0  # If we can't parse, give neutral score

        word_overlap = len(ing_words & usda_words) / max(len(ing_words), len(usda_words))

        # Start with word overlap score (0-40 points)
        score = word_overlap * 40

        # Cooking state alignment (up to 30 points)
        if ing_cooking and usda_cooking:
            # Both have cooking state markers
            if ing_cooking == usda_cooking:
                score += 30  # Perfect match
            elif ing_cooking & usda_cooking:
                score += 15  # Some overlap
            else:
                # Conflicting states (e.g., raw vs cooked) - major penalty
                score -= 25
        elif ing_cooking or usda_cooking:
            # One has state, other doesn't - minor penalty
            score -= 5
        else:
            # Neither has explicit state - neutral, add small bonus
            score += 15

        # Physical form alignment (up to 20 points)
        if ing_form and usda_form:
            if ing_form == usda_form:
                score += 20  # Perfect match
            elif ing_form & usda_form:
                score += 10  # Some overlap
            else:
                # Different forms (e.g., whole vs diced, paste vs sauce)
                # Check if forms are incompatible for culinary role
                incompatible_pairs = [
                    ({'whole'}, {'diced', 'ground', 'shredded'}),
                    ({'paste'}, {'sauce'}),
                    ({'powder'}, {'paste', 'sauce'})
                ]
                is_incompatible = any(
                    (ing_form & p1 and usda_form & p2) or (ing_form & p2 and usda_form & p1)
                    for p1, p2 in incompatible_pairs
                )
                if is_incompatible:
                    score -= 20
                else:
                    score -= 5
        elif ing_form and not usda_form:
            # Ingredient specifies form but USDA doesn't - acceptable for simple prep
            simple_prep = {'shredded', 'sliced', 'diced'}
            if ing_form <= simple_prep:
                score += 10  # Simple prep is fine
            else:
                score -= 5  # Complex form might matter
        else:
            score += 10  # Form not specified or both unspecified

        # Liquid modifier alignment (up to 10 points)
        if ing_has_liquid and usda_has_liquid:
            # Both mention liquid - check if compatible
            if 'drained' in ingredient and 'with' in usda_match:
                score -= 15  # Drained vs with liquid is incompatible
            elif 'drained' in usda_match and 'with' in ingredient:
                score -= 15
            else:
                score += 10  # Both have liquid modifiers that seem compatible
        elif ing_has_liquid != usda_has_liquid:
            # One has liquid modifier, other doesn't
            if 'drained' in ingredient or 'drained' in usda_match:
                score -= 10  # Drained vs not specified is problematic
            else:
                score -= 3  # Minor mismatch
        else:
            score += 5  # Neither has liquid modifier

        # Ensure score is in reasonable range (0-100)
        score = max(0.0, min(100.0, score))

        return score

    except Exception as e:
        # Fallback to safe default
        return 10.0
