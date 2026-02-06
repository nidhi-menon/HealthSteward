"""SQLAlchemy ORM models for HealthSteward."""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
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
    doctor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("doctors.id"), nullable=False
    )
    scheduled_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="scheduled"
    )  # scheduled, completed, cancelled
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    profile: Mapped["HealthProfile"] = relationship(back_populates="appointments")
    doctor: Mapped["Doctor"] = relationship(back_populates="appointments")
    visit_prep: Mapped[Optional["VisitPrep"]] = relationship(
        back_populates="appointment", uselist=False, cascade="all, delete-orphan"
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
