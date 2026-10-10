import re
import math
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = ingredient.lower().strip()
        usda_match = usda_match.lower().strip()

        # Remove gram weights from ingredient
        ingredient = re.sub(r'^\d+g?\s*', '', ingredient)

        # Extract parentheticals and post-comma qualifiers
        ing_parens = re.findall(r'\([^)]+\)', ingredient)
        ing_base = re.sub(r'\([^)]+\)', '', ingredient)
        ing_parts = [p.strip() for p in ing_base.split(',')]

        usda_parts = [p.strip() for p in usda_match.split(',')]

        # Macro category signatures based on keywords
        macro_signatures = {
            'pure_fat': ['oil', 'butter', 'lard', 'shortening', 'ghee', 'margarine'],
            'lean_protein': ['chicken breast', 'turkey breast', 'cod', 'tilapia', 'shrimp', 'egg white', 'tuna'],
            'fatty_protein': ['salmon', 'mackerel', 'beef', 'pork', 'lamb', 'egg', 'whole egg'],
            'dairy_fat': ['cream', 'cheese', 'whole milk', 'yogurt'],
            'leafy_green': ['spinach', 'lettuce', 'kale', 'cabbage', 'chard', 'arugula'],
            'starchy_carb': ['pasta', 'rice', 'potato', 'bread', 'noodle', 'quinoa', 'oats'],
            'sugar_carb': ['sugar', 'honey', 'syrup', 'molasses', 'agave'],
            'legume': ['bean', 'lentil', 'chickpea', 'pea'],
            'nut_seed': ['almond', 'walnut', 'cashew', 'peanut', 'tahini', 'sesame'],
            'condiment': ['sauce', 'paste', 'vinegar', 'mustard', 'ketchup', 'mayonnaise'],
            'spice': ['salt', 'pepper', 'cumin', 'cinnamon', 'ginger', 'turmeric', 'paprika'],
            'grain_product': ['cereal', 'granola', 'cracker', 'flour'],
            'fruit': ['apple', 'banana', 'berry', 'orange', 'grape', 'mango', 'tomato'],
            'root_veg': ['carrot', 'beet', 'turnip', 'radish', 'onion', 'garlic']
        }

        def get_macro_category(text):
            text_lower = text.lower()
            scores = defaultdict(float)

            for category, keywords in macro_signatures.items():
                for keyword in keywords:
                    if keyword in text_lower:
                        scores[category] += len(keyword) / (len(text_lower) + 1)

            if not scores:
                return 'unknown'
            return max(scores, key=scores.get)

        ing_category = get_macro_category(ingredient)
        usda_category = get_macro_category(usda_match)

        # Base score from category match
        if ing_category == usda_category and ing_category != 'unknown':
            category_score = 50.0
        elif ing_category == 'unknown' or usda_category == 'unknown':
            category_score = 25.0
        else:
            category_score = 10.0

        # State mismatch penalties
        state_descriptors = {
            'preparation': ['raw', 'cooked', 'frozen', 'canned', 'dried', 'fresh'],
            'liquid': ['drained', 'with oil', 'with sauce', 'in brine', 'in water', 'with liquid'],
            'form': ['ground', 'whole', 'sliced', 'diced', 'shredded', 'chopped', 'pureed']
        }

        def extract_states(text):
            states = set()
            for category, descriptors in state_descriptors.items():
                for desc in descriptors:
                    if desc in text:
                        states.add((category, desc))
            return states

        ing_states = extract_states(ingredient)
        usda_states = extract_states(usda_match)

        # Critical mismatches
        state_penalty = 0.0

        # Check preparation state conflicts
        ing_prep = {s[1] for s in ing_states if s[0] == 'preparation'}
        usda_prep = {s[1] for s in usda_states if s[0] == 'preparation'}

        critical_conflicts = [
            ('raw', 'cooked'),
            ('fresh', 'canned'),
            ('frozen', 'fresh')
        ]

        for s1, s2 in critical_conflicts:
            if (s1 in ing_prep and s2 in usda_prep) or (s2 in ing_prep and s1 in usda_prep):
                state_penalty += 25.0

        # Check liquid state conflicts (very important for nutrition)
        ing_liquid = {s[1] for s in ing_states if s[0] == 'liquid'}
        usda_liquid = {s[1] for s in usda_states if s[0] == 'liquid'}

        if 'drained' in ing_liquid and any(x in usda_liquid for x in ['with oil', 'with sauce', 'with liquid']):
            state_penalty += 30.0
        elif any(x in ing_liquid for x in ['with oil', 'with sauce']) and 'drained' in usda_liquid:
            state_penalty += 30.0

        # Keyword overlap score using term frequency
        def tokenize(text):
            return set(re.findall(r'\b\w+\b', text.lower())) - {'the', 'a', 'an', 'with', 'from', 'in'}

        ing_tokens = tokenize(ing_parts[0] if ing_parts else ingredient)
        usda_tokens = tokenize(usda_parts[0] if usda_parts else usda_match)

        common_tokens = ing_tokens & usda_tokens
        if ing_tokens and usda_tokens:
            overlap_ratio = len(common_tokens) / math.sqrt(len(ing_tokens) * len(usda_tokens))
            overlap_score = overlap_ratio * 30.0
        else:
            overlap_score = 0.0

        # Composite/sauce penalty
        composite_words = ['sauce', 'paste', 'blend', 'mix', 'seasoning']
        ing_is_composite = any(w in ingredient for w in composite_words)
        usda_is_composite = any(w in usda_match for w in composite_words)

        composite_penalty = 0.0
        if ing_is_composite != usda_is_composite:
            composite_penalty = 15.0

        # Final score calculation
        final_score = category_score + overlap_score - state_penalty - composite_penalty

        # Clamp to 0-100 range
        final_score = max(0.0, min(100.0, final_score))

        return final_score

    except Exception:
        return 25.0
