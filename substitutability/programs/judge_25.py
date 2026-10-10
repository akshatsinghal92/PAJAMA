import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).lower().strip()
        usda_match = str(usda_match).lower().strip()

        if not ingredient or not usda_match:
            return 0.0

        # Remove gram weights like "200g", "30g"
        ingredient = re.sub(r'\b\d+g?\s*', '', ingredient).strip()

        # Extract core food terms (remove common prep words and punctuation)
        prep_words = {'from', 'tube', 'thawed', 'shredded', 'diced', 'whole', 'chopped',
                     'sliced', 'minced', 'ground', 'fresh', 'frozen'}

        def tokenize(text):
            # Remove parentheticals
            text = re.sub(r'\([^)]*\)', '', text)
            # Split on non-alphanumeric
            tokens = re.findall(r'\b[a-z]+\b', text)
            # Remove common prep words
            return [t for t in tokens if t not in prep_words and len(t) > 2]

        ing_tokens = set(tokenize(ingredient))
        usda_tokens = set(tokenize(usda_match))

        # Calculate token overlap
        overlap = ing_tokens & usda_tokens
        union = ing_tokens | usda_tokens

        if not union:
            return 0.0

        base_score = len(overlap) / len(union) * 100

        # Detect preparation states that affect macros
        prep_states_ing = {
            'raw': 'raw' in ingredient,
            'cooked': 'cooked' in ingredient,
            'drained': 'drained' in ingredient,
            'with_oil': 'with oil' in ingredient or 'in oil' in ingredient,
            'canned': 'canned' in ingredient,
            'sauce': 'sauce' in ingredient,
            'paste': 'paste' in ingredient
        }

        prep_states_usda = {
            'raw': 'raw' in usda_match,
            'cooked': 'cooked' in usda_match,
            'drained': 'drained' in usda_match,
            'with_oil': 'with oil' in usda_match or 'in oil' in usda_match,
            'canned': 'canned' in usda_match,
            'sauce': 'sauce' in usda_match,
            'paste': 'paste' in usda_match
        }

        # Apply penalties for macro-changing mismatches
        penalty = 0.0

        # Raw vs cooked mismatch (major macro impact)
        if (prep_states_ing['raw'] and prep_states_usda['cooked']) or \
           (prep_states_ing['cooked'] and prep_states_usda['raw']):
            penalty += 40.0

        # Drained vs with oil mismatch (fat content changes)
        if prep_states_ing['drained'] and prep_states_usda['with_oil']:
            penalty += 50.0

        if not prep_states_ing['drained'] and prep_states_usda['with_oil'] and prep_states_ing['canned']:
            penalty += 30.0

        # Sauce/paste mismatch (different concentration = different macros)
        if prep_states_ing['sauce'] != prep_states_usda['sauce']:
            penalty += 45.0

        if prep_states_ing['paste'] != prep_states_usda['paste']:
            penalty += 45.0

        # Infer macro classes
        def get_macro_class(text, tokens):
            # Pure fats
            fat_words = {'oil', 'butter', 'lard', 'fat', 'shortening'}
            if any(w in tokens for w in fat_words):
                return 'fat'

            # Proteins
            protein_words = {'chicken', 'beef', 'pork', 'fish', 'meat', 'tofu', 'egg', 'shrimp'}
            if any(w in tokens for w in protein_words):
                return 'protein'

            # Vegetables
            veg_words = {'cabbage', 'lettuce', 'spinach', 'kale', 'tomato', 'pepper',
                        'carrot', 'bean', 'peas', 'broccoli', 'cauliflower'}
            if any(w in tokens for w in veg_words):
                return 'vegetable'

            # Grains/starches
            grain_words = {'pasta', 'rice', 'bread', 'flour', 'cereal', 'grain', 'noodle', 'granola'}
            if any(w in tokens for w in grain_words):
                return 'grain'

            # Condiments/sauces (low per-serving impact but different if substituted)
            condiment_words = {'sauce', 'vinegar', 'mustard', 'ketchup', 'mayo', 'dressing'}
            if any(w in tokens for w in condiment_words):
                return 'condiment'

            # Spices/seasonings (negligible macros)
            spice_words = {'salt', 'pepper', 'spice', 'garlic', 'ginger', 'herb', 'seasoning'}
            if any(w in tokens for w in spice_words):
                return 'spice'

            return 'other'

        ing_class = get_macro_class(ingredient, ing_tokens)
        usda_class = get_macro_class(usda_match, usda_tokens)

        # Bonus for matching macro class
        if ing_class == usda_class and ing_class != 'other':
            base_score += 20.0
        elif ing_class != usda_class:
            # Penalty for different macro classes
            penalty += 25.0

        # Special handling for exact/near-exact matches
        if overlap and len(overlap) >= min(len(ing_tokens), len(usda_tokens)):
            base_score += 15.0

        # Calculate final score
        final_score = max(0.0, base_score - penalty)

        return final_score

    except Exception:
        return 0.0
