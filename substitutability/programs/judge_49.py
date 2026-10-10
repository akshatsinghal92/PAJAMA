import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    """
    Judge USDA match substitutability based on food category consistency.
    Higher score = more substitutable.
    """
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize inputs
        ing_lower = ingredient.lower().strip()
        usda_lower = usda_match.lower().strip()

        # Remove gram weights (e.g., "300g")
        ing_lower = re.sub(r'^\d+g\s+', '', ing_lower)

        # Define food category keywords with weighted importance
        categories = {
            'dairy': {
                'keywords': ['milk', 'cheese', 'yogurt', 'cream', 'butter', 'dairy', 'whey', 'curd', 'mozzarella', 'cheddar', 'parmesan', 'feta', 'ricotta', 'cottage cheese'],
                'weight': 1.0
            },
            'produce_vegetable': {
                'keywords': ['vegetable', 'cabbage', 'lettuce', 'carrot', 'celery', 'broccoli', 'cauliflower', 'pepper', 'onion', 'garlic', 'tomato', 'cucumber', 'zucchini', 'squash', 'eggplant', 'spinach', 'kale', 'bean', 'pea'],
                'weight': 1.0
            },
            'produce_fruit': {
                'keywords': ['fruit', 'apple', 'banana', 'orange', 'berry', 'grape', 'melon', 'peach', 'pear', 'plum', 'cherry', 'strawberry', 'blueberry', 'raspberry'],
                'weight': 1.0
            },
            'meat_poultry': {
                'keywords': ['chicken', 'turkey', 'duck', 'poultry', 'beef', 'pork', 'lamb', 'veal', 'meat', 'steak', 'chop', 'breast', 'thigh', 'wing'],
                'weight': 1.0
            },
            'fish_seafood': {
                'keywords': ['fish', 'salmon', 'tuna', 'cod', 'tilapia', 'seafood', 'shrimp', 'crab', 'lobster', 'clam', 'oyster', 'mussel', 'squid'],
                'weight': 1.0
            },
            'grain_cereal': {
                'keywords': ['pasta', 'rice', 'wheat', 'oat', 'barley', 'quinoa', 'cereal', 'granola', 'bread', 'flour', 'grain', 'noodle', 'macaroni', 'spaghetti', 'penne'],
                'weight': 1.0
            },
            'legume': {
                'keywords': ['lentil', 'chickpea', 'legume', 'soybean', 'tofu', 'tempeh'],
                'weight': 1.0
            },
            'spice_herb': {
                'keywords': ['spice', 'herb', 'basil', 'oregano', 'thyme', 'rosemary', 'parsley', 'cilantro', 'pepper', 'paprika', 'cumin', 'coriander', 'ginger', 'cinnamon', 'nutmeg', 'clove', 'bay leaf', 'mint', 'sage', 'dill', 'salt', 'turmeric', 'cardamom', 'saffron'],
                'weight': 1.0
            },
            'oil_fat': {
                'keywords': ['oil', 'olive oil', 'vegetable oil', 'canola oil', 'coconut oil', 'fat', 'lard', 'shortening'],
                'weight': 1.0
            },
            'sweetener': {
                'keywords': ['sugar', 'honey', 'syrup', 'maple syrup', 'molasses', 'agave', 'sweetener', 'brown sugar'],
                'weight': 1.0
            },
            'condiment_sauce': {
                'keywords': ['sauce', 'ketchup', 'mustard', 'mayonnaise', 'mayo', 'vinegar', 'soy sauce', 'fish sauce', 'hot sauce', 'salsa', 'relish', 'chutney', 'paste', 'dressing'],
                'weight': 1.0
            },
            'nut_seed': {
                'keywords': ['nut', 'almond', 'walnut', 'pecan', 'cashew', 'peanut', 'seed', 'sesame', 'sunflower', 'pumpkin seed', 'tahini'],
                'weight': 1.0
            }
        }

        def get_category_scores(text):
            """Return dict of category: score for given text"""
            scores = defaultdict(float)
            for category, info in categories.items():
                for keyword in info['keywords']:
                    if keyword in text:
                        # Longer keywords are more specific
                        scores[category] += len(keyword) * info['weight']
            return scores

        # Get category scores for both ingredient and USDA match
        ing_scores = get_category_scores(ing_lower)
        usda_scores = get_category_scores(usda_lower)

        # If neither has categories, return low score
        if not ing_scores or not usda_scores:
            return 10.0

        # Find top category for each
        ing_top_cat = max(ing_scores.items(), key=lambda x: x[1])[0] if ing_scores else None
        usda_top_cat = max(usda_scores.items(), key=lambda x: x[1])[0] if usda_scores else None

        base_score = 0.0

        # Category match scoring
        if ing_top_cat == usda_top_cat:
            # Same primary category - high base score
            base_score = 75.0
            # Bonus if both have strong signals in that category
            ing_strength = ing_scores[ing_top_cat]
            usda_strength = usda_scores[usda_top_cat]
            base_score += min(15.0, (ing_strength + usda_strength) / 10.0)
        else:
            # Different primary categories
            # Check if there's any overlap in secondary categories
            common_cats = set(ing_scores.keys()) & set(usda_scores.keys())
            if common_cats:
                # Some category overlap - moderate score
                base_score = 40.0
            else:
                # No category overlap - low score
                base_score = 15.0

        # Penalize preparation/state mismatches that suggest different forms
        preparation_flags = {
            'cooked': ['cooked', 'boiled', 'fried', 'baked', 'roasted', 'grilled'],
            'raw': ['raw', 'fresh', 'uncooked'],
            'canned': ['canned', 'tinned'],
            'frozen': ['frozen'],
            'dried': ['dried', 'dehydrated'],
            'processed': ['sauce', 'paste', 'puree', 'ground']
        }

        def get_prep_state(text):
            """Return set of preparation states found in text"""
            states = set()
            for state, keywords in preparation_flags.items():
                if any(kw in text for kw in keywords):
                    states.add(state)
            return states

        ing_prep = get_prep_state(ing_lower)
        usda_prep = get_prep_state(usda_lower)

        # If one mentions "sauce" but the other doesn't, penalize heavily
        ing_has_sauce = 'sauce' in ing_lower or 'paste' in ing_lower
        usda_has_sauce = 'sauce' in usda_lower or 'paste' in usda_lower

        if ing_has_sauce != usda_has_sauce:
            base_score *= 0.4  # Heavy penalty for sauce mismatch

        # If there's a preparation state conflict (e.g., raw vs cooked)
        conflicting_states = [('cooked', 'raw'), ('fresh', 'canned'), ('frozen', 'canned')]
        for state1, state2 in conflicting_states:
            if (state1 in ing_prep and state2 in usda_prep) or (state2 in ing_prep and state1 in usda_prep):
                base_score *= 0.6

        # Bonus for exact or near-exact word matches
        ing_words = set(re.findall(r'\b\w+\b', ing_lower))
        usda_words = set(re.findall(r'\b\w+\b', usda_lower))

        # Remove common stop words and weights
        stop_words = {'g', 'the', 'a', 'an', 'and', 'or', 'with', 'from', 'to', 'in', 'of'}
        ing_words -= stop_words
        usda_words -= stop_words

        common_words = ing_words & usda_words
        if common_words and len(common_words) >= 2:
            base_score += 5.0

        # Check for "with oil" or similar additions in USDA that aren't in ingredient
        if 'with oil' in usda_lower and 'oil' not in ing_lower:
            base_score *= 0.5

        return round(base_score, 2)

    except Exception:
        # Fallback score on any error
        return 10.0
