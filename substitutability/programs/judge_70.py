import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = ingredient.lower().strip()
        usda_match = usda_match.lower().strip()

        # Extract core food name from ingredient (remove gram weight, parentheticals, post-comma states)
        ing_core = re.sub(r'^\d+g?\s*', '', ingredient)  # Remove leading weight
        ing_core = re.sub(r'\([^)]*\)', '', ing_core)     # Remove parentheticals
        ing_core = ing_core.split(',')[0].strip()         # Take pre-comma part

        # Culinary role categories with keywords
        roles = {
            'fat': ['oil', 'butter', 'lard', 'margarine', 'shortening', 'ghee'],
            'acid': ['vinegar', 'lemon', 'lime', 'citrus', 'wine'],
            'sweetener': ['sugar', 'honey', 'syrup', 'molasses', 'agave'],
            'protein': ['chicken', 'beef', 'pork', 'fish', 'tofu', 'egg', 'turkey', 'lamb', 'shrimp'],
            'pasta': ['pasta', 'noodle', 'spaghetti', 'penne', 'fusilli', 'macaroni'],
            'grain': ['rice', 'quinoa', 'barley', 'oats', 'wheat'],
            'sauce': ['sauce', 'paste', 'spread', 'dressing'],
            'aromatic': ['garlic', 'onion', 'ginger', 'shallot', 'leek'],
            'herb_spice': ['salt', 'pepper', 'basil', 'oregano', 'cumin', 'paprika', 'spice', 'herb'],
            'vegetable': ['tomato', 'carrot', 'cabbage', 'bean', 'pea', 'broccoli', 'spinach'],
            'thickener': ['flour', 'cornstarch', 'starch', 'gelatin']
        }

        # Identify roles for both ingredient and USDA match
        ing_roles = set()
        usda_roles = set()

        for role, keywords in roles.items():
            if any(kw in ing_core for kw in keywords):
                ing_roles.add(role)
            if any(kw in usda_match for kw in keywords):
                usda_roles.add(role)

        # Base score starts at 50
        score = 50.0

        # Role alignment: +30 if roles overlap, -25 if completely disjoint
        if ing_roles and usda_roles:
            role_overlap = len(ing_roles & usda_roles)
            if role_overlap > 0:
                score += 30.0
            else:
                score -= 25.0

        # State/form consistency checks
        state_keywords = {
            'raw': r'\braw\b',
            'cooked': r'\bcooked\b',
            'canned': r'\bcanned\b',
            'frozen': r'\bfrozen\b',
            'dried': r'\bdried\b',
            'fresh': r'\bfresh\b',
            'drained': r'\bdrained\b',
            'thawed': r'\bthawed\b'
        }

        ing_states = {state for state, pattern in state_keywords.items() if re.search(pattern, ingredient)}
        usda_states = {state for state, pattern in state_keywords.items() if re.search(pattern, usda_match)}

        # Critical state mismatches
        critical_mismatches = [
            ('raw', 'cooked'),
            ('cooked', 'raw'),
            ('drained', 'with oil'),
            ('drained', 'in liquid')
        ]

        for ing_st, usda_st in critical_mismatches:
            if ing_st in ingredient and usda_st in usda_match:
                score -= 40.0

        # Check for "with oil" or "with" additions in USDA when ingredient says "drained"
        if 'drained' in ingredient and re.search(r'\bwith\b', usda_match):
            score -= 35.0

        # Form/shape consistency
        form_keywords = {
            'whole': r'\bwhole\b',
            'diced': r'\bdiced\b',
            'chopped': r'\bchopped\b',
            'shredded': r'\bshredded\b',
            'sliced': r'\bsliced\b',
            'ground': r'\bground\b',
            'crushed': r'\bcrushed\b',
            'minced': r'\bminced\b'
        }

        ing_forms = {form for form, pattern in form_keywords.items() if re.search(pattern, ingredient)}
        usda_forms = {form for form, pattern in form_keywords.items() if re.search(pattern, usda_match)}

        # Penalize form mismatches (e.g., whole vs diced)
        if ing_forms and usda_forms and not (ing_forms & usda_forms):
            score -= 20.0

        # Special case: if ingredient specifies form but USDA doesn't, that's often OK (raw material)
        if ing_forms and not usda_forms and 'raw' in usda_match:
            score += 10.0

        # Extract core food words (nouns) for lexical similarity
        def extract_food_words(text):
            # Remove common prep/state words
            stopwords = {'with', 'from', 'in', 'the', 'and', 'or', 'of', 'cooked', 'raw', 'canned',
                        'frozen', 'dried', 'fresh', 'drained', 'thawed', 'oil', 'water'}
            words = re.findall(r'\b[a-z]+\b', text)
            return [w for w in words if len(w) > 2 and w not in stopwords]

        ing_words = set(extract_food_words(ing_core))
        usda_words = set(extract_food_words(usda_match))

        # Lexical overlap bonus
        if ing_words and usda_words:
            overlap_ratio = len(ing_words & usda_words) / max(len(ing_words), len(usda_words))
            score += overlap_ratio * 25.0

        # Detect "sauce/paste vs base" mismatch (e.g., tahini sauce vs tahini)
        sauce_indicators = ['sauce', 'paste', 'dressing', 'spread']
        ing_is_sauce = any(si in ing_core for si in sauce_indicators)
        usda_is_sauce = any(si in usda_match for si in sauce_indicators)

        if ing_is_sauce != usda_is_sauce:
            score -= 30.0

        # Exact substring match bonus
        ing_clean = re.sub(r'[^a-z\s]', '', ing_core).strip()
        usda_clean = re.sub(r'[^a-z\s]', '', usda_match).strip()

        if ing_clean in usda_clean or usda_clean in ing_clean:
            score += 15.0

        # Clamp score to 0-100 range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 50.0
