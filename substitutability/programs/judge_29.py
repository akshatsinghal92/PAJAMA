import re
import math
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).lower().strip()
        usda_match = str(usda_match).lower().strip()

        if not ingredient or not usda_match:
            return 0.0

        # Remove gram weight prefix from ingredient
        ingredient = re.sub(r'^\d+g?\s*', '', ingredient)

        # Extract core food words (remove common prep/state words for comparison)
        def extract_core_words(text):
            words = re.findall(r'\b[a-z]+\b', text)
            return set(words) - {'the', 'a', 'an', 'with', 'from', 'of', 'and', 'or'}

        ing_words = extract_core_words(ingredient)
        usda_words = extract_core_words(usda_match)

        # Define macro category indicators
        pure_fats = {'oil', 'butter', 'ghee', 'lard', 'margarine', 'shortening'}
        proteins = {'chicken', 'beef', 'pork', 'fish', 'turkey', 'lamb', 'tofu', 'egg', 'meat'}
        carbs = {'pasta', 'rice', 'bread', 'flour', 'sugar', 'honey', 'noodle', 'cereal', 'granola'}
        vegetables = {'cabbage', 'carrot', 'broccoli', 'spinach', 'kale', 'lettuce', 'tomato', 'beans', 'peas'}
        condiments = {'sauce', 'paste', 'vinegar', 'salt', 'pepper', 'spice', 'seasoning'}

        # Detect state/prep keywords that indicate nutritional changes
        oil_added = {'with oil', 'in oil', 'cooked with oil', 'fried'}
        cooking_states = {'cooked', 'fried', 'baked', 'grilled', 'roasted', 'boiled'}
        raw_states = {'raw', 'fresh', 'uncooked'}
        liquid_states = {'drained', 'with liquid', 'in juice', 'in brine', 'canned'}
        sauce_forms = {'sauce', 'paste', 'puree', 'soup'}

        # Check for state mismatches
        ing_has_oil = any(term in ingredient for term in oil_added)
        usda_has_oil = any(term in usda_match for term in oil_added)
        oil_mismatch = ing_has_oil != usda_has_oil

        ing_cooked = any(term in ingredient for term in cooking_states)
        usda_cooked = any(term in usda_match for term in cooking_states)
        ing_raw = any(term in ingredient for term in raw_states)
        usda_raw = any(term in usda_match for term in raw_states)
        cooking_mismatch = (ing_cooked and usda_raw) or (ing_raw and usda_cooked)

        ing_drained = 'drained' in ingredient
        usda_with_liquid = any(term in usda_match for term in ['with liquid', 'in juice', 'in brine', 'soup'])
        liquid_mismatch = ing_drained and usda_with_liquid

        ing_sauce = any(term in ingredient for term in sauce_forms)
        usda_base = not any(term in usda_match for term in sauce_forms)
        sauce_mismatch = ing_sauce and usda_base

        # Calculate word overlap (core food identity)
        common_words = ing_words & usda_words
        total_unique = len(ing_words | usda_words)
        overlap_ratio = len(common_words) / total_unique if total_unique > 0 else 0.0

        # Detect macro category matches
        def get_macro_category(words):
            if words & pure_fats:
                return 'fat'
            if words & proteins:
                return 'protein'
            if words & carbs:
                return 'carb'
            if words & vegetables:
                return 'vegetable'
            if words & condiments:
                return 'condiment'
            return 'other'

        ing_category = get_macro_category(ing_words)
        usda_category = get_macro_category(usda_words)
        category_match = ing_category == usda_category

        # Base score from word overlap (0-40 points)
        score = overlap_ratio * 40

        # Bonus for same macro category (0-20 points)
        if category_match and ing_category != 'other':
            score += 20
        elif ing_category == 'other' or usda_category == 'other':
            score += 5

        # Bonus for having core food name overlap (0-15 points)
        if len(common_words) >= 2:
            score += 15
        elif len(common_words) == 1:
            score += 10

        # Heavy penalties for state mismatches (each -25 points)
        if oil_mismatch:
            score -= 25
        if cooking_mismatch:
            score -= 25
        if liquid_mismatch:
            score -= 25
        if sauce_mismatch:
            score -= 25

        # Penalty for form mismatch (frozen, canned, dried)
        ing_frozen = 'frozen' in ingredient
        usda_frozen = 'frozen' in usda_match
        if ing_frozen != usda_frozen:
            score -= 15

        # Special bonus for exact condiments/spices (they have consistent macros)
        if ing_category == 'condiment' and usda_category == 'condiment' and overlap_ratio > 0.5:
            score += 20

        # Normalize to 0-100 range with sigmoid-like transformation
        normalized_score = 100 / (1 + math.exp(-score / 15))

        return round(normalized_score, 2)

    except Exception:
        return 50.0
