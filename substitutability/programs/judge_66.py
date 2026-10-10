import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = ingredient.lower().strip()
        usda_match = usda_match.lower().strip()

        # Remove gram weights
        ingredient = re.sub(r'^\d+g?\s*', '', ingredient)

        # Define culinary role categories
        role_map = {
            'fat': ['oil', 'butter', 'lard', 'ghee', 'shortening', 'margarine'],
            'acid': ['vinegar', 'lemon', 'lime', 'citrus'],
            'sweetener': ['sugar', 'honey', 'syrup', 'molasses', 'agave'],
            'binder': ['egg', 'gelatin', 'flour'],
            'thickener': ['cornstarch', 'flour', 'roux', 'arrowroot'],
            'aromatic': ['garlic', 'onion', 'ginger', 'shallot', 'scallion'],
            'herb': ['basil', 'parsley', 'cilantro', 'thyme', 'rosemary'],
            'spice': ['pepper', 'cumin', 'paprika', 'cinnamon', 'turmeric'],
            'condiment': ['sauce', 'paste', 'ketchup', 'mustard', 'mayo'],
            'protein': ['chicken', 'beef', 'pork', 'fish', 'tofu', 'turkey'],
            'grain': ['rice', 'pasta', 'noodle', 'couscous', 'quinoa'],
            'dairy': ['milk', 'cheese', 'yogurt', 'cream'],
            'vegetable': ['tomato', 'carrot', 'celery', 'cabbage', 'spinach', 'beans'],
            'seasoning': ['salt', 'soy sauce', 'fish sauce']
        }

        # Extract roles for both
        def get_roles(text):
            roles = set()
            for role, keywords in role_map.items():
                if any(kw in text for kw in keywords):
                    roles.add(role)
            return roles

        ing_roles = get_roles(ingredient)
        usda_roles = get_roles(usda_match)

        # Base score from role overlap
        if not ing_roles or not usda_roles:
            role_score = 5.0
        else:
            overlap = len(ing_roles & usda_roles)
            total = len(ing_roles | usda_roles)
            role_score = 10.0 * (overlap / total) if total > 0 else 5.0

        # State and preparation keywords that affect interchangeability
        state_keywords = {
            'cooked': ['cooked', 'baked', 'roasted', 'fried', 'boiled', 'steamed'],
            'raw': ['raw', 'fresh', 'uncooked'],
            'canned': ['canned', 'tinned'],
            'frozen': ['frozen'],
            'dried': ['dried', 'dehydrated'],
            'drained': ['drained'],
            'with_liquid': ['with oil', 'with water', 'in brine', 'in juice'],
            'ground': ['ground', 'minced', 'powdered'],
            'whole': ['whole'],
            'chopped': ['chopped', 'diced', 'sliced', 'shredded'],
            'paste': ['paste'],
            'sauce_form': ['sauce']
        }

        def get_states(text):
            states = set()
            for state_cat, keywords in state_keywords.items():
                if any(kw in text for kw in keywords):
                    states.add(state_cat)
            return states

        ing_states = get_states(ingredient)
        usda_states = get_states(usda_match)

        # Check for problematic state mismatches
        penalty = 0.0

        # Cooked vs raw/uncooked mismatch
        if ('cooked' in ing_states) != ('cooked' in usda_states):
            # Especially bad for pasta/grains
            if any(kw in ingredient or kw in usda_match for kw in ['pasta', 'rice', 'noodle']):
                penalty += 6.0
            else:
                penalty += 3.0

        # Drained vs with liquid mismatch
        if 'drained' in ing_states and 'with_liquid' in usda_states:
            penalty += 5.0

        # Sauce vs base ingredient (tahini sauce vs tahini)
        if 'sauce_form' in ing_states and 'sauce_form' not in usda_states:
            # Check if base ingredient matches
            ing_base = re.sub(r'\s+sauce.*', '', ingredient)
            if ing_base not in usda_match:
                penalty += 4.5

        # Paste vs non-paste
        if 'paste' in ing_states and 'paste' not in usda_states:
            penalty += 3.0

        # Form mismatch (whole vs chopped matters for some items)
        if 'whole' in ing_states and 'chopped' in usda_states:
            if 'tomato' in ingredient or 'cherry' in ingredient:
                penalty += 2.5

        # Frozen vs thawed contradiction
        if 'frozen' in ingredient and 'thawed' in ingredient:
            if 'frozen' in usda_match and 'thawed' not in usda_match:
                penalty += 2.0

        # Core ingredient match bonus
        ing_core = re.sub(r'\(.*?\)', '', ingredient)
        ing_core = re.sub(r',.*', '', ing_core)
        ing_words = set(re.findall(r'\b[a-z]+\b', ing_core))
        usda_words = set(re.findall(r'\b[a-z]+\b', usda_match))

        # Remove common stopwords
        stopwords = {'the', 'and', 'or', 'with', 'from', 'tube', 'can'}
        ing_words -= stopwords
        usda_words -= stopwords

        word_overlap = len(ing_words & usda_words)
        if word_overlap >= 2:
            role_score += 2.0
        elif word_overlap == 1:
            role_score += 1.0

        # Calculate final score
        final_score = max(0.0, role_score - penalty)

        return final_score

    except Exception:
        return 5.0
