import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).lower()
        usda_match = str(usda_match).lower()

        # Remove gram weights like "200g", "30g"
        ingredient = re.sub(r'^\d+g?\s*', '', ingredient)

        # Form taxonomy with compatibility scores
        form_groups = {
            'fresh': {'fresh', 'raw', 'uncooked'},
            'frozen': {'frozen'},
            'canned': {'canned', 'jarred', 'tinned'},
            'dried': {'dried', 'dehydrated', 'desiccated', 'powder', 'powdered', 'ground'},
            'paste': {'paste', 'puree', 'pureed', 'concentrate'},
            'cooked': {'cooked', 'prepared', 'ready'},
            'processed': {'smoked', 'cured', 'pickled', 'fermented'},
        }

        # Extract form markers from both strings
        def extract_forms(text):
            found = set()
            for form_type, keywords in form_groups.items():
                for keyword in keywords:
                    if re.search(r'\b' + keyword + r'\b', text):
                        found.add(form_type)
            return found

        ingredient_forms = extract_forms(ingredient)
        usda_forms = extract_forms(usda_match)

        # Check for preparation state modifiers
        ingredient_has_drained = 'drained' in ingredient
        ingredient_has_thawed = 'thawed' in ingredient
        usda_has_oil = bool(re.search(r'\bwith oil\b|\boil\b', usda_match))
        usda_has_sauce = bool(re.search(r'\bwith sauce\b|\bsauce\b', usda_match))

        # Base score
        score = 50.0

        # Perfect form match
        if ingredient_forms and usda_forms:
            if ingredient_forms == usda_forms:
                score += 40.0
            elif ingredient_forms & usda_forms:  # Partial overlap
                score += 20.0
            else:
                score -= 30.0
        elif not ingredient_forms and not usda_forms:
            # Both unspecified - neutral, slight bonus
            score += 10.0

        # Recoverable forms bonus
        if 'frozen' in ingredient_forms and ingredient_has_thawed:
            if 'frozen' in usda_forms:
                score += 25.0  # Frozen, thawed matches frozen perfectly
            elif 'fresh' in usda_forms or not usda_forms:
                score += 10.0  # Can be recovered to fresh-like state

        # Incompatible preparation states - critical penalties
        if ingredient_has_drained and (usda_has_oil or usda_has_sauce):
            score -= 50.0  # Major mismatch: drained vs with oil/sauce

        # Cooked vs uncooked mismatch
        if 'cooked' in usda_forms and 'cooked' not in ingredient:
            # USDA is cooked but ingredient doesn't mention cooking
            # Check if ingredient implies raw/fresh
            if 'fresh' in ingredient_forms or 'raw' in ingredient_forms:
                score -= 35.0
            elif not any(form in ingredient_forms for form in ['cooked', 'prepared']):
                score -= 20.0  # Mild penalty if state unclear

        # Water content mismatches
        if 'dried' in usda_forms and ('fresh' in ingredient_forms or 'frozen' in ingredient_forms or 'canned' in ingredient_forms):
            score -= 25.0  # Dried has different concentration

        if 'paste' in usda_forms and 'paste' not in ingredient:
            if any(word in ingredient for word in ['whole', 'chopped', 'diced', 'sliced']):
                score -= 30.0  # Paste vs whole form mismatch

        # Form modifier penalties
        if 'sauce' in usda_match and 'sauce' not in ingredient:
            score -= 25.0  # Sauce is a prepared form, not base ingredient

        # Token overlap analysis for form keywords
        ingredient_tokens = set(re.findall(r'\b\w+\b', ingredient))
        usda_tokens = set(re.findall(r'\b\w+\b', usda_match))

        form_keywords = {'fresh', 'frozen', 'canned', 'dried', 'raw', 'cooked',
                        'paste', 'powder', 'jarred', 'drained', 'thawed', 'whole'}

        ingredient_form_tokens = ingredient_tokens & form_keywords
        usda_form_tokens = usda_tokens & form_keywords

        if ingredient_form_tokens and usda_form_tokens:
            overlap = len(ingredient_form_tokens & usda_form_tokens)
            total = len(ingredient_form_tokens | usda_form_tokens)
            if total > 0:
                overlap_ratio = overlap / total
                score += (overlap_ratio * 15.0)

        # Normalize to 0-100 range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 25.0
