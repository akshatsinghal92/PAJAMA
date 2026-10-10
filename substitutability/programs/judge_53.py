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

        # Define food categories with keyword indicators
        categories = {
            'dairy': ['milk', 'cheese', 'yogurt', 'cream', 'butter', 'curd', 'whey', 'kefir', 'buttermilk'],
            'produce_vegetable': ['cabbage', 'carrot', 'broccoli', 'spinach', 'lettuce', 'kale', 'celery',
                                 'onion', 'garlic', 'pepper', 'cucumber', 'zucchini', 'eggplant', 'bean',
                                 'pea', 'corn', 'asparagus', 'cauliflower'],
            'produce_fruit': ['apple', 'banana', 'orange', 'berry', 'grape', 'lemon', 'lime', 'mango',
                             'pineapple', 'peach', 'pear', 'cherry', 'plum', 'melon'],
            'produce_tomato': ['tomato', 'tomatoes'],
            'meat': ['beef', 'pork', 'lamb', 'veal', 'steak', 'bacon', 'sausage', 'ham', 'ribs'],
            'poultry': ['chicken', 'turkey', 'duck', 'hen', 'poultry'],
            'fish': ['fish', 'salmon', 'tuna', 'cod', 'tilapia', 'trout', 'anchovy', 'sardine', 'mackerel'],
            'seafood': ['shrimp', 'prawn', 'crab', 'lobster', 'clam', 'oyster', 'mussel', 'scallop', 'squid'],
            'grain': ['pasta', 'rice', 'bread', 'flour', 'wheat', 'oat', 'barley', 'quinoa', 'couscous',
                     'noodle', 'macaroni', 'spaghetti', 'penne', 'cereal', 'granola'],
            'legume': ['lentil', 'chickpea', 'bean', 'pea', 'soy', 'tofu'],
            'spice': ['spice', 'cinnamon', 'cumin', 'paprika', 'turmeric', 'curry', 'coriander', 'cardamom',
                     'pepper', 'chili', 'cayenne', 'ginger', 'clove', 'nutmeg', 'oregano', 'basil', 'thyme',
                     'rosemary', 'parsley', 'sage', 'bay'],
            'oil': ['oil', 'olive oil', 'vegetable oil', 'canola', 'sesame oil', 'coconut oil'],
            'fat': ['butter', 'lard', 'shortening', 'margarine', 'ghee'],
            'sweetener': ['sugar', 'honey', 'syrup', 'molasses', 'agave', 'stevia'],
            'condiment': ['sauce', 'vinegar', 'mustard', 'ketchup', 'mayo', 'relish', 'salsa', 'pesto',
                         'tahini', 'soy sauce', 'fish sauce', 'worcestershire'],
            'salt': ['salt'],
            'nut_seed': ['almond', 'walnut', 'peanut', 'cashew', 'pecan', 'pistachio', 'seed', 'sesame',
                        'sunflower', 'pumpkin seed']
        }

        # Extract core terms by removing common modifiers
        def extract_core_terms(text):
            # Remove gram weight prefix like "200g "
            text = re.sub(r'^\d+g?\s+', '', text)
            # Remove parentheticals
            text = re.sub(r'\([^)]*\)', '', text)
            # Split on comma and take first part as primary
            parts = text.split(',')
            primary = parts[0].strip()
            secondary = ' '.join(parts[1:]).strip() if len(parts) > 1 else ''
            return primary, secondary, text

        # Classify text into categories
        def classify(text):
            found_categories = set()
            words = text.lower().split()
            text_lower = text.lower()

            for category, keywords in categories.items():
                for keyword in keywords:
                    # Check if keyword appears as whole word or in compound
                    if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                        found_categories.add(category)

            return found_categories

        # Parse both inputs
        ing_primary, ing_secondary, ing_full = extract_core_terms(ingredient)
        usda_primary, usda_secondary, usda_full = extract_core_terms(usda_match)

        # Classify both
        ing_categories = classify(ing_full)
        usda_categories = classify(usda_full)

        # Base score calculation
        score = 0.0

        # If no categories detected, use string similarity as fallback
        if not ing_categories or not usda_categories:
            # Simple word overlap scoring
            ing_words = set(ing_primary.split())
            usda_words = set(usda_primary.split())
            if ing_words and usda_words:
                overlap = len(ing_words & usda_words)
                total = len(ing_words | usda_words)
                score = (overlap / total) * 50.0 if total > 0 else 0.0
            return score

        # Category overlap scoring
        common_categories = ing_categories & usda_categories

        if common_categories:
            # Strong match - same category
            base_score = 70.0

            # Bonus for multiple matching categories
            category_bonus = len(common_categories) * 5.0

            # Check for exact word matches
            ing_words = set(ing_primary.split())
            usda_words = set(usda_primary.split())
            word_overlap = len(ing_words & usda_words)
            word_bonus = word_overlap * 3.0

            score = base_score + category_bonus + word_bonus

        else:
            # Different categories - penalize
            # Some categories are more compatible than others
            compatible_pairs = [
                {'produce_vegetable', 'produce_fruit'},
                {'produce_vegetable', 'produce_tomato'},
                {'meat', 'poultry'},
                {'fish', 'seafood'},
                {'oil', 'fat'},
                {'spice', 'condiment'}
            ]

            is_compatible = False
            for pair in compatible_pairs:
                if (ing_categories & pair) and (usda_categories & pair):
                    is_compatible = True
                    break

            if is_compatible:
                score = 30.0  # Somewhat compatible
            else:
                score = 10.0  # Very different categories

        # Cap score at 100
        score = min(score, 100.0)

        return float(score)

    except Exception:
        return 0.0
