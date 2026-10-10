import re
from collections import Counter


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize to lowercase
        ing_lower = ingredient.lower()
        usda_lower = usda_match.lower()

        # Remove gram weights like "300g", "30g"
        ing_lower = re.sub(r'^\d+g?\s*', '', ing_lower)

        # Remove parentheticals
        ing_lower = re.sub(r'\([^)]*\)', '', ing_lower)
        usda_lower = re.sub(r'\([^)]*\)', '', usda_lower)

        # Split on commas to isolate primary food vs descriptors
        ing_parts = [p.strip() for p in ing_lower.split(',')]
        usda_parts = [p.strip() for p in usda_lower.split(',')]

        ing_primary = ing_parts[0] if ing_parts else ''
        usda_primary = usda_parts[0] if usda_parts else ''

        # Tokenize into words, removing common stop words
        stop_words = {'the', 'a', 'an', 'from', 'of', 'for', 'with', 'in', 'on', 'at'}

        def tokenize(text):
            tokens = re.findall(r'\b\w+\b', text)
            return [t for t in tokens if t not in stop_words and len(t) > 1]

        ing_tokens = set(tokenize(ing_primary))
        usda_tokens = set(tokenize(usda_primary))

        # Base score from token overlap (Jaccard similarity scaled)
        if not ing_tokens or not usda_tokens:
            return 0.0

        intersection = ing_tokens & usda_tokens
        union = ing_tokens | usda_tokens

        base_score = len(intersection) / len(union) * 100

        # Bonus for exact head noun match (first meaningful noun)
        # Extract likely head nouns (non-prep words)
        prep_words = {'frozen', 'fresh', 'canned', 'dried', 'cooked', 'raw', 'uncooked',
                      'thawed', 'drained', 'shredded', 'diced', 'whole', 'ground',
                      'chopped', 'sliced', 'minced', 'crushed'}

        ing_nouns = [t for t in tokenize(ing_primary) if t not in prep_words]
        usda_nouns = [t for t in tokenize(usda_primary) if t not in prep_words]

        if ing_nouns and usda_nouns:
            # Compare first 2 nouns for core identity
            ing_core = set(ing_nouns[:2])
            usda_core = set(usda_nouns[:2])

            if ing_core & usda_core:
                base_score += 20

        # Check for state/preparation conflicts
        # These indicate different forms that are NOT substitutable
        conflict_patterns = [
            ('cooked', 'raw'),
            ('cooked', 'uncooked'),
            ('raw', 'cooked'),
            ('sauce', 'paste'),
            ('sauce', 'seed'),
            ('oil', 'butter'),
            ('paste', 'sauce'),
        ]

        ing_all = ' '.join(ing_parts)
        usda_all = ' '.join(usda_parts)

        # Penalize if one has "cooked" and the other has "raw/uncooked"
        ing_has_cooked = 'cooked' in ing_all
        usda_has_cooked = 'cooked' in usda_all
        ing_has_raw = 'raw' in ing_all or 'uncooked' in ing_all
        usda_has_raw = 'raw' in usda_all or 'uncooked' in usda_all

        if (ing_has_cooked and usda_has_raw) or (ing_has_raw and usda_has_cooked):
            base_score *= 0.3

        # Penalize if USDA has "with oil" or added ingredients not in ingredient
        if 'with oil' in usda_all and 'oil' not in ing_all:
            base_score *= 0.4

        if 'with butter' in usda_all and 'butter' not in ing_all:
            base_score *= 0.4

        # Penalize sauce/tahini mismatches
        ing_has_sauce = 'sauce' in ing_all
        usda_has_sauce = 'sauce' in usda_all

        if ing_has_sauce != usda_has_sauce:
            base_score *= 0.5

        # Penalize form mismatches for specific cases
        form_words = ['whole', 'diced', 'crushed', 'ground', 'shredded', 'sliced']
        ing_forms = [w for w in form_words if w in ing_all]
        usda_forms = [w for w in form_words if w in usda_all]

        # If ingredient specifies a form but USDA doesn't match, penalize
        if ing_forms and not any(f in usda_all for f in ing_forms):
            if usda_forms:  # USDA has a different form
                base_score *= 0.5

        # Clamp score to 0-100 range
        return max(0.0, min(100.0, base_score))

    except Exception:
        return 0.0
