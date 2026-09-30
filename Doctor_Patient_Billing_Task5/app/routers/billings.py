from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Appointment, Billing, Doctor, Patient, User
from app.schemas import (
    BillingCreate, BillingPatch, BillingPut, BillingResponse,
    PaginatedBillings, PaymentStatus, PaymentMode, DoctorRevenue, DailyRevenue
)

router = APIRouter(tags=["Billing"])
reports_router = APIRouter(prefix="/reports", tags=["Billing Reports"])


def _doctor_for_user(db: Session, user: User) -> Doctor:
    doctor = db.query(Doctor).filter(
        Doctor.email == user.email, Doctor.is_active.is_(True)
    ).first()
    if not doctor:
        raise HTTPException(status_code=403, detail="Active doctor profile not found")
    return doctor


def _visible_billing_query(db: Session, user: User):
    q = db.query(Billing).filter(Billing.is_active.is_(True))
    if user.role == "doctor":
        doctor = _doctor_for_user(db, user)
        q = q.filter(Billing.doctor_id == doctor.id)
    return q


def _get_visible_billing(db: Session, billing_id: int, user: User) -> Billing:
    obj = _visible_billing_query(db, user).filter(Billing.id == billing_id).first()
    if not obj:
        # Avoid exposing whether a different doctor's billing exists.
        raise HTTPException(status_code=404, detail="Billing record not found")
    return obj


def _validate_relations(db: Session, patient_id: int, doctor_id: int, appointment_id: Optional[int]):
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.is_active.is_(True)).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Active patient not found")
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id, Doctor.is_active.is_(True)).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Active doctor not found")
    if patient.doctor_id is not None and patient.doctor_id != doctor_id:
        raise HTTPException(status_code=400, detail="Patient is assigned to a different doctor")
    appointment = None
    if appointment_id is not None:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        if appointment.doctor_id != doctor_id or appointment.patient_id != patient_id:
            raise HTTPException(status_code=400, detail="Appointment must belong to the same doctor and patient")
        if appointment.status == "cancelled":
            raise HTTPException(status_code=400, detail="Cannot bill a cancelled appointment")
    return patient, doctor, appointment


def _amount(fee: Decimal, charges: Decimal) -> Decimal:
    return (Decimal(fee) + Decimal(charges)).quantize(Decimal("0.01"))


def _apply_update(obj: Billing, changes: dict, username: str):
    for key, value in changes.items():
        if hasattr(value, "value"):
            value = value.value
        setattr(obj, key, value)
    obj.total_amount = _amount(obj.consultation_fee, obj.additional_charges)
    if obj.payment_status == "paid" and not obj.payment_mode:
        raise HTTPException(status_code=422, detail="payment_mode is required when payment_status is paid")
    obj.updated_by = username


@router.post("/billings", response_model=BillingResponse, status_code=status.HTTP_201_CREATED)
def create_billing(
    payload: BillingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    _, _, appointment = _validate_relations(db, payload.patient_id, payload.doctor_id, payload.appointment_id)
    if payload.payment_status == PaymentStatus.paid and payload.payment_mode is None:
        raise HTTPException(status_code=422, detail="payment_mode is required when payment_status is paid")
    obj = Billing(
        patient_id=payload.patient_id,
        doctor_id=payload.doctor_id,
        appointment_id=payload.appointment_id,
        consultation_fee=payload.consultation_fee,
        additional_charges=payload.additional_charges,
        total_amount=_amount(payload.consultation_fee, payload.additional_charges),
        payment_status=payload.payment_status.value,
        payment_mode=payload.payment_mode.value if payload.payment_mode else None,
        is_active=True,
        created_by=user.username,
        updated_by=user.username,
    )
    try:
        # One commit makes bill creation and appointment completion atomic.
        db.add(obj)
        if appointment is not None:
            appointment.status = "completed"
            appointment.updated_by = user.username
        db.commit()
        db.refresh(obj)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A billing record already exists for this appointment or a constraint was violated")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to create billing record; transaction rolled back")
    return obj


