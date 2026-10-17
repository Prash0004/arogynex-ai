"""Transparent rule-based nutrition engine.

IMPORTANT: nutrient values are intentionally left as None ("Nutritional data unavailable").
Fill them from a verified source such as ICMR-NIN IFCT 2017 before using them.
Costs are ILLUSTRATIVE placeholders (INR per serving) - replace with local market prices.
"""
FOODS = [
    # name, group, veg, allergens, cost_inr, meal slots
    ("Rice (cooked)", "cereal", True, [], 6, ["lunch", "dinner"]),
    ("Whole-wheat roti", "cereal", True, ["gluten"], 4, ["breakfast", "lunch", "dinner"]),
    ("Ragi / millet porridge", "cereal", True, [], 5, ["breakfast"]),
    ("Poha with vegetables", "cereal", True, [], 8, ["breakfast", "snack"]),
    ("Dal (lentils)", "pulse", True, [], 10, ["lunch", "dinner"]),
    ("Chana (chickpeas)", "pulse", True, [], 9, ["snack", "lunch"]),
    ("Seasonal vegetable sabzi", "vegetable", True, [], 8, ["lunch", "dinner"]),
    ("Leafy greens (saag)", "vegetable", True, [], 5, ["lunch", "dinner"]),
    ("Seasonal fruit (banana/guava)", "fruit", True, [], 8, ["breakfast", "snack"]),
    ("Curd", "dairy", True, ["milk"], 8, ["lunch", "snack"]),
    ("Milk", "dairy", True, ["milk"], 12, ["breakfast", "snack"]),
    ("Egg (boiled)", "egg", False, ["egg"], 7, ["breakfast", "snack", "dinner"]),
    ("Fish curry", "fish", False, ["fish"], 25, ["lunch", "dinner"]),
    ("Roasted peanuts", "nuts", True, ["peanut"], 6, ["snack"]),
]
SLOTS = ["breakfast", "lunch", "snack", "dinner"]
# plate-balance rule: each meal should cover these groups when possible (priority order)
SLOT_GROUPS = {
    "breakfast": ["cereal", "fruit", "dairy", "egg"],
    "lunch": ["cereal", "pulse", "vegetable", "dairy"],
    "snack": ["fruit", "pulse", "nuts", "egg"],
    "dinner": ["cereal", "vegetable", "pulse", "egg"],
}
WHY = {
    "cereal": "Main energy source; prefer whole grains / millets where available.",
    "pulse": "Plant protein and fibre; affordable and widely available.",
    "vegetable": "Vitamins, minerals and fibre; include leafy greens often.",
    "fruit": "Vitamins and fibre; choose what is in season.",
    "dairy": "Protein and calcium where suitable.",
    "egg": "Protein source where suitable and available.",
    "fish": "Protein source where suitable and available.",
    "nuts": "Energy-dense snack; check for allergy first.",
}
REFER = ["diabetes", "kidney disease", "pregnancy", "eating disorder", "severe allergy"]


def recommend(vegetarian=True, allergies=(), available_groups=None, budget_per_day=60,
              excluded=(), conditions=()):
    allergies = {a.strip().lower() for a in allergies if a.strip()}
    excluded = {e.lower() for e in excluded}
    refer = [c for c in conditions if c.lower() in REFER]
    if refer:
        return {"referral": True, "message": "Because of: " + ", ".join(refer) +
                " - please consult a qualified doctor or dietitian. No diet plan generated.",
                "plan": {}, "total_cost": None}

    def ok(f):
        name, group, veg, alg, cost, _ = f
        if vegetarian and not veg: return False
        if allergies & {a.lower() for a in alg}: return False
        if name.lower() in excluded: return False
        if available_groups is not None and group not in available_groups: return False
        return True

    pool = [f for f in FOODS if ok(f)]
    plan, total, used = {}, 0.0, set()
    for slot in SLOTS:
        items = []
        for g in SLOT_GROUPS[slot]:
            cands = sorted([f for f in pool if f[1] == g and slot in f[5]], key=lambda f: (f[0] in used, f[4]))
            if not cands: continue
            pick = cands[0]
            if total + pick[4] > budget_per_day: continue
            alts = [c[0] for c in cands[1:3]]
            items.append({"food": pick[0], "group": g, "cost_inr": pick[4], "why": WHY[g],
                          "alternatives": alts, "nutrients": "Nutritional data unavailable",
                          "portion": "Portion guidance unavailable - use a validated reference"})
            used.add(pick[0]); total += pick[4]
        plan[slot] = items
    warnings = []
    if not pool: warnings.append("No foods match the constraints.")
    if total >= budget_per_day: warnings.append("Budget limit reached; some meal groups were skipped.")
    return {"referral": False, "plan": plan, "total_cost": total, "budget": budget_per_day,
            "eligible_foods": len(pool), "warnings": warnings,
            "disclaimer": "General healthy-eating suggestion only, not medical advice."}
