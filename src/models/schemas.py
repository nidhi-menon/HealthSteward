"""Pydantic schemas for API request/response validation."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# Health Profile Schemas
# ============================================================================


class HealthProfileBase(BaseModel):
    """Base schema for health profile data."""

    name: str = Field(..., min_length=1, max_length=255)
    date_of_birth: Optional[date] = None
    blood_type: Optional[str] = Field(None, max_length=10)
    allergies: Optional[str] = None
    emergency_contact_name: Optional[str] = Field(None, max_length=255)
    emergency_contact_phone: Optional[str] = Field(None, max_length=50)


class HealthProfileCreate(HealthProfileBase):
    """Schema for creating a health profile."""

    pass


class HealthProfileUpdate(BaseModel):
    """Schema for updating a health profile."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    date_of_birth: Optional[date] = None
    blood_type: Optional[str] = Field(None, max_length=10)
    allergies: Optional[str] = None
    emergency_contact_name: Optional[str] = Field(None, max_length=255)
    emergency_contact_phone: Optional[str] = Field(None, max_length=50)


class HealthProfileResponse(HealthProfileBase):
    """Schema for health profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Condition Schemas
# ============================================================================


class ConditionBase(BaseModel):
    """Base schema for condition data."""

    name: str = Field(..., min_length=1, max_length=255)
    diagnosed_date: Optional[date] = None
    severity: Optional[str] = Field(None, max_length=50)
    status: str = Field(default="active", max_length=50)
    notes: Optional[str] = None


class ConditionCreate(ConditionBase):
    """Schema for creating a condition."""

    pass


class ConditionUpdate(BaseModel):
    """Schema for updating a condition."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    diagnosed_date: Optional[date] = None
    severity: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class ConditionResponse(ConditionBase):
    """Schema for condition response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Medication Schemas
# ============================================================================


class MedicationBase(BaseModel):
    """Base schema for medication data."""

    name: str = Field(..., min_length=1, max_length=255)
    dosage: Optional[str] = Field(None, max_length=100)
    frequency: Optional[str] = Field(None, max_length=100)
    prescribing_doctor: Optional[str] = Field(None, max_length=255)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    purpose: Optional[str] = None
    side_effects: Optional[str] = None


class MedicationCreate(MedicationBase):
    """Schema for creating a medication."""

    pass


class MedicationUpdate(BaseModel):
    """Schema for updating a medication."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    dosage: Optional[str] = Field(None, max_length=100)
    frequency: Optional[str] = Field(None, max_length=100)
    prescribing_doctor: Optional[str] = Field(None, max_length=255)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    purpose: Optional[str] = None
    side_effects: Optional[str] = None


class MedicationResponse(MedicationBase):
    """Schema for medication response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Doctor Schemas
# ============================================================================


class DoctorBase(BaseModel):
    """Base schema for doctor data."""

    name: str = Field(..., min_length=1, max_length=255)
    specialty: Optional[str] = Field(None, max_length=255)
    clinic: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class DoctorCreate(DoctorBase):
    """Schema for creating a doctor."""

    pass


class DoctorUpdate(BaseModel):
    """Schema for updating a doctor."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    specialty: Optional[str] = Field(None, max_length=255)
    clinic: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class DoctorResponse(DoctorBase):
    """Schema for doctor response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Appointment Schemas
# ============================================================================


class AppointmentBase(BaseModel):
    """Base schema for appointment data."""

    doctor_id: str
    scheduled_date: datetime
    purpose: Optional[str] = None
    status: str = Field(default="scheduled", max_length=50)
    notes: Optional[str] = None


class AppointmentCreate(AppointmentBase):
    """Schema for creating an appointment."""

    pass


class AppointmentUpdate(BaseModel):
    """Schema for updating an appointment."""

    doctor_id: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    purpose: Optional[str] = None
    status: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class AppointmentResponse(AppointmentBase):
    """Schema for appointment response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Visit Prep Schemas
# ============================================================================


class VisitPrepResponse(BaseModel):
    """Schema for visit prep response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    appointment_id: str
    generated_questions: Optional[dict] = None
    context_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class VisitPrepRequest(BaseModel):
    """Schema for requesting visit prep generation."""

    additional_concerns: Optional[str] = None


# ============================================================================
# Conversation Log Schemas
# ============================================================================


class ConversationLogResponse(BaseModel):
    """Schema for conversation log response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    extra_data: Optional[dict] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    timestamp: datetime
