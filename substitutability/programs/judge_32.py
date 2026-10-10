import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).lower().strip()
        usda_match = str(usda_match).lower().strip()

        if not ingredient or not usda_match:
            return 0.0

        # Remove gram weights from ingredient
        ingredient_clean = re.sub(r'^\d+g?\s*', '', ingredient)

        # Extract core terms (remove parentheticals)
        ingredient_clean = re.sub(r'\([^)]*\)', '', ingredient_clean).strip()

        # Macro category classification based on keyword density
        def get_macro_signature(text):
            sig = defaultdict(float)

            # High protein sources
            protein_words = ['chicken', 'beef', 'pork', 'fish', 'salmon', 'tuna', 'turkey',
                           'lamb', 'shrimp', 'tofu', 'tempeh', 'egg', 'lentil', 'bean',
                           'chickpea', 'meat', 'sausage', 'bacon', 'ham']
            sig['protein'] = sum(1.5 for w in protein_words if w in text)

            # Fat sources
            fat_words = ['oil', 'butter', 'cream', 'cheese', 'avocado', 'nut', 'seed',
                        'tahini', 'mayo', 'margarine']
            sig['fat'] = sum(2.0 for w in fat_words if w in text)

            # Carb sources
            carb_words = ['pasta', 'rice', 'bread', 'potato', 'grain', 'cereal',
                         'flour', 'granola', 'oat', 'quinoa', 'noodle']
            sig['carb'] = sum(1.5 for w in carb_words if w in text)

            # Low-calorie vegetables
            veg_words = ['lettuce', 'spinach', 'kale', 'cabbage', 'broccoli', 'cauliflower',
                        'cucumber', 'celery', 'zucchini', 'pepper', 'tomato', 'green bean',
                        'carrot', 'onion', 'garlic', 'mushroom']
            sig['vegetable'] = sum(1.0 for w in veg_words if w in text)

            # Very low-calorie: spices, vinegar, water-based
            spice_words = ['spice', 'salt', 'pepper', 'vinegar', 'sauce', 'paste',
                          'extract', 'powder', 'seasoning']
            sig['condiment'] = sum(1.0 for w in spice_words if w in text)

            return sig

        ing_sig = get_macro_signature(ingredient_clean)
        usda_sig = get_macro_signature(usda_match)

        # Calculate signature similarity using dot product + normalization
        categories = ['protein', 'fat', 'carb', 'vegetable', 'condiment']

        ing_vec = [ing_sig[c] for c in categories]
        usda_vec = [usda_sig[c] for c in categories]

        ing_norm = sum(x**2 for x in ing_vec) ** 0.5
        usda_norm = sum(x**2 for x in usda_vec) ** 0.5

        if ing_norm == 0 or usda_norm == 0:
            # Fallback: simple text overlap
            ing_words = set(re.findall(r'\b\w+\b', ingredient_clean))
            usda_words = set(re.findall(r'\b\w+\b', usda_match))
            overlap = len(ing_words & usda_words)
            base_score = min(overlap * 15, 50)
        else:
            # Cosine similarity scaled to 0-100
            dot_product = sum(a * b for a, b in zip(ing_vec, usda_vec))
            cosine_sim = dot_product / (ing_norm * usda_norm)
            base_score = cosine_sim * 100

        # State/preparation mismatch penalties
        penalties = 0

        # Check for cooked/raw mismatch (affects macros for starches and some veg)
        ing_has_cooked = any(w in ingredient_clean for w in ['cooked', 'boiled', 'baked', 'fried'])
        usda_has_cooked = any(w in usda_match for w in ['cooked', 'boiled', 'baked', 'fried'])
        ing_has_raw = 'raw' in ingredient_clean
        usda_has_raw = 'raw' in usda_match

        # Penalty for state mismatch in carb/protein foods
        if (ing_has_cooked and usda_has_raw) or (ing_has_raw and usda_has_cooked):
            if any(c in ingredient_clean for c in ['pasta', 'rice', 'potato', 'chicken', 'meat']):
                penalties += 30

        # Penalty for oil addition/removal (major macro impact)
        ing_mentions_oil = 'oil' in ingredient_clean
        usda_mentions_oil = 'oil' in usda_match

        if ing_mentions_oil != usda_mentions_oil:
            # Only penalize if one explicitly mentions oil
            if 'with oil' in usda_match or 'in oil' in usda_match:
                penalties += 35

        # Penalty for "drained" in ingredient but USDA doesn't account for it
        if 'drained' in ingredient_clean:
            if 'cooked' in usda_match or 'with' in usda_match:
                # USDA includes liquid/extras that were drained
                penalties += 25

        # Penalty for sauce vs pure ingredient (tahini sauce vs tahini)
        ing_is_sauce = 'sauce' in ingredient_clean or 'paste' in ingredient_clean
        usda_is_pure = not any(w in usda_match for w in ['sauce', 'paste', 'with', 'in'])

        if ing_is_sauce and usda_is_pure:
            # Check if it's not just a descriptor match
            ing_base_words = set(re.findall(r'\b\w{4,}\b', ingredient_clean))
            usda_base_words = set(re.findall(r'\b\w{4,}\b', usda_match))

            if ing_base_words & usda_base_words:
                # Same base food but different form
                penalties += 30

        # Boost for exact or near-exact descriptor matches
        boost = 0
        ing_words = set(re.findall(r'\b\w{3,}\b', ingredient_clean))
        usda_words = set(re.findall(r'\b\w{3,}\b', usda_match))

        common_words = ing_words & usda_words
        if len(common_words) >= 2:
            boost = len(common_words) * 10

        # Final score
        final_score = base_score + boost - penalties

        # Clamp to reasonable range
        return max(0, min(final_score, 100))

    except Exception:
        return 50.0
