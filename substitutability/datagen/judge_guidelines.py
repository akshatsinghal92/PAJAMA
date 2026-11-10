"""Annotation guidelines appended AFTER the verbatim production prompt for the Haiku stand-in judge (v2).
Derived from an error analysis of 344 rows (gpt-oss-120b vs Haiku vs a blind reviewer).
Examples deliberately use foods that are NOT in the evaluation rows."""
GUIDELINES = """

ANNOTATION GUIDELINES (apply these when deciding the two conditions above)

A. Ignore the quantity. The leading weight (e.g. "5g") is decoration. Never accept a different food because
   "only a small amount is used", and never reject because the amount is large.

B. Same food under another name = substitutable. Before rejecting, ask: is this literally the same food?
   Regional / culinary / trade names count: aubergine -> Eggplant, raw; garbanzo beans -> Chickpeas;
   rocket -> Arugula, raw; prawns -> Shrimp, raw; littleneck or cherrystone clams -> Mollusks, clam, raw; courgette -> Squash, summer, zucchini; scallion -> Onions, spring.
   The inner part or a cut of the same vegetable sold as the same thing (celery hearts -> Celery, raw) also counts.

C. Read USDA wording correctly.
   - "mature seeds, raw" / "dry" for beans, peas and lentils IS the dried legume as bought (dried chickpeas -> Chickpeas, mature seeds, raw = yes).
   - "raw" means uncooked. Knife work or handling the recipe does itself (chopped, minced, sliced, cubed, halved,
     peeled, trimmed, shucked, stemmed, rinsed, chilled, room temperature, ground at home for meat or fish)
     does NOT change the match: finely chopped fresh jalapeno -> Peppers, jalapeno, raw = yes.
   - "unbaked"/"uncooked" ready-made products match their USDA product (unbaked puff pastry sheet -> Puff pastry, frozen, ready-to-bake = yes).
   - If the USDA entry names the same dish or product with the same components, it is a match even if USDA adds
     the standard descriptor (buttered peas and carrots -> Peas and carrots, cooked, fat added = yes).

D. Plain ingredient -> the standard default version = yes (milk -> Milk, whole; sour cream -> Sour cream, regular;
   cottage cheese -> Cheese, cottage, creamed). A plain ingredient -> a MODIFIED version = no: reduced/low/fat-free,
   reduced/low sodium, calcium reduced, lactose reduced, lite, sweetened/unsweetened, "with added solution/additives",
   flavoured. When the ingredient itself asks for that version, the matching modified entry = yes
   (low-sodium soy sauce -> Soy sauce, reduced sodium).
   BUT a descriptor is not a "modification" when it simply describes how that product is normally sold. Many products
   are normally low fat or normally treated: flavoured yogurts, frozen yogurt, yogurt parfaits and buttermilk are
   typically low fat; dried apricots and dried apple are typically sulfured; canned fruit is typically in syrup or juice.
   So strawberry yogurt -> Yogurt, strawberry, low fat = yes, and dried peaches -> Peaches, dehydrated, sulfured = yes.
   Only reject when the descriptor makes it differ from what a shopper would normally buy under the plain name.

E. Frozen and thawed: matches the fresh/raw entry when the food is normally cooked or mixed and freezing does not show
   (frozen peas, frozen shrimp, frozen berries for baking, frozen nuts, frozen cheese for cooking, frozen meat).
   It does not match when the thawed food would visibly differ where it is served fresh.
   A frozen product that is thawed -> the FROZEN USDA entry of the same product = yes (frozen mango chunks, thawed ->
   Mango, frozen). A USDA entry that names only the food, with no state at all (e.g. "Lychee"), is the generic food
   and matches fresh, thawed or plain versions of it.

F. These are NOT substitutable even though they look close:
   - a different cut of meat (pork belly vs pork loin; beef brisket vs beef chuck);
   - a different oil, fat, flour or sugar (sunflower oil vs canola oil; bread flour vs cake flour);
   - a sibling variety with a different taste (Fuji apple vs Granny Smith; navel orange vs blood orange);
   - a different ripeness or packing medium (ripe vs overripe; in syrup vs juice pack vs water pack);
   - a different state: raw vs cooked, fresh vs dried herb, whole vs ground spice, plain vs toasted/smoked/roasted;
   - a single ingredient vs a blend or product containing it (lard -> Shortening, lard and vegetable oil = no);
   - the raw plant/source vs the processed ingredient (gelatin powder vs pork skin; cornstarch vs corn);
   - industrial / food-service specialty fats and ingredients vs the home ingredient.

G. Brands: a branded entry of the same plain product type = yes (rolled oats -> QUAKER Old Fashioned Oats);
   a branded entry with an added flavour or modification = no.

Be consistent: the same pattern must get the same answer every time.
"""
