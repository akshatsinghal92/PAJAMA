import re
import math

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ing = ingredient.lower().strip()
        usda = usda_match.lower().strip()

        ing = re.sub(r'\b\d+g?\b', '', ing).strip()
        ing = re.sub(r'\([^)]*\)', '', ing).strip()
        usda = re.sub(r'\([^)]*\)', '', usda).strip()

        score = 80.0

        additive_signals = [
            'oil', 'salted', 'salt', 'sugar', 'sweetened', 'sauce', 'sauced',
            'seasoned', 'seasoning', 'spiced', 'flavored', 'breaded', 'fried',
            'glazed', 'marinated', 'butter', 'buttered', 'cream', 'creamed',
            'syrup', 'honey', 'garlic', 'onion', 'pepper', 'herb', 'spice'
        ]

        usda_parts = [p.strip() for p in usda.split(',')]
        ing_parts = [p.strip() for p in ing.split(',')]

        usda_additive_count = 0
        ing_additive_count = 0

        for term in additive_signals:
            if term in usda:
                usda_additive_count += 1
            if term in ing:
                ing_additive_count += 1

        additive_excess = usda_additive_count - ing_additive_count
        if additive_excess > 0:
            score -= additive_excess * 22.0

        if len(usda_parts) > 1:
            secondary_descriptors = ' '.join(usda_parts[1:])
            secondary_additive_count = sum(1 for term in additive_signals if term in secondary_descriptors)
            score -= secondary_additive_count * 8.0

        sauce_mismatch = ('sauce' in ing) != ('sauce' in usda)
        if sauce_mismatch:
            score -= 40.0

        usda_processed = any(word in usda for word in ['cooked', 'fried', 'baked', 'roasted'])
        ing_unprocessed = 'raw' in ing or ('pasta' in ing and 'cooked' not in ing)

        if usda_processed and ing_unprocessed:
            score -= 28.0

        compound_words = ['with', 'and', 'plus']
        usda_compound_count = sum(1 for word in compound_words if word in usda)
        ing_compound_count = sum(1 for word in compound_words if word in ing)

        if usda_compound_count > ing_compound_count:
            score -= (usda_compound_count - ing_compound_count) * 18.0

        ing_tokens = set(re.findall(r'[a-z]{3,}', ing))
        usda_tokens = set(re.findall(r'[a-z]{3,}', usda))

        if ing_tokens:
            overlap = len(ing_tokens & usda_tokens)
            overlap_ratio = overlap / len(ing_tokens)
            score += overlap_ratio * 25.0

        usda_len = len(usda)
        if usda_len > 50:
            extra_chars = usda_len - 50
            score -= math.log1p(extra_chars) * 2.0

        score = max(0.0, min(100.0, score))

        return round(score, 2)

    except Exception:
        return 35.0
