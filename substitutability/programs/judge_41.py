import re

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Noise words to ignore during token extraction
        ignore_words = {
            'to', 'taste', 'from', 'tube', 'the', 'a', 'an',
            'chopped', 'diced', 'sliced', 'minced', 'crushed', 'shredded',
            'thawed', 'frozen', 'defrosted', 'optional'
        }

        def extract_tokens(text):
            text = text.lower()
            # Remove gram weights (e.g., "300g", "40g")
            text = re.sub(r'\b\d+g\b', '', text)
            # Remove parenthetical content
            text = re.sub(r'\([^)]*\)', '', text)
            # Remove punctuation
            text = re.sub(r'[,;:.]', ' ', text)
            # Split and filter noise words
            tokens = text.split()
            return set(t for t in tokens if t and t not in ignore_words)

        ingredient_tokens = extract_tokens(ingredient)
        usda_tokens = extract_tokens(usda_match)

        if not ingredient_tokens or not usda_tokens:
            return 0.0

        # Calculate Jaccard similarity (intersection over union)
        overlap = ingredient_tokens & usda_tokens
        union = ingredient_tokens | usda_tokens

        if not union:
            return 0.0

        jaccard_score = len(overlap) / len(union)
        base_score = jaccard_score * 100

        # Apply penalties for specific mismatches that indicate non-substitutability
        ingredient_lower = ingredient.lower()
        usda_lower = usda_match.lower()

        # Specific pasta shape lost
        if 'penne' in ingredient_lower and 'penne' not in usda_lower:
            base_score *= 0.2

        # Specific tomato type lost
        if 'cherry' in ingredient_lower and 'cherry' not in usda_lower:
            base_score *= 0.2

        # Whole form vs cooked mismatch
        if 'whole' in ingredient_lower and 'cooked' in usda_lower:
            base_score *= 0.3

        # Sauce vs raw ingredient mismatch
        if 'sauce' in ingredient_lower and 'sauce' not in usda_lower:
            base_score *= 0.2

        # Drained but USDA has oil
        if 'drained' in ingredient_lower and 'oil' in usda_lower:
            base_score *= 0.1

        # Diced form vs generic cooked
        if 'diced' in ingredient_lower and 'cooked' in usda_lower and 'diced' not in usda_lower:
            base_score *= 0.2

        return base_score

    except Exception:
        return 0.0
