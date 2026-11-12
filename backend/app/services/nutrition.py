"""Personalised nutrition — a transparent constraint engine.

Priority order (higher never overridden by lower):
  1. Explicit doctor instructions (verified diet advice / consultation notes)   — hard constraints
  2. Allergies and diet preference (veg / egg / non-veg / vegan)                 — hard constraints
  3. Patient-confirmed conditions                                                — hard constraints
  4. Latest verified report findings                                             — safety blocks + soft preferences
  5. Age, activity, budget, cooking time                                         — soft preferences

Notably, high-protein foods are NOT recommended by default: they are blocked when kidney markers are
outside range or protein is restricted, unless the doctor explicitly advised high protein.
Every recommendation carries human-readable reasons, and every applied rule is stored on the plan.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FoodRecommendation, MedicalReport, NutritionPlan, PatientProfile, User

MEALS = ["breakfast", "lunch", "snack", "dinner"]
CATEGORIES = {
    "high_protein": "High protein", "diabetes_friendly": "Diabetes-friendly", "heart_healthy": "Heart-healthy", "low_sodium": "Low sodium",
    "vegetarian": "Vegetarian", "non_vegetarian": "Non-vegetarian", "budget_friendly": "Budget-friendly", "easy_to_cook": "Easy to cook",
}
CONDITION_RULES = {
    "diabetes": ["low_sugar"], "type 2 diabetes": ["low_sugar"], "prediabetes": ["low_sugar"], "hypertension": ["low_sodium"], "high blood pressure": ["low_sodium"],
    "heart disease": ["low_fat", "low_sodium"], "high cholesterol": ["low_fat"], "kidney disease": ["protein_restricted", "low_sodium"], "ckd": ["protein_restricted", "low_sodium"],
    "gout": ["low_purine"],
}
DIET_ALLOWED = {
    "vegan": {"vegan"}, "vegetarian": {"vegan", "vegetarian"}, "eggetarian": {"vegan", "vegetarian", "eggetarian"},
    "non_vegetarian": {"vegan", "vegetarian", "eggetarian", "non_vegetarian"},
}
ALLERGEN_ALIASES = {"milk": "dairy", "lactose": "dairy", "dairy": "dairy", "paneer": "dairy", "wheat": "gluten", "gluten": "gluten", "egg": "egg", "eggs": "egg",
                    "soy": "soy", "soya": "soy", "fish": "fish", "seafood": "fish", "peanut": "peanut", "peanuts": "peanut", "nuts": "nuts", "sesame": "sesame"}
RESTRICTION_LABELS = {
    "low_sodium": "Low salt", "low_sugar": "Low sugar", "low_fat": "Low fat", "high_fibre": "High fibre", "protein_restricted": "Protein restricted",
    "low_potassium": "Low potassium", "fluid_restricted": "Fluid restricted", "low_purine": "Low purine", "high_protein": "Higher protein",
}


def food_tags(f: FoodRecommendation) -> list[str]:
    tags = set(f.tags or [])
    if f.protein_g >= 12:
        tags.add("high_protein")
    if f.glycemic == "low" and f.fibre_g >= 4:
        tags.add("diabetes_friendly")
    if f.fat_g <= 12 and f.sodium_mg <= 450 and f.fibre_g >= 3:
        tags.add("heart_healthy")
    if f.sodium_mg <= 350:
        tags.add("low_sodium")
    if f.prep_minutes <= 20:
        tags.add("easy_to_cook")
    if f.cost_level == "low":
        tags.add("budget_friendly")
    tags.add("non_vegetarian" if f.diet == "non_vegetarian" else "vegetarian" if f.diet in ("vegan", "vegetarian") else "eggetarian")
    return sorted(tags)


def age_of(profile: PatientProfile | None) -> int | None:
    if not profile or not profile.date_of_birth:
        return None
    t = date.today()
    return t.year - profile.date_of_birth.year - ((t.month, t.day) < (profile.date_of_birth.month, profile.date_of_birth.day))


def derive_constraints(db: Session, user: User) -> dict:
    profile = db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id))
    hard: dict[str, str] = {}  # restriction -> source
    soft: dict[str, str] = {}
    blocks: dict[str, str] = {}
    notes: list[str] = []
    doctor = [e for e in (profile.doctor_diet_instructions if profile else []) or []]
    for e in doctor:
        if e.get("tag"):
            hard[e["tag"]] = f"Doctor's advice ({e.get('doctor') or 'your doctor'})"
    for cond in (profile.conditions if profile else []) or []:
        for tag in CONDITION_RULES.get(str(cond).lower().strip(), []):
            hard.setdefault(tag, f"Your condition: {cond}")
    latest = db.scalar(select(MedicalReport).where(MedicalReport.user_id == user.id).order_by(MedicalReport.report_date.desc().nulls_last()).limit(1))
    if latest:
        status = {p.canonical_name: p.status for p in latest.parameters}
        label = f"Your report ({latest.report_date or latest.title})"
        if status.get("hba1c") == "high" or status.get("fasting_glucose") == "high" or status.get("pp_glucose") == "high":
            soft.setdefault("low_sugar", f"{label}: blood sugar above range")
        if any(status.get(k) == "high" for k in ("ldl", "total_cholesterol", "triglycerides")) or status.get("hdl") == "low":
            soft.setdefault("low_fat", f"{label}: cholesterol outside range")
        if status.get("creatinine") == "high" or status.get("urea") == "high" or status.get("egfr") == "low":
            if "high_protein" not in hard:
                blocks["high_protein"] = f"{label}: kidney markers outside range — high-protein foods are not suggested. Ask your doctor about protein."
        if status.get("potassium") == "high":
            blocks["high_potassium"] = f"{label}: potassium above range — high-potassium foods are not suggested."
        if status.get("uric_acid") == "high":
            soft.setdefault("low_purine", f"{label}: uric acid above range")
        if status.get("hemoglobin") == "low":
            notes.append("Your haemoglobin was low — iron-rich foods like spinach, dal and jaggery-free chikki may help; ask your doctor about supplements.")
    if "protein_restricted" in hard:
        blocks["high_protein"] = hard["protein_restricted"]
    if "low_potassium" in hard:
        blocks["high_potassium"] = hard["low_potassium"]
    age = age_of(profile)
    if age and age >= 60:
        notes.append("Softer, easy-to-cook meals are preferred for comfort and digestion.")
    allergies = {ALLERGEN_ALIASES.get(a.lower().strip(), a.lower().strip()) for a in (profile.allergies if profile else []) or []}
    return {"hard": hard, "soft": {k: v for k, v in soft.items() if k not in hard}, "blocks": blocks, "allergies": sorted(allergies),
            "diet": profile.food_preference if profile else "vegetarian", "age": age, "activity": profile.activity_level if profile else "light",
            "budget": profile.budget_preference if profile else "moderate", "notes": notes,
            "doctor_instructions": [e["text"] for e in doctor if e.get("text")]}


def passes(f: FoodRecommendation, c: dict) -> tuple[bool, str | None]:
    if f.diet not in DIET_ALLOWED.get(c["diet"], DIET_ALLOWED["vegetarian"]):
        return False, "diet preference"
    if set(f.allergens or []) & set(c["allergies"]):
        return False, "allergy"
    h = c["hard"]
    if "low_sodium" in h and f.sodium_mg > 450:
        return False, "doctor/condition: low salt"
    if "low_sugar" in h and f.glycemic == "high":
        return False, "low sugar"
    if "low_fat" in h and f.fat_g > 16:
        return False, "low fat"
    if "low_purine" in h and f.diet == "non_vegetarian":
        return False, "low purine"
    if "high_protein" in c["blocks"] and f.protein_g >= 20:
        return False, "protein caution"
    if "high_potassium" in c["blocks"] and (f.potassium_mg or 0) > 400:
        return False, "potassium caution"
    return True, None


def score(f: FoodRecommendation, c: dict) -> tuple[float, list[str]]:
    tags = food_tags(f)
    s, reasons = 1.0, []
    all_r = {**c["hard"], **c["soft"]}
    if "low_sugar" in all_r and "diabetes_friendly" in tags:
        s += 2 if "low_sugar" in c["hard"] else 1.2
        reasons.append(f"Low glycemic, high fibre — {all_r['low_sugar']}")
    if "low_sodium" in all_r and f.sodium_mg <= 350:
        s += 2
        reasons.append(f"Low in salt ({int(f.sodium_mg)} mg sodium) — {all_r['low_sodium']}")
    if "low_fat" in all_r and "heart_healthy" in tags:
        s += 1.5
        reasons.append(f"Heart-healthy, low fat — {all_r['low_fat']}")
    if "high_fibre" in all_r and f.fibre_g >= 6:
        s += 1.2
        reasons.append(f"High fibre ({f.fibre_g:g} g) — {all_r['high_fibre']}")
    if "high_protein" in c["hard"] and f.protein_g >= 12:
        s += 1.5
        reasons.append(f"Good protein ({f.protein_g:g} g) — {c['hard']['high_protein']}")
    if c.get("age") and c["age"] >= 60 and f.prep_minutes <= 25:
        s += 0.5
        reasons.append("Easy to prepare")
    if c["budget"] == "low" and f.cost_level == "low":
        s += 0.5
        reasons.append("Budget-friendly")
    if not reasons:
        reasons.append("Balanced home-style option that fits your preferences")
    return s, reasons


def estimate_targets(db: Session, user: User, c: dict) -> dict:
    profile = db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id))
    out: dict = {"basis": "estimate", "fibre_g": "25–30", "note": "Estimates only — your doctor or dietitian may set different targets."}
    if profile and profile.weight_kg and profile.height_cm and c.get("age"):
        male = (profile.gender or "").lower().startswith("m")
        bmr = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * c["age"] + (5 if male else -161)
        factor = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725}.get(c.get("activity") or "light", 1.375)
        kcal = round(bmr * factor / 50) * 50
        out["calories"] = f"{kcal - 150}–{kcal + 150}"
        if "high_protein" in c["blocks"] or "protein_restricted" in c["hard"]:
            out["protein_g"] = "As advised by your doctor"
        else:
            out["protein_g"] = f"{round(profile.weight_kg * 0.8)}–{round(profile.weight_kg * 1.0)}"
    if "low_sodium" in c["hard"] or "low_sodium" in c["soft"]:
        out["sodium_mg"] = "Below 2000 (or as your doctor advised)"
    return out


def recommendations(db: Session, user: User, meal: str | None = None, category: str | None = None) -> dict:
    c = derive_constraints(db, user)
    foods = db.scalars(select(FoodRecommendation).where((FoodRecommendation.user_id.is_(None)) | (FoodRecommendation.user_id == user.id))).all()
    items, excluded = [], []
    for f in foods:
        ok, why = passes(f, c)
        if not ok:
            excluded.append({"slug": f.slug, "name": f.name, "reason": why})
            continue
        if meal and meal not in f.meal_types:
            continue
        tags = food_tags(f)
        if category and category not in tags:
            continue
        s, reasons = score(f, c)
        items.append({"food": f, "score": s, "reasons": reasons, "tags": tags})
    items.sort(key=lambda x: (-x["score"], x["food"].name))
    return {"constraints": c, "items": items, "excluded": excluded}


def generate_plan(db: Session, user: User, week_start: date | None = None) -> NutritionPlan:
    week_start = week_start or (date.today() - timedelta(days=date.today().weekday()))
    rec = recommendations(db, user)
    c = rec["constraints"]
    by_meal = {m: [i for i in rec["items"] if m in i["food"].meal_types] for m in MEALS}
    days = []
    for d in range(7):
        day = {"date": (week_start + timedelta(days=d)).isoformat(), "meals": {}}
        for m in MEALS:
            pool = by_meal[m]
            if not pool:
                day["meals"][m] = []
                continue
            top = pool[: max(3, min(6, len(pool)))]
            pick = top[(d * 2 + MEALS.index(m)) % len(top)]
            day["meals"][m] = [pick["food"].id]
        days.append(day)
    for p in db.scalars(select(NutritionPlan).where(NutritionPlan.user_id == user.id, NutritionPlan.is_active.is_(True))):
        p.is_active = False
    plan = NutritionPlan(user_id=user.id, week_start=week_start, generated_by="constraint-engine-v1", days=days, targets=estimate_targets(db, user, c),
                         constraints={"hard": c["hard"], "soft": c["soft"], "blocks": c["blocks"], "allergies": c["allergies"], "diet": c["diet"],
                                      "notes": c["notes"], "doctor_instructions": c["doctor_instructions"], "excluded_count": len(rec["excluded"])})
    db.add(plan)
    db.flush()
    return plan


def serialize_food(f: FoodRecommendation, reasons: list[str] | None = None, lang: str = "en") -> dict:
    return {"id": f.id, "slug": f.slug, "name": f.name, "name_hi": f.name_hi, "description": f.description, "meal_types": f.meal_types, "diet": f.diet,
            "tags": food_tags(f), "allergens": f.allergens, "calories": f.calories, "protein_g": f.protein_g, "carbs_g": f.carbs_g, "fat_g": f.fat_g,
            "fibre_g": f.fibre_g, "sodium_mg": f.sodium_mg, "potassium_mg": f.potassium_mg, "glycemic": f.glycemic, "cost_level": f.cost_level,
            "prep_minutes": f.prep_minutes, "serving": f.serving, "ingredients": f.ingredients, "steps": f.steps, "substitutions": f.substitutions,
            "image_url": f.image_url, "reasons": reasons or []}
