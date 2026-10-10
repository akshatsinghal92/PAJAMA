import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        ingredient = str(ingredient).lower()
        usda_match = str(usda_match).lower()

        # Remove gram weights like "200g", "30g"
        ingredient = re.sub(r'^\d+g?\s*', '', ingredient)
        ingredient = re.sub(r'\(\s*[^)]*\s*\)', '', ingredient)

        # Trivial prep states that don't change substitutability
        trivial_states = {
            'raw', 'fresh', 'chopped', 'diced', 'minced', 'sliced',
            'shredded', 'grated', 'thawed', 'whole', 'halved', 'quartered',
            'peeled', 'trimmed', 'washed', 'rinsed', 'cut', 'crushed',
            'ground', 'cubed', 'julienned', 'torn', 'pieces'
        }

        # Non-trivial states that change cooking/outcome
        nontrivial_states = {
            'cooked', 'fried', 'baked', 'roasted', 'boiled', 'steamed',
            'grilled', 'sauteed', 'simmered', 'braised', 'blanched',
            'toasted', 'caramelized', 'reduced', 'smoked'
        }

        # Product form modifiers that change substitutability
        form_modifiers = {
            'sauce', 'paste', 'puree', 'juice', 'oil', 'extract',
            'concentrate', 'powder', 'flakes', 'meal', 'flour',
            'butter', 'cream', 'milk', 'stock', 'broth'
        }

        # Packaging/processing states that matter
        packaging_states = {
            'canned', 'frozen', 'dried', 'pickled', 'preserved',
            'jarred', 'bottled', 'vacuum-packed'
        }

        # Liquid/oil modifiers
        liquid_modifiers = {
            'drained', 'in oil', 'in water', 'in syrup', 'in brine',
            'with oil', 'with water', 'packed in', 'submerged'
        }

        # Extract state keywords from both strings
        def extract_states(text):
            words = re.findall(r'\b\w+\b', text)
            found_trivial = set()
            found_nontrivial = set()
            found_form = set()
            found_packaging = set()
            found_liquid = set()

            for word in words:
                if word in trivial_states:
                    found_trivial.add(word)
                if word in nontrivial_states:
                    found_nontrivial.add(word)
                if word in form_modifiers:
                    found_form.add(word)
                if word in packaging_states:
                    found_packaging.add(word)

            # Check for multi-word liquid modifiers
            text_lower = text.lower()
            for mod in liquid_modifiers:
                if mod in text_lower:
                    found_liquid.add(mod)

            return found_trivial, found_nontrivial, found_form, found_packaging, found_liquid

        ing_trivial, ing_nontrivial, ing_form, ing_pkg, ing_liquid = extract_states(ingredient)
        usda_trivial, usda_nontrivial, usda_form, usda_pkg, usda_liquid = extract_states(usda_match)

        # Start with base score
        score = 75.0

        # Check for form modifier mismatches (major penalty)
        if ing_form != usda_form:
            if ing_form and usda_form:
                # Both have forms but different (e.g., sauce vs paste)
                score -= 40.0
            elif ing_form or usda_form:
                # One has form modifier, other doesn't (e.g., tahini vs tahini sauce)
                score -= 35.0

        # Check for non-trivial state mismatches (major penalty)
        if ing_nontrivial or usda_nontrivial:
            if ing_nontrivial != usda_nontrivial:
                # Different cooking states (e.g., raw pasta vs cooked pasta)
                score -= 45.0

        # Check liquid/packing medium mismatches
        if ing_liquid != usda_liquid:
            if ing_liquid and usda_liquid:
                # Different liquid states (e.g., drained vs with oil)
                score -= 30.0
            elif 'drained' in ing_liquid and usda_liquid:
                # Ingredient drained but USDA has liquid
                score -= 35.0

        # Check packaging state alignment
        if ing_pkg and usda_pkg:
            if ing_pkg == usda_pkg:
                score += 5.0
            else:
                # Different packaging (usually OK but slight concern)
                score -= 5.0

        # Trivial state differences are OK (slight bonus for matching)
        trivial_overlap = len(ing_trivial & usda_trivial)
        if trivial_overlap > 0:
            score += trivial_overlap * 3.0

        # Check core ingredient similarity using character overlap
        ing_clean = re.sub(r'\b(' + '|'.join(trivial_states | nontrivial_states | form_modifiers | packaging_states) + r')\b', '', ingredient)
        usda_clean = re.sub(r'\b(' + '|'.join(trivial_states | nontrivial_states | form_modifiers | packaging_states) + r')\b', '', usda_match)

        ing_clean = re.sub(r'[^a-z]', '', ing_clean)
        usda_clean = re.sub(r'[^a-z]', '', usda_clean)

        if ing_clean and usda_clean:
            # Character-level overlap
            ing_chars = Counter(ing_clean)
            usda_chars = Counter(usda_clean)
            common = sum((ing_chars & usda_chars).values())
            total = max(sum(ing_chars.values()), sum(usda_chars.values()))
            if total > 0:
                char_sim = (common / total) * 100
                # Weight core similarity heavily
                score = score * 0.6 + char_sim * 0.4

        # Bonus for exact substring matches
        ing_words = set(re.findall(r'\b\w+\b', ingredient))
        usda_words = set(re.findall(r'\b\w+\b', usda_match))
        common_words = ing_words & usda_words
        # Filter out stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'with', 'from', 'in', 'to'}
        common_words = common_words - stop_words - trivial_states

        if len(common_words) >= 2:
            score += len(common_words) * 2.0

        # Clamp score to reasonable range
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 50.0
