import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        ingredient = ingredient.lower().strip()
        usda_match = usda_match.lower().strip()

        # Remove gram weights like "300g", "30g "
        ingredient = re.sub(r'^\d+g\s*', '', ingredient)

        # Processing/additive keywords that indicate added components
        additive_keywords = {
            'sauce', 'seasoned', 'sweetened', 'flavored', 'breaded',
            'marinated', 'glazed', 'spiced', 'salted', 'sugared',
            'buttered', 'creamed', 'prepared', 'mixed', 'blend'
        }

        # Cooking state keywords
        cooking_states = {
            'cooked', 'fried', 'baked', 'roasted', 'grilled',
            'boiled', 'steamed', 'sauteed', 'pan-fried'
        }

        # Oil/fat additions
        oil_keywords = {
            'with oil', 'in oil', 'with butter', 'with fat',
            'oil-packed', 'butter sauce'
        }

        # Start with base score
        score = 100.0

        # Tokenize both strings
        ing_tokens = set(re.findall(r'\b\w+\b', ingredient))
        usda_tokens = set(re.findall(r'\b\w+\b', usda_match))

        # Check for additive keywords in USDA that aren't in ingredient
        usda_additives = set()
        ing_additives = set()

        for keyword in additive_keywords:
            keyword_parts = keyword.split()
            if all(part in usda_tokens for part in keyword_parts):
                usda_additives.add(keyword)
            if all(part in ing_tokens for part in keyword_parts):
                ing_additives.add(keyword)

        # Penalize if USDA has additives ingredient doesn't
        new_additives = usda_additives - ing_additives
        score -= len(new_additives) * 30.0

        # Check for oil/fat additions in USDA
        for oil_phrase in oil_keywords:
            if oil_phrase in usda_match and oil_phrase not in ingredient:
                score -= 35.0

        # Check cooking state mismatches
        usda_cooking = cooking_states & usda_tokens
        ing_cooking = cooking_states & ing_tokens

        # Special case: ingredient is "drained" but USDA is "cooked"
        if 'drained' in ing_tokens and usda_cooking:
            score -= 40.0
        elif usda_cooking and not ing_cooking:
            # USDA is cooked but ingredient isn't
            score -= 25.0

        # Check for compound vs simple mismatches
        # If ingredient is simple (e.g., "tahini") but USDA is compound (e.g., "tahini sauce")
        ing_words = ingredient.split()
        usda_words = usda_match.split()

        # Count meaningful words (not prep/state words)
        stop_words = {'raw', 'fresh', 'frozen', 'canned', 'dried', 'whole',
                      'ground', 'chopped', 'sliced', 'diced', 'shredded',
                      'thawed', 'drained', 'from', 'tube'}

        ing_meaningful = [w for w in ing_tokens if w not in stop_words and len(w) > 2]
        usda_meaningful = [w for w in usda_tokens if w not in stop_words and len(w) > 2]

        # If USDA has significantly more meaningful words, likely added complexity
        word_diff = len(usda_meaningful) - len(ing_meaningful)
        if word_diff > 2:
            score -= word_diff * 8.0

        # Reward high overlap in core food terms
        if ing_meaningful and usda_meaningful:
            overlap = len(set(ing_meaningful) & set(usda_meaningful))
            overlap_ratio = overlap / max(len(ing_meaningful), len(usda_meaningful))
            score += overlap_ratio * 20.0

        # Bonus for very close matches (minimal difference)
        if ingredient.replace(',', '').strip() == usda_match.replace(',', '').strip():
            score += 30.0

        # Check for "table" salt - this is acceptable
        if 'salt' in ingredient and 'salt, table' in usda_match:
            score += 10.0

        # Clamp score to 0-100 range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 50.0
