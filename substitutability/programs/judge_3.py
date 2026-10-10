import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).strip()
        usda_match = str(usda_match).strip()

        if not ingredient or not usda_match:
            return 0.0

        # Remove gram weights like "200g", "30g", etc.
        ingredient = re.sub(r'^\d+g?\s+', '', ingredient, flags=re.IGNORECASE)
        ingredient = re.sub(r'^\d+\s*grams?\s+', '', ingredient, flags=re.IGNORECASE)

        # Remove parentheticals
        ingredient = re.sub(r'\([^)]*\)', '', ingredient)
        usda_match = re.sub(r'\([^)]*\)', '', usda_match)

        # Normalize to lowercase
        ing_lower = ingredient.lower()
        usda_lower = usda_match.lower()

        # Remove common prep/state words that are just noise for food identity
        noise_words = {'fresh', 'frozen', 'dried', 'packaged', 'organic', 'natural',
                       'unsalted', 'salted', 'chopped', 'sliced', 'diced', 'minced',
                       'shredded', 'grated', 'ground', 'crushed', 'whole', 'halved',
                       'quartered', 'peeled', 'unpeeled', 'with', 'without', 'from',
                       'tube', 'jar', 'can', 'bottle', 'of', 'the', 'a', 'an', 'and',
                       'or', 'in', 'on', 'at', 'to', 'for'}

        # Tokenize and clean
        ing_tokens = [w for w in re.findall(r'\b\w+\b', ing_lower) if w not in noise_words and len(w) > 1]
        usda_tokens = [w for w in re.findall(r'\b\w+\b', usda_lower) if w not in noise_words and len(w) > 1]

        if not ing_tokens or not usda_tokens:
            return 0.0

        # Convert to sets for overlap calculation
        ing_set = set(ing_tokens)
        usda_set = set(usda_tokens)

        # Calculate Jaccard similarity (intersection over union)
        intersection = len(ing_set & usda_set)
        union = len(ing_set | usda_set)

        if union == 0:
            return 0.0

        jaccard_score = (intersection / union) * 100

        # Check for state mismatches that indicate NON-substitutability

        # Cooked vs raw/uncooked state mismatch
        ing_cooked = 'cooked' in ing_lower or 'fried' in ing_lower or 'baked' in ing_lower or 'roasted' in ing_lower
        usda_cooked = 'cooked' in usda_lower or 'fried' in usda_lower or 'baked' in usda_lower or 'roasted' in usda_lower
        ing_raw = 'raw' in ing_lower or 'uncooked' in ing_lower
        usda_raw = 'raw' in usda_lower or 'uncooked' in usda_lower

        # If one is explicitly cooked and the other is explicitly raw/uncooked, penalty
        if (ing_cooked and usda_raw) or (ing_raw and usda_cooked):
            jaccard_score *= 0.3

        # Sauce vs base ingredient mismatch
        ing_sauce = 'sauce' in ing_lower or 'paste' in ing_lower
        usda_sauce = 'sauce' in usda_lower or 'paste' in usda_lower

        # If one is a sauce/paste and the other is not, but they share the base food
        if ing_sauce != usda_sauce:
            # Check if they share a common base food word
            base_overlap = ing_set & usda_set
            if base_overlap:
                # e.g., "tahini sauce" vs "tahini" or "garlic paste" vs "garlic"
                # These are NOT substitutable
                jaccard_score *= 0.4

        # Check for added ingredients in USDA that aren't in ingredient
        # e.g., "canned green beans, drained" vs "Green beans, canned, cooked with oil"
        added_ingredients = {'oil', 'butter', 'salt', 'sugar', 'cream', 'cheese', 'milk'}
        usda_has_addition = any(word in usda_lower for word in added_ingredients)
        ing_has_addition = any(word in ing_lower for word in added_ingredients)

        if usda_has_addition and not ing_has_addition:
            # USDA has added ingredients not mentioned in recipe ingredient
            jaccard_score *= 0.5

        # Check for preparation method mismatches
        # e.g., "drained" ingredient vs USDA without that state
        if 'drained' in ing_lower and 'drained' not in usda_lower:
            # This could indicate excess liquid in USDA version
            jaccard_score *= 0.8

        # Bonus for very high token overlap (likely exact or near-exact match)
        if intersection >= min(len(ing_set), len(usda_set)):
            # All tokens from smaller set are in larger set
            jaccard_score *= 1.3

        # Cap the score at 100
        final_score = min(jaccard_score, 100.0)

        return final_score

    except Exception:
        return 0.0
