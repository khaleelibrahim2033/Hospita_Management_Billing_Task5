
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Role(str, Enum):
    admin = "admin"
    doctor = "doctor"


# USER SCHEMAS
class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    role: Role = Role.doctor


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: Role

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# DOCTOR SCHEMAS
class DoctorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    specialization: str = Field(min_length=2, max_length=100)
    email: EmailStr


class DoctorUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    specialization: Optional[str] = Field(
        default=None, min_length=2, max_length=100
    )
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class DoctorResponse(BaseModel):
    id: int
    name: str
    specialization: str
    email: EmailStr
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# PATIENT SCHEMAS
class PatientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    age: int = Field(gt=0)
    phone: str = Field(pattern=r"^\d{10}$")
    doctor_id: Optional[int] = Field(default=None, gt=0)


class PatientUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    age: Optional[int] = Field(default=None, gt=0)
    phone: Optional[str] = Field(default=None, pattern=r"^\d{10}$")


class PatientResponse(BaseModel):
    id: int
    name: str
    age: int
    phone: str
    doctor_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# PAGINATION SCHEMA
class PaginatedPatients(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[PatientResponse]

from datetime import datetime

class AppointmentStatus(str, Enum):
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"

class AppointmentCreate(BaseModel):
    doctor_id: int = Field(gt=0)
    patient_id: int = Field(gt=0)
    appointment_date: datetime
    status: AppointmentStatus = AppointmentStatus.scheduled

class AppointmentUpdate(BaseModel):
    appointment_date: Optional[datetime] = None
    status: Optional[AppointmentStatus] = None

class AppointmentResponse(BaseModel):
    id: int
    doctor_id: int
    patient_id: int
    appointment_date: datetime
    status: AppointmentStatus
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# BILLING SCHEMAS
from decimal import Decimal
from pydantic import model_validator

class PaymentStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    cancelled = "cancelled"

class PaymentMode(str, Enum):
    cash = "cash"
    card = "card"
    upi = "upi"

class BillingCreate(BaseModel):
    patient_id: int = Field(gt=0)
    doctor_id: int = Field(gt=0)
    appointment_id: Optional[int] = Field(default=None, gt=0)
    consultation_fee: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    additional_charges: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    payment_status: PaymentStatus = PaymentStatus.pending
    payment_mode: Optional[PaymentMode] = None

    @model_validator(mode="after")
    def validate_payment_mode(self):
        if self.payment_status == PaymentStatus.paid and self.payment_mode is None:
            raise ValueError("payment_mode is required when payment_status is paid")
        return self

class BillingPut(BaseModel):
    consultation_fee: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    additional_charges: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    payment_status: PaymentStatus
    payment_mode: Optional[PaymentMode] = None

    @model_validator(mode="after")
    def validate_payment_mode(self):
        if self.payment_status == PaymentStatus.paid and self.payment_mode is None:
            raise ValueError("payment_mode is required when payment_status is paid")
        return self

class BillingPatch(BaseModel):
    consultation_fee: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    additional_charges: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    payment_status: Optional[PaymentStatus] = None
    payment_mode: Optional[PaymentMode] = None

    @model_validator(mode="after")
    def reject_empty(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied")
        return self

class BillingResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    appointment_id: Optional[int]
    consultation_fee: Decimal
    additional_charges: Decimal
    total_amount: Decimal
    payment_status: PaymentStatus
    payment_mode: Optional[PaymentMode]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class PaginatedBillings(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[BillingResponse]

class DoctorRevenue(BaseModel):
    doctor_id: int
    total_revenue: Decimal

class DailyRevenue(BaseModel):
    date: str
    total_revenue: Decimal
