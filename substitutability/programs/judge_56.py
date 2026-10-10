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

        # Category definitions with hierarchical keywords
        categories = {
            'dairy': ['milk', 'cheese', 'yogurt', 'cream', 'butter', 'curd', 'whey', 'buttermilk', 'ricotta', 'mozzarella', 'cheddar', 'parmesan', 'feta'],
            'produce_veg': ['lettuce', 'cabbage', 'carrot', 'onion', 'garlic', 'potato', 'tomato', 'pepper', 'cucumber', 'spinach', 'kale', 'broccoli', 'cauliflower', 'celery', 'mushroom', 'bean', 'peas', 'corn', 'zucchini', 'eggplant', 'radish', 'beet'],
            'produce_fruit': ['apple', 'banana', 'orange', 'berry', 'grape', 'melon', 'peach', 'pear', 'cherry', 'strawberry', 'blueberry', 'raspberry', 'lemon', 'lime', 'mango', 'pineapple'],
            'protein_meat': ['beef', 'pork', 'lamb', 'veal', 'bacon', 'ham', 'sausage', 'steak', 'ribs', 'ground beef', 'patty'],
            'protein_poultry': ['chicken', 'turkey', 'duck', 'poultry', 'breast', 'thigh', 'wing', 'drumstick'],
            'protein_fish': ['fish', 'salmon', 'tuna', 'cod', 'tilapia', 'trout', 'sardine', 'anchovy', 'mackerel', 'seafood', 'shrimp', 'crab', 'lobster', 'clam', 'mussel'],
            'protein_egg': ['egg', 'yolk', 'white'],
            'grain': ['pasta', 'rice', 'bread', 'cereal', 'oat', 'wheat', 'flour', 'quinoa', 'barley', 'couscous', 'bulgur', 'noodle', 'macaroni', 'spaghetti', 'penne', 'farro', 'granola'],
            'legume': ['lentil', 'chickpea', 'kidney bean', 'black bean', 'pinto bean', 'navy bean', 'soy', 'tofu', 'edamame'],
            'spice_herb': ['salt', 'pepper', 'basil', 'oregano', 'thyme', 'rosemary', 'parsley', 'cilantro', 'dill', 'sage', 'mint', 'cinnamon', 'cumin', 'paprika', 'turmeric', 'ginger', 'nutmeg', 'clove', 'cardamom', 'coriander', 'chili', 'cayenne', 'spice', 'herb', 'seasoning'],
            'oil_fat': ['oil', 'olive oil', 'vegetable oil', 'canola oil', 'coconut oil', 'sesame oil', 'lard', 'shortening', 'fat', 'grease'],
            'sweetener': ['sugar', 'honey', 'syrup', 'molasses', 'agave', 'stevia', 'sweetener'],
            'condiment': ['sauce', 'ketchup', 'mustard', 'mayo', 'mayonnaise', 'vinegar', 'soy sauce', 'fish sauce', 'hot sauce', 'salsa', 'relish', 'chutney', 'paste', 'pesto', 'dressing'],
            'nuts_seeds': ['almond', 'walnut', 'pecan', 'cashew', 'peanut', 'pistachio', 'hazelnut', 'nut', 'seed', 'sesame', 'sunflower', 'pumpkin seed', 'tahini', 'nut butter', 'peanut butter'],
            'beverage': ['juice', 'wine', 'beer', 'broth', 'stock', 'milk', 'water', 'tea', 'coffee']
        }

        # Processing state keywords
        processing_states = {
            'raw': ['raw', 'fresh', 'uncooked'],
            'cooked': ['cooked', 'boiled', 'steamed', 'roasted', 'baked', 'fried', 'grilled', 'sauteed'],
            'canned': ['canned', 'canning'],
            'frozen': ['frozen', 'freeze'],
            'dried': ['dried', 'dry', 'dehydrated'],
            'prepared': ['prepared', 'sauce', 'paste', 'puree', 'diced', 'chopped', 'shredded', 'sliced', 'ground']
        }

        # Extract gram weight prefix and clean text
        def clean_text(text):
            text = re.sub(r'^\d+g?\s*', '', text)
            text = re.sub(r'\(.*?\)', '', text)
            text = re.sub(r',.*$', '', text)
            return text.strip()

        ing_clean = clean_text(ingredient)
        usda_clean = clean_text(usda_match)

        # Classify into categories
        def classify(text, full_text):
            matches = []
            for cat, keywords in categories.items():
                for keyword in keywords:
                    if keyword in text or keyword in full_text:
                        matches.append(cat)
            return list(set(matches))

        ing_cats = classify(ing_clean, ingredient)
        usda_cats = classify(usda_clean, usda_match)

        if not ing_cats or not usda_cats:
            return 30.0

        # Calculate category similarity using Jaccard-like coefficient
        # Map related categories to parent groups
        def get_parent_category(cat):
            if cat.startswith('produce_'):
                return 'produce'
            if cat.startswith('protein_'):
                return 'protein'
            return cat

        ing_parents = [get_parent_category(c) for c in ing_cats]
        usda_parents = [get_parent_category(c) for c in usda_cats]

        # Exact category match score
        exact_matches = len(set(ing_cats) & set(usda_cats))
        parent_matches = len(set(ing_parents) & set(usda_parents))

        # Base category score
        if exact_matches > 0:
            category_score = 85.0 + (exact_matches * 5.0)
        elif parent_matches > 0:
            category_score = 70.0 + (parent_matches * 5.0)
        else:
            category_score = 25.0

        # Detect processing states
        def get_processing_states(text):
            states = []
            for state, keywords in processing_states.items():
                for keyword in keywords:
                    if keyword in text:
                        states.append(state)
            return list(set(states))

        ing_states = get_processing_states(ingredient)
        usda_states = get_processing_states(usda_match)

        # Processing state modifier
        state_penalty = 0.0

        # Check for problematic mismatches
        if 'cooked' in usda_states and 'cooked' not in ing_states and 'raw' not in usda_states:
            state_penalty += 20.0

        if 'sauce' in usda_match and 'sauce' not in ingredient:
            state_penalty += 25.0
        elif 'sauce' in ingredient and 'sauce' not in usda_match:
            state_penalty += 25.0

        if 'paste' in ingredient and 'paste' not in usda_match:
            state_penalty += 15.0
        elif 'paste' in usda_match and 'paste' not in ingredient:
            state_penalty += 15.0

        # Oil/cooking modifier mismatch
        if ('with oil' in usda_match or 'in oil' in usda_match) and 'drained' in ingredient:
            state_penalty += 30.0

        # Canned state check
        if 'canned' in ing_states and 'canned' in usda_states:
            state_penalty -= 5.0  # Small bonus for matching canned state

        # Calculate final score with exponential decay for penalties
        penalty_factor = math.exp(-state_penalty / 40.0)
        final_score = category_score * penalty_factor

        # Apply smoothing to ensure discriminative output
        final_score = max(0.0, min(100.0, final_score))

        # Add small variance based on text similarity for tie-breaking
        common_words = set(ing_clean.split()) & set(usda_clean.split())
        word_bonus = len(common_words) * 1.5
        final_score = min(100.0, final_score + word_bonus)

        return round(final_score, 2)

    except Exception as e:
        return 50.0
