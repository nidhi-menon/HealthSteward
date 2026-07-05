"""SQLAlchemy ORM models for HealthSteward."""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


def generate_uuid() -> str:
    """Generate a UUID string for primary keys."""
    return str(uuid.uuid4())


class HealthProfile(Base):
    """User health profile containing personal and emergency contact info."""

    __tablename__ = "health_profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_birth: Mapped[Optional[date]] = mapped_column(nullable=True)
    blood_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    allergies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    conditions: Mapped[list["Condition"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    medications: Mapped[list["Medication"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    doctors: Mapped[list["Doctor"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    vitals: Mapped[list["Vitals"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    lab_orders: Mapped[list["LabOrder"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    referrals: Mapped[list["Referral"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    follow_ups: Mapped[list["FollowUp"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class Condition(Base):
    """Medical condition tracked for a health profile."""

    __tablename__ = "conditions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("health_profiles.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    icd_10: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    diagnosed_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # mild, moderate, severe
    status: Mapped[str] = mapped_column(
        String(50), default="active"
    )  # active, managed, resolved
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    profile: Mapped["HealthProfile"] = relationship(back_populates="conditions")


class Medication(Base):
    """Medication being taken by a health profile."""

    __tablename__ = "medications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("health_profiles.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dosage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    frequency: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # e.g., "twice daily"
    prescribing_doctor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    side_effects: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    profile: Mapped["HealthProfile"] = relationship(back_populates="medications")


class Doctor(Base):
    """Healthcare provider associated with a health profile."""

    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("health_profiles.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    specialty: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    clinic: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exclude_from_prep_context: Mapped[bool] = mapped_column(
        default=False
    )  # Exclude this doctor's visits from prep context (e.g., sensitive specialties)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    profile: Mapped["HealthProfile"] = relationship(back_populates="doctors")
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )


class Appointment(Base):
    """Scheduled appointment with a doctor."""

    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("health_profiles.id"), nullable=False
    )
    doctor_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("doctors.id"), nullable=True
    )
    scheduled_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="scheduled"
    )  # scheduled, completed, cancelled
    prep_notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Notes before the visit (concerns, questions to ask)
    visit_notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Notes during/after the visit (what was discussed, outcomes)
    visit_notes_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )  # Timestamp when visit_notes was last updated
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    profile: Mapped["HealthProfile"] = relationship(back_populates="appointments")
    doctor: Mapped[Optional["Doctor"]] = relationship(back_populates="appointments")
    visit_prep: Mapped[Optional["VisitPrep"]] = relationship(
        back_populates="appointment", uselist=False, cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="appointment", cascade="all, delete-orphan"
    )


class VisitPrep(Base):
    """AI-generated visit preparation for an appointment."""

    __tablename__ = "visit_preps"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    appointment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("appointments.id"), unique=True, nullable=False
    )
    generated_questions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    context_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    appointment: Mapped["Appointment"] = relationship(back_populates="visit_prep")


class ConversationLog(Base):
    """Log of conversations with the AI agent for training data."""

    __tablename__ = "conversation_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # user, assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )


class Document(Base):
    """Uploaded document (e.g. after-visit summary PDF) for a health profile."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("health_profiles.id"), nullable=False
    )
    appointment_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("appointments.id"), nullable=True
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    visit_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    provider_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    facility_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    parse_status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, parsing, completed, failed
    parse_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_parse_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    profile: Mapped["HealthProfile"] = relationship(back_populates="documents")
    appointment: Mapped[Optional["Appointment"]] = relationship(back_populates="documents")
    vitals: Mapped[Optional["Vitals"]] = relationship(
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    lab_orders: Mapped[list["LabOrder"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    referrals: Mapped[list["Referral"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    follow_ups: Mapped[list["FollowUp"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Vitals(Base):
    """Vitals measured during a visit, linked to a document."""

    __tablename__ = "vitals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("health_profiles.id"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id"), unique=True, nullable=False
    )
    weight: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bmi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    blood_pressure: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    heart_rate: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    temperature: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    measured_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    # Relationships
    profile: Mapped["HealthProfile"] = relationship(back_populates="vitals")
    document: Mapped["Document"] = relationship(back_populates="vitals")


class LabOrder(Base):
    """Lab test ordered during a visit."""

    __tablename__ = "lab_orders"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("health_profiles.id"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id"), nullable=False
    )
    test_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ordered_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ordered")
    snoozed_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    # Relationships
    profile: Mapped["HealthProfile"] = relationship(back_populates="lab_orders")
    document: Mapped["Document"] = relationship(back_populates="lab_orders")


class Referral(Base):
    """Referral to a specialist from a visit."""

    __tablename__ = "referrals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("health_profiles.id"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id"), nullable=False
    )
    specialty: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    snoozed_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    # Relationships
    profile: Mapped["HealthProfile"] = relationship(back_populates="referrals")
    document: Mapped["Document"] = relationship(back_populates="referrals")


class FollowUp(Base):
    """Follow-up recommendation from a visit."""

    __tablename__ = "follow_ups"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("health_profiles.id"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    timeframe: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    snoozed_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    # Relationships
    profile: Mapped["HealthProfile"] = relationship(back_populates="follow_ups")
    document: Mapped["Document"] = relationship(back_populates="follow_ups")


class NudgeState(Base):
    """Snooze state for computed nudges that have no persistent DB row (appointment-based)."""

    __tablename__ = "nudge_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("health_profiles.id"), nullable=False
    )
    nudge_type: Mapped[str] = mapped_column(String(100), nullable=False)
    item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    snoozed_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )
