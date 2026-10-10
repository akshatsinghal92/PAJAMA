import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ing_lower = ingredient.lower()
        usda_lower = usda_match.lower()

        # Extract core text by removing gram weights and parentheticals
        ing_clean = re.sub(r'^\d+g?\s*', '', ing_lower)
        ing_clean = re.sub(r'\([^)]*\)', '', ing_clean).strip()
        usda_clean = re.sub(r'\([^)]*\)', '', usda_lower).strip()

        # Food category keyword sets (variant 2: comprehensive multi-level taxonomy)
        categories = {
            'dairy': {
                'primary': ['milk', 'cheese', 'yogurt', 'cream', 'butter', 'ghee', 'paneer', 'curd', 'kefir', 'buttermilk'],
                'secondary': ['dairy', 'whey', 'casein', 'lactose']
            },
            'produce_veg': {
                'primary': ['lettuce', 'cabbage', 'carrot', 'broccoli', 'cauliflower', 'spinach', 'kale', 'tomato',
                           'cucumber', 'pepper', 'onion', 'garlic', 'celery', 'zucchini', 'eggplant', 'radish',
                           'beet', 'potato', 'bean', 'pea', 'corn', 'mushroom', 'squash', 'pumpkin'],
                'secondary': ['vegetable', 'veggie', 'greens', 'salad']
            },
            'produce_fruit': {
                'primary': ['apple', 'banana', 'orange', 'grape', 'berry', 'strawberry', 'blueberry', 'cherry',
                           'peach', 'pear', 'plum', 'mango', 'pineapple', 'lemon', 'lime', 'melon', 'watermelon'],
                'secondary': ['fruit', 'citrus']
            },
            'meat_poultry': {
                'primary': ['chicken', 'turkey', 'duck', 'beef', 'pork', 'lamb', 'veal', 'goat', 'bacon', 'sausage',
                           'ham', 'steak', 'chop', 'breast', 'thigh', 'wing', 'drumstick', 'ground beef', 'mince'],
                'secondary': ['meat', 'poultry']
            },
            'seafood': {
                'primary': ['fish', 'salmon', 'tuna', 'cod', 'tilapia', 'shrimp', 'prawn', 'crab', 'lobster',
                           'clam', 'mussel', 'oyster', 'squid', 'octopus', 'anchovy', 'sardine'],
                'secondary': ['seafood', 'shellfish']
            },
            'grain': {
                'primary': ['rice', 'wheat', 'oat', 'barley', 'quinoa', 'bulgur', 'couscous', 'pasta', 'noodle',
                           'bread', 'flour', 'cereal', 'granola', 'bran', 'farro', 'millet', 'rye'],
                'secondary': ['grain', 'whole grain']
            },
            'legume': {
                'primary': ['lentil', 'chickpea', 'garbanzo', 'black bean', 'kidney bean', 'pinto bean',
                           'navy bean', 'soy', 'tofu', 'tempeh', 'edamame', 'peanut'],
                'secondary': ['legume', 'pulse', 'bean']
            },
            'spice_herb': {
                'primary': ['salt', 'pepper', 'cumin', 'coriander', 'turmeric', 'paprika', 'cinnamon', 'ginger',
                           'garlic powder', 'onion powder', 'oregano', 'basil', 'thyme', 'rosemary', 'sage',
                           'parsley', 'cilantro', 'dill', 'mint', 'chili', 'cayenne', 'nutmeg', 'clove',
                           'cardamom', 'fennel', 'bay', 'vanilla'],
                'secondary': ['spice', 'herb', 'seasoning', 'spices']
            },
            'oil_fat': {
                'primary': ['oil', 'olive oil', 'canola oil', 'vegetable oil', 'coconut oil', 'sesame oil',
                           'sunflower oil', 'avocado oil', 'lard', 'shortening', 'margarine'],
                'secondary': ['fat', 'grease']
            },
            'sweetener': {
                'primary': ['sugar', 'honey', 'syrup', 'maple syrup', 'agave', 'molasses', 'stevia', 'aspartame'],
                'secondary': ['sweetener', 'sweet']
            },
            'condiment_sauce': {
                'primary': ['ketchup', 'mustard', 'mayo', 'mayonnaise', 'soy sauce', 'fish sauce', 'hot sauce',
                           'worcestershire', 'vinegar', 'salsa', 'pesto', 'tahini', 'hummus', 'jam', 'jelly',
                           'pickle', 'relish', 'chutney', 'paste'],
                'secondary': ['sauce', 'condiment', 'dressing', 'marinade']
            },
            'nut_seed': {
                'primary': ['almond', 'walnut', 'pecan', 'cashew', 'pistachio', 'hazelnut', 'macadamia',
                           'sunflower seed', 'pumpkin seed', 'sesame seed', 'chia', 'flax'],
                'secondary': ['nut', 'seed']
            }
        }

        def get_category_scores(text):
            scores = defaultdict(float)
            words = text.split()
            for category, keywords in categories.items():
                for word in words:
                    # Primary keyword match
                    for kw in keywords['primary']:
                        if kw in text or word == kw.split()[0]:
                            scores[category] += 10.0
                    # Secondary keyword match
                    for kw in keywords['secondary']:
                        if kw in text:
                            scores[category] += 3.0
            return scores

        ing_scores = get_category_scores(ing_clean)
        usda_scores = get_category_scores(usda_clean)

        # Find top categories for each
        ing_top_cat = max(ing_scores, key=ing_scores.get) if ing_scores else None
        usda_top_cat = max(usda_scores, key=usda_scores.get) if usda_scores else None

        base_score = 0.0

        # Category match scoring
        if ing_top_cat and usda_top_cat:
            if ing_top_cat == usda_top_cat:
                # Same category: high base score
                base_score = 70.0
                # Bonus for strength of category match
                base_score += min(ing_scores[ing_top_cat], usda_scores[usda_top_cat]) / 2
            else:
                # Different categories: low base score
                base_score = 20.0
        else:
            # No clear category detected
            base_score = 30.0

        # Text overlap bonus (shared words)
        ing_words = set(ing_clean.split())
        usda_words = set(usda_clean.split())
        ing_words = {w for w in ing_words if len(w) > 2}
        usda_words = {w for w in usda_words if len(w) > 2}

        if ing_words and usda_words:
            overlap = len(ing_words & usda_words)
            overlap_ratio = overlap / max(len(ing_words), len(usda_words))
            base_score += overlap_ratio * 15.0

        # State mismatch penalties
        state_mismatches = [
            ('raw', 'cooked'), ('raw', 'fried'), ('raw', 'roasted'),
            ('fresh', 'dried'), ('fresh', 'frozen'), ('fresh', 'canned'),
            ('frozen', 'fresh'), ('canned', 'fresh'), ('dried', 'fresh'),
            ('whole', 'ground'), ('whole', 'sliced'), ('whole', 'diced'),
            ('plain', 'sauce'), ('seed', 'butter'), ('seed', 'paste')
        ]

        for state1, state2 in state_mismatches:
            if (state1 in ing_clean and state2 in usda_clean) or \
               (state2 in ing_clean and state1 in usda_clean):
                base_score *= 0.6
                break

        # Additional processing mismatch check
        if 'sauce' in ing_clean and 'sauce' not in usda_clean:
            base_score *= 0.7
        if 'paste' in ing_clean and 'paste' not in usda_clean:
            base_score *= 0.7

        return round(max(0.0, min(100.0, base_score)), 2)

    except Exception:
        return 0.0
