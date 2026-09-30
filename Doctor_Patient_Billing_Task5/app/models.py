from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index,
    Integer, Numeric, String, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class AuditMixin:
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)

class User(AuditMixin, Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="doctor")

class Doctor(AuditMixin, Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    specialization = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    patients = relationship("Patient", back_populates="doctor")
    appointments = relationship("Appointment", back_populates="doctor")

class Patient(AuditMixin, Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    age = Column(Integer, nullable=False)
    phone = Column(String(15), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    doctor = relationship("Doctor", back_populates="patients")
    appointments = relationship("Appointment", back_populates="patient")

class Appointment(AuditMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (Index("ix_appointments_doctor_date_status", "doctor_id", "appointment_date", "status"),)
    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    appointment_date = Column(DateTime, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="scheduled", index=True)
    doctor = relationship("Doctor", back_populates="appointments")
    patient = relationship("Patient", back_populates="appointments")


class Billing(AuditMixin, Base):
    """Billing record. One appointment can have at most one bill."""
    __tablename__ = "billings"
    __table_args__ = (
        UniqueConstraint("appointment_id", name="uq_billings_appointment_id"),
        CheckConstraint("consultation_fee >= 0", name="ck_billings_consultation_fee_nonnegative"),
        CheckConstraint("additional_charges >= 0", name="ck_billings_additional_charges_nonnegative"),
        CheckConstraint("total_amount >= 0", name="ck_billings_total_amount_nonnegative"),
        CheckConstraint("payment_status IN ('pending', 'paid', 'cancelled')", name="ck_billings_payment_status"),
        CheckConstraint("payment_mode IS NULL OR payment_mode IN ('cash', 'card', 'upi')", name="ck_billings_payment_mode"),
        Index("ix_billings_doctor_created", "doctor_id", "created_at"),
        Index("ix_billings_patient_created", "patient_id", "created_at"),
    )
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="RESTRICT"), nullable=True, index=True)
    consultation_fee = Column(Numeric(12, 2), nullable=False)
    additional_charges = Column(Numeric(12, 2), nullable=False, default=0)
    total_amount = Column(Numeric(12, 2), nullable=False)
    payment_status = Column(String(20), nullable=False, default="pending", index=True)
    payment_mode = Column(String(20), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    patient = relationship("Patient")
    doctor = relationship("Doctor")
    appointment = relationship("Appointment")
