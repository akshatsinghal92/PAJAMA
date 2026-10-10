import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        # Normalize inputs
        ing_lower = ingredient.lower()
        usda_lower = usda_match.lower()

        # Remove gram weights (e.g., "300g ", "40g ")
        ing_lower = re.sub(r'^\d+g?\s+', '', ing_lower)

        # Define preservation/form categories with keywords
        form_keywords = {
            'frozen': ['frozen', 'froze'],
            'canned': ['canned', 'tinned'],
            'dried': ['dried', 'dehydrated', 'dry'],
            'fresh': ['fresh', 'raw'],
            'jarred': ['jarred', 'jar'],
            'powder': ['powder', 'powdered'],
            'paste': ['paste'],
            'sauce': ['sauce'],
            'ground': ['ground', 'minced', 'crushed'],
            'whole': ['whole'],
            'diced': ['diced', 'chopped', 'cut'],
            'cooked': ['cooked', 'prepared', 'ready-to'],
            'uncooked': ['uncooked', 'raw'],
        }

        # Preparation state keywords
        prep_keywords = {
            'drained': ['drained'],
            'thawed': ['thawed', 'defrosted'],
            'with_oil': ['with oil', 'in oil', 'oil'],
            'with_salt': ['with salt', 'salted'],
            'no_salt': ['no salt', 'unsalted', 'without salt'],
        }

        # Extract forms from both texts
        def extract_forms(text):
            forms = set()
            for form, keywords in form_keywords.items():
                if any(kw in text for kw in keywords):
                    forms.add(form)
            return forms

        def extract_prep(text):
            prep = set()
            for p, keywords in prep_keywords.items():
                if any(kw in text for kw in keywords):
                    prep.add(p)
            return prep

        ing_forms = extract_forms(ing_lower)
        usda_forms = extract_forms(usda_lower)
        ing_prep = extract_prep(ing_lower)
        usda_prep = extract_prep(usda_lower)

        # Base score
        score = 60.0

        # Perfect form match gets high score
        if ing_forms and usda_forms and ing_forms == usda_forms:
            score += 30.0
        elif ing_forms and usda_forms:
            # Partial match
            overlap = len(ing_forms & usda_forms)
            total = len(ing_forms | usda_forms)
            score += 20.0 * (overlap / total)

        # Compatible form pairs (one can substitute the other)
        compatible_pairs = [
            ('frozen', 'fresh'),  # frozen can sub for fresh in many cases
            ('fresh', 'frozen'),
            ('ground', 'powder'),
            ('powder', 'ground'),
            ('diced', 'whole'),  # if you can dice it
            ('whole', 'fresh'),
        ]

        for ing_form in ing_forms:
            for usda_form in usda_forms:
                if (ing_form, usda_form) in compatible_pairs:
                    score += 10.0

        # Incompatible form combinations that kill substitutability
        incompatible_pairs = [
            ('paste', 'sauce'),
            ('sauce', 'paste'),
            ('powder', 'fresh'),
            ('fresh', 'powder'),
            ('dried', 'fresh'),
            ('fresh', 'dried'),
            ('canned', 'fresh'),
            ('fresh', 'canned'),
        ]

        for ing_form in ing_forms:
            for usda_form in usda_forms:
                if (ing_form, usda_form) in incompatible_pairs:
                    score -= 25.0

        # Handle preparation state mismatches
        # Ingredient says "drained" but USDA has "with oil" = bad
        if 'drained' in ing_prep and 'with_oil' in usda_prep:
            score -= 30.0

        # Ingredient is "thawed" (from frozen) but USDA is "cooked" = mismatch
        if 'thawed' in ing_prep and 'cooked' in usda_forms:
            score -= 20.0

        # If ingredient specifies "drained" and USDA is "cooked" without drained
        if 'drained' in ing_prep and 'cooked' in usda_forms and 'drained' not in usda_lower:
            score -= 25.0

        # Cooked vs uncooked mismatch is critical
        if 'cooked' in ing_forms and 'uncooked' in usda_forms:
            score -= 35.0
        if 'uncooked' in ing_forms and 'cooked' in usda_forms:
            score -= 35.0

        # "Pasta" vs "Pasta, cooked" mismatch (Example 1)
        if 'pasta' in ing_lower and 'pasta' in usda_lower:
            ing_has_cooked = 'cooked' in ing_lower
            usda_has_cooked = 'cooked' in usda_lower
            if ing_has_cooked != usda_has_cooked:
                score -= 30.0

        # Check for added ingredients in USDA that weren't in recipe
        # "with oil", "with salt" when ingredient doesn't mention it
        usda_additions = []
        if 'with oil' in usda_lower or 'in oil' in usda_lower:
            if 'oil' not in ing_lower:
                usda_additions.append('oil')
        if 'with salt' in usda_lower and 'no salt' not in usda_lower:
            if 'salt' not in ing_lower and 'unsalted' in ing_lower:
                usda_additions.append('salt')

        for addition in usda_additions:
            score -= 15.0

        # Boost for exact matches or very close matches
        # Remove common words and check similarity
        def simplify(text):
            text = re.sub(r'\d+g?\s*', '', text)
            text = re.sub(r'[^\w\s]', ' ', text)
            words = text.lower().split()
            # Remove common qualifiers
            stopwords = {'the', 'a', 'an', 'from', 'with', 'without', 'in', 'on'}
            return set(w for w in words if w not in stopwords and len(w) > 1)

        ing_words = simplify(ing_lower)
        usda_words = simplify(usda_lower)

        if ing_words and usda_words:
            word_overlap = len(ing_words & usda_words) / len(ing_words | usda_words)
            score += word_overlap * 15.0

        # Clamp score to reasonable range
        score = max(0.0, min(100.0, score))

        return round(score, 2)

    except Exception:
        return 50.0
