import re

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        ingredient = str(ingredient).lower()
        usda_match = str(usda_match).lower()

        # Define discriminating qualifier categories
        prep_states = {'raw', 'cooked', 'frozen', 'canned', 'dried', 'fresh', 'thawed', 'uncooked', 'roasted', 'grilled', 'baked', 'fried', 'steamed', 'boiled'}
        forms = {'whole', 'diced', 'chopped', 'shredded', 'ground', 'sliced', 'crushed', 'minced', 'paste', 'puree', 'mashed'}
        fat_levels = {'skim', 'whole', 'low-fat', '2%', 'nonfat', 'reduced-fat', 'fat-free', 'full-fat'}
        colors = {'red', 'green', 'yellow', 'white', 'black', 'orange', 'purple', 'brown', 'pink'}
        parts = {'breast', 'thigh', 'wing', 'leg', 'drumstick', 'tenderloin', 'fillet', 'steak'}
        varieties = {'cherry', 'roma', 'beefsteak', 'plum', 'bell', 'jalapeño', 'sweet', 'hot', 'spicy'}
        sweetness = {'sweet', 'unsweetened', 'sweetened', 'sugar-free'}
        cuts = {'boneless', 'bone-in', 'skinless', 'skin-on'}

        def extract_qualifiers(text):
            quals = {
                'prep': set(),
                'form': set(),
                'fat': set(),
                'color': set(),
                'part': set(),
                'variety': set(),
                'sweet': set(),
                'cut': set()
            }

            for word in prep_states:
                if re.search(r'\b' + re.escape(word) + r'\b', text):
                    quals['prep'].add(word)
            for word in forms:
                if re.search(r'\b' + re.escape(word) + r'\b', text):
                    quals['form'].add(word)
            for word in fat_levels:
                if word in text:
                    quals['fat'].add(word)
            for word in colors:
                if re.search(r'\b' + re.escape(word) + r'\b', text):
                    quals['color'].add(word)
            for word in parts:
                if re.search(r'\b' + re.escape(word) + r'\b', text):
                    quals['part'].add(word)
            for word in varieties:
                if re.search(r'\b' + re.escape(word) + r'\b', text):
                    quals['variety'].add(word)
            for word in sweetness:
                if word in text:
                    quals['sweet'].add(word)
            for word in cuts:
                if word in text:
                    quals['cut'].add(word)

            return quals

        ing_qual = extract_qualifiers(ingredient)
        usda_qual = extract_qualifiers(usda_match)

        score = 100.0

        # Check each qualifier category
        for category in ['prep', 'form', 'fat', 'color', 'part', 'variety', 'sweet', 'cut']:
            ing_set = ing_qual[category]
            usda_set = usda_qual[category]

            if ing_set and usda_set:
                # Both specify qualifiers
                if ing_set & usda_set:
                    # Match found
                    score += 8
                else:
                    # Contradiction - penalize heavily
                    score -= 30
            elif len(ing_set) > 0 and len(usda_set) == 0:
                # Ingredient specifies, USDA doesn't - minor penalty
                score -= 3
            elif len(ing_set) == 0 and len(usda_set) > 0:
                # USDA specifies, ingredient doesn't - minor penalty
                score -= 3

        # Special case handling for specific contradictions

        # Drained vs with oil
        if 'drained' in ingredient and ('with oil' in usda_match or 'in oil' in usda_match):
            score -= 45

        # Sauce vs plain ingredient
        if 'sauce' in ingredient and 'sauce' not in usda_match:
            score -= 35
        elif 'sauce' not in ingredient and 'sauce' in usda_match:
            score -= 35

        # Pasta cooked state mismatch
        if 'pasta' in ingredient or 'pasta' in usda_match:
            ing_cooked = 'cooked' in ing_qual['prep']
            usda_cooked = 'cooked' in usda_qual['prep']
            if ing_cooked != usda_cooked:
                score -= 40

        # Patty vs non-patty
        if 'patty' in ingredient and 'patty' not in usda_match:
            score -= 25
        elif 'patty' not in ingredient and 'patty' in usda_match:
            score -= 25

        # Specific form contradictions
        if 'whole' in ingredient and ('diced' in usda_match or 'chopped' in usda_match):
            score -= 20

        # Reward exact matches of key terms
        ing_words = set(re.findall(r'\b\w+\b', ingredient))
        usda_words = set(re.findall(r'\b\w+\b', usda_match))
        common_words = ing_words & usda_words

        # Filter out common stopwords
        stopwords = {'with', 'from', 'the', 'and', 'or', 'of', 'in', 'to', 'a', 'an'}
        common_words = common_words - stopwords

        if len(common_words) >= 2:
            score += len(common_words) * 2

        # Normalize to 0-100 range
        score = max(0.0, min(100.0, score))

        return float(score)

    except Exception:
        return 50.0
