import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        ingredient_lower = ingredient.lower()
        usda_lower = usda_match.lower()

        # Define form/preservation categories with keywords
        form_keywords = {
            'frozen': ['frozen', 'freeze'],
            'canned': ['canned', 'can,'],
            'dried': ['dried', 'dry', 'dehydrated'],
            'fresh': ['fresh', 'raw'],
            'jarred': ['jarred', 'jar'],
            'paste': ['paste', 'puree', 'pureed'],
            'powder': ['powder', 'powdered', 'ground'],
            'cooked': ['cooked', 'prepared', 'ready'],
            'liquid': ['sauce', 'broth', 'stock', 'juice', 'liquid', 'syrup'],
            'drained': ['drained', 'no liquid'],
            'with_liquid': ['with oil', 'in oil', 'in sauce', 'in syrup', 'in water', 'with liquid'],
            'thawed': ['thawed', 'defrosted'],
            'uncooked': ['uncooked', 'raw', 'unprepared'],
            'whole': ['whole', 'uncut'],
            'processed': ['diced', 'chopped', 'sliced', 'shredded', 'minced', 'crushed']
        }

        # Extract forms from both strings
        def extract_forms(text):
            found = set()
            for category, keywords in form_keywords.items():
                for kw in keywords:
                    if kw in text:
                        found.add(category)
            return found

        ingredient_forms = extract_forms(ingredient_lower)
        usda_forms = extract_forms(usda_lower)

        # Start with base score
        score = 70.0

        # Check for exact form matches (reward)
        common_forms = ingredient_forms & usda_forms
        score += len(common_forms) * 8.0

        # Define incompatible form pairs (heavy penalties)
        incompatible_pairs = [
            ('frozen', 'fresh'),
            ('cooked', 'uncooked'),
            ('drained', 'with_liquid'),
            ('powder', 'fresh'),
            ('dried', 'canned'),
            ('paste', 'whole'),
            ('liquid', 'powder'),
        ]

        # Check for incompatibilities
        penalty_multiplier = 1.0
        for form_a, form_b in incompatible_pairs:
            if (form_a in ingredient_forms and form_b in usda_forms) or \
               (form_b in ingredient_forms and form_a in usda_forms):
                penalty_multiplier *= 0.55

        # Special handling for recoverable forms (frozen->thawed is ok)
        if 'frozen' in ingredient_forms and 'thawed' in ingredient_forms:
            if 'frozen' in usda_forms:
                score += 15.0

        # Penalize if ingredient specifies drained but USDA has liquid
        if 'drained' in ingredient_forms and 'with_liquid' in usda_forms:
            penalty_multiplier *= 0.4

        # Reward if both have same preservation method
        preservation_methods = {'frozen', 'canned', 'dried', 'fresh', 'jarred'}
        ing_preservation = ingredient_forms & preservation_methods
        usda_preservation = usda_forms & preservation_methods

        if ing_preservation and usda_preservation:
            if ing_preservation == usda_preservation:
                score += 20.0
            else:
                penalty_multiplier *= 0.65

        # Check cooking state alignment
        if 'cooked' in ingredient_forms and 'uncooked' in usda_forms:
            penalty_multiplier *= 0.45
        elif 'uncooked' in ingredient_forms and 'cooked' in usda_forms:
            penalty_multiplier *= 0.45

        # Detect sauce vs base ingredient mismatch
        if 'sauce' in ingredient_lower and 'sauce' not in usda_lower:
            if not any(x in usda_lower for x in ['prepared', 'ready', 'with']):
                penalty_multiplier *= 0.5

        # Apply penalty multiplier
        score *= penalty_multiplier

        # Bonus for minimal differences when forms are similar
        if len(ingredient_forms) > 0 and len(usda_forms) > 0:
            overlap_ratio = len(common_forms) / max(len(ingredient_forms), len(usda_forms))
            if overlap_ratio > 0.6:
                score += 10.0 * overlap_ratio

        # Clamp to 0-100 range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 50.0
