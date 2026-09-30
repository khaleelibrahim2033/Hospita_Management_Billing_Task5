
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Doctor, Patient, User
from app.schemas import (
    DoctorCreate,
    DoctorResponse,
    DoctorUpdate,
    PatientResponse,
)

router = APIRouter(prefix="/doctors", tags=["Doctors"])


# CREATE DOCTOR
@router.post(
    "",
    response_model=DoctorResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_doctor(
    payload: DoctorCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    email = str(payload.email)

    existing = db.query(Doctor).filter(Doctor.email == email).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Doctor email already exists",
        )

    doctor = Doctor(
        name=payload.name,
        specialization=payload.specialization,
        email=email,
        created_by=_.username, updated_by=_.username,
    )

    try:
        db.add(doctor)
        db.commit()
        db.refresh(doctor)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to create doctor",
        )

    return doctor


# GET ALL ACTIVE DOCTORS
@router.get("", response_model=list[DoctorResponse])
def list_doctors(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    specialization: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(Doctor).filter(Doctor.is_active.is_(True))

    if specialization:
        query = query.filter(
            Doctor.specialization.ilike(f"%{specialization}%")
        )

    return (
        query.order_by(Doctor.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


# GET DOCTOR BY ID
@router.get("/{doctor_id}", response_model=DoctorResponse)
def get_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    doctor = (
        db.query(Doctor)
        .filter(
            Doctor.id == doctor_id,
            Doctor.is_active.is_(True),
        )
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor not found",
        )

    return doctor


# UPDATE DOCTOR
@router.put("/{doctor_id}", response_model=DoctorResponse)
def update_doctor(
    doctor_id: int,
    payload: DoctorUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    doctor = (
        db.query(Doctor)
        .filter(
            Doctor.id == doctor_id,
            Doctor.is_active.is_(True),
        )
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    if update_data.get("email") is not None:
        email = str(update_data["email"])

        existing = (
            db.query(Doctor)
            .filter(
                Doctor.email == email,
                Doctor.id != doctor_id,
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Doctor email already exists",
            )

        update_data["email"] = email

    doctor.updated_by = _.username
    for field, value in update_data.items():
        setattr(doctor, field, value)

    try:
        db.commit()
        db.refresh(doctor)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to update doctor",
        )

    return doctor


# SOFT DELETE DOCTOR
@router.delete("/{doctor_id}", response_model=DoctorResponse)
def delete_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    doctor = (
        db.query(Doctor)
        .filter(
            Doctor.id == doctor_id,
            Doctor.is_active.is_(True),
        )
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor not found",
        )

    doctor.is_active = False
    doctor.updated_by = _.username

    try:
        db.commit()
        db.refresh(doctor)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to delete doctor",
        )

    return doctor


# ASSIGN PATIENT TO DOCTOR
@router.post(
    "/{doctor_id}/patients/{patient_id}",
    response_model=PatientResponse,
)
def assign_patient(
    doctor_id: int,
    patient_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    doctor = (
        db.query(Doctor)
        .filter(
            Doctor.id == doctor_id,
            Doctor.is_active.is_(True),
        )
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Active doctor not found",
        )

    patient = (
        db.query(Patient)
        .filter(
            Patient.id == patient_id,
            Patient.is_active.is_(True),
        )
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Active patient not found",
        )

    patient.doctor_id = doctor.id
    patient.updated_by = _.username

    try:
        db.commit()
        db.refresh(patient)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to assign patient",
        )

    return patient


# GET PATIENTS ASSIGNED TO A DOCTOR
@router.get(
    "/{doctor_id}/patients",
    response_model=list[PatientResponse],
)
def get_doctor_patients(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doctor = (
        db.query(Doctor)
        .filter(
            Doctor.id == doctor_id,
            Doctor.is_active.is_(True),
        )
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor not found",
        )

    if current_user.role == "doctor":
        linked_doctor = (
            db.query(Doctor)
            .filter(
                Doctor.email == current_user.email,
                Doctor.is_active.is_(True),
            )
            .first()
        )

        if not linked_doctor or linked_doctor.id != doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctors can only view their own assigned patients",
            )

    return (
        db.query(Patient)
        .filter(
            Patient.doctor_id == doctor_id,
            Patient.is_active.is_(True),
        )
        .order_by(Patient.id)
        .all()
    )