import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient_lower = ingredient.lower()
        usda_lower = usda_match.lower()

        # Remove gram weights and parentheticals
        ingredient_clean = re.sub(r'^\d+g?\s*', '', ingredient_lower)
        ingredient_clean = re.sub(r'\([^)]*\)', '', ingredient_clean)
        ingredient_clean = re.sub(r'\s+', ' ', ingredient_clean).strip()

        usda_clean = re.sub(r'\([^)]*\)', '', usda_lower)
        usda_clean = re.sub(r'\s+', ' ', usda_clean).strip()

        # Food category keywords with weights
        categories = {
            'dairy': ['milk', 'cheese', 'yogurt', 'cream', 'butter', 'dairy', 'cheddar', 'mozzarella', 'parmesan', 'ricotta'],
            'meat': ['chicken', 'beef', 'pork', 'lamb', 'turkey', 'duck', 'meat', 'steak', 'patty'],
            'fish': ['fish', 'salmon', 'tuna', 'cod', 'tilapia', 'shrimp', 'prawn', 'seafood', 'anchovy'],
            'vegetable': ['tomato', 'carrot', 'onion', 'pepper', 'lettuce', 'cabbage', 'broccoli', 'bean', 'peas', 'corn', 'spinach', 'kale', 'celery', 'cucumber'],
            'fruit': ['apple', 'banana', 'orange', 'berry', 'lemon', 'lime', 'grape', 'melon', 'mango', 'peach'],
            'grain': ['pasta', 'rice', 'bread', 'wheat', 'barley', 'oat', 'cereal', 'granola', 'quinoa', 'couscous'],
            'legume': ['bean', 'lentil', 'chickpea', 'pea'],
            'spice': ['salt', 'pepper', 'paprika', 'cumin', 'cinnamon', 'ginger', 'turmeric', 'spice', 'herb', 'basil', 'oregano', 'thyme', 'rosemary'],
            'oil': ['oil', 'olive oil', 'vegetable oil', 'canola', 'coconut oil'],
            'fat': ['butter', 'lard', 'shortening', 'ghee'],
            'sweetener': ['sugar', 'honey', 'syrup', 'molasses', 'agave'],
            'condiment': ['sauce', 'vinegar', 'ketchup', 'mustard', 'mayo', 'dressing', 'salsa', 'paste', 'tahini'],
            'nut': ['almond', 'walnut', 'peanut', 'cashew', 'pecan', 'nut'],
            'seed': ['seed', 'sesame', 'sunflower', 'pumpkin seed']
        }

        # Determine categories for ingredient and USDA match
        def get_categories(text):
            found = []
            words = text.split()
            for cat, keywords in categories.items():
                for keyword in keywords:
                    if keyword in text:
                        found.append(cat)
                        break
            return list(set(found))

        ing_cats = get_categories(ingredient_clean)
        usda_cats = get_categories(usda_clean)

        # Base score: category overlap
        if not ing_cats or not usda_cats:
            score = 50.0
        else:
            overlap = len(set(ing_cats) & set(usda_cats))
            total = max(len(ing_cats), len(usda_cats))
            score = 100.0 * (overlap / total) if total > 0 else 50.0

        # Preparation state penalties
        prep_states = {
            'cooked': ['cooked', 'roasted', 'baked', 'fried', 'grilled', 'steamed'],
            'raw': ['raw', 'fresh', 'uncooked'],
            'canned': ['canned', 'tinned'],
            'frozen': ['frozen'],
            'dried': ['dried', 'dehydrated'],
            'processed': ['sauce', 'paste', 'puree', 'diced', 'crushed', 'shredded']
        }

        def get_prep_states(text):
            found = []
            for state, keywords in prep_states.items():
                for keyword in keywords:
                    if keyword in text:
                        found.append(state)
            return list(set(found))

        ing_prep = get_prep_states(ingredient_clean)
        usda_prep = get_prep_states(usda_clean)

        # Penalize prep state mismatches
        if ing_prep and usda_prep:
            prep_overlap = len(set(ing_prep) & set(usda_prep))
            if prep_overlap == 0:
                score *= 0.4  # Heavy penalty for conflicting prep states
            else:
                score *= 1.1  # Small bonus for matching prep

        # Check for "drained" in ingredient but "with oil" or other additions in USDA
        if 'drained' in ingredient_clean and ('with oil' in usda_clean or 'with ' in usda_clean):
            score *= 0.3

        # Reward exact substring matches
        ing_tokens = set(re.findall(r'\b\w+\b', ingredient_clean))
        usda_tokens = set(re.findall(r'\b\w+\b', usda_clean))

        # Remove common stopwords
        stopwords = {'a', 'an', 'the', 'and', 'or', 'but', 'with', 'from', 'to', 'of', 'in', 'for'}
        ing_tokens -= stopwords
        usda_tokens -= stopwords

        if ing_tokens and usda_tokens:
            token_overlap = len(ing_tokens & usda_tokens)
            token_union = len(ing_tokens | usda_tokens)
            token_score = token_overlap / token_union if token_union > 0 else 0
            score = score * (0.6 + 0.4 * token_score)

        # Special case: sauce vs base ingredient
        if 'sauce' in ingredient_clean and 'sauce' not in usda_clean:
            score *= 0.5
        elif 'sauce' not in ingredient_clean and 'sauce' in usda_clean:
            score *= 0.5

        # Normalize to 0-100 range
        score = max(0.0, min(100.0, score))

        return float(score)

    except Exception:
        return 50.0
