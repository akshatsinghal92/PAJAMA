import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        ingredient = str(ingredient).lower().strip()
        usda_match = str(usda_match).lower().strip()

        if not ingredient or not usda_match:
            return 50.0

        # Remove gram weights from ingredient (e.g., "200g ")
        ingredient = re.sub(r'^\d+g\s+', '', ingredient)
        ingredient = re.sub(r'^\d+\s*g\s+', '', ingredient)

        # Extract core ingredient (before comma)
        ingredient_core = ingredient.split(',')[0].strip()

        # Remove parentheticals
        ingredient_core = re.sub(r'\([^)]*\)', '', ingredient_core).strip()
        usda_clean = re.sub(r'\([^)]*\)', '', usda_match).strip()

        # Define additive and processing keywords
        additive_keywords = {
            'oil', 'salt', 'salted', 'sugar', 'sweetened', 'sauce', 'sauced',
            'seasoned', 'seasoning', 'spiced', 'spice blend', 'flavored',
            'breaded', 'breading', 'battered', 'fried', 'marinated',
            'glazed', 'candied', 'syrup', 'honey', 'butter', 'buttered',
            'cream', 'creamed', 'cheese', 'gravy', 'sauce mix'
        }

        processing_keywords = {
            'cooked', 'fried', 'baked', 'roasted', 'grilled', 'broiled',
            'sauteed', 'steamed', 'boiled', 'braised', 'stewed',
            'smoked', 'cured', 'pickled', 'fermented', 'dried'
        }

        # Split into words for analysis
        ingredient_words = set(re.findall(r'\b\w+\b', ingredient_core))
        usda_words = set(re.findall(r'\b\w+\b', usda_clean))

        # Feature 1: Check for additives in USDA not in ingredient
        usda_additives = usda_words.intersection(additive_keywords)
        ingredient_additives = ingredient_words.intersection(additive_keywords)
        extra_additives = usda_additives - ingredient_additives

        # Feature 2: Check for processing differences
        usda_processing = usda_words.intersection(processing_keywords)
        ingredient_processing = ingredient_words.intersection(processing_keywords)

        # If ingredient mentions a specific processing, USDA should match
        if ingredient_processing and not usda_processing:
            processing_penalty = 20
        elif usda_processing and not ingredient_processing:
            # USDA has processing ingredient doesn't mention
            processing_penalty = 25
        elif ingredient_processing and usda_processing:
            # Both have processing - check if they match
            if ingredient_processing.intersection(usda_processing):
                processing_penalty = 0
            else:
                processing_penalty = 30
        else:
            processing_penalty = 0

        # Feature 3: Word overlap ratio (Jaccard similarity)
        if len(ingredient_words.union(usda_words)) > 0:
            overlap_ratio = len(ingredient_words.intersection(usda_words)) / len(ingredient_words.union(usda_words))
        else:
            overlap_ratio = 0

        # Feature 4: Core term matching
        # Extract the main food term (usually first word or two)
        ingredient_terms = ingredient_core.split()[:2]
        usda_terms = usda_clean.split(',')[0].split()[:2]

        core_match = any(term in usda_clean for term in ingredient_terms if len(term) > 3)

        # Feature 5: Length asymmetry (USDA much longer = more additives/processing)
        usda_word_count = len(usda_words)
        ingredient_word_count = len(ingredient_words)
        length_ratio = usda_word_count / max(ingredient_word_count, 1)

        if length_ratio > 2.0:
            length_penalty = 15
        elif length_ratio > 1.5:
            length_penalty = 10
        else:
            length_penalty = 0

        # Feature 6: Compound detection (commas in USDA suggest qualifiers)
        usda_parts = [p.strip() for p in usda_clean.split(',')]
        extra_qualifiers = len(usda_parts) - 1

        # Check if extra qualifiers are just descriptive vs additive
        qualifier_penalty = 0
        for i in range(1, len(usda_parts)):
            qualifier = usda_parts[i]
            qualifier_words = set(re.findall(r'\b\w+\b', qualifier))

            # If qualifier contains additives/processing not in ingredient
            if qualifier_words.intersection(additive_keywords):
                qualifier_penalty += 10
            elif qualifier_words.intersection(processing_keywords):
                # Check if it matches ingredient's processing state
                if 'drained' in ingredient and 'cooked' in qualifier:
                    qualifier_penalty += 15

        # Base score starts at 100
        score = 100.0

        # Apply penalties
        score -= len(extra_additives) * 15  # Each extra additive is a big penalty
        score -= processing_penalty
        score -= length_penalty
        score -= qualifier_penalty

        # Rewards for good matches
        score += overlap_ratio * 30  # Reward word overlap
        if core_match:
            score += 15  # Reward core term matching

        # Feature 7: Exact or near-exact match detection
        if ingredient_core == usda_clean.split(',')[0].strip():
            score += 20

        # Feature 8: Sauce/paste detection (specific to examples)
        if 'sauce' in ingredient_core and 'sauce' not in usda_clean:
            score -= 25
        if 'paste' in ingredient_core and 'paste' not in usda_clean:
            score -= 25
        if 'sauce' in usda_clean and 'sauce' not in ingredient_core:
            score -= 25

        # Feature 9: State mismatch (raw vs cooked, fresh vs canned)
        if 'raw' in ingredient_words and 'cooked' in usda_words:
            score -= 20
        if 'fresh' in ingredient_words and 'canned' in usda_words:
            score -= 15
        if 'frozen' in ingredient_words and 'fresh' in usda_words:
            score -= 10

        # Clamp score to 0-100 range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 50.0
