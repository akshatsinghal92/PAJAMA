import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        ingredient = str(ingredient).lower()
        usda_match = str(usda_match).lower()

        # Remove gram weights
        ingredient = re.sub(r'^\d+g?\s*', '', ingredient)

        # Extract core words (remove punctuation, split on whitespace/commas)
        def tokenize(text):
            tokens = re.findall(r'\b[a-z]+\b', text)
            return set(tokens)

        ing_tokens = tokenize(ingredient)
        usda_tokens = tokenize(usda_match)

        # Define additive/processing keywords that signal non-substitutability
        additives = {
            'oil', 'sauce', 'seasoned', 'sweetened', 'flavored', 'breaded',
            'battered', 'glazed', 'marinated', 'pickled', 'smoked', 'cured',
            'salted', 'sugared', 'spiced', 'herbed', 'buttered', 'creamed',
            'frosted', 'iced', 'candied', 'honeyed', 'syruped', 'caramelized'
        }

        processing_terms = {
            'cooked', 'fried', 'baked', 'roasted', 'grilled', 'broiled',
            'steamed', 'boiled', 'sauteed', 'toasted', 'blanched', 'seared'
        }

        compound_indicators = {
            'blend', 'mix', 'mixture', 'prepared', 'seasoning', 'paste',
            'powder', 'spread', 'dressing', 'marinade'
        }

        # Start with high base score
        score = 100.0

        # Check for additives in USDA that aren't in ingredient
        usda_additives = usda_tokens & additives
        ing_additives = ing_tokens & additives

        unexpected_additives = usda_additives - ing_additives

        # Heavy penalty for unexpected additives
        score -= len(unexpected_additives) * 35

        # Check for processing state mismatches
        usda_processing = usda_tokens & processing_terms
        ing_processing = ing_tokens & processing_terms

        # If USDA has processing that ingredient doesn't mention
        unexpected_processing = usda_processing - ing_processing

        # Special case: if ingredient says "drained" or "raw", cooked is bad
        if 'drained' in ing_tokens or 'raw' in ing_tokens:
            if 'cooked' in usda_tokens:
                score -= 40

        # Otherwise, unexpected processing is moderately bad
        score -= len(unexpected_processing) * 25

        # Check for compound/prepared indicators
        usda_compounds = usda_tokens & compound_indicators
        ing_compounds = ing_tokens & compound_indicators

        # If ingredient is simple but USDA is compound, penalize
        if len(usda_compounds) > len(ing_compounds):
            score -= (len(usda_compounds) - len(ing_compounds)) * 20

        # Bonus for exact or near-exact matches
        if ingredient.strip() == usda_match.strip():
            score += 30

        # Check word overlap ratio
        if len(usda_tokens) > 0:
            overlap = len(ing_tokens & usda_tokens) / len(usda_tokens)
            score += overlap * 15

        # Check for "with" phrases in USDA (e.g., "with oil", "with sauce")
        if re.search(r'\bwith\b', usda_match):
            # Extract what comes after "with"
            with_match = re.search(r'with\s+(\w+)', usda_match)
            if with_match:
                added_component = with_match.group(1)
                # If ingredient doesn't mention this component, big penalty
                if added_component not in ingredient:
                    score -= 45

        # Look for specific problematic patterns
        # "X sauce" vs plain "X" - very different
        if 'sauce' in usda_tokens and 'sauce' not in ing_tokens:
            score -= 35

        # Normalize to 0-100 range
        score = max(0, min(100, score))

        return score

    except Exception:
        return 50.0
