import re
import math

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).lower().strip()
        usda_match = str(usda_match).lower().strip()

        if not ingredient or not usda_match:
            return 0.0

        # Clean ingredient text (remove gram weights, parentheticals)
        ing_clean = re.sub(r'^\d+g?\s*', '', ingredient)
        ing_clean = re.sub(r'\([^)]*\)', '', ing_clean).strip()

        # Extract key food words (remove common modifiers)
        def extract_food_core(text):
            stopwords = {'with', 'from', 'in', 'to', 'and', 'or', 'the', 'a', 'an', 'of'}
            words = re.findall(r'\b[a-z]+\b', text)
            return [w for w in words if len(w) > 2 and w not in stopwords]

        ing_words = extract_food_core(ing_clean)
        usda_words = extract_food_core(usda_match)

        # Macro profile categories with estimated per-100g values [calories, protein_g, carbs_g, fat_g]
        macro_profiles = {
            'pure_fat': [880, 0, 0, 100],  # oils, butter
            'lean_protein': [120, 25, 0, 2],  # chicken breast, white fish
            'fatty_protein': [250, 20, 0, 18],  # salmon, beef
            'leafy_green': [25, 2, 4, 0],  # spinach, lettuce
            'starchy_veg': [80, 2, 18, 0],  # potatoes, corn
            'fruit': [50, 0.5, 12, 0],  # most fruits
            'grain_raw': [350, 10, 75, 2],  # pasta, rice (dry)
            'grain_cooked': [130, 3, 28, 0.5],  # pasta, rice (cooked)
            'legume_cooked': [120, 8, 20, 0.5],  # beans, lentils
            'dairy_full': [60, 3, 5, 3],  # milk, yogurt
            'cheese': [350, 25, 2, 28],  # cheese
            'condiment_sauce': [100, 2, 10, 5],  # sauces with substance
            'condiment_liquid': [20, 1, 3, 0],  # vinegar, soy sauce, fish sauce
            'spice': [300, 10, 60, 5],  # dried spices (rarely eaten in quantity)
            'sugar': [400, 0, 100, 0],  # honey, sugar
            'nut_seed': [600, 20, 20, 50],  # nuts, tahini, seeds
            'processed_grain': [400, 10, 70, 5],  # cereal, granola, crackers
            'general_veg': [40, 2, 8, 0],  # tomatoes, peppers, onions
        }

        # Categorization rules
        def categorize(words_list, full_text):
            text_full = ' '.join(words_list) + ' ' + full_text

            # Pure fats
            if any(w in text_full for w in ['oil', 'butter', 'lard', 'ghee']):
                return 'pure_fat'

            # Proteins
            is_protein = any(w in text_full for w in ['chicken', 'turkey', 'fish', 'beef', 'pork', 'lamb', 'meat', 'salmon', 'tuna', 'cod', 'shrimp', 'prawn'])
            if is_protein:
                if any(w in text_full for w in ['salmon', 'beef', 'pork', 'lamb', 'thigh']):
                    return 'fatty_protein'
                return 'lean_protein'

            # Cheese
            if 'cheese' in text_full:
                return 'cheese'

            # Nuts and seeds
            if any(w in text_full for w in ['tahini', 'peanut', 'almond', 'walnut', 'cashew', 'seed', 'sesame']):
                return 'nut_seed'

            # Grains
            is_grain = any(w in text_full for w in ['pasta', 'rice', 'noodle', 'grain', 'quinoa', 'couscous'])
            if is_grain:
                if any(w in text_full for w in ['cooked', 'boiled', 'steamed']):
                    return 'grain_cooked'
                return 'grain_raw'

            # Processed grains
            if any(w in text_full for w in ['cereal', 'granola', 'cracker', 'bread']):
                return 'processed_grain'

            # Legumes
            if any(w in text_full for w in ['bean', 'lentil', 'chickpea', 'pea', 'legume']):
                return 'legume_cooked'

            # Leafy greens
            if any(w in text_full for w in ['spinach', 'kale', 'lettuce', 'arugula', 'chard', 'cabbage', 'greens']):
                return 'leafy_green'

            # Starchy veg
            if any(w in text_full for w in ['potato', 'corn', 'yam', 'parsnip']):
                return 'starchy_veg'

            # Fruits
            if any(w in text_full for w in ['apple', 'banana', 'berry', 'orange', 'lemon', 'lime', 'fruit']):
                return 'fruit'

            # Dairy
            if any(w in text_full for w in ['milk', 'yogurt', 'cream']) and 'cheese' not in text_full:
                return 'dairy_full'

            # Liquid condiments
            if any(w in text_full for w in ['vinegar', 'sauce', 'soy', 'fish sauce', 'worcestershire']):
                if any(w in text_full for w in ['vinegar', 'fish sauce', 'soy']):
                    return 'condiment_liquid'
                return 'condiment_sauce'

            # Spices and salt
            if any(w in text_full for w in ['spice', 'salt', 'pepper', 'cumin', 'paprika', 'cinnamon', 'ginger', 'garlic powder', 'onion powder']):
                return 'spice'

            # Sugar
            if any(w in text_full for w in ['sugar', 'honey', 'syrup', 'molasses']):
                return 'sugar'

            # General vegetables (tomatoes, peppers, etc.)
            if any(w in text_full for w in ['tomato', 'pepper', 'onion', 'garlic', 'carrot', 'celery', 'vegetable', 'broccoli', 'cauliflower', 'zucchini', 'cucumber', 'eggplant']):
                return 'general_veg'

            # Default to general veg if nothing else matches
            return 'general_veg'

        ing_category = categorize(ing_words, ing_clean)
        usda_category = categorize(usda_words, usda_match)

        # Get macro profiles
        ing_macros = macro_profiles[ing_category]
        usda_macros = macro_profiles[usda_category]

        # Calculate macro distance (Euclidean distance in normalized space)
        # Normalize by typical ranges: cals/1000, protein/30, carbs/100, fat/100
        def macro_distance(m1, m2):
            cal_diff = (m1[0] - m2[0]) / 1000
            pro_diff = (m1[1] - m2[1]) / 30
            carb_diff = (m1[2] - m2[2]) / 100
            fat_diff = (m1[3] - m2[3]) / 100

            return math.sqrt(cal_diff**2 + pro_diff**2 + carb_diff**2 + fat_diff**2)

        distance = macro_distance(ing_macros, usda_macros)

        # Base score: invert distance (closer = higher score)
        # Use exponential decay for smooth scoring
        base_score = 100 * math.exp(-distance)

        # Preparation state penalties
        prep_penalty = 0

        # Check for state mismatches (cooked vs raw, canned vs fresh, drained vs with liquid)
        ing_cooked = any(w in ing_clean for w in ['cooked', 'boiled', 'steamed', 'roasted', 'baked', 'fried'])
        usda_cooked = any(w in usda_match for w in ['cooked', 'boiled', 'steamed', 'roasted', 'baked', 'fried'])

        ing_raw = 'raw' in ing_clean or (not ing_cooked and ing_category in ['leafy_green', 'general_veg'])
        usda_raw = 'raw' in usda_match or (not usda_cooked and usda_category in ['leafy_green', 'general_veg'])

        ing_canned = 'canned' in ing_clean
        usda_canned = 'canned' in usda_match

        ing_drained = 'drained' in ing_clean
        usda_with_liquid = any(w in usda_match for w in ['with oil', 'with sauce', 'with liquid', 'in sauce', 'in oil'])

        # Penalize state mismatches for foods where it matters
        if ing_category in ['grain_raw', 'grain_cooked', 'legume_cooked', 'general_veg', 'starchy_veg']:
            if (ing_cooked != usda_cooked) or (ing_raw != usda_raw):
                prep_penalty += 30

        # Penalize canned+drained vs canned+with-liquid
        if ing_drained and usda_with_liquid:
            prep_penalty += 40

        # Penalize canned vs not-canned for vegetables (macro difference)
        if ing_category in ['general_veg', 'leafy_green']:
            if ing_canned != usda_canned:
                prep_penalty += 25

        # Word overlap bonus (lexical similarity)
        overlap = len(set(ing_words) & set(usda_words))
        overlap_bonus = min(20, overlap * 8)

        # Sauce vs base ingredient penalty
        ing_is_sauce = 'sauce' in ing_clean
        usda_is_base = 'sauce' not in usda_match
        if ing_is_sauce and usda_is_base:
            prep_penalty += 35

        # Final score
        final_score = base_score + overlap_bonus - prep_penalty

        # Clamp to 0-100 range
        return max(0.0, min(100.0, final_score))

    except Exception:
        return 0.0
