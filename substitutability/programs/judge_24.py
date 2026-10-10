import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        ingredient = str(ingredient).lower()
        usda_match = str(usda_match).lower()

        # Remove gram weights like "300g"
        ingredient = re.sub(r'^\d+g?\s*', '', ingredient)

        # Define preservation/form keywords with categories
        preservation_forms = {
            'frozen': {'frozen', 'freeze'},
            'canned': {'canned', 'can'},
            'dried': {'dried', 'dry', 'dehydrated'},
            'fresh': {'fresh', 'raw'},
            'powder': {'powder', 'powdered', 'ground'},
            'paste': {'paste', 'puree', 'pureed'},
            'jarred': {'jarred', 'jar'},
            'bottled': {'bottled', 'bottle'},
            'pickled': {'pickled', 'pickle'},
            'smoked': {'smoked', 'smoke'},
            'salted': {'salted', 'salt-cured'},
            'fermented': {'fermented'}
        }

        # Preparation state keywords
        prep_states = {
            'cooked': {'cooked', 'boiled', 'baked', 'fried', 'roasted', 'grilled'},
            'uncooked': {'uncooked', 'raw', 'fresh'},
            'thawed': {'thawed', 'defrosted'}
        }

        # Liquid/consistency forms
        consistency_forms = {
            'sauce': {'sauce', 'gravy'},
            'oil': {'oil'},
            'broth': {'broth', 'stock'},
            'juice': {'juice'},
            'concentrate': {'concentrate', 'concentrated'}
        }

        # Additional qualifiers that signal specific preparation
        qualifiers = {
            'drained': {'drained'},
            'with_oil': {'with oil', 'in oil', 'cooked with oil'},
            'with_salt': {'with salt', 'salted'},
            'shredded': {'shredded', 'grated'},
            'diced': {'diced', 'chopped'},
            'whole': {'whole'}
        }

        def extract_forms(text):
            forms = {
                'preservation': set(),
                'prep_state': set(),
                'consistency': set(),
                'qualifiers': set()
            }

            for form_type, keywords in preservation_forms.items():
                if any(kw in text for kw in keywords):
                    forms['preservation'].add(form_type)

            for state_type, keywords in prep_states.items():
                if any(kw in text for kw in keywords):
                    forms['prep_state'].add(state_type)

            for cons_type, keywords in consistency_forms.items():
                if any(kw in text for kw in keywords):
                    forms['consistency'].add(cons_type)

            for qual_type, keywords in qualifiers.items():
                if any(kw in text for kw in keywords):
                    forms['qualifiers'].add(qual_type)

            return forms

        ingredient_forms = extract_forms(ingredient)
        usda_forms = extract_forms(usda_match)

        score = 50.0  # Base score

        # Check preservation form compatibility
        if ingredient_forms['preservation'] and usda_forms['preservation']:
            # Direct match is best
            if ingredient_forms['preservation'] & usda_forms['preservation']:
                score += 30
            # Compatible transitions
            elif ('frozen' in ingredient_forms['preservation'] and 'fresh' in usda_forms['preservation']):
                # Frozen ingredient can use fresh USDA entry
                score += 20
            elif ('fresh' in ingredient_forms['preservation'] and 'frozen' in usda_forms['preservation']):
                # Fresh ingredient less compatible with frozen USDA
                score += 10
            else:
                # Incompatible preservation forms
                score -= 40
        elif not ingredient_forms['preservation'] and not usda_forms['preservation']:
            # Both unspecified - assume compatible
            score += 15
        elif ingredient_forms['preservation'] and not usda_forms['preservation']:
            # USDA unspecified, ingredient specified - partial credit
            score += 5

        # Check preparation state compatibility
        if ingredient_forms['prep_state'] and usda_forms['prep_state']:
            if ingredient_forms['prep_state'] & usda_forms['prep_state']:
                score += 20
            elif ('thawed' in ingredient_forms['prep_state'] and
                  'uncooked' in usda_forms['prep_state']):
                # Thawed ingredient matches uncooked USDA
                score += 15
            elif ('cooked' in ingredient_forms['prep_state'] and
                  'uncooked' in usda_forms['prep_state']):
                # Major incompatibility
                score -= 50
            elif ('uncooked' in ingredient_forms['prep_state'] and
                  'cooked' in usda_forms['prep_state']):
                # Major incompatibility
                score -= 50
            else:
                score -= 20
        elif not ingredient_forms['prep_state'] and not usda_forms['prep_state']:
            score += 10

        # Check consistency form compatibility
        if ingredient_forms['consistency'] and usda_forms['consistency']:
            if ingredient_forms['consistency'] & usda_forms['consistency']:
                score += 25
            else:
                # Different consistency forms are usually incompatible
                score -= 35
        elif ingredient_forms['consistency'] and not usda_forms['consistency']:
            # Ingredient specifies sauce/oil/etc but USDA doesn't
            score -= 25
        elif not ingredient_forms['consistency'] and usda_forms['consistency']:
            # USDA specifies liquid form but ingredient doesn't
            score -= 15

        # Check qualifier compatibility
        if ingredient_forms['qualifiers'] and usda_forms['qualifiers']:
            matching = ingredient_forms['qualifiers'] & usda_forms['qualifiers']
            total_quals = ingredient_forms['qualifiers'] | usda_forms['qualifiers']

            if len(matching) == len(total_quals):
                # All qualifiers match
                score += 15
            else:
                # Some mismatch in qualifiers
                conflict_penalty = (len(total_quals) - len(matching)) * 10
                score -= conflict_penalty
        elif ingredient_forms['qualifiers'] and not usda_forms['qualifiers']:
            # Ingredient has specific qualifiers USDA lacks
            score -= len(ingredient_forms['qualifiers']) * 5

        # Normalize score to 0-100 range
        score = max(0, min(100, score))

        return float(score)

    except Exception:
        return 0.0
