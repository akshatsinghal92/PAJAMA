import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).strip()
        usda_match = str(usda_match).strip()

        if not ingredient or not usda_match:
            return 0.0

        # Normalize to lowercase
        ing_lower = ingredient.lower()
        usda_lower = usda_match.lower()

        # Remove gram weight prefix (e.g., "200g ")
        ing_lower = re.sub(r'^\d+g?\s+', '', ing_lower)

        # Remove parentheticals from ingredient
        ing_clean = re.sub(r'\([^)]*\)', '', ing_lower).strip()

        # Split on commas to separate main ingredient from descriptors
        ing_parts = [p.strip() for p in ing_clean.split(',')]
        usda_parts = [p.strip() for p in usda_lower.split(',')]

        ing_main = ing_parts[0] if ing_parts else ""
        ing_descriptors = set(ing_parts[1:]) if len(ing_parts) > 1 else set()

        usda_main = usda_parts[0] if usda_parts else ""
        usda_descriptors = set(usda_parts[1:]) if len(usda_parts) > 1 else set()

        # Extract tokens for role matching
        ing_tokens = set(re.findall(r'\b\w+\b', ing_main))
        usda_tokens = set(re.findall(r'\b\w+\b', usda_main))

        # Core ingredient overlap (Jaccard similarity)
        common_tokens = ing_tokens & usda_tokens
        all_tokens = ing_tokens | usda_tokens

        if not all_tokens:
            return 0.0

        base_score = (len(common_tokens) / len(all_tokens)) * 100

        # Define culinary role categories and their keywords
        role_keywords = {
            'fat': ['oil', 'butter', 'lard', 'fat', 'margarine', 'shortening'],
            'aromatic': ['garlic', 'onion', 'ginger', 'shallot', 'leek', 'celery'],
            'acid': ['vinegar', 'lemon', 'lime', 'citrus', 'wine'],
            'sweetener': ['sugar', 'honey', 'syrup', 'molasses', 'agave'],
            'binder': ['egg', 'flour', 'starch', 'gelatin', 'xanthan'],
            'thickener': ['flour', 'cornstarch', 'starch', 'roux', 'paste'],
            'seasoning': ['salt', 'pepper', 'spice', 'herb', 'seasoning'],
            'sauce': ['sauce', 'paste', 'spread', 'dressing', 'condiment'],
            'protein': ['chicken', 'beef', 'pork', 'fish', 'tofu', 'bean', 'lentil'],
            'grain': ['rice', 'pasta', 'noodle', 'quinoa', 'barley', 'wheat'],
            'vegetable': ['carrot', 'potato', 'tomato', 'pepper', 'cabbage', 'bean', 'pea']
        }

        # Identify roles
        ing_roles = set()
        usda_roles = set()

        for role, keywords in role_keywords.items():
            if any(kw in ing_lower for kw in keywords):
                ing_roles.add(role)
            if any(kw in usda_lower for kw in keywords):
                usda_roles.add(role)

        # Reward role alignment
        if ing_roles and usda_roles:
            role_overlap = len(ing_roles & usda_roles)
            role_union = len(ing_roles | usda_roles)
            role_score = (role_overlap / role_union) * 20
            base_score += role_score
        elif ing_roles == usda_roles:  # Both empty is neutral
            pass
        else:  # One has roles, other doesn't
            base_score *= 0.8

        # State mismatch penalties
        ing_states = set()
        usda_states = set()

        # Extract preparation states
        state_patterns = {
            'raw': r'\b(raw|fresh|uncooked)\b',
            'cooked': r'\b(cooked|baked|fried|grilled|roasted|boiled|steamed)\b',
            'frozen': r'\b(frozen)\b',
            'canned': r'\b(canned|tinned)\b',
            'dried': r'\b(dried|dehydrated)\b',
            'ground': r'\b(ground|minced|chopped|diced|shredded|grated)\b',
            'whole': r'\b(whole|intact)\b',
            'drained': r'\b(drained|rinsed)\b',
            'with_oil': r'\b(with oil|in oil|oiled)\b',
            'with_liquid': r'\b(with liquid|in liquid|in juice|in sauce|in syrup)\b',
            'thawed': r'\b(thawed|defrosted)\b',
            'paste': r'\b(paste)\b',
            'sauce': r'\b(sauce)\b'
        }

        for state, pattern in state_patterns.items():
            if re.search(pattern, ing_lower):
                ing_states.add(state)
            if re.search(pattern, usda_lower):
                usda_states.add(state)

        # Critical incompatibilities (culinary role changes)
        critical_conflicts = [
            ({'raw'}, {'cooked'}),
            ({'frozen'}, {'cooked'}),
            ({'drained'}, {'with_oil'}),
            ({'drained'}, {'with_liquid'}),
            ({'paste'}, set()),  # Paste in ing but not in usda
            ({'sauce'}, set()),  # Sauce in ing but not in usda
        ]

        for ing_conflict, usda_conflict in critical_conflicts:
            if ing_conflict.issubset(ing_states) and usda_conflict == (usda_states & {'raw', 'cooked', 'with_oil', 'with_liquid', 'paste', 'sauce'}):
                base_score *= 0.3
                break
            if usda_conflict.issubset(usda_states) and ing_conflict == (ing_states & {'raw', 'cooked', 'with_oil', 'with_liquid', 'paste', 'sauce'}):
                base_score *= 0.3
                break

        # Check for "pasta cooked" problem: raw pasta vs cooked pasta
        if 'pasta' in ing_lower or 'noodle' in ing_lower:
            ing_has_cooked = 'cooked' in ing_lower
            usda_has_cooked = 'cooked' in usda_lower
            if ing_has_cooked != usda_has_cooked:
                base_score *= 0.2

        # Tahini vs tahini sauce problem
        if 'tahini' in ing_lower and 'tahini' in usda_lower:
            ing_has_sauce = 'sauce' in ing_lower
            usda_has_sauce = 'sauce' in usda_lower
            if ing_has_sauce != usda_has_sauce:
                base_score *= 0.3

        # Drained vs with oil/liquid
        if 'drained' in ing_lower:
            if 'with oil' in usda_lower or 'in oil' in usda_lower or 'cooked with oil' in usda_lower:
                base_score *= 0.2

        # General state alignment bonus
        if ing_states and usda_states:
            state_match_count = len(ing_states & usda_states)
            if state_match_count > 0:
                base_score *= 1.1

        # Bonus for very similar strings (simple exact matches)
        ing_words = ing_main.split()
        usda_words = usda_main.split()

        if ing_words and usda_words:
            word_overlap = len(set(ing_words) & set(usda_words))
            word_union = len(set(ing_words) | set(usda_words))
            if word_union > 0:
                word_sim = word_overlap / word_union
                if word_sim > 0.8:
                    base_score *= 1.2

        # Cap score at 100
        return min(base_score, 100.0)

    except Exception:
        return 0.0
