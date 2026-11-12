"""Demo data. Every clinical value created here is flagged `is_sample=True` and shown as SAMPLE DATA in the UI.

Usage:  python -m app.seed            (food catalog + demo accounts)
        python -m app.seed --reset    (drop demo accounts first)
"""
from __future__ import annotations

import random
import sys
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    Appointment,
    CaregiverConnection,
    FoodRecommendation,
    HealthMeasurement,
    MealSchedule,
    MedicalReport,
    MedicineLog,
    PatientProfile,
    Prescription,
    PrescriptionMedicine,
    ReminderSettings,
    ReportParameter,
    User,
)
from app.seed_data.foods import FOOD_IMAGES, FOODS
from app.services import rag, reports, scheduling, timeutil
from app.services.consent import DEFAULT_PERMISSIONS, record_consent
from app.services.medical_knowledge import canonicalize
from app.services.notify import create_notification
from app.services.nutrition import generate_plan

DEMO_PATIENT = "demo.patient@healthmate.app"
DEMO_CAREGIVER = "demo.caregiver@healthmate.app"
DEMO_PASSWORD = "demo1234"


def ensure_catalog(db: Session) -> int:
    existing = {f.slug: f for f in db.scalars(select(FoodRecommendation).where(FoodRecommendation.user_id.is_(None)))}
    n = 0
    for (slug, name, name_hi, meals, diet, cost, prep, serving, nut, gi, allergens, desc, ingredients, steps, subs) in FOODS:
        kcal, p, c, f, fib, na, k = nut
        row = existing.get(slug) or FoodRecommendation(slug=slug)
        row.name, row.name_hi, row.meal_types, row.diet, row.cost_level, row.prep_minutes, row.serving = name, name_hi, meals, diet, cost, prep, serving
        row.calories, row.protein_g, row.carbs_g, row.fat_g, row.fibre_g, row.sodium_mg, row.potassium_mg, row.glycemic = kcal, p, c, f, fib, na, k, gi
        row.allergens, row.description, row.ingredients, row.steps, row.substitutions, row.tags = allergens, desc, ingredients, steps, subs, []
        row.image_url = FOOD_IMAGES.get(slug)
        if slug not in existing:
            db.add(row)
            n += 1
    db.flush()
    return n


SAMPLE_REPORTS = [
    ("Diabetes & Lipid Profile", date.today() - timedelta(days=140), "CityCare Diagnostics, Lucknow", [
        ("Diabetes", "HbA1c", "8.1", "%", "4.0 - 5.6"), ("Diabetes", "Fasting Blood Sugar", "156", "mg/dL", "70 - 100"),
        ("Lipid Profile", "Total Cholesterol", "232", "mg/dL", "< 200"), ("Lipid Profile", "LDL Cholesterol", "158", "mg/dL", "< 100"),
        ("Lipid Profile", "HDL Cholesterol", "41", "mg/dL", "> 40"), ("Lipid Profile", "Triglycerides", "190", "mg/dL", "< 150"),
        ("Kidney Function", "Serum Creatinine", "1.0", "mg/dL", "0.7 - 1.3"), ("Haematology", "Haemoglobin", "12.6", "g/dL", "13.0 - 17.0"),
    ]),
    ("Diabetes & Lipid Profile", date.today() - timedelta(days=21), "CityCare Diagnostics, Lucknow", [
        ("Diabetes", "HbA1c", "7.4", "%", "4.0 - 5.6"), ("Diabetes", "Fasting Blood Sugar", "138", "mg/dL", "70 - 100"),
        ("Lipid Profile", "Total Cholesterol", "214", "mg/dL", "< 200"), ("Lipid Profile", "LDL Cholesterol", "132", "mg/dL", "< 100"),
        ("Lipid Profile", "HDL Cholesterol", "44", "mg/dL", "> 40"), ("Lipid Profile", "Triglycerides", "162", "mg/dL", "< 150"),
        ("Kidney Function", "Serum Creatinine", "1.1", "mg/dL", "0.7 - 1.3"), ("Haematology", "Haemoglobin", "13.2", "g/dL", "13.0 - 17.0"),
        ("Thyroid", "TSH", "3.2", "µIU/mL", "0.4 - 4.0"), ("Vitamins", "Vitamin D (25-OH)", "18", "ng/mL", "30 - 100"),
    ]),
]

