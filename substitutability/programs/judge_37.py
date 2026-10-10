import re
import math

def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient).lower().strip()
        usda = str(usda_match).lower().strip()

        if not ing or not usda:
            return 0.0

        # Remove gram weights and parentheticals
        ing = re.sub(r'^\d+g?\s+', '', ing)
        ing = re.sub(r'\([^)]*\)', '', ing).strip()
        usda = re.sub(r'\([^)]*\)', '', usda).strip()

        # Define specificity marker categories with different weights
        state_markers = {'frozen', 'canned', 'fresh', 'dried', 'raw', 'cooked', 'thawed', 'drained'}
        form_markers = {'whole', 'diced', 'sliced', 'shredded', 'ground', 'chopped', 'crushed', 'minced', 'penne'}
        quality_markers = {'extra', 'virgin', 'refined', 'organic', 'low', 'reduced', 'fat'}
        type_markers = {'sauce', 'paste', 'powder', 'concentrate', 'tube', 'balsamic', 'cherry', 'table'}

        all_markers = state_markers | form_markers | quality_markers | type_markers

        # Tokenize
        ing_tokens = set(re.findall(r'\b\w+\b', ing))
        usda_tokens = set(re.findall(r'\b\w+\b', usda))

        # Extract markers by category
        def get_category_markers(tokens):
            return {
                'state': tokens & state_markers,
                'form': tokens & form_markers,
                'quality': tokens & quality_markers,
                'type': tokens & type_markers
            }

        ing_cats = get_category_markers(ing_tokens)
        usda_cats = get_category_markers(usda_tokens)

        # Count total specificity
        ing_spec_count = sum(len(v) for v in ing_cats.values())
        usda_spec_count = sum(len(v) for v in usda_cats.values())

        # Compute specificity score using geometric approach
        base_score = 65.0

        # Case 1: Ingredient is unqualified (generic)
        if ing_spec_count == 0:
            if usda_spec_count == 0:
                # Both generic - perfect alignment
                base_score += 35.0
            else:
                # USDA adds qualifiers - penalize exponentially by count
                penalty = 40.0 * (1.0 - math.exp(-0.8 * usda_spec_count))
                base_score -= penalty

        # Case 2: Ingredient has qualifiers
        else:
            # Category-weighted matching
            category_weights = {'state': 3.0, 'form': 2.5, 'quality': 1.5, 'type': 2.8}

            match_score = 0.0
            max_possible = 0.0

            for cat, weight in category_weights.items():
                ing_cat = ing_cats[cat]
                usda_cat = usda_cats[cat]

                if ing_cat:
                    max_possible += len(ing_cat) * weight
                    common = ing_cat & usda_cat
                    match_score += len(common) * weight

                    # Heavy penalty for missing ingredient markers
                    missing = ing_cat - usda_cat
                    base_score -= len(missing) * weight * 8.0

                # Moderate penalty for USDA adding markers not in ingredient
                usda_extra = usda_cat - ing_cat
                if usda_extra:
                    base_score -= len(usda_extra) * weight * 4.5

            # Reward proportional match
            if max_possible > 0:
                match_ratio = match_score / max_possible
                base_score += match_ratio * 30.0

        # Token overlap bonus (basic lexical similarity)
        common_tokens = ing_tokens & usda_tokens
        if ing_tokens:
            overlap_ratio = len(common_tokens) / len(ing_tokens)
            base_score += overlap_ratio * 10.0

        # Check for critical state conflicts (e.g., raw vs cooked)
        ing_state = ing_tokens & state_markers
        usda_state = usda_tokens & state_markers

        conflict_pairs = [
            ({'raw'}, {'cooked'}),
            ({'frozen'}, {'fresh'}),
            ({'drained'}, {'cooked with oil', 'oil'})
        ]

        for ing_set, usda_set in conflict_pairs:
            if ing_state & ing_set and usda_state & usda_set:
                base_score -= 35.0

        # Specificity disparity penalty (logarithmic)
        if ing_spec_count > 0 and usda_spec_count > 0:
            disparity = abs(ing_spec_count - usda_spec_count)
            if disparity > 0:
                disparity_penalty = 8.0 * math.log1p(disparity)
                base_score -= disparity_penalty

        # Clamp to 0-100 range
        return max(0.0, min(100.0, base_score))

    except Exception:
        return 50.0