@router.get("/billings/{billing_id}", response_model=BillingResponse)
def get_billing(billing_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_visible_billing(db, billing_id, user)


def _list_billings(db, user, payment_status, doctor_id, patient_id, from_date, to_date, skip, limit):
    q = _visible_billing_query(db, user)
    if doctor_id is not None:
        q = q.filter(Billing.doctor_id == doctor_id)
    if patient_id is not None:
        q = q.filter(Billing.patient_id == patient_id)
    if payment_status is not None:
        q = q.filter(Billing.payment_status == payment_status.value)
    if from_date is not None:
        q = q.filter(Billing.created_at >= datetime.combine(from_date, time.min))
    if to_date is not None:
        q = q.filter(Billing.created_at < datetime.combine(to_date + timedelta(days=1), time.min))
    total = q.count()
    items = q.order_by(Billing.created_at.desc(), Billing.id.desc()).offset(skip).limit(limit).all()
    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.get("/patients/{patient_id}/billings", response_model=PaginatedBillings)
def patient_billings(
    patient_id: int,
    payment_status: Optional[PaymentStatus] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if user.role == "doctor":
        doctor = _doctor_for_user(db, user)
        if patient.doctor_id != doctor.id:
            raise HTTPException(status_code=403, detail="Doctors can only view billings for their assigned patients")
    return _list_billings(db, user, payment_status, None, patient_id, from_date, to_date, skip, limit)


@router.get("/doctors/{doctor_id}/billings", response_model=PaginatedBillings)
def doctor_billings(
    doctor_id: int,
    payment_status: Optional[PaymentStatus] = None,
    patient_id: Optional[int] = Query(None, gt=0),
    from_date: Optional[date] = None, to_date: Optional[date] = None,
    skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    if user.role == "doctor" and _doctor_for_user(db, user).id != doctor_id:
        raise HTTPException(status_code=403, detail="Doctors can only view their own billings")
    return _list_billings(db, user, payment_status, doctor_id, patient_id, from_date, to_date, skip, limit)


@router.get("/billings", response_model=PaginatedBillings)
def list_billings(
    payment_status: Optional[PaymentStatus] = None,
    doctor_id: Optional[int] = Query(None, gt=0),
    patient_id: Optional[int] = Query(None, gt=0),
    from_date: Optional[date] = None, to_date: Optional[date] = None,
    skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date")
    if user.role == "doctor":
        own = _doctor_for_user(db, user)
        if doctor_id is not None and doctor_id != own.id:
            raise HTTPException(status_code=403, detail="Doctors can only view their own billings")
    return _list_billings(db, user, payment_status, doctor_id, patient_id, from_date, to_date, skip, limit)


@router.put("/billings/{billing_id}", response_model=BillingResponse)
def put_billing(
    billing_id: int, payload: BillingPut, db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    obj = db.query(Billing).filter(Billing.id == billing_id, Billing.is_active.is_(True)).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Billing record not found")
    _apply_update(obj, payload.model_dump(), user.username)
    try:
        db.commit(); db.refresh(obj)
    except SQLAlchemyError:
        db.rollback(); raise HTTPException(status_code=500, detail="Unable to update billing record")
    return obj


@router.patch("/billings/{billing_id}", response_model=BillingResponse)
def patch_billing(
    billing_id: int, payload: BillingPatch, db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    obj = db.query(Billing).filter(Billing.id == billing_id, Billing.is_active.is_(True)).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Billing record not found")
    _apply_update(obj, payload.model_dump(exclude_unset=True), user.username)
    try:
        db.commit(); db.refresh(obj)
    except SQLAlchemyError:
        db.rollback(); raise HTTPException(status_code=500, detail="Unable to update billing record")
    return obj


@router.delete("/billings/{billing_id}", status_code=status.HTTP_200_OK)
def delete_billing(
    billing_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin),
):
    obj = db.query(Billing).filter(Billing.id == billing_id, Billing.is_active.is_(True)).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Billing record not found")
    obj.is_active = False
    obj.updated_by = user.username
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback(); raise HTTPException(status_code=500, detail="Unable to soft-delete billing record")
    return {"message": "Billing record soft-deleted successfully"}


@reports_router.get("/revenue/doctor", response_model=list[DoctorRevenue])
def revenue_per_doctor(
    from_date: Optional[date] = None, to_date: Optional[date] = None,
    doctor_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db), user: User = Depends(require_admin),
):
    q = db.query(Billing.doctor_id, func.sum(Billing.total_amount).label("total_revenue")).filter(
        Billing.is_active.is_(True), Billing.payment_status == "paid"
    )
    if doctor_id is not None: q = q.filter(Billing.doctor_id == doctor_id)
    if from_date is not None: q = q.filter(Billing.created_at >= datetime.combine(from_date, time.min))
    if to_date is not None: q = q.filter(Billing.created_at < datetime.combine(to_date + timedelta(days=1), time.min))
    rows = q.group_by(Billing.doctor_id).order_by(Billing.doctor_id).all()
    return [{"doctor_id": r.doctor_id, "total_revenue": r.total_revenue or Decimal("0.00")} for r in rows]


@reports_router.get("/revenue/daily", response_model=list[DailyRevenue])
def revenue_per_day(
    from_date: Optional[date] = None, to_date: Optional[date] = None,
    doctor_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db), user: User = Depends(require_admin),
):
    day_expr = func.date(Billing.created_at)
    q = db.query(day_expr.label("revenue_date"), func.sum(Billing.total_amount).label("total_revenue")).filter(
        Billing.is_active.is_(True), Billing.payment_status == "paid"
    )
    if doctor_id is not None: q = q.filter(Billing.doctor_id == doctor_id)
    if from_date is not None: q = q.filter(Billing.created_at >= datetime.combine(from_date, time.min))
    if to_date is not None: q = q.filter(Billing.created_at < datetime.combine(to_date + timedelta(days=1), time.min))
    rows = q.group_by(day_expr).order_by(day_expr).all()
    return [{"date": str(r.revenue_date), "total_revenue": r.total_revenue or Decimal("0.00")} for r in rows]


@reports_router.get("/revenue")
def revenue_summary(
    doctor_id: Optional[int] = Query(None, gt=0),
    from_date: Optional[date] = None, to_date: Optional[date] = None,
    db: Session = Depends(get_db), user: User = Depends(require_admin),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date")
    q = db.query(func.sum(Billing.total_amount)).filter(
        Billing.is_active.is_(True), Billing.payment_status == "paid"
    )
    if doctor_id is not None: q = q.filter(Billing.doctor_id == doctor_id)
    if from_date is not None: q = q.filter(Billing.created_at >= datetime.combine(from_date, time.min))
    if to_date is not None: q = q.filter(Billing.created_at < datetime.combine(to_date + timedelta(days=1), time.min))
    total = q.scalar() or Decimal("0.00")
    return {"doctor_id": doctor_id, "from_date": from_date, "to_date": to_date, "total_revenue": total, "revenue_basis": "active billings with payment_status=paid"}
