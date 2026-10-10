import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize inputs
        ing_text = str(ingredient).lower().strip()
        usda_text = str(usda_match).lower().strip()

        if not ing_text or not usda_text:
            return 0.0

        # Remove gram weights like "300g ", "10g ", etc.
        ing_text = re.sub(r'^\d+g?\s+', '', ing_text)

        # Remove parentheticals
        ing_text = re.sub(r'\([^)]*\)', '', ing_text)
        usda_text = re.sub(r'\([^)]*\)', '', usda_text)

        # Extract text before comma (primary description)
        ing_primary = ing_text.split(',')[0].strip()
        usda_primary = usda_text.split(',')[0].strip()

        # Character-level trigram similarity for fuzzy matching
        def get_trigrams(text):
            text = ' ' + text + ' '  # Add padding
            return set(text[i:i+3] for i in range(len(text) - 2))

        ing_trigrams = get_trigrams(ing_primary)
        usda_trigrams = get_trigrams(usda_primary)

        if not ing_trigrams or not usda_trigrams:
            return 0.0

        # Jaccard similarity on trigrams
        intersection = len(ing_trigrams & usda_trigrams)
        union = len(ing_trigrams | usda_trigrams)
        trigram_score = (intersection / union) * 100 if union > 0 else 0.0

        # Extract significant words (exclude common prep/state descriptors)
        stop_words = {'the', 'and', 'or', 'with', 'from', 'for', 'of', 'to', 'in', 'a', 'an'}

        def extract_words(text):
            words = re.findall(r'\b[a-z]+\b', text)
            return [w for w in words if len(w) > 2 and w not in stop_words]

        ing_words = set(extract_words(ing_primary))
        usda_words = set(extract_words(usda_primary))

        # Core food term overlap
        if ing_words and usda_words:
            word_overlap = len(ing_words & usda_words) / max(len(ing_words), len(usda_words))
        else:
            word_overlap = 0.0

        # Check for preparation state conflicts
        # These indicate the food is in a different state that affects substitutability
        state_indicators = {
            'cooked': ['cooked', 'boiled', 'fried', 'baked', 'roasted', 'grilled'],
            'raw': ['raw', 'fresh', 'uncooked'],
            'canned': ['canned', 'tinned'],
            'frozen': ['frozen'],
            'dried': ['dried', 'dehydrated'],
            'drained': ['drained'],
            'with_additions': ['with oil', 'with salt', 'with sugar', 'seasoned']
        }

        def get_states(text):
            found_states = set()
            for state_key, state_terms in state_indicators.items():
                for term in state_terms:
                    if term in text:
                        found_states.add(state_key)
            return found_states

        ing_states = get_states(ing_text)
        usda_states = get_states(usda_text)

        # Apply penalty for state mismatches
        state_penalty = 1.0

        # Conflicting states
        if ('cooked' in ing_states and 'raw' in usda_states) or \
           ('raw' in ing_states and 'cooked' in usda_states):
            state_penalty *= 0.3

        # Drained vs with additions conflict
        if 'drained' in ing_states and 'with_additions' in usda_states:
            state_penalty *= 0.4

        # Check for form mismatches (sauce vs paste, whole vs diced, etc.)
        form_words_ing = set(re.findall(r'\b(sauce|paste|powder|flakes|diced|whole|sliced|shredded|chopped|ground)\b', ing_text))
        form_words_usda = set(re.findall(r'\b(sauce|paste|powder|flakes|diced|whole|sliced|shredded|chopped|ground)\b', usda_text))

        form_penalty = 1.0
        if form_words_ing and form_words_usda and not (form_words_ing & form_words_usda):
            # Different forms mentioned and no overlap
            form_penalty *= 0.5

        # Combine scores with multiplicative penalties
        base_score = (trigram_score * 0.6 + word_overlap * 40)
        final_score = base_score * state_penalty * form_penalty

        return max(0.0, min(100.0, final_score))

    except Exception:
        return 0.0
