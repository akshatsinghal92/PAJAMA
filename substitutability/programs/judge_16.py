import re
from collections import defaultdict

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0

        # Normalize inputs
        ing = ingredient.lower().strip()
        usda = usda_match.lower().strip()

        # Remove gram weights (e.g., "300g", "40 g")
        ing = re.sub(r'^\d+\s*g\s+', '', ing)

        # Remove parentheticals
        ing = re.sub(r'\([^)]*\)', '', ing)
        usda = re.sub(r'\([^)]*\)', '', usda)

        # Critical state markers that change cooking/outcome
        critical_states = {
            'cooked': ['cooked', 'baked', 'fried', 'roasted', 'grilled', 'boiled', 'steamed'],
            'with_additives': ['with oil', 'with butter', 'with salt', 'seasoned', 'marinated'],
            'form_modifiers': ['sauce', 'paste', 'puree', 'juice', 'extract', 'syrup'],
            'preservation': ['canned', 'frozen', 'dried', 'pickled', 'smoked', 'cured']
        }

        # Trivial prep states that don't affect substitutability
        trivial_preps = ['raw', 'fresh', 'chopped', 'diced', 'minced', 'sliced',
                         'shredded', 'grated', 'thawed', 'drained', 'whole', 'crushed']

        # State extraction function
        def extract_states(text):
            states = defaultdict(list)
            for category, markers in critical_states.items():
                for marker in markers:
                    if marker in text:
                        states[category].append(marker)

            trivial_found = [prep for prep in trivial_preps if prep in text]
            return states, trivial_found

        ing_critical, ing_trivial = extract_states(ing)
        usda_critical, usda_trivial = extract_states(usda)

        # Extract core food terms (remove all state descriptors)
        def extract_core_terms(text):
            # Remove all known state words
            all_state_words = []
            for markers in critical_states.values():
                all_state_words.extend(markers)
            all_state_words.extend(trivial_preps)

            words = text.split()
            core = []
            for word in words:
                cleaned = re.sub(r'[,;]', '', word)
                if cleaned and cleaned not in all_state_words:
                    core.append(cleaned)
            return ' '.join(core)

        ing_core = extract_core_terms(ing)
        usda_core = extract_core_terms(usda)

        # Base score calculation
        score = 50.0

        # Core term similarity (Jaccard on words)
        ing_words = set(ing_core.split())
        usda_words = set(usda_core.split())

        if ing_words and usda_words:
            intersection = len(ing_words & usda_words)
            union = len(ing_words | usda_words)
            core_similarity = intersection / union if union > 0 else 0
            score += core_similarity * 30

        # Critical state compatibility scoring

        # PENALTY: USDA has 'cooked' but ingredient doesn't explicitly mention it
        if 'cooked' in usda_critical and 'cooked' not in ing_critical:
            # Exception: if ingredient has 'canned', cooked might be acceptable
            if 'canned' not in ing:
                score -= 40

        # PENALTY: Form modifier mismatch (sauce vs raw ingredient)
        ing_has_form = bool(ing_critical.get('form_modifiers'))
        usda_has_form = bool(usda_critical.get('form_modifiers'))
        if ing_has_form != usda_has_form:
            score -= 35

        # PENALTY: Additive mismatch (ingredient says 'drained' but USDA has 'with oil')
        if 'drained' in ing and any('with' in marker for category in usda_critical.values() for marker in category):
            score -= 30

        # PENALTY: Preservation state mismatch
        ing_preservation = set(ing_critical.get('preservation', []))
        usda_preservation = set(usda_critical.get('preservation', []))
        if ing_preservation != usda_preservation:
            # Some preservation states are compatible
            if not (ing_preservation.issubset(usda_preservation) or usda_preservation.issubset(ing_preservation)):
                score -= 15

        # REWARD: Trivial prep difference only (shredded vs raw)
        if not ing_critical and not usda_critical and (ing_trivial or usda_trivial):
            score += 20

        # REWARD: Both have same critical states
        for category in critical_states.keys():
            if ing_critical.get(category) and usda_critical.get(category):
                if set(ing_critical[category]) == set(usda_critical[category]):
                    score += 15

        # REWARD: Exact substring match in core terms
        if ing_core and usda_core:
            if ing_core in usda_core or usda_core in ing_core:
                score += 10

        # PENALTY: Length disparity suggests detail mismatch
        word_count_diff = abs(len(ing.split()) - len(usda.split()))
        if word_count_diff > 4:
            score -= word_count_diff * 2

        # Ensure score is in reasonable range
        score = max(0, min(100, score))

        return float(score)

    except Exception:
        # Fallback on any error
        return 25.0
