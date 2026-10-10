import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).lower()
        usda_match = str(usda_match).lower()

        # Remove gram weights like "300g", "40g"
        ingredient = re.sub(r'^\d+g?\s*', '', ingredient)

        # Extract preparation states and form descriptors
        prep_states = {
            'cooked': ['cooked', 'boiled', 'steamed', 'baked', 'fried', 'roasted', 'grilled'],
            'raw': ['raw', 'fresh', 'uncooked'],
            'canned': ['canned', 'tinned'],
            'frozen': ['frozen'],
            'dried': ['dried', 'dehydrated'],
            'ground': ['ground', 'minced', 'powdered'],
            'whole': ['whole', 'entire'],
            'diced': ['diced', 'chopped', 'cubed'],
            'shredded': ['shredded', 'grated'],
            'with_liquid': ['with oil', 'with water', 'with liquid', 'with sauce', 'in brine'],
            'drained': ['drained', 'without liquid', 'dry'],
            'paste': ['paste'],
            'sauce': ['sauce'],
            'oil': ['oil'],
            'thawed': ['thawed']
        }

        # Role descriptors that indicate culinary function
        role_keywords = {
            'fat': ['oil', 'butter', 'lard', 'shortening', 'fat'],
            'seasoning': ['salt', 'pepper', 'spice', 'herb', 'seasoning'],
            'acid': ['vinegar', 'lemon', 'lime', 'citrus'],
            'sweetener': ['sugar', 'honey', 'syrup', 'sweetener'],
            'thickener': ['flour', 'starch', 'cornstarch'],
            'protein': ['chicken', 'beef', 'pork', 'fish', 'tofu', 'egg', 'meat'],
            'grain': ['pasta', 'rice', 'bread', 'cereal', 'grain'],
            'vegetable': ['tomato', 'onion', 'garlic', 'carrot', 'cabbage', 'bean', 'pea'],
            'condiment': ['sauce', 'paste', 'ketchup', 'mustard', 'mayo']
        }

        def extract_states(text):
            found_states = {}
            for state_category, keywords in prep_states.items():
                for kw in keywords:
                    if kw in text:
                        found_states[state_category] = True
                        break
            return found_states

        def extract_roles(text):
            found_roles = set()
            for role_category, keywords in role_keywords.items():
                for kw in keywords:
                    if kw in text:
                        found_roles.add(role_category)
            return found_roles

        def extract_core_food(text):
            # Remove common modifiers to get core food item
            text = re.sub(r'\b(fresh|frozen|dried|canned|raw|cooked|chopped|diced|shredded|ground|whole)\b', '', text)
            text = re.sub(r'\(.*?\)', '', text)  # Remove parentheticals
            text = re.sub(r',.*$', '', text)  # Remove comma-separated descriptors
            text = text.strip()
            return text

        ing_states = extract_states(ingredient)
        usda_states = extract_states(usda_match)
        ing_roles = extract_roles(ingredient)
        usda_roles = extract_roles(usda_match)
        ing_core = extract_core_food(ingredient)
        usda_core = extract_core_food(usda_match)

        # Base score starts at 50
        score = 50.0

        # Role compatibility: reward if roles overlap
        if ing_roles and usda_roles:
            role_overlap = len(ing_roles & usda_roles) / max(len(ing_roles), len(usda_roles))
            score += role_overlap * 30
        elif not ing_roles and not usda_roles:
            # Both have no specific role markers - neutral
            score += 10

        # Core food similarity using character overlap
        if ing_core and usda_core:
            # Calculate character-level similarity
            ing_chars = set(ing_core.replace(' ', ''))
            usda_chars = set(usda_core.replace(' ', ''))
            if ing_chars and usda_chars:
                char_overlap = len(ing_chars & usda_chars) / max(len(ing_chars), len(usda_chars))
                score += char_overlap * 25

            # Substring matching bonus
            if ing_core in usda_core or usda_core in ing_core:
                score += 15

        # Critical state mismatch penalties
        critical_mismatches = 0

        # Cooked vs raw is critical
        if ing_states.get('cooked') and usda_states.get('raw'):
            critical_mismatches += 1
        if ing_states.get('raw') and usda_states.get('cooked'):
            critical_mismatches += 1

        # Drained vs with liquid is critical
        if ing_states.get('drained') and usda_states.get('with_liquid'):
            critical_mismatches += 1
        if ing_states.get('with_liquid') and usda_states.get('drained'):
            critical_mismatches += 1

        # Sauce/paste form mismatches
        if ing_states.get('sauce') and not usda_states.get('sauce'):
            if ing_states.get('paste') or 'paste' in usda_match:
                critical_mismatches += 0.5  # Less severe
            else:
                critical_mismatches += 1
        if ing_states.get('paste') and usda_states.get('sauce'):
            critical_mismatches += 0.5

        # Apply penalties for critical mismatches
        score -= critical_mismatches * 35

        # Bonus for state agreement on critical dimensions
        state_agreements = 0
        if ing_states.get('cooked') and usda_states.get('cooked'):
            state_agreements += 1
        if ing_states.get('raw') and usda_states.get('raw'):
            state_agreements += 1
        if ing_states.get('canned') and usda_states.get('canned'):
            state_agreements += 1
        if ing_states.get('drained') and usda_states.get('drained'):
            state_agreements += 1

        score += state_agreements * 8

        # Penalize if USDA has extra preparation that changes function
        if usda_states.get('with_liquid') and not ing_states.get('with_liquid'):
            if not ing_states.get('canned'):  # Unless both are canned
                score -= 20

        # Physical cut differences (shredded, diced) are usually okay if roles match
        minor_prep_diff = 0
        if (ing_states.get('shredded') or ing_states.get('diced')) != (usda_states.get('shredded') or usda_states.get('diced')):
            if ing_roles & usda_roles:  # Roles match, so cut is minor
                minor_prep_diff = -5
            else:
                minor_prep_diff = -15
        score += minor_prep_diff

        # Word overlap bonus (excluding common words)
        common_words = {'with', 'from', 'in', 'the', 'a', 'an', 'or', 'and', 'of'}
        ing_words = set(re.findall(r'\b[a-z]{3,}\b', ingredient)) - common_words
        usda_words = set(re.findall(r'\b[a-z]{3,}\b', usda_match)) - common_words

        if ing_words and usda_words:
            word_overlap = len(ing_words & usda_words) / len(ing_words | usda_words)
            score += word_overlap * 20

        # Clamp score to 0-100 range
        score = max(0.0, min(100.0, score))

        return round(score, 2)

    except Exception:
        return 50.0
