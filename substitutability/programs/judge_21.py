import re
from collections import Counter


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        ingredient = str(ingredient).lower()
        usda_match = str(usda_match).lower()

        # Remove gram weights and parentheticals
        ingredient = re.sub(r'^\d+g\s*', '', ingredient)
        ingredient = re.sub(r'\([^)]*\)', '', ingredient)

        # Define preservation/form categories with keywords
        preservation_forms = {
            'frozen': ['frozen', 'freeze'],
            'canned': ['canned', 'can'],
            'dried': ['dried', 'dry', 'dehydrated'],
            'fresh': ['fresh', 'raw'],
            'jarred': ['jarred', 'jar'],
            'paste': ['paste'],
            'powder': ['powder', 'powdered', 'ground'],
            'bottled': ['bottled', 'bottle'],
            'pickled': ['pickled'],
            'smoked': ['smoked'],
            'cooked': ['cooked', 'cooked'],
            'uncooked': ['uncooked', 'raw'],
        }

        # State modifiers that indicate processing
        state_modifiers = {
            'liquid_added': ['with oil', 'with sauce', 'with liquid', 'with water', 'in brine', 'in syrup'],
            'liquid_removed': ['drained', 'dried', 'strained'],
            'heated': ['cooked', 'baked', 'roasted', 'fried', 'grilled'],
            'unheated': ['raw', 'uncooked', 'fresh'],
            'thawed': ['thawed', 'defrosted'],
            'sauce_form': ['sauce'],
            'concentrated': ['concentrate', 'concentrated', 'paste'],
            'diluted': ['diluted', 'broth', 'stock'],
            'whole': ['whole'],
            'cut': ['diced', 'chopped', 'sliced', 'shredded', 'minced'],
        }

        # Extract forms from both strings
        ing_forms = set()
        for form, keywords in preservation_forms.items():
            if any(kw in ingredient for kw in keywords):
                ing_forms.add(form)

        usda_forms = set()
        for form, keywords in preservation_forms.items():
            if any(kw in usda_match for kw in keywords):
                usda_forms.add(form)

        # Extract state modifiers
        ing_states = set()
        for state, keywords in state_modifiers.items():
            if any(kw in ingredient for kw in keywords):
                ing_states.add(state)

        usda_states = set()
        for state, keywords in state_modifiers.items():
            if any(kw in usda_match for kw in keywords):
                usda_states.add(state)

        # Base score starts at 60
        score = 60.0

        # Perfect form match bonus
        if ing_forms and usda_forms and ing_forms & usda_forms:
            score += 25.0

        # No explicit form detected - assume fresh/raw compatibility
        if not ing_forms and not usda_forms:
            score += 15.0

        # Penalize form conflicts
        conflicting_forms = [
            ('frozen', 'fresh'),
            ('frozen', 'canned'),
            ('canned', 'fresh'),
            ('dried', 'fresh'),
            ('paste', 'powder'),
        ]
        for f1, f2 in conflicting_forms:
            if (f1 in ing_forms and f2 in usda_forms) or (f2 in ing_forms and f1 in usda_forms):
                score -= 30.0

        # State modifier analysis
        # Reward thawed + frozen compatibility
        if 'thawed' in ing_states and 'frozen' in usda_forms:
            score += 20.0

        # Penalize liquid_added vs liquid_removed conflict
        if ('liquid_added' in usda_states and 'liquid_removed' in ing_states):
            score -= 35.0
        if ('liquid_removed' in usda_states and 'liquid_added' in ing_states):
            score -= 35.0

        # Penalize heated vs unheated mismatch
        if ('heated' in ing_states and 'unheated' in usda_states):
            score -= 25.0
        if ('unheated' in ing_states and 'heated' in usda_states):
            score -= 25.0

        # Penalize sauce vs paste/base mismatch
        if 'sauce_form' in ing_states and 'concentrated' in usda_states:
            score -= 20.0
        if 'concentrated' in ing_states and 'sauce_form' in usda_states:
            score -= 20.0

        # Bonus for matching cut types
        if 'cut' in ing_states and 'cut' in usda_states:
            score += 10.0

        # Token overlap as tiebreaker
        ing_tokens = set(re.findall(r'\b\w+\b', ingredient))
        usda_tokens = set(re.findall(r'\b\w+\b', usda_match))

        # Remove common stopwords
        stopwords = {'the', 'a', 'an', 'and', 'or', 'with', 'from', 'to', 'of', 'in', 'on'}
        ing_tokens -= stopwords
        usda_tokens -= stopwords

        if ing_tokens and usda_tokens:
            overlap = len(ing_tokens & usda_tokens) / max(len(ing_tokens), len(usda_tokens))
            score += overlap * 10.0

        # Clamp score to 0-100 range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 50.0
