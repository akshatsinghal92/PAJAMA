import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize
        ing = ingredient.lower().strip()
        usda = usda_match.lower().strip()

        # Remove gram weights (e.g., "200g", "30g")
        ing = re.sub(r'^\d+\.?\d*\s*g\s*', '', ing)

        # Remove parentheticals from ingredient
        ing = re.sub(r'\([^)]*\)', '', ing)

        # Split on commas - keep main part before comma for ingredient
        ing_parts = ing.split(',')
        ing_main = ing_parts[0].strip()
        ing_qualifiers = ' '.join(p.strip() for p in ing_parts[1:])

        # For USDA, first part is main food, rest are descriptors
        usda_parts = usda.split(',')
        usda_main = usda_parts[0].strip()
        usda_qualifiers = ' '.join(p.strip() for p in usda_parts[1:])

        # Tokenize
        def tokenize(text):
            words = re.findall(r'\b\w+\b', text)
            return [w for w in words if len(w) > 1]

        ing_main_tokens = set(tokenize(ing_main))
        usda_main_tokens = set(tokenize(usda_main))
        ing_qual_tokens = set(tokenize(ing_qualifiers))
        usda_qual_tokens = set(tokenize(usda_qualifiers))

        # Core food identity match using Jaccard similarity
        main_overlap = ing_main_tokens & usda_main_tokens
        main_union = ing_main_tokens | usda_main_tokens

        if not main_union:
            return 0.0

        # Base score from main food token overlap
        main_score = (len(main_overlap) / len(main_union)) * 100

        # Detect critical preparation mismatches
        penalty = 0

        # Raw/uncooked ingredient vs cooked USDA
        ing_has_uncooked = any(w in ing_main for w in ['raw', 'uncooked', 'fresh', 'frozen'])
        usda_has_cooked = 'cooked' in usda_qualifiers or 'cooked' in usda_main
        if ing_has_uncooked and usda_has_cooked:
            penalty += 50
        elif not ing_has_uncooked and not usda_has_cooked:
            # Neither specifies cooking state - check if one is pasta (raw pasta vs cooked pasta)
            if 'pasta' in ing_main and 'cooked' in usda:
                penalty += 50

        # Drained vs with liquid/oil
        ing_has_drained = 'drained' in ing_qualifiers or 'drained' in ing_main
        usda_has_added = any(phrase in usda for phrase in ['with oil', 'with liquid', 'in oil', 'in liquid'])
        if ing_has_drained and usda_has_added:
            penalty += 60

        # Specific form/cut mismatches
        form_words = r'\b(diced|whole|shredded|sliced|minced|paste|sauce|chopped|ground|crushed)\b'
        ing_forms = set(re.findall(form_words, ing))
        usda_forms = set(re.findall(form_words, usda))

        if ing_forms and usda_forms:
            if not (ing_forms & usda_forms):
                # Different forms specified
                penalty += 45
        elif ing_forms and not usda_forms:
            # Ingredient specifies form, USDA is generic
            penalty += 15

        # Specific type mismatch (e.g., "cherry tomatoes" vs just "tomatoes")
        ing_specific_types = set(re.findall(r'\b(cherry|grape|roma|beefsteak|penne|spaghetti|fusilli)\b', ing_main))
        if ing_specific_types and not any(t in usda_main for t in ing_specific_types):
            penalty += 35

        # Bonus for strong lexical matches
        bonus = 0
        for token in ing_main_tokens:
            if len(token) > 3 and token in usda_main:
                bonus += 12

        # Extra bonus for very close main food match
        if len(main_overlap) >= 2 and len(main_overlap) == len(ing_main_tokens):
            bonus += 20

        # Calculate final score
        score = main_score + bonus - penalty

        # Clamp to 0-100 range
        return max(0.0, min(100.0, score))

    except Exception:
        return 0.0
