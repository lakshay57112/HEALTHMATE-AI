from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_patient
from app.db.session import get_db
from app.models import FoodRecommendation, NutritionPlan, User
from app.services import nutrition

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


def _active_plan(db: Session, user: User) -> NutritionPlan:
    plan = db.scalar(select(NutritionPlan).where(NutritionPlan.user_id == user.id, NutritionPlan.is_active.is_(True)).order_by(NutritionPlan.created_at.desc()))
    if not plan:
        plan = nutrition.generate_plan(db, user)
        db.commit()
    return plan


def _expand_plan(db: Session, user: User, plan: NutritionPlan) -> dict:
    rec = nutrition.recommendations(db, user)
    reasons = {i["food"].id: i["reasons"] for i in rec["items"]}
    ids = {fid for d in plan.days for ids in d["meals"].values() for fid in ids}
    foods = {f.id: f for f in db.scalars(select(FoodRecommendation).where(FoodRecommendation.id.in_(ids)))} if ids else {}
    days = []
    for d in plan.days:
        meals = {m: [nutrition.serialize_food(foods[i], reasons.get(i)) for i in ids_ if i in foods] for m, ids_ in d["meals"].items()}
        totals = {k: round(sum(f[k] for fs in meals.values() for f in fs), 1) for k in ("calories", "protein_g", "carbs_g", "fat_g", "fibre_g", "sodium_mg")}
        days.append({"date": d["date"], "meals": meals, "totals": totals})
    return {"id": plan.id, "week_start": plan.week_start.isoformat(), "generated_by": plan.generated_by, "constraints": plan.constraints, "targets": plan.targets,
            "days": days, "created_at": plan.created_at.isoformat()}


@router.get("/overview")
def overview(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    plan = _expand_plan(db, user, _active_plan(db, user))
    today = date.today().isoformat()
    today_plan = next((d for d in plan["days"] if d["date"] == today), plan["days"][0] if plan["days"] else None)
    labels = nutrition.RESTRICTION_LABELS
    c = plan["constraints"]
    rules = [{"tag": k, "label": labels.get(k, k), "source": v, "kind": "doctor" if v.startswith("Doctor") else "condition"} for k, v in c.get("hard", {}).items()]
    rules += [{"tag": k, "label": labels.get(k, k), "source": v, "kind": "report"} for k, v in c.get("soft", {}).items()]
    rules += [{"tag": k, "label": "Caution", "source": v, "kind": "safety"} for k, v in c.get("blocks", {}).items()]
    return {"today": today_plan, "rules": rules, "targets": plan["targets"], "doctor_instructions": c.get("doctor_instructions", []), "notes": c.get("notes", []),
            "allergies": c.get("allergies", []), "diet": c.get("diet"), "categories": nutrition.CATEGORIES, "plan_id": plan["id"]}


@router.get("/recommendations")
def recommendations(meal: Literal["breakfast", "lunch", "snack", "dinner"] | None = None, category: str | None = None, q: str | None = None,
                    user: User = Depends(require_patient), db: Session = Depends(get_db)):
    rec = nutrition.recommendations(db, user, meal=meal, category=category)
    items = [nutrition.serialize_food(i["food"], i["reasons"]) for i in rec["items"]]
    if q:
        items = [i for i in items if q.lower() in i["name"].lower() or q.lower() in (i["name_hi"] or "")]
    return {"items": items, "excluded": rec["excluded"], "categories": nutrition.CATEGORIES}


@router.get("/foods/{food_id}")
def food_detail(food_id: str, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    f = db.get(FoodRecommendation, food_id)
    if not f or (f.user_id and f.user_id != user.id):
        raise HTTPException(404, "Food not found")
    rec = nutrition.recommendations(db, user)
    match = next((i for i in rec["items"] if i["food"].id == f.id), None)
    excluded = next((e for e in rec["excluded"] if e["slug"] == f.slug), None)
    return {"food": nutrition.serialize_food(f, match["reasons"] if match else []), "suitable": match is not None,
            "not_suitable_reason": excluded["reason"] if excluded else None}


@router.get("/plan")
def get_plan(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return {"plan": _expand_plan(db, user, _active_plan(db, user))}


@router.post("/plan/regenerate")
def regenerate(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    plan = nutrition.generate_plan(db, user)
    db.commit()
    return {"plan": _expand_plan(db, user, plan)}


class SwapIn(BaseModel):
    date: str
    meal: Literal["breakfast", "lunch", "snack", "dinner"]
    food_id: str


@router.put("/plan/swap")
def swap(body: SwapIn, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    plan = _active_plan(db, user)
    rec = nutrition.recommendations(db, user, meal=body.meal)
    if body.food_id not in {i["food"].id for i in rec["items"]}:
        raise HTTPException(400, "That food doesn't fit your current dietary rules")
    days = [dict(d, meals=dict(d["meals"])) for d in plan.days]
    for d in days:
        if d["date"] == body.date:
            d["meals"][body.meal] = [body.food_id]
            break
    else:
        raise HTTPException(404, "Day not in plan")
    plan.days = days
    db.commit()
    return {"plan": _expand_plan(db, user, plan)}
