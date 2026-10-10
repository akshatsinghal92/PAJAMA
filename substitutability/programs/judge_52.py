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

        # Define food categories with comprehensive keyword sets
        # Each category gets multiple weighted indicators
        category_keywords = {
            'dairy': {
                'primary': ['milk', 'cheese', 'cream', 'yogurt', 'butter', 'whey', 'curd', 'dairy', 'cottage', 'ricotta', 'mozzarella', 'cheddar', 'parmesan', 'feta'],
                'secondary': ['lactose', 'casein', 'buttermilk', 'kefir', 'ghee']
            },
            'produce': {
                'primary': ['vegetable', 'tomato', 'onion', 'garlic', 'potato', 'carrot', 'pepper', 'lettuce', 'cabbage', 'spinach', 'broccoli', 'mushroom', 'bean', 'pea', 'corn', 'cucumber', 'zucchini', 'eggplant', 'squash', 'celery'],
                'secondary': ['fresh', 'raw', 'leafy', 'green', 'root']
            },
            'meat_poultry_fish': {
                'primary': ['chicken', 'beef', 'pork', 'turkey', 'lamb', 'fish', 'salmon', 'tuna', 'shrimp', 'meat', 'poultry', 'veal', 'duck', 'bacon', 'sausage', 'ham'],
                'secondary': ['ground', 'breast', 'thigh', 'fillet', 'steak', 'chop', 'wing', 'leg']
            },
            'grain': {
                'primary': ['pasta', 'rice', 'bread', 'flour', 'wheat', 'oat', 'barley', 'quinoa', 'cereal', 'grain', 'noodle', 'macaroni', 'spaghetti', 'penne', 'couscous', 'granola'],
                'secondary': ['whole grain', 'refined', 'semolina', 'bulgur', 'millet']
            },
            'legume': {
                'primary': ['lentil', 'chickpea', 'bean', 'pea', 'soy', 'tofu', 'tempeh', 'legume', 'pulse'],
                'secondary': ['split', 'dried', 'edamame']
            },
            'spice_herb': {
                'primary': ['spice', 'herb', 'pepper', 'salt', 'cumin', 'paprika', 'oregano', 'basil', 'thyme', 'rosemary', 'parsley', 'cilantro', 'ginger', 'turmeric', 'cinnamon', 'nutmeg', 'clove', 'cardamom', 'coriander', 'sage', 'dill', 'mint'],
                'secondary': ['dried', 'ground', 'fresh', 'leaf', 'seed']
            },
            'oil_fat': {
                'primary': ['oil', 'fat', 'olive oil', 'vegetable oil', 'canola', 'shortening', 'lard', 'margarine', 'tahini'],
                'secondary': ['cooking', 'pressed', 'virgin', 'refined']
            },
            'sweetener': {
                'primary': ['sugar', 'honey', 'syrup', 'molasses', 'agave', 'sweetener', 'stevia', 'maple syrup'],
                'secondary': ['brown', 'white', 'powdered', 'granulated']
            },
            'condiment': {
                'primary': ['sauce', 'ketchup', 'mustard', 'mayo', 'vinegar', 'soy sauce', 'fish sauce', 'hot sauce', 'salsa', 'chutney', 'relish', 'dressing', 'paste'],
                'secondary': ['seasoning', 'marinade', 'glaze']
            }
        }

        def get_category_scores(text):
            """Returns a dict of category: weighted_score for all categories found in text"""
            scores = defaultdict(float)

            for category, keywords in category_keywords.items():
                primary_matches = sum(1 for kw in keywords['primary'] if kw in text)
                secondary_matches = sum(1 for kw in keywords['secondary'] if kw in text)

                # Primary keywords worth 3 points, secondary worth 1
                total_score = primary_matches * 3.0 + secondary_matches * 1.0

                if total_score > 0:
                    scores[category] = total_score

            return scores

        # Get category scores for both texts
        ing_scores = get_category_scores(ingredient)
        usda_scores = get_category_scores(usda_match)

        # If neither has any category match, return low score
        if not ing_scores or not usda_scores:
            return 10.0

        # Calculate overlap score using weighted intersection
        # Find common categories and their minimum scores
        common_categories = set(ing_scores.keys()) & set(usda_scores.keys())

        if not common_categories:
            # No common category - penalize heavily
            return 5.0

        # Calculate category alignment score
        # Use the minimum of the two scores for each common category
        alignment_score = sum(min(ing_scores[cat], usda_scores[cat]) for cat in common_categories)

        # Normalize by the total categories detected
        total_categories_detected = len(set(ing_scores.keys()) | set(usda_scores.keys()))

        # Calculate category consistency ratio
        # High when most categories overlap, low when many categories differ
        consistency_ratio = len(common_categories) / total_categories_detected

        # Base score from alignment
        base_score = alignment_score * 5.0

        # Bonus for high consistency ratio
        consistency_bonus = consistency_ratio * 20.0

        # Penalty for having too many different categories (suggests mismatch)
        different_categories = total_categories_detected - len(common_categories)
        diversity_penalty = different_categories * 3.0

        # Final score
        final_score = base_score + consistency_bonus - diversity_penalty

        # Clamp to reasonable range 0-100
        final_score = max(0.0, min(100.0, final_score))

        return final_score

    except Exception:
        return 10.0
