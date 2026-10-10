import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ing_lower = ingredient.lower()
        usda_lower = usda_match.lower()

        # Define food categories with comprehensive keyword sets
        categories = {
            'dairy': {'milk', 'cheese', 'yogurt', 'cream', 'butter', 'ghee', 'curd', 'paneer',
                     'cottage', 'ricotta', 'mozzarella', 'parmesan', 'cheddar', 'feta', 'brie',
                     'whey', 'lactose', 'dairy'},
            'meat': {'beef', 'pork', 'lamb', 'veal', 'steak', 'bacon', 'ham', 'sausage',
                    'salami', 'prosciutto', 'ribs', 'ground meat', 'meatball', 'patty'},
            'poultry': {'chicken', 'turkey', 'duck', 'goose', 'hen', 'fowl', 'poultry'},
            'fish': {'fish', 'salmon', 'tuna', 'cod', 'trout', 'sardine', 'anchovy', 'tilapia',
                    'mackerel', 'herring', 'halibut', 'seafood', 'bass'},
            'shellfish': {'shrimp', 'crab', 'lobster', 'mussel', 'clam', 'oyster', 'scallop',
                         'prawn', 'crawfish', 'shellfish'},
            'vegetable': {'carrot', 'broccoli', 'cabbage', 'lettuce', 'spinach', 'kale',
                         'celery', 'onion', 'garlic', 'pepper', 'tomato', 'cucumber', 'zucchini',
                         'eggplant', 'squash', 'pumpkin', 'beet', 'radish', 'turnip', 'leek',
                         'scallion', 'shallot', 'asparagus', 'artichoke', 'bean', 'pea',
                         'vegetable', 'greens'},
            'fruit': {'apple', 'banana', 'orange', 'lemon', 'lime', 'berry', 'strawberry',
                     'blueberry', 'raspberry', 'grape', 'melon', 'watermelon', 'peach', 'pear',
                     'plum', 'cherry', 'mango', 'pineapple', 'papaya', 'kiwi', 'fruit'},
            'grain': {'wheat', 'rice', 'oat', 'barley', 'quinoa', 'corn', 'rye', 'millet',
                     'bulgur', 'couscous', 'farro', 'grain', 'cereal', 'granola'},
            'pasta': {'pasta', 'penne', 'spaghetti', 'linguine', 'fettuccine', 'rigatoni',
                     'macaroni', 'noodle', 'lasagna', 'ravioli'},
            'legume': {'lentil', 'chickpea', 'pinto', 'kidney bean', 'black bean', 'navy bean',
                      'lima bean', 'soy', 'tofu', 'tempeh', 'legume', 'pulse'},
            'nut_seed': {'almond', 'walnut', 'pecan', 'cashew', 'pistachio', 'hazelnut',
                        'peanut', 'seed', 'sunflower', 'pumpkin seed', 'sesame', 'tahini',
                        'flax', 'chia'},
            'spice_herb': {'salt', 'pepper', 'paprika', 'cumin', 'coriander', 'cinnamon',
                          'nutmeg', 'clove', 'cardamom', 'turmeric', 'ginger', 'oregano',
                          'basil', 'thyme', 'rosemary', 'sage', 'parsley', 'cilantro', 'dill',
                          'mint', 'bay', 'spice', 'herb', 'seasoning'},
            'oil_fat': {'oil', 'olive oil', 'vegetable oil', 'canola', 'sunflower oil',
                       'coconut oil', 'sesame oil', 'lard', 'shortening', 'fat', 'grease'},
            'sweetener': {'sugar', 'honey', 'syrup', 'maple', 'molasses', 'agave', 'stevia',
                         'sweetener', 'glucose', 'fructose'},
            'condiment': {'ketchup', 'mustard', 'mayo', 'mayonnaise', 'relish', 'chutney',
                         'pickle', 'sauce', 'dressing', 'vinegar', 'soy sauce', 'fish sauce',
                         'worcestershire', 'hot sauce', 'salsa', 'condiment'},
            'baking': {'flour', 'baking powder', 'baking soda', 'yeast', 'cornstarch',
                      'gelatin', 'agar', 'pectin'},
            'beverage': {'juice', 'coffee', 'tea', 'soda', 'water', 'milk', 'wine', 'beer',
                        'beverage', 'drink'},
        }

        # Extract meaningful terms (remove gram weights, common prep words)
        def extract_terms(text):
            # Remove gram weights like "200g", "30g"
            text = re.sub(r'\d+g\s*', '', text)
            # Remove parentheticals
            text = re.sub(r'\([^)]*\)', '', text)
            # Split by comma and take relevant parts
            parts = text.split(',')
            # Common prep words to filter out
            prep_words = {'frozen', 'fresh', 'dried', 'canned', 'cooked', 'raw', 'chopped',
                         'diced', 'sliced', 'minced', 'shredded', 'grated', 'ground',
                         'whole', 'crushed', 'peeled', 'drained', 'thawed', 'uncooked',
                         'roasted', 'toasted', 'blanched', 'steamed', 'boiled', 'fried'}

            terms = []
            for part in parts:
                words = part.strip().split()
                terms.extend([w for w in words if w not in prep_words and len(w) > 2])
            return ' '.join(terms)

        ing_terms = extract_terms(ing_lower)
        usda_terms = extract_terms(usda_lower)

        # Classify into categories
        def classify_categories(text):
            found = set()
            for cat, keywords in categories.items():
                for keyword in keywords:
                    if keyword in text:
                        found.add(cat)
                        break
            return found

        ing_cats = classify_categories(ing_lower)
        usda_cats = classify_categories(usda_lower)

        # Base score: category overlap
        if ing_cats and usda_cats:
            common_cats = ing_cats & usda_cats
            if common_cats:
                # Strong match: shared categories
                base_score = 70.0 + (len(common_cats) * 10.0)
            else:
                # No shared categories: penalty
                base_score = 20.0
        else:
            # One or both have no clear category
            base_score = 40.0

        # Bonus: word overlap between cleaned terms
        ing_words = set(ing_terms.split())
        usda_words = set(usda_terms.split())
        common_words = ing_words & usda_words
        word_overlap_score = len(common_words) * 5.0

        # Penalty: state mismatch indicators
        state_penalty = 0.0

        # Check for problematic state mismatches
        ing_has_sauce = 'sauce' in ing_lower and 'sauce' not in usda_lower
        usda_has_sauce = 'sauce' in usda_lower and 'sauce' not in ing_lower
        if ing_has_sauce or usda_has_sauce:
            state_penalty += 30.0

        # Cooked state mismatch
        ing_cooked = 'cooked' in ing_lower or 'fried' in ing_lower or 'roasted' in ing_lower
        usda_cooked = 'cooked' in usda_lower or 'fried' in usda_lower or 'roasted' in usda_lower
        ing_raw = 'raw' in ing_lower or 'fresh' in ing_lower
        usda_raw = 'raw' in usda_lower or 'fresh' in usda_lower

        if (ing_cooked and usda_raw) or (ing_raw and usda_cooked):
            state_penalty += 15.0

        # Drained vs with liquid mismatch
        ing_drained = 'drained' in ing_lower
        usda_has_liquid = any(x in usda_lower for x in ['with oil', 'with sauce', 'in liquid'])
        if ing_drained and usda_has_liquid:
            state_penalty += 25.0

        # Calculate final score
        final_score = base_score + word_overlap_score - state_penalty

        # Clamp to reasonable range
        final_score = max(0.0, min(100.0, final_score))

        return final_score

    except Exception:
        return 0.0
