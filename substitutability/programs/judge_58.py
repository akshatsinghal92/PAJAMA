import re
from collections import Counter

def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 50.0

        # Clean and normalize
        ing_lower = ingredient.lower().strip()
        usda_lower = usda_match.lower().strip()

        # Remove gram weights (e.g., "200g", "30 g")
        ing_clean = re.sub(r'\b\d+\s*g\b', '', ing_lower).strip()

        # Remove parentheticals from ingredient
        ing_clean = re.sub(r'\([^)]*\)', '', ing_clean).strip()

        # Split into words for analysis
        ing_words = set(re.findall(r'\b\w+\b', ing_clean))
        usda_words = set(re.findall(r'\b\w+\b', usda_lower))

        # Start with high base score (plain match assumed)
        score = 100.0

        # Define additive/processing keywords with severity weights
        # High severity: strong flavoring agents that change taste significantly
        high_severity = {
            'sauce', 'gravy', 'dressing', 'marinade', 'glazed', 'candied',
            'sweetened', 'sugared', 'honeyed', 'breaded', 'battered',
            'seasoned', 'spiced', 'flavored', 'blend'
        }

        # Medium severity: added fats/oils that change texture/taste
        medium_severity = {
            'fried', 'buttered', 'creamed', 'oiled'
        }

        # Low severity: processing that may add subtle taste
        low_severity = {
            'salted', 'smoked', 'roasted', 'toasted', 'processed'
        }

        # Detect phrases (multi-word patterns)
        high_severity_phrases = [
            'with oil', 'in oil', 'with butter', 'with salt',
            'with sugar', 'with sauce', 'and pepper'
        ]

        # Check for high severity additives in USDA but not in ingredient
        for keyword in high_severity:
            if keyword in usda_lower and keyword not in ing_clean:
                score -= 35.0

        # Check for medium severity
        for keyword in medium_severity:
            if keyword in usda_lower and keyword not in ing_clean:
                score -= 25.0

        # Check for low severity
        for keyword in low_severity:
            if keyword in usda_lower and keyword not in ing_clean:
                score -= 15.0

        # Check for additive phrases
        for phrase in high_severity_phrases:
            if phrase in usda_lower and phrase not in ing_clean:
                score -= 30.0

        # Bonus: Check if core food terms match
        # Extract core nouns (likely food items) by filtering out common modifiers
        modifiers = {
            'fresh', 'frozen', 'canned', 'dried', 'raw', 'cooked',
            'whole', 'diced', 'sliced', 'chopped', 'shredded',
            'ground', 'minced', 'crushed', 'peeled', 'drained',
            'uncooked', 'prepared', 'unprepared', 'thawed'
        }

        ing_core = ing_words - modifiers
        usda_core = usda_words - modifiers

        # Calculate word overlap (Jaccard similarity on core terms)
        if ing_core and usda_core:
            common = ing_core & usda_core
            union = ing_core | usda_core
            overlap_ratio = len(common) / len(union) if union else 0
            score += overlap_ratio * 20.0

        # Penalty for compound descriptors suggesting mixed ingredients
        compound_indicators = ['mix', 'combination', 'mixed', 'assorted', 'variety']
        for indicator in compound_indicators:
            if indicator in usda_lower and indicator not in ing_clean:
                score -= 20.0

        # Cap score between 0 and 100
        score = max(0.0, min(100.0, score))

        return score

    except Exception:
        return 50.0
