"""Structured-output contracts for document extraction (validated with Pydantic)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

DocType = Literal["lab_report", "prescription", "consultation_note", "diet_advice", "appointment", "other"]
MealRelation = Literal["before_meal", "after_meal", "with_meal", "empty_stomach", "bedtime", "any"]


class LabParameter(BaseModel):
    test_group: str | None = None
    name: str
    value_text: str
    unit: str | None = None
    ref_text: str | None = None
    ref_low: float | None = None
    ref_high: float | None = None
    flag_in_report: str | None = None  # H / L as printed

    @field_validator("name", "value_text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class LabReportExtraction(BaseModel):
    lab_name: str | None = None
    report_date: str | None = None  # ISO yyyy-mm-dd
    patient_name: str | None = None
    title: str | None = None
    tests: list[LabParameter] = Field(default_factory=list)


class RxMedicine(BaseModel):
    name: str
    brand_name: str | None = None
    generic_name: str | None = None
    generic_source: Literal["document", "dictionary", "none"] = "none"
    form: str | None = None
    strength: str | None = None
    dosage: str | None = None
    frequency: str | None = None
    meal_relation: MealRelation = "any"
    duration_days: int | None = None
    duration_text: str | None = None
    instructions: str | None = None

    @field_validator("duration_days")
    @classmethod
    def positive(cls, v: int | None) -> int | None:
        if v is not None and (v <= 0 or v > 3650):
            raise ValueError("duration out of range")
        return v


class PrescriptionExtraction(BaseModel):
    doctor_name: str | None = None
    clinic: str | None = None
    prescribed_date: str | None = None
    patient_name: str | None = None
    notes: str | None = None
    follow_up_date: str | None = None
    medicines: list[RxMedicine] = Field(default_factory=list)


class DietAdviceExtraction(BaseModel):
    doctor_name: str | None = None
    advice_date: str | None = None
    instructions: list[str] = Field(default_factory=list)
    restrictions: list[str] = Field(default_factory=list)  # normalized tags e.g. low_sodium


class AppointmentExtraction(BaseModel):
    doctor_name: str | None = None
    specialization: str | None = None
    clinic: str | None = None
    address: str | None = None
    phone: str | None = None
    date: str | None = None  # ISO
    time: str | None = None  # HH:MM 24h
    notes: str | None = None


class ConsultationExtraction(BaseModel):
    doctor_name: str | None = None
    specialization: str | None = None
    clinic: str | None = None
    visit_date: str | None = None
    summary: str | None = None
    advice: list[str] = Field(default_factory=list)
    diet_instructions: list[str] = Field(default_factory=list)
    restrictions: list[str] = Field(default_factory=list)
    follow_up_date: str | None = None


SCHEMAS: dict[str, type[BaseModel]] = {
    "lab_report": LabReportExtraction,
    "prescription": PrescriptionExtraction,
    "diet_advice": DietAdviceExtraction,
    "appointment": AppointmentExtraction,
    "consultation_note": ConsultationExtraction,
}
