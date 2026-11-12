"""SQLAlchemy models for HealthMate AI.

Sensitive free text (OCR output, notes, extraction payloads, chat content) is stored
encrypted at rest via EncryptedText / EncryptedJSON column types.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    LargeBinary,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.crypto import EncryptedJSON, EncryptedText
from app.db.session import Base


def uid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# ---------------------------------------------------------------- identity
class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="patient")  # patient | caregiver
    language: Mapped[str] = mapped_column(String(5), default="en")  # en | hi
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    profile: Mapped[PatientProfile | None] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class PatientProfile(TimestampMixin, Base):
    __tablename__ = "patient_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(30))
    blood_group: Mapped[str | None] = mapped_column(String(5))
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    # Only patient-confirmed conditions are stored here (never AI-inferred).
    conditions: Mapped[list] = mapped_column(JSON, default=list)
    allergies: Mapped[list] = mapped_column(JSON, default=list)
    food_preference: Mapped[str] = mapped_column(String(20), default="vegetarian")  # vegetarian|eggetarian|non_vegetarian|vegan
    cuisine_preferences: Mapped[list] = mapped_column(JSON, default=list)
    activity_level: Mapped[str] = mapped_column(String(20), default="light")  # sedentary|light|moderate|active
    budget_preference: Mapped[str] = mapped_column(String(20), default="moderate")
    # Explicit doctor diet instructions (from verified diet-advice documents or manual entry)
    doctor_diet_instructions: Mapped[list] = mapped_column(JSON, default=list)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(120))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(30))
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    large_text: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="profile")


class CaregiverConnection(TimestampMixin, Base):
    __tablename__ = "caregiver_connections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    patient_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    caregiver_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    invite_email: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    relationship_type: Mapped[str] = mapped_column(String(30))  # son|daughter|spouse|family|housemate|caretaker
    phone: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|active|revoked|declined
    invite_token_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Patient-controlled permission flags
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    escalation_minutes: Mapped[int] = mapped_column(Integer, default=30)
    is_emergency_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConsentRecord(TimestampMixin, Base):
    """Append-only consent ledger. The latest record per (user, type, target) wins."""

    __tablename__ = "consent_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    consent_type: Mapped[str] = mapped_column(String(50))  # ai_processing|caregiver_share|terms
    target_id: Mapped[str | None] = mapped_column(String(36))
    granted: Mapped[bool] = mapped_column(Boolean)
    scope: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64))


# ---------------------------------------------------------------- documents
class MedicalDocument(TimestampMixin, Base):
    __tablename__ = "medical_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    declared_type: Mapped[str | None] = mapped_column(String(30))
    detected_type: Mapped[str | None] = mapped_column(String(30))  # lab_report|prescription|consultation_note|diet_advice|appointment|other
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="uploaded")  # uploaded|processing|needs_review|verified|failed|rejected
    ocr_text: Mapped[str | None] = mapped_column(EncryptedText)
    ocr_method: Mapped[str | None] = mapped_column(String(40))
    extraction: Mapped[dict | None] = mapped_column(EncryptedJSON)
    extractor: Mapped[str | None] = mapped_column(String(60))
    confidence: Mapped[float | None] = mapped_column(Float)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    pipeline_steps: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    document_date: Mapped[date | None] = mapped_column(Date)


class DocumentBlob(TimestampMixin, Base):
    """Encrypted file bytes, used when STORAGE_BACKEND=db (hosts without persistent disks)."""

    __tablename__ = "document_blobs"
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)


class DocumentChunk(TimestampMixin, Base):
    """Retrieval chunks for RAG. Text encrypted at rest; embeddings optional."""

    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("medical_documents.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(30))  # document|report|prescription|diet|appointment
    source_label: Mapped[str] = mapped_column(String(255))
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(EncryptedText)
    embedding: Mapped[list | None] = mapped_column(JSON)
    injection_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class MedicalReport(TimestampMixin, Base):
    __tablename__ = "medical_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("medical_documents.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    report_date: Mapped[date | None] = mapped_column(Date)
    lab_name: Mapped[str | None] = mapped_column(String(200))
    summary: Mapped[dict | None] = mapped_column(EncryptedJSON)  # {en, hi, findings[], questions[]}
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)

    parameters: Mapped[list[ReportParameter]] = relationship(back_populates="report", cascade="all, delete-orphan", order_by="ReportParameter.position")


class ReportParameter(Base):
    __tablename__ = "report_parameters"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    report_id: Mapped[str] = mapped_column(ForeignKey("medical_reports.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    test_group: Mapped[str | None] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(120))
    canonical_name: Mapped[str] = mapped_column(String(120), index=True)
    value: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str] = mapped_column(String(60))
    unit: Mapped[str | None] = mapped_column(String(40))
    ref_low: Mapped[float | None] = mapped_column(Float)
    ref_high: Mapped[float | None] = mapped_column(Float)
    ref_text: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(10), default="unknown")  # normal|high|low|unknown
    report_date: Mapped[date | None] = mapped_column(Date)

    report: Mapped[MedicalReport] = relationship(back_populates="parameters")


# ---------------------------------------------------------------- medicines
class Prescription(TimestampMixin, Base):
    __tablename__ = "prescriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("medical_documents.id", ondelete="SET NULL"))
    doctor_name: Mapped[str | None] = mapped_column(String(120))
    clinic: Mapped[str | None] = mapped_column(String(200))
    prescribed_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(EncryptedText)
    status: Mapped[str] = mapped_column(String(20), default="verified")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    medicines: Mapped[list[PrescriptionMedicine]] = relationship(back_populates="prescription")


class PrescriptionMedicine(TimestampMixin, Base):
    __tablename__ = "prescription_medicines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    prescription_id: Mapped[str | None] = mapped_column(ForeignKey("prescriptions.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(120))
    brand_name: Mapped[str | None] = mapped_column(String(120))
    generic_name: Mapped[str | None] = mapped_column(String(120))
    form: Mapped[str | None] = mapped_column(String(30))  # tablet|capsule|syrup|injection|...
    strength: Mapped[str | None] = mapped_column(String(40))
    dosage: Mapped[str | None] = mapped_column(String(60))
    frequency: Mapped[str | None] = mapped_column(String(40))  # as written, e.g. 1-0-1, BD
    slots: Mapped[list] = mapped_column(JSON, default=list)  # morning|afternoon|evening|night
    meal_relation: Mapped[str] = mapped_column(String(20), default="any")  # before_meal|after_meal|with_meal|empty_stomach|bedtime|any
    duration_days: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    instructions: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual|prescription
    verified: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    as_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    stock_count: Mapped[int | None] = mapped_column(Integer)
    refill_threshold: Mapped[int] = mapped_column(Integer, default=5)
    color: Mapped[str | None] = mapped_column(String(20))

    prescription: Mapped[Prescription | None] = relationship(back_populates="medicines")
    schedules: Mapped[list[MedicineSchedule]] = relationship(back_populates="medicine", cascade="all, delete-orphan")


class MedicineSchedule(TimestampMixin, Base):
    __tablename__ = "medicine_schedules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    medicine_id: Mapped[str] = mapped_column(ForeignKey("prescription_medicines.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    slot: Mapped[str] = mapped_column(String(20))
    time_of_day: Mapped[str] = mapped_column(String(5))  # HH:MM local
    meal_anchor: Mapped[str | None] = mapped_column(String(20))  # breakfast|lunch|snack|dinner
    offset_minutes: Mapped[int] = mapped_column(Integer, default=0)
    rule: Mapped[str] = mapped_column(String(60))  # which deterministic rule produced this time
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    medicine: Mapped[PrescriptionMedicine] = relationship(back_populates="schedules")


class MedicineLog(TimestampMixin, Base):
    __tablename__ = "medicine_logs"
    __table_args__ = (UniqueConstraint("schedule_id", "scheduled_for", name="uq_log_schedule_time"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    schedule_id: Mapped[str] = mapped_column(ForeignKey("medicine_schedules.id", ondelete="CASCADE"), index=True)
    medicine_id: Mapped[str] = mapped_column(ForeignKey("prescription_medicines.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20))  # taken|skipped|snoozed|missed|reminded
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snooze_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    caregiver_alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actor_user_id: Mapped[str | None] = mapped_column(String(36))
    note: Mapped[str | None] = mapped_column(String(255))


class ReminderSettings(TimestampMixin, Base):
    __tablename__ = "reminder_settings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    voice_language: Mapped[str] = mapped_column(String(10), default="hi-IN")
    voice_name: Mapped[str | None] = mapped_column(String(120))
    volume: Mapped[float] = mapped_column(Float, default=1.0)
    rate: Mapped[float] = mapped_column(Float, default=0.9)
    repeat_count: Mapped[int] = mapped_column(Integer, default=2)
    repeat_interval_minutes: Mapped[int] = mapped_column(Integer, default=10)
    snooze_minutes: Mapped[int] = mapped_column(Integer, default=15)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    refill_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    appointment_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(5))
    quiet_hours_end: Mapped[str | None] = mapped_column(String(5))


# ---------------------------------------------------------------- meals & nutrition
class MealSchedule(TimestampMixin, Base):
    __tablename__ = "meal_schedules"
    __table_args__ = (UniqueConstraint("user_id", "meal", name="uq_meal_user"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    meal: Mapped[str] = mapped_column(String(20))  # breakfast|lunch|snack|dinner
    time_of_day: Mapped[str] = mapped_column(String(5))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class MealLog(TimestampMixin, Base):
    __tablename__ = "meal_logs"
    __table_args__ = (UniqueConstraint("user_id", "meal", "log_date", name="uq_meal_log"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    meal: Mapped[str] = mapped_column(String(20))
    log_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))  # done|delayed|skipped
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delayed_until: Mapped[str | None] = mapped_column(String(5))


class FoodRecommendation(TimestampMixin, Base):
    """Food catalog item. user_id NULL = shared catalog; set = user-specific/generated."""

    __tablename__ = "food_recommendations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(120))
    name_hi: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    meal_types: Mapped[list] = mapped_column(JSON, default=list)  # breakfast|lunch|snack|dinner
    diet: Mapped[str] = mapped_column(String(20))  # vegetarian|eggetarian|non_vegetarian|vegan
    tags: Mapped[list] = mapped_column(JSON, default=list)
    allergens: Mapped[list] = mapped_column(JSON, default=list)
    calories: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float] = mapped_column(Float)
    carbs_g: Mapped[float] = mapped_column(Float)
    fat_g: Mapped[float] = mapped_column(Float)
    fibre_g: Mapped[float] = mapped_column(Float)
    sodium_mg: Mapped[float] = mapped_column(Float)
    potassium_mg: Mapped[float | None] = mapped_column(Float)
    glycemic: Mapped[str] = mapped_column(String(10), default="medium")  # low|medium|high
    cost_level: Mapped[str] = mapped_column(String(10), default="low")
    prep_minutes: Mapped[int] = mapped_column(Integer, default=20)
    serving: Mapped[str] = mapped_column(String(60))
    ingredients: Mapped[list] = mapped_column(JSON, default=list)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    substitutions: Mapped[list] = mapped_column(JSON, default=list)
    image_url: Mapped[str | None] = mapped_column(String(500))


class NutritionPlan(TimestampMixin, Base):
    __tablename__ = "nutrition_plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    week_start: Mapped[date] = mapped_column(Date)
    generated_by: Mapped[str] = mapped_column(String(60))
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)  # rules applied + why
    targets: Mapped[dict] = mapped_column(JSON, default=dict)
    days: Mapped[list] = mapped_column(JSON, default=list)  # [{date, meals:{breakfast:[food_id],...}}]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------- appointments & measurements
class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    doctor_name: Mapped[str] = mapped_column(String(120))
    specialization: Mapped[str | None] = mapped_column(String(120))
    clinic: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(30))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20), default="upcoming")  # upcoming|completed|cancelled
    notes: Mapped[str | None] = mapped_column(EncryptedText)
    consultation_summary: Mapped[str | None] = mapped_column(EncryptedText)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("medical_documents.id", ondelete="SET NULL"))
    prescription_id: Mapped[str | None] = mapped_column(ForeignKey("prescriptions.id", ondelete="SET NULL"))
    reminder_minutes_before: Mapped[int] = mapped_column(Integer, default=120)
    source: Mapped[str] = mapped_column(String(20), default="manual")


class HealthMeasurement(TimestampMixin, Base):
    __tablename__ = "health_measurements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)  # blood_pressure|glucose|heart_rate|weight
    value: Mapped[float] = mapped_column(Float)
    value2: Mapped[float | None] = mapped_column(Float)  # diastolic for BP
    unit: Mapped[str] = mapped_column(String(20))
    context: Mapped[str | None] = mapped_column(String(30))  # fasting|post_meal|random|resting
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual|report|sample
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(String(255))


class DailyCheckin(TimestampMixin, Base):
    __tablename__ = "daily_checkins"
    __table_args__ = (UniqueConstraint("user_id", "checkin_date", name="uq_checkin_day"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    checkin_date: Mapped[date] = mapped_column(Date)
    mood: Mapped[str] = mapped_column(String(20))  # great|good|okay|unwell
    energy: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(EncryptedText)


# ---------------------------------------------------------------- notifications & audit
class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # medicine_due|medicine_missed|refill|appointment|caregiver|document|system
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(10), default="info")  # info|warning|critical
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    dedupe_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    push_status: Mapped[str | None] = mapped_column(String(20))  # sent|failed|disabled|none


class PushSubscription(TimestampMixin, Base):
    __tablename__ = "push_subscriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    user_agent: Mapped[str | None] = mapped_column(String(255))


class AuditLog(TimestampMixin, Base):
    """Privacy-conscious audit trail: who did what to which resource. Never stores medical content."""

    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    patient_user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(60))
    resource_type: Mapped[str | None] = mapped_column(String(40))
    resource_id: Mapped[str | None] = mapped_column(String(36))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64))


# ---------------------------------------------------------------- agent
class ChatMessage(TimestampMixin, Base):
    __tablename__ = "chat_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user|assistant
    content: Mapped[str] = mapped_column(EncryptedText)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)  # tool calls, citations, guardrail flags (no PHI)


class AgentMemory(TimestampMixin, Base):
    """Long-term agent memory — only facts the user explicitly asked to remember or verified profile facts."""

    __tablename__ = "agent_memories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(EncryptedText)
    source: Mapped[str] = mapped_column(String(30), default="user_request")


class AgentProposal(TimestampMixin, Base):
    """Human-in-the-loop: actions the agent proposes, executed only after the patient confirms."""

    __tablename__ = "agent_proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(40))  # create_appointment|log_measurement|remember
    payload: Mapped[dict] = mapped_column(EncryptedJSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected|expired
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentTrace(TimestampMixin, Base):
    """Observability: one row per agent/pipeline run with redacted spans."""

    __tablename__ = "agent_traces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # assistant|extraction
    model: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20))
    spans: Mapped[list] = mapped_column(JSON, default=list)
    total_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    guardrail_events: Mapped[list] = mapped_column(JSON, default=list)


class LLMCache(TimestampMixin, Base):
    """Response cache keyed by hash(prompt_version + model + input). Avoids re-paying for identical documents."""

    __tablename__ = "llm_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    model: Mapped[str] = mapped_column(String(80))
    response: Mapped[dict] = mapped_column(EncryptedJSON)
    hits: Mapped[int] = mapped_column(Integer, default=0)
