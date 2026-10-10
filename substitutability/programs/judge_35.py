import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Clean and normalize
        ing_clean = ingredient.lower().strip()
        usda_clean = usda_match.lower().strip()

        # Remove gram weights like "200g", "30g"
        ing_clean = re.sub(r'^\d+g?\s*', '', ing_clean)

        # Remove parentheticals
        ing_clean = re.sub(r'\([^)]*\)', '', ing_clean)
        usda_clean = re.sub(r'\([^)]*\)', '', usda_clean)

        # State/preparation descriptors that add specificity
        state_descriptors = {
            'raw', 'cooked', 'frozen', 'canned', 'dried', 'fresh', 'thawed',
            'uncooked', 'boiled', 'baked', 'fried', 'roasted', 'grilled',
            'steamed', 'drained', 'with oil', 'with salt', 'without oil',
            'ground', 'whole', 'chopped', 'diced', 'sliced', 'shredded',
            'crushed', 'minced', 'paste', 'powder', 'sauce', 'puree'
        }

        # Variant descriptors (specific types)
        variant_descriptors = {
            'extra virgin', 'virgin', 'light', 'dark', 'white', 'red', 'green',
            'black', 'yellow', 'brown', 'table', 'kosher', 'sea', 'cherry',
            'roma', 'beefsteak', 'plum', 'grape', 'sweet', 'spicy', 'hot',
            'mild', 'medium', 'aged', 'young', 'mature', 'organic'
        }

        # Tokenize
        ing_tokens = set(re.findall(r'\b\w+\b', ing_clean))
        usda_tokens = set(re.findall(r'\b\w+\b', usda_clean))

        # Extract multi-word descriptors from USDA
        usda_descriptors = set()
        for desc in state_descriptors | variant_descriptors:
            if desc in usda_clean:
                usda_descriptors.add(desc)

        # Extract multi-word descriptors from ingredient
        ing_descriptors = set()
        for desc in state_descriptors | variant_descriptors:
            if desc in ing_clean:
                ing_descriptors.add(desc)

        # Core food tokens (non-descriptor words)
        descriptor_words = set()
        for desc in state_descriptors | variant_descriptors:
            descriptor_words.update(desc.split())

        ing_core = ing_tokens - descriptor_words
        usda_core = usda_tokens - descriptor_words

        # Base overlap score (0-40)
        if not ing_core or not usda_core:
            core_score = 0
        else:
            core_overlap = len(ing_core & usda_core)
            core_union = len(ing_core | usda_core)
            core_score = (core_overlap / core_union) * 40 if core_union > 0 else 0

        # Specificity alignment score (0-60)
        specificity_score = 50

        # Penalty: USDA adds descriptors ingredient doesn't have
        usda_extra_descriptors = usda_descriptors - ing_descriptors
        for extra in usda_extra_descriptors:
            # Heavy penalty for state changes
            if extra in state_descriptors:
                specificity_score -= 15
            else:
                specificity_score -= 10

        # Penalty: USDA missing descriptors ingredient has
        usda_missing_descriptors = ing_descriptors - usda_descriptors
        for missing in usda_missing_descriptors:
            # Heavy penalty for missing important qualifiers
            if missing in state_descriptors:
                specificity_score -= 12
            else:
                specificity_score -= 8

        # Bonus: exact descriptor match when ingredient is qualified
        if ing_descriptors and ing_descriptors == usda_descriptors:
            specificity_score += 20

        # Bonus: both are unqualified (appropriate generality)
        if not ing_descriptors and not usda_descriptors and ing_core & usda_core:
            specificity_score += 15

        # Penalize if ingredient is unqualified but USDA is over-specific
        if not ing_descriptors and len(usda_descriptors) > 0:
            specificity_score -= 10 * len(usda_descriptors)

        # Final score
        total_score = core_score + specificity_score

        # Clamp to 0-100
        return max(0.0, min(100.0, total_score))

    except Exception:
        return 50.0
