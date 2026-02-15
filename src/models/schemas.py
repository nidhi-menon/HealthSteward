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
    icd_10: Optional[str] = Field(None, max_length=20)
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
    icd_10: Optional[str] = Field(None, max_length=20)
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
    exclude_from_prep_context: bool = Field(
        default=False,
        description="Exclude this doctor's visits from prep context (e.g., sensitive specialties)"
    )


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
    exclude_from_prep_context: Optional[bool] = None


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
    prep_notes: Optional[str] = Field(
        None, description="Notes before the visit (concerns, questions to ask)"
    )
    visit_notes: Optional[str] = Field(
        None, description="Notes during/after the visit (what was discussed, outcomes)"
    )


class AppointmentCreate(AppointmentBase):
    """Schema for creating an appointment."""

    pass


class AppointmentUpdate(BaseModel):
    """Schema for updating an appointment."""

    doctor_id: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    purpose: Optional[str] = None
    status: Optional[str] = Field(None, max_length=50)
    prep_notes: Optional[str] = None
    visit_notes: Optional[str] = None


class AppointmentResponse(AppointmentBase):
    """Schema for appointment response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    visit_notes_updated_at: Optional[datetime] = None
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


# ============================================================================
# Document Schemas
# ============================================================================


class ScannedFileResponse(BaseModel):
    """A PDF file found in the scan directory."""

    filename: str
    file_size_bytes: int
    modified_date: datetime
    status: str  # new, pending, parsing, completed, failed
    document_id: Optional[str] = None


class DocumentResponse(BaseModel):
    """Schema for document metadata response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    appointment_id: Optional[str] = None
    original_filename: str
    file_size_bytes: int
    visit_date: Optional[str] = None
    provider_name: Optional[str] = None
    facility_name: Optional[str] = None
    parse_status: str
    parse_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Parsed Items Schemas (for review screen)
# ============================================================================


class ParsedVitals(BaseModel):
    weight: Optional[str] = None
    bmi: Optional[float] = None
    blood_pressure: Optional[str] = None
    heart_rate: Optional[str] = None
    temperature: Optional[str] = None


class ParsedDiagnosis(BaseModel):
    condition: str
    icd_10: Optional[str] = None


class ParsedMedicationChange(BaseModel):
    name: str
    action: str  # start, stop, changed
    strength: Optional[str] = None
    instructions: Optional[str] = None
    date: Optional[str] = None


class ParsedLabOrder(BaseModel):
    test: str
    ordered_date: Optional[str] = None


class ParsedReferral(BaseModel):
    specialty: str
    provider: Optional[str] = None
    reason: Optional[str] = None


class ParsedFollowUp(BaseModel):
    description: str
    timeframe: Optional[str] = None
    target_date: Optional[str] = None


class ParsedAppointment(BaseModel):
    description: str
    date: Optional[str] = None
    time: Optional[str] = None
    location: Optional[str] = None
    phone: Optional[str] = None


class ParsedItemsResponse(BaseModel):
    """Full parsed output for the review screen."""

    patient: dict = {}
    provider: dict = {}
    vitals: ParsedVitals = ParsedVitals()
    diagnoses: list[ParsedDiagnosis] = []
    medication_changes: list[ParsedMedicationChange] = []
    lab_orders: list[ParsedLabOrder] = []
    referrals: list[ParsedReferral] = []
    follow_up_recommended: list[ParsedFollowUp] = []
    upcoming_appointments: list[ParsedAppointment] = []
    notes: list[str] = []


class ApplyItemsRequest(BaseModel):
    """User's selections of which parsed items to accept."""

    diagnoses: list[ParsedDiagnosis] = []
    medication_starts: list[ParsedMedicationChange] = []
    medication_stops: list[ParsedMedicationChange] = []
    medication_updates: list[ParsedMedicationChange] = []
    vitals: Optional[ParsedVitals] = None
    lab_orders: list[ParsedLabOrder] = []
    referrals: list[ParsedReferral] = []
    follow_ups: list[ParsedFollowUp] = []


# ============================================================================
# New Model Response Schemas
# ============================================================================


class VitalsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    document_id: str
    weight: Optional[str] = None
    bmi: Optional[float] = None
    blood_pressure: Optional[str] = None
    heart_rate: Optional[str] = None
    temperature: Optional[str] = None
    measured_date: Optional[str] = None
    created_at: datetime


class LabOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    document_id: str
    test_name: str
    ordered_date: Optional[str] = None
    status: str
    created_at: datetime


class ReferralResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    document_id: str
    specialty: str
    provider_name: Optional[str] = None
    reason: Optional[str] = None
    status: str
    created_at: datetime


class FollowUpResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    document_id: str
    description: str
    timeframe: Optional[str] = None
    target_date: Optional[str] = None
    status: str
    created_at: datetime
