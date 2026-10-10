import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50

        ing_lower = ingredient.lower()
        usda_lower = usda_match.lower()

        # Define preservation/form keywords with weights
        form_categories = {
            'frozen': {'frozen', 'freeze'},
            'canned': {'canned', 'tinned', 'can'},
            'dried': {'dried', 'dehydrated', 'dry'},
            'fresh': {'fresh', 'raw'},
            'jarred': {'jarred', 'jar'},
            'paste': {'paste', 'puree', 'pureed'},
            'powder': {'powder', 'powdered', 'ground'},
            'bottled': {'bottled', 'bottle'},
            'pickled': {'pickled', 'pickle'},
            'smoked': {'smoked', 'smoke'},
            'fermented': {'fermented'}
        }

        # Extract forms present in each string
        ing_forms = set()
        usda_forms = set()

        for category, keywords in form_categories.items():
            for keyword in keywords:
                if keyword in ing_lower:
                    ing_forms.add(category)
                if keyword in usda_lower:
                    usda_forms.add(category)

        # Check cooking state keywords
        ing_cooked_state = None
        usda_cooked_state = None

        cooked_indicators = {'cooked', 'boiled', 'fried', 'baked', 'roasted', 'grilled', 'steamed'}
        uncooked_indicators = {'raw', 'uncooked', 'fresh'}

        for indicator in cooked_indicators:
            if indicator in ing_lower:
                ing_cooked_state = 'cooked'
            if indicator in usda_lower:
                usda_cooked_state = 'cooked'

        for indicator in uncooked_indicators:
            if indicator in ing_lower:
                ing_cooked_state = 'raw'
            if indicator in usda_lower:
                usda_cooked_state = 'raw'

        # Check for state modifiers that affect substitutability
        ing_drained = 'drained' in ing_lower or 'drain' in ing_lower
        usda_with_liquid = any(x in usda_lower for x in ['with oil', 'with liquid', 'with brine', 'with juice'])

        ing_thawed = 'thawed' in ing_lower or 'thaw' in ing_lower

        # Check for concentration differences
        ing_sauce = 'sauce' in ing_lower
        usda_sauce = 'sauce' in usda_lower

        # Scoring logic
        base_score = 100

        # If both have no explicit forms, assume compatible (like basic ingredients)
        if not ing_forms and not usda_forms:
            base_score = 85
        # If forms match exactly
        elif ing_forms and usda_forms and ing_forms == usda_forms:
            base_score = 95
        # If forms are compatible (ingredient thawed but USDA frozen is OK)
        elif 'frozen' in usda_forms and ing_thawed:
            base_score = 90
        # If one is subset of other (partial match)
        elif ing_forms and usda_forms:
            overlap = len(ing_forms & usda_forms)
            total_unique = len(ing_forms | usda_forms)
            if overlap > 0:
                base_score = 70 + (overlap / total_unique) * 25
            else:
                # Different forms - major penalty
                base_score = 30
        # If only one has form specified
        elif ing_forms or usda_forms:
            base_score = 50

        # Apply cooked state penalty if mismatched
        if ing_cooked_state and usda_cooked_state:
            if ing_cooked_state != usda_cooked_state:
                base_score -= 35

        # Drained vs with liquid is a major issue
        if ing_drained and usda_with_liquid:
            base_score -= 40

        # Sauce vs non-sauce mismatch
        if ing_sauce != usda_sauce:
            base_score -= 25

        # Check for water content mismatches via keywords
        water_content_keywords = {
            'condensed': -1,
            'concentrated': -1,
            'diluted': -1,
            'reduced': -1
        }

        ing_water = sum(v for k, v in water_content_keywords.items() if k in ing_lower)
        usda_water = sum(v for k, v in water_content_keywords.items() if k in usda_lower)

        if abs(ing_water - usda_water) > 0:
            base_score -= 20

        # Physical form differences
        physical_forms = {
            'whole': 1,
            'diced': 2,
            'chopped': 2,
            'sliced': 2,
            'shredded': 3,
            'minced': 4,
            'crushed': 4
        }

        ing_physical = [v for k, v in physical_forms.items() if k in ing_lower]
        usda_physical = [v for k, v in physical_forms.items() if k in usda_lower]

        # Physical form similarity (if both specified)
        if ing_physical and usda_physical:
            physical_diff = abs(ing_physical[0] - usda_physical[0])
            if physical_diff == 0:
                base_score += 5
            elif physical_diff <= 1:
                base_score -= 5
            else:
                base_score -= 15

        # Bonus for compatible preservation terminology
        compatible_pairs = [
            ('canned', 'tinned'),
            ('dried', 'dehydrated'),
            ('fresh', 'raw')
        ]

        for term1, term2 in compatible_pairs:
            if (term1 in ing_lower and term2 in usda_lower) or (term2 in ing_lower and term1 in usda_lower):
                base_score += 10
                break

        # Clamp score to reasonable range
        final_score = max(0, min(100, base_score))

        return final_score

    except Exception:
        return 50
