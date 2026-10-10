import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        ingredient_lower = ingredient.lower().strip()
        usda_lower = usda_match.lower().strip()

        # Remove gram weights from ingredient
        ingredient_clean = re.sub(r'^\d+g?\s*', '', ingredient_lower)
        ingredient_clean = re.sub(r'^\d+\s*grams?\s*', '', ingredient_clean)

        # Additive/processing keywords that indicate complexity
        additive_keywords = [
            'with oil', 'with salt', 'with sugar', 'with butter',
            'sweetened', 'unsweetened', 'flavored', 'seasoned',
            'breaded', 'battered', 'fried', 'deep fried',
            'sauce', 'gravy', 'dressing', 'marinade',
            'blend', 'mixture', 'seasoning mix', 'spice blend',
            'added', 'enriched', 'fortified',
            'in oil', 'in brine', 'in syrup', 'in sauce'
        ]

        # Processing state keywords
        processing_keywords = [
            'cooked', 'raw', 'baked', 'roasted', 'grilled',
            'frozen', 'fresh', 'canned', 'dried',
            'pickled', 'smoked', 'cured', 'fermented'
        ]

        # Extract core food name from ingredient (before commas/parens)
        ing_core = re.split(r'[,\(]', ingredient_clean)[0].strip()

        # Count additive keywords in each
        ing_additives = sum(1 for kw in additive_keywords if kw in ingredient_clean)
        usda_additives = sum(1 for kw in additive_keywords if kw in usda_lower)

        # Base score starts high
        score = 100.0

        # MAJOR PENALTY: USDA has additives that ingredient lacks
        additive_difference = usda_additives - ing_additives
        if additive_difference > 0:
            score -= additive_difference * 35.0

        # Check for specific problematic patterns
        # Pattern 1: Ingredient wants plain item, USDA has "with X"
        has_with_pattern = re.search(r'\bwith\s+\w+', usda_lower)
        if has_with_pattern and 'with' not in ingredient_clean:
            score -= 30.0

        # Pattern 2: Ingredient says "sauce" but USDA doesn't (or vice versa)
        ing_is_sauce = 'sauce' in ingredient_clean
        usda_is_sauce = 'sauce' in usda_lower
        if ing_is_sauce != usda_is_sauce:
            score -= 40.0

        # Pattern 3: Processing state mismatch
        # Extract processing states from both
        ing_processing = [kw for kw in processing_keywords if kw in ingredient_clean]
        usda_processing = [kw for kw in processing_keywords if kw in usda_lower]

        # If ingredient specifies state and USDA has different state
        if ing_processing and usda_processing:
            ing_set = set(ing_processing)
            usda_set = set(usda_processing)
            if not ing_set.intersection(usda_set):
                # Completely different processing states
                score -= 25.0

        # Pattern 4: Check for compound additions via "and"
        usda_has_compound = ' and ' in usda_lower or ', and ' in usda_lower
        ing_has_compound = ' and ' in ingredient_clean or ', and ' in ingredient_clean
        if usda_has_compound and not ing_has_compound:
            score -= 20.0

        # Pattern 5: Word overlap bonus (more overlap = more similar)
        # Tokenize and count overlapping meaningful words
        stop_words = {'the', 'a', 'an', 'with', 'in', 'on', 'of', 'for', 'to'}

        ing_words = set(re.findall(r'\b\w+\b', ing_core)) - stop_words
        usda_words = set(re.findall(r'\b\w+\b', usda_lower)) - stop_words

        if ing_words:
            overlap_ratio = len(ing_words.intersection(usda_words)) / len(ing_words)
            score += overlap_ratio * 15.0

        # Pattern 6: Detect "blend", "mix", "combination" in USDA
        mixture_words = ['blend', 'mix', 'mixture', 'combination', 'seasoning']
        usda_is_mixture = any(word in usda_lower for word in mixture_words)
        ing_is_mixture = any(word in ingredient_clean for word in mixture_words)

        if usda_is_mixture and not ing_is_mixture:
            score -= 25.0

        # Pattern 7: Check comma count difference (more commas = more descriptors/additives)
        ing_comma_count = ingredient_clean.count(',')
        usda_comma_count = usda_lower.count(',')

        # USDA having many more commas suggests more complexity
        comma_diff = usda_comma_count - ing_comma_count
        if comma_diff > 1:
            score -= comma_diff * 8.0

        # Ensure score stays in reasonable range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 50.0
