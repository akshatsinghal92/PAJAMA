import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize inputs
        ing_lower = ingredient.lower().strip()
        usda_lower = usda_match.lower().strip()

        # Remove gram weights like "200g", "30g"
        ing_lower = re.sub(r'^\d+g?\s*', '', ing_lower)

        # Define multi-tier category keywords
        # Each category has primary and secondary indicators
        category_keywords = {
            'dairy': {
                'primary': ['milk', 'cheese', 'yogurt', 'cream', 'butter', 'whey', 'curd', 'kefir', 'buttermilk'],
                'secondary': ['dairy', 'lactose', 'casein', 'ricotta', 'mozzarella', 'cheddar', 'parmesan', 'feta']
            },
            'produce_veg': {
                'primary': ['carrot', 'broccoli', 'cabbage', 'lettuce', 'spinach', 'kale', 'celery', 'onion', 'garlic',
                           'pepper', 'tomato', 'cucumber', 'zucchini', 'squash', 'bean', 'pea', 'corn', 'potato',
                           'mushroom', 'eggplant', 'radish', 'beet', 'turnip', 'leek', 'asparagus', 'artichoke'],
                'secondary': ['vegetable', 'veggie', 'greens', 'leafy', 'root', 'bulb']
            },
            'produce_fruit': {
                'primary': ['apple', 'banana', 'orange', 'berry', 'grape', 'lemon', 'lime', 'cherry', 'peach',
                           'pear', 'plum', 'mango', 'melon', 'pineapple', 'strawberry', 'blueberry', 'raspberry'],
                'secondary': ['fruit', 'citrus', 'tropical']
            },
            'meat': {
                'primary': ['beef', 'pork', 'lamb', 'veal', 'steak', 'bacon', 'ham', 'sausage', 'ground meat',
                           'meatball', 'patty', 'ribs'],
                'secondary': ['meat', 'red meat']
            },
            'poultry': {
                'primary': ['chicken', 'turkey', 'duck', 'goose', 'hen', 'poultry'],
                'secondary': ['bird', 'fowl']
            },
            'fish': {
                'primary': ['fish', 'salmon', 'tuna', 'cod', 'tilapia', 'trout', 'halibut', 'mackerel', 'sardine',
                           'anchovy', 'herring'],
                'secondary': ['seafood', 'fillet']
            },
            'shellfish': {
                'primary': ['shrimp', 'crab', 'lobster', 'clam', 'oyster', 'mussel', 'scallop', 'prawn', 'crayfish'],
                'secondary': ['shellfish', 'crustacean', 'mollusk']
            },
            'grain': {
                'primary': ['rice', 'wheat', 'pasta', 'noodle', 'bread', 'flour', 'cereal', 'oat', 'barley',
                           'quinoa', 'couscous', 'bulgur', 'farro', 'rye', 'millet'],
                'secondary': ['grain', 'whole grain', 'refined', 'semolina']
            },
            'legume': {
                'primary': ['lentil', 'chickpea', 'bean', 'pea', 'soy', 'tofu', 'edamame', 'hummus'],
                'secondary': ['legume', 'pulse', 'protein']
            },
            'spice': {
                'primary': ['pepper', 'salt', 'paprika', 'cumin', 'coriander', 'turmeric', 'cinnamon', 'ginger',
                           'nutmeg', 'clove', 'cardamom', 'cayenne', 'chili', 'curry', 'oregano', 'basil',
                           'thyme', 'rosemary', 'sage', 'parsley', 'dill', 'mint', 'cilantro'],
                'secondary': ['spice', 'herb', 'seasoning', 'ground', 'dried']
            },
            'oil': {
                'primary': ['oil', 'olive oil', 'vegetable oil', 'canola', 'sunflower', 'sesame', 'coconut oil',
                           'peanut oil', 'avocado oil'],
                'secondary': ['fat', 'lipid']
            },
            'sweetener': {
                'primary': ['sugar', 'honey', 'syrup', 'molasses', 'agave', 'maple', 'stevia', 'sucrose', 'fructose'],
                'secondary': ['sweetener', 'sweet']
            },
            'condiment': {
                'primary': ['sauce', 'ketchup', 'mustard', 'mayo', 'mayonnaise', 'vinegar', 'soy sauce',
                           'worcestershire', 'hot sauce', 'salsa', 'chutney', 'relish', 'dressing', 'gravy'],
                'secondary': ['condiment', 'dressing']
            },
            'nut_seed': {
                'primary': ['almond', 'walnut', 'cashew', 'peanut', 'pecan', 'pistachio', 'hazelnut', 'seed',
                           'sunflower seed', 'pumpkin seed', 'sesame seed', 'chia', 'flax'],
                'secondary': ['nut', 'seed']
            },
            'beverage': {
                'primary': ['juice', 'water', 'broth', 'stock', 'wine', 'beer', 'coffee', 'tea', 'soda'],
                'secondary': ['beverage', 'drink', 'liquid']
            }
        }

        def compute_category_scores(text):
            """Return dictionary of category: score for the text"""
            scores = defaultdict(float)

            for category, keywords in category_keywords.items():
                primary_matches = sum(1 for kw in keywords['primary'] if kw in text)
                secondary_matches = sum(1 for kw in keywords['secondary'] if kw in text)

                # Weighted scoring: primary keywords worth more
                scores[category] = primary_matches * 3.0 + secondary_matches * 1.0

            return scores

        # Compute category scores for both ingredient and USDA match
        ing_scores = compute_category_scores(ing_lower)
        usda_scores = compute_category_scores(usda_lower)

        # Find top categories for each
        ing_top_category = max(ing_scores.items(), key=lambda x: x[1]) if ing_scores else (None, 0)
        usda_top_category = max(usda_scores.items(), key=lambda x: x[1]) if usda_scores else (None, 0)

        # Base score starts at 50
        score = 50.0

        # If both have no strong category signal, return neutral
        if ing_top_category[1] == 0 and usda_top_category[1] == 0:
            return score

        # Calculate category overlap using cosine-like similarity
        all_categories = set(ing_scores.keys()) | set(usda_scores.keys())
        dot_product = sum(ing_scores[cat] * usda_scores[cat] for cat in all_categories)

        ing_magnitude = sum(v * v for v in ing_scores.values()) ** 0.5
        usda_magnitude = sum(v * v for v in usda_scores.values()) ** 0.5

        if ing_magnitude > 0 and usda_magnitude > 0:
            similarity = dot_product / (ing_magnitude * usda_magnitude)

            # Scale similarity (0-1) to bonus/penalty (-30 to +30)
            category_adjustment = (similarity - 0.5) * 60
            score += category_adjustment
        else:
            # If one has no signal, penalize
            score -= 20

        # Additional bonus if top categories match exactly
        if ing_top_category[0] == usda_top_category[0] and ing_top_category[0] is not None:
            score += 15

        # Penalty for cross-category high confidence mismatches
        if (ing_top_category[0] != usda_top_category[0] and
            ing_top_category[1] > 2 and usda_top_category[1] > 2):
            score -= 25

        # Special handling for common confusions
        # Spice vs vegetable
        if (('spice' in [ing_top_category[0], usda_top_category[0]]) and
            ('produce_veg' in [ing_top_category[0], usda_top_category[0]])):
            score -= 30

        # Sauce vs base ingredient
        if 'sauce' in ing_lower and 'sauce' not in usda_lower:
            score -= 20
        elif 'sauce' in usda_lower and 'sauce' not in ing_lower:
            score -= 20

        # Ensure score stays in reasonable range
        score = max(0, min(100, score))

        return round(score, 2)

    except Exception:
        return 50.0
