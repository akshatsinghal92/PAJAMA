"""Reserve ~100 core foods from the REAL data so generation never touches them (plan: 'Final check on real data')."""
import collections as C
import json
import re
import sys

from common import DATA, WORK, norm, strip_qty

FORM = {"fresh", "frozen", "canned", "jarred", "dried", "dry", "cooked", "raw", "diced", "chopped", "shredded",
        "minced", "sliced", "grated", "shaved", "ground", "toasted", "roasted", "smoked", "melted", "ripe", "thawed",
        "drained", "squeezed", "soaked", "peeled", "whole", "large", "small", "baby", "optional", "taste", "from",
        "tube", "cloves", "florets", "leaves", "fillet", "fillets", "segments", "kernels", "chunks", "and", "to",
        "sushi", "grade", "sharp", "mixed", "purple", "red", "green", "white", "yellow", "black", "extra", "virgin"}


def core_of(ingredient: str) -> str:
    toks = [t for t in norm(ingredient).split() if t not in FORM and not t.isdigit()]
    return " ".join(toks)


def build(n: int = 100) -> list[str]:
    cnt = C.Counter()
    for sp in ("val", "test"):
        for line in open(DATA / f"{sp}.jsonl"):
            r = json.loads(line)
            c = core_of(r["ingredient"])
            if c:
                cnt[c] += 1
    terms = [t for t, _ in cnt.most_common(n)]
    (WORK / "blocklist.json").write_text(json.dumps(terms, indent=1))
    return terms


def is_blocked(food: str, terms: list[str]) -> bool:
    """Blocked only when the food's CORE name (form/prep words stripped) equals a reserved real-data core.
    ('black pepper' -> 'pepper' is blocked; 'sweet potato' and 'rice noodles' are not blocked by 'potato'/'rice')."""
    c = core_of(food)
    return c in set(terms) or norm(food) in set(terms)


if __name__ == "__main__":
    t = build()
    print(len(t), "block terms:\n", ", ".join(t))
