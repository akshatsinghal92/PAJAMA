import re
import math
from collections import defaultdict


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).lower().strip()
        usda_match = str(usda_match).lower().strip()

        if not ingredient or not usda_match:
            return 0.0

        # Clean ingredient text: remove gram weights, parentheticals
        ingredient_clean = re.sub(r'^\d+g?\s*', '', ingredient)
        ingredient_clean = re.sub(r'\([^)]*\)', '', ingredient_clean)
        ingredient_clean = ingredient_clean.strip()

        # Extract key terms from both
        ing_terms = set(re.findall(r'\b\w+\b', ingredient_clean))
        usda_terms = set(re.findall(r'\b\w+\b', usda_match))

        # Macro category definitions with typical per-100g profiles
        # Format: (calories, protein_g, carbs_g, fat_g)
        macro_categories = {
            'pure_fat': {
                'keywords': {'oil', 'butter', 'lard', 'shortening', 'ghee', 'margarine'},
                'profile': (900, 0, 0, 100)
            },
            'lean_protein': {
                'keywords': {'chicken breast', 'turkey breast', 'cod', 'tilapia', 'shrimp', 'tuna', 'whitefish'},
                'profile': (120, 25, 0, 2)
            },
            'fatty_protein': {
                'keywords': {'salmon', 'chicken thigh', 'beef', 'pork', 'lamb', 'bacon', 'sausage'},
                'profile': (200, 20, 0, 13)
            },
            'leafy_greens': {
                'keywords': {'spinach', 'kale', 'lettuce', 'arugula', 'chard', 'cabbage', 'greens'},
                'profile': (25, 3, 4, 0.3)
            },
            'non_starchy_veg': {
                'keywords': {'tomato', 'cucumber', 'pepper', 'broccoli', 'cauliflower', 'zucchini', 'carrot', 'beans'},
                'profile': (30, 2, 6, 0.2)
            },
            'starchy_carb': {
                'keywords': {'pasta', 'rice', 'bread', 'potato', 'noodle', 'flour', 'tortilla'},
                'profile': (350, 10, 75, 1)
            },
            'cereal_grain': {
                'keywords': {'granola', 'cereal', 'oats', 'muesli', 'grain'},
                'profile': (380, 10, 65, 7)
            },
            'sugar': {
                'keywords': {'sugar', 'honey', 'syrup', 'molasses', 'agave'},
                'profile': (380, 0, 95, 0)
            },
            'condiment_vinegar': {
                'keywords': {'vinegar', 'lemon juice', 'lime juice'},
                'profile': (20, 0, 3, 0)
            },
            'sauce': {
                'keywords': {'sauce', 'paste', 'dressing', 'marinade', 'gravy'},
                'profile': (100, 3, 10, 5)
            },
            'spice': {
                'keywords': {'salt', 'pepper', 'spice', 'seasoning', 'herb'},
                'profile': (5, 0, 1, 0)
            },
            'tahini_nut_butter': {
                'keywords': {'tahini', 'peanut butter', 'almond butter', 'sesame'},
                'profile': (600, 18, 20, 53)
            },
            'fish_sauce': {
                'keywords': {'fish sauce', 'soy sauce', 'worcestershire'},
                'profile': (35, 5, 3, 0)
            }
        }

        def detect_category(terms):
            """Detect macro category from text terms."""
            text = ' '.join(terms)

            # Check multi-word patterns first
            if 'fish sauce' in text:
                return 'fish_sauce'
            if 'chicken breast' in text:
                return 'lean_protein'
            if 'chicken thigh' in text:
                return 'fatty_protein'

            # Single keyword matching
            for cat_name, cat_data in macro_categories.items():
                for kw in cat_data['keywords']:
                    if kw in terms:
                        return cat_name

            return 'unknown'

        ing_category = detect_category(ing_terms)
        usda_category = detect_category(usda_terms)

        # Default profile for unknown categories
        default_profile = (100, 5, 10, 3)

        ing_profile = macro_categories.get(ing_category, {}).get('profile', default_profile)
        usda_profile = macro_categories.get(usda_category, {}).get('profile', default_profile)

        # Calculate Euclidean distance between macro profiles
        # Normalize by typical ranges: cal/1000, protein/30, carbs/100, fat/100
        cal_dist = (ing_profile[0] - usda_profile[0]) / 1000.0
        prot_dist = (ing_profile[1] - usda_profile[1]) / 30.0
        carb_dist = (ing_profile[2] - usda_profile[2]) / 100.0
        fat_dist = (ing_profile[3] - usda_profile[3]) / 100.0

        euclidean_dist = math.sqrt(cal_dist**2 + prot_dist**2 + carb_dist**2 + fat_dist**2)

        # Base score: convert distance to similarity (lower distance = higher score)
        # Max distance ~2.5, so we invert it
        base_score = max(0, 10 - euclidean_dist * 4)

        # State mismatch penalties
        penalty = 0.0

        # Detect state descriptors
        state_descriptors = {
            'cooked': {'cooked', 'boiled', 'baked', 'fried', 'roasted', 'grilled'},
            'raw': {'raw', 'fresh', 'uncooked'},
            'canned': {'canned', 'tinned'},
            'frozen': {'frozen'},
            'dried': {'dried', 'dehydrated'},
            'drained': {'drained'},
            'with_oil': {'with oil', 'in oil', 'oiled'}
        }

        def has_state(terms, state_set):
            text = ' '.join(terms)
            return any(state in text for state in state_set)

        ing_cooked = has_state(ing_terms, state_descriptors['cooked'])
        usda_cooked = has_state(usda_terms, state_descriptors['cooked'])
        ing_raw = has_state(ing_terms, state_descriptors['raw'])
        usda_raw = has_state(usda_terms, state_descriptors['raw'])
        ing_drained = has_state(ing_terms, state_descriptors['drained'])
        usda_oil = has_state(usda_terms, state_descriptors['with_oil'])

        # Penalize cooked/raw mismatches for vegetables and grains
        if ing_category in ['non_starchy_veg', 'starchy_carb', 'leafy_greens']:
            if (ing_cooked and usda_raw) or (ing_raw and usda_cooked):
                penalty += 3.0

        # Penalize drained vs with oil for canned items
        if ing_drained and usda_oil:
            penalty += 3.0

        # Check for "sauce" vs base ingredient mismatch
        ing_sauce = 'sauce' in ing_terms or 'paste' in ing_terms
        usda_sauce = 'sauce' in usda_terms or 'paste' in usda_terms

        if ing_sauce != usda_sauce:
            # Sauce vs base ingredient is a significant macro difference
            penalty += 2.5

        # Word overlap bonus (shows similarity in description)
        common_words = ing_terms & usda_terms
        overlap_bonus = min(2.0, len(common_words) * 0.4)

        final_score = base_score - penalty + overlap_bonus

        # Clamp to 0-10 range
        final_score = max(0.0, min(10.0, final_score))

        return final_score

    except Exception:
        return 5.0
