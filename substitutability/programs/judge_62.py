import re
from collections import Counter


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).lower().strip()
        usda_match = str(usda_match).lower().strip()

        # Remove gram weights like "300g", "30g", etc.
        ingredient = re.sub(r'^\d+g?\s+', '', ingredient)
        ingredient = re.sub(r'\(\s*from\s+[^)]+\)', '', ingredient)
        ingredient = re.sub(r'\s*,\s*[^,]*$', '', ingredient)

        # Extract tokens
        def tokenize(text):
            tokens = re.findall(r'\b[a-z]+\b', text)
            return set(tokens) - {'and', 'or', 'the', 'a', 'an', 'with', 'from'}

        ing_tokens = tokenize(ingredient)
        usda_tokens = tokenize(usda_match)

        # Define additive/processing terms that increase complexity
        additive_terms = {
            'oil', 'oils', 'butter', 'fried', 'breaded', 'battered',
            'sauce', 'sauces', 'seasoned', 'spiced', 'flavored', 'sweetened',
            'salted', 'sugared', 'glazed', 'marinated', 'prepared',
            'seasoning', 'blend', 'mix', 'mixed', 'compound',
            'enriched', 'fortified', 'modified', 'processed',
            'syrup', 'honey', 'sugar', 'salt', 'sodium',
            'cream', 'creamed', 'creamy', 'buttered',
            'gravy', 'dressing', 'coating', 'breading'
        }

        # State/preparation terms
        state_terms = {
            'cooked', 'raw', 'frozen', 'fresh', 'dried', 'canned',
            'roasted', 'grilled', 'baked', 'boiled', 'steamed',
            'thawed', 'drained', 'rinsed'
        }

        # Start with high base score
        score = 100.0

        # Additives in USDA but not in ingredient = penalty
        usda_additives = usda_tokens & additive_terms
        ing_additives = ing_tokens & additive_terms
        added_complexity = usda_additives - ing_additives

        # Heavy penalty for each additive the USDA entry introduces
        score -= len(added_complexity) * 25.0

        # Additional penalty for specific high-impact additives
        high_impact = {'sauce', 'sauces', 'oil', 'fried', 'breaded', 'seasoned'}
        critical_additions = added_complexity & high_impact
        score -= len(critical_additions) * 15.0

        # State mismatch penalty
        usda_states = usda_tokens & state_terms
        ing_states = ing_tokens & state_terms

        # If ingredient specifies a state but USDA has different state
        if ing_states and usda_states:
            if not (ing_states & usda_states):
                score -= 30.0
        # If USDA adds a state change the ingredient didn't mention
        elif not ing_states and usda_states:
            unexpected_states = usda_states - {'raw', 'fresh'}
            if unexpected_states:
                score -= 20.0

        # Reward core ingredient overlap
        core_overlap = len(ing_tokens & usda_tokens)
        if core_overlap > 0:
            score += core_overlap * 5.0

        # Penalty if USDA is significantly more complex
        usda_complexity = len(usda_tokens & additive_terms)
        ing_complexity = len(ing_tokens & additive_terms)

        if usda_complexity > ing_complexity + 1:
            score -= 15.0

        # Bonus for simple, plain matches
        if len(usda_additives) == 0 and len(ing_additives) == 0:
            score += 10.0

        # Check for exact semantic match patterns
        ing_clean = re.sub(r'\s+', ' ', ingredient).strip()
        usda_clean = re.sub(r'\s+', ' ', usda_match).strip()

        # If core terms appear in both with no additives, boost
        if core_overlap >= 2 and len(added_complexity) == 0:
            score += 15.0

        # Penalize if USDA has compound descriptors ingredient lacks
        usda_descriptor_count = len(usda_clean.split(','))
        if usda_descriptor_count > 2 and len(added_complexity) > 0:
            score -= 10.0

        # Normalize to reasonable range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 50.0