SAMPLE_MEDS = [
    dict(name="Metformin", brand_name="Glycomet", generic_name="Metformin", form="tablet", strength="500mg", dosage="1 tablet", frequency="1-0-1", slots=["morning", "night"],
         meal_relation="after_meal", duration_days=90, stock_count=46, instructions=None),
    dict(name="Telmisartan", brand_name="Telma", generic_name="Telmisartan", form="tablet", strength="40mg", dosage="1 tablet", frequency="1-0-0", slots=["morning"],
         meal_relation="any", duration_days=90, stock_count=4, instructions="Take at the same time every day"),
    dict(name="Atorvastatin", brand_name="Atorva", generic_name="Atorvastatin", form="tablet", strength="10mg", dosage="1 tablet", frequency="0-0-1", slots=["night"],
         meal_relation="after_meal", duration_days=90, stock_count=30, instructions=None),
    dict(name="Calcium + Vitamin D3", brand_name="Shelcal", generic_name="Calcium + Vitamin D3", form="tablet", strength="500mg", dosage="1 tablet", frequency="0-1-0",
         slots=["afternoon"], meal_relation="after_meal", duration_days=60, stock_count=25, instructions=None),
]


def _delete_demo(db: Session) -> None:
    for email in (DEMO_PATIENT, DEMO_CAREGIVER):
        u = db.scalar(select(User).where(User.email == email))
        if u:
            db.query(CaregiverConnection).filter((CaregiverConnection.patient_user_id == u.id) | (CaregiverConnection.caregiver_user_id == u.id)).delete()
            db.delete(u)
    db.flush()


