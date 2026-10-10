import re
from collections import Counter


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 5.0

        ing = ingredient.lower().strip()
        usda = usda_match.lower().strip()

        # Remove gram weights like "200g", "30g"
        ing = re.sub(r'^\d+g?\s*', '', ing)

        # Extract form/preservation markers with semantic grouping
        preservation_forms = {
            'frozen': ['frozen'],
            'canned': ['canned', 'tinned'],
            'dried': ['dried', 'dehydrated', 'dry'],
            'fresh': ['fresh', 'raw'],
            'jarred': ['jarred', 'jar'],
            'paste': ['paste'],
            'powder': ['powder', 'powdered', 'ground'],
            'bottled': ['bottled', 'bottle']
        }

        # Processing states that matter
        processing_states = {
            'cooked': ['cooked', 'boiled', 'steamed', 'roasted', 'baked'],
            'raw': ['raw', 'uncooked', 'fresh'],
            'thawed': ['thawed', 'defrosted'],
            'drained': ['drained'],
            'marinated': ['marinated'],
            'pickled': ['pickled']
        }

        # Physical form descriptors
        physical_forms = {
            'whole': ['whole', 'entire'],
            'diced': ['diced', 'cubed', 'chopped'],
            'shredded': ['shredded', 'grated'],
            'sliced': ['sliced'],
            'crushed': ['crushed'],
            'minced': ['minced'],
            'puree': ['puree', 'pureed'],
            'juice': ['juice'],
            'sauce': ['sauce']
        }

        # Oil/fat presence indicators
        oil_indicators = ['with oil', 'in oil', 'cooked with oil', 'oil added']

        def extract_features(text):
            features = {
                'preservation': set(),
                'processing': set(),
                'physical': set(),
                'has_oil': False,
                'tokens': set(re.findall(r'\b\w+\b', text))
            }

            # Check preservation forms
            for form, keywords in preservation_forms.items():
                if any(kw in text for kw in keywords):
                    features['preservation'].add(form)

            # Check processing states
            for state, keywords in processing_states.items():
                if any(kw in text for kw in keywords):
                    features['processing'].add(state)

            # Check physical forms
            for form, keywords in physical_forms.items():
                if any(kw in text for kw in keywords):
                    features['physical'].add(form)

            # Check for oil presence
            features['has_oil'] = any(indicator in text for indicator in oil_indicators)

            return features

        ing_feat = extract_features(ing)
        usda_feat = extract_features(usda)

        # Base score
        score = 50.0

        # 1. PRESERVATION FORM ALIGNMENT (most critical)
        if ing_feat['preservation'] and usda_feat['preservation']:
            # Both specify preservation - must match
            if ing_feat['preservation'] & usda_feat['preservation']:
                score += 25.0  # Perfect match
            else:
                # Check for compatible forms
                compatible = [
                    ({'frozen'}, {'frozen'}),
                    ({'fresh'}, {'fresh'}),
                    ({'canned'}, {'canned'})
                ]
                if any(ing_feat['preservation'] == a and usda_feat['preservation'] == b
                       for a, b in compatible):
                    score += 15.0
                else:
                    score -= 30.0  # Incompatible preservation
        elif ing_feat['preservation'] or usda_feat['preservation']:
            # Only one specifies - mild penalty
            score -= 10.0
        else:
            # Neither specifies - assume compatible
            score += 10.0

        # 2. PROCESSING STATE ALIGNMENT
        # Special handling for cooked vs raw
        ing_cooked = 'cooked' in ing_feat['processing']
        usda_cooked = 'cooked' in ing_feat['processing']
        ing_raw = 'raw' in ing_feat['processing']
        usda_raw = 'raw' in usda_feat['processing']

        # Check if ingredient is "thawed" frozen - recoverable to frozen
        ing_thawed = 'thawed' in ing_feat['processing']
        if ing_thawed and 'frozen' in usda_feat['preservation']:
            score += 15.0  # Thawed frozen matches frozen

        # Cooked/raw mismatch is critical
        if (ing_cooked and usda_raw) or (ing_raw and usda_cooked):
            score -= 35.0
        elif ing_cooked == usda_cooked:
            score += 10.0

        # Drained is a critical modifier
        if 'drained' in ing_feat['processing']:
            if ing_feat['has_oil'] or usda_feat['has_oil']:
                score -= 40.0  # Drained but USDA has oil = incompatible
            elif any(word in usda for word in ['with oil', 'cooked with']):
                score -= 35.0
            else:
                score += 5.0  # Drained and no oil mentioned

        # Oil presence mismatch
        if ing_feat['has_oil'] != usda_feat['has_oil']:
            score -= 25.0

        # 3. PHYSICAL FORM ALIGNMENT
        # Sauce vs non-sauce is critical
        if 'sauce' in ing_feat['physical'] and 'sauce' not in usda_feat['physical']:
            if 'paste' in usda_feat['physical'] or 'puree' in usda_feat['physical']:
                score -= 15.0  # Somewhat related
            else:
                score -= 30.0  # Sauce vs solid/base ingredient
        elif 'sauce' in usda_feat['physical'] and 'sauce' not in ing_feat['physical']:
            score -= 30.0

        # Juice is different from whole/solid
        if 'juice' in ing_feat['physical'] or 'juice' in usda_feat['physical']:
            if ing_feat['physical'] & usda_feat['physical']:
                score += 10.0
            else:
                score -= 20.0

        # Prep forms like shredded, diced are less critical
        prep_forms = {'shredded', 'diced', 'sliced', 'minced', 'crushed'}
        ing_prep = ing_feat['physical'] & prep_forms
        usda_prep = usda_feat['physical'] & prep_forms

        if ing_prep and not usda_prep:
            # Ingredient specifies prep, USDA doesn't - acceptable
            score += 5.0
        elif not ing_prep and usda_prep:
            # USDA specifies prep, ingredient doesn't - mild penalty
            score -= 5.0

        # 4. TOKEN OVERLAP BONUS (secondary)
        # Core food overlap
        common_tokens = ing_feat['tokens'] & usda_feat['tokens']
        if len(common_tokens) >= 2:
            score += 5.0

        # 5. SPECIAL CASES
        # Pasta: cooked vs uncooked is critical
        if 'pasta' in ing_feat['tokens'] or 'pasta' in usda_feat['tokens']:
            if 'cooked' in usda and 'cooked' not in ing:
                score -= 40.0

        # Salt, spices are usually simple matches
        if any(token in ing_feat['tokens'] for token in ['salt', 'pepper', 'spice']):
            if any(token in usda_feat['tokens'] for token in ['salt', 'pepper', 'spice']):
                score += 15.0

        # Normalize to 0-100 range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 50.0