def seed_demo(db: Session) -> None:
    ensure_catalog(db)
    if db.scalar(select(User).where(User.email == DEMO_PATIENT)):
        return
    rnd = random.Random(42)
    tzname = "Asia/Kolkata"
    pt = User(email=DEMO_PATIENT, password_hash=hash_password(DEMO_PASSWORD), full_name="Ramesh Kumar", role="patient", language="en", is_demo=True)
    cg = User(email=DEMO_CAREGIVER, password_hash=hash_password(DEMO_PASSWORD), full_name="Priya Kumar", role="caregiver", language="en", is_demo=True)
    db.add_all([pt, cg])
    db.flush()
    db.add(PatientProfile(user_id=pt.id, date_of_birth=date(1957, 8, 15), gender="male", phone="+91 98765 43210", blood_group="B+", height_cm=168, weight_kg=74,
                          timezone=tzname, conditions=["Type 2 diabetes", "Hypertension"], allergies=["Peanuts"], food_preference="vegetarian", activity_level="light",
                          budget_preference="moderate", emergency_contact_name="Priya Kumar (daughter)", emergency_contact_phone="+91 91234 56789", onboarding_complete=True,
                          doctor_diet_instructions=[
                              {"text": "Reduce salt — avoid pickles, papad and packaged namkeen", "doctor": "Dr. Anjali Mehta", "date": (date.today() - timedelta(days=21)).isoformat()},
                              {"text": "Avoid sweets and sugary drinks", "doctor": "Dr. Anjali Mehta", "date": (date.today() - timedelta(days=21)).isoformat()},
                              {"text": "Walk 30 minutes daily after dinner", "doctor": "Dr. Anjali Mehta", "date": (date.today() - timedelta(days=21)).isoformat()},
                              {"tag": "low_sodium", "doctor": "Dr. Anjali Mehta", "date": (date.today() - timedelta(days=21)).isoformat()},
                              {"tag": "low_sugar", "doctor": "Dr. Anjali Mehta", "date": (date.today() - timedelta(days=21)).isoformat()},
                          ]))
    db.add(ReminderSettings(user_id=pt.id, voice_language="hi-IN"))
    for meal, t in {"breakfast": "08:30", "lunch": "13:00", "snack": "17:00", "dinner": "20:30"}.items():
        db.add(MealSchedule(user_id=pt.id, meal=meal, time_of_day=t))
    record_consent(db, pt.id, "terms", True)
    record_consent(db, pt.id, "ai_processing", True, scope={"documents": True, "assistant": True})
    record_consent(db, cg.id, "terms", True)
    db.flush()

    for title, rdate, lab, params in SAMPLE_REPORTS:
        rpt = MedicalReport(user_id=pt.id, title=title, report_date=rdate, lab_name=lab, is_sample=True)
        db.add(rpt)
        for i, (grp, name, val, unit, ref) in enumerate(params):
            from app.services.extraction.rules import parse_range

            lo, hi = parse_range(ref)
            v = float(val)
            rpt.parameters.append(ReportParameter(user_id=pt.id, position=i, test_group=grp, name=name, canonical_name=canonicalize(name), value=v, value_text=val,
                                                  unit=unit, ref_low=lo, ref_high=hi, ref_text=ref, status=reports.compute_status(v, lo, hi), report_date=rdate))
        db.flush()
        rpt.summary = reports.build_summary(rpt)
        rag.index_chunks(db, pt.id, document_id=None, source_type="report", label=f"{title} ({rdate}) [sample]", texts=reports.fact_lines(rpt), verified=True, replace=False)

    start = date.today() - timedelta(days=21)
    rx = Prescription(user_id=pt.id, doctor_name="Dr. Anjali Mehta", clinic="Mehta Diabetes & Heart Clinic", prescribed_date=start, status="verified",
                      notes="Review after 4 weeks with fasting sugar report", verified_at=timeutil.now_utc())
    db.add(rx)
    db.flush()
    colors = ["#4D8B73", "#E9AA53", "#6C8EBF", "#9B7BB8"]
    meds = []
    for i, m in enumerate(SAMPLE_MEDS):
        med = PrescriptionMedicine(user_id=pt.id, prescription_id=rx.id, source="prescription", verified=True, start_date=start,
                                   end_date=start + timedelta(days=m["duration_days"] - 1), color=colors[i], refill_threshold=5, **m)
        db.add(med)
        db.flush()
        for sch in scheduling.regenerate_schedules(db, med):
            sch.created_at = timeutil.local_dt(start, "00:00", tzname)
        meds.append(med)
    rag.index_chunks(db, pt.id, document_id=None, source_type="prescription", label=f"Prescription {start} [sample]", replace=False, verified=True,
                     texts=["Verified prescription from Dr. Anjali Mehta (Mehta Diabetes & Heart Clinic).\n" + "\n".join(
                         f"{m.name} {m.strength} — {m.dosage} {m.frequency}, {m.meal_relation.replace('_', ' ')}" for m in meds) + "\nDoctor notes: Review after 4 weeks with fasting sugar report."])
    rag.index_chunks(db, pt.id, document_id=None, source_type="diet", label="Doctor's diet advice [sample]", replace=False, verified=True,
                     texts=["Doctor's diet advice from Dr. Anjali Mehta:\n- Reduce salt — avoid pickles, papad and packaged namkeen\n- Avoid sweets and sugary drinks\n- Walk 30 minutes daily after dinner"])

    # Medicine logs for the past 7 days (mostly taken, a few missed) — sample history
    tz = timeutil.tz_for(tzname)
    now = timeutil.now_utc()
    for d in range(7, 0, -1):
        day = date.today() - timedelta(days=d)
        for med in meds:
            for s in med.schedules:
                planned = timeutil.local_dt(day, s.time_of_day, tzname)
                status = "taken" if rnd.random() > 0.12 else rnd.choice(["missed", "skipped"])
                db.add(MedicineLog(schedule_id=s.id, medicine_id=med.id, user_id=pt.id, scheduled_for=planned, status=status,
                                   acted_at=planned + timedelta(minutes=rnd.randint(0, 25)) if status != "missed" else None, actor_user_id=pt.id))
    # Today: doses already past are marked taken (except one left for the demo)
    for med in meds:
        for s in med.schedules:
            planned = timeutil.local_dt(date.today(), s.time_of_day, tzname)
            if planned < now - timedelta(minutes=90) and med.name != "Telmisartan":
                db.add(MedicineLog(schedule_id=s.id, medicine_id=med.id, user_id=pt.id, scheduled_for=planned, status="taken", acted_at=planned + timedelta(minutes=5), actor_user_id=pt.id))

    # Sample measurements (14 days)
    for d in range(14, -1, -1):
        when = datetime.combine(date.today() - timedelta(days=d), time(7, 30), tzinfo=tz).astimezone(timezone.utc)
        if when > now:
            when = now - timedelta(minutes=30)
        db.add(HealthMeasurement(user_id=pt.id, kind="blood_pressure", value=rnd.randint(128, 142), value2=rnd.randint(80, 90), unit="mmHg", context="resting", measured_at=when, source="sample", is_sample=True))
        db.add(HealthMeasurement(user_id=pt.id, kind="glucose", value=rnd.randint(118, 152), unit="mg/dL", context="fasting", measured_at=when + timedelta(minutes=5), source="sample", is_sample=True))
        db.add(HealthMeasurement(user_id=pt.id, kind="heart_rate", value=rnd.randint(68, 82), unit="bpm", context="resting", measured_at=when + timedelta(minutes=6), source="sample", is_sample=True))
        if d % 3 == 0:
            db.add(HealthMeasurement(user_id=pt.id, kind="weight", value=round(74.6 - (14 - d) * 0.05 + rnd.uniform(-0.2, 0.2), 1), unit="kg", measured_at=when, source="sample", is_sample=True))

    db.add(Appointment(user_id=pt.id, doctor_name="Dr. Anjali Mehta", specialization="Diabetologist", clinic="Mehta Diabetes & Heart Clinic",
                       address="12, Vikas Nagar, Lucknow", phone="0522-4001234", status="upcoming", prescription_id=rx.id, source="manual",
                       scheduled_at=timeutil.local_dt(date.today() + timedelta(days=6), "10:30", tzname), notes="Bring fasting sugar report and medicine box"))
    db.add(Appointment(user_id=pt.id, doctor_name="Dr. Anjali Mehta", specialization="Diabetologist", clinic="Mehta Diabetes & Heart Clinic", status="completed", source="manual",
                       scheduled_at=timeutil.local_dt(start, "11:00", tzname), consultation_summary="Sugar improving. Continue medicines. Reduce salt and sweets. Walk daily."))
    db.add(Appointment(user_id=pt.id, doctor_name="Dr. Suresh Rao", specialization="Ophthalmologist", clinic="Vision Eye Centre", status="upcoming", source="manual",
                       scheduled_at=timeutil.local_dt(date.today() + timedelta(days=24), "16:00", tzname), notes="Annual diabetic eye check-up"))

    conn = CaregiverConnection(patient_user_id=pt.id, caregiver_user_id=cg.id, invite_email=DEMO_CAREGIVER, name="Priya Kumar", relationship_type="daughter",
                               phone="+91 91234 56789", status="active", permissions={**DEFAULT_PERMISSIONS, "view_reports": True}, escalation_minutes=30,
                               is_emergency_contact=True, accepted_at=timeutil.now_utc() - timedelta(days=20))
    db.add(conn)
    db.flush()
    record_consent(db, pt.id, "caregiver_share", True, target_id=conn.id, scope=conn.permissions)

    generate_plan(db, pt)
    create_notification(db, pt.id, "refill", "Refill reminder", "Only 4 tablets of Telmisartan left. Please arrange a refill.", severity="warning",
                        data={"url": "/app/medicines"}, dedupe_key=f"seed-refill:{pt.id}", push=False)
    create_notification(db, pt.id, "appointment", "Upcoming appointment", "Dr. Anjali Mehta in 6 days, 10:30 AM.", data={"url": "/app/appointments"},
                        dedupe_key=f"seed-appt:{pt.id}", push=False)
    create_notification(db, cg.id, "caregiver_daily_summary", "Daily summary for Ramesh", "Medicines: all doses taken yesterday.",
                        data={"url": f"/caregiver?patient={pt.id}"}, dedupe_key=f"seed-cg:{cg.id}", push=False)
    db.flush()


def main() -> None:
    db = SessionLocal()
    try:
        if "--reset" in sys.argv:
            _delete_demo(db)
        added = ensure_catalog(db)
        seed_demo(db)
        db.commit()
        print(f"Seed complete. Food catalog +{added}. Demo patient: {DEMO_PATIENT} / {DEMO_PASSWORD} · caregiver: {DEMO_CAREGIVER} / {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
