
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Patient, User, Doctor
from app.schemas import (
    PaginatedPatients,
    PatientCreate,
    PatientUpdate,
    PatientResponse,
)

router = APIRouter(prefix="/patients", tags=["Patients"])


def get_doctor(db: Session, doctor_id: int):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor not found",
        )

    if not doctor.is_active:
        raise HTTPException(
            status_code=400,
            detail="Cannot assign patient to an inactive doctor",
        )

    return doctor


def get_current_doctor(db: Session, current_user: User):
    doctor = (
        db.query(Doctor)
        .filter(Doctor.email == current_user.email)
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=403,
            detail="Doctor profile not found",
        )

    if not doctor.is_active:
        raise HTTPException(
            status_code=403,
            detail="Your doctor profile is inactive",
        )

    return doctor


# CREATE PATIENT
@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doctor_id = payload.doctor_id

    if current_user.role == "doctor":
        doctor = get_current_doctor(db, current_user)

        if doctor_id is not None and doctor_id != doctor.id:
            raise HTTPException(
                status_code=403,
                detail="Doctors can only assign patients to themselves",
            )

        doctor_id = doctor.id

    elif doctor_id is not None:
        get_doctor(db, doctor_id)

    patient = Patient(
        name=payload.name,
        age=payload.age,
        phone=payload.phone,
        doctor_id=doctor_id,
        created_by=current_user.username,
        updated_by=current_user.username,
    )

    try:
        db.add(patient)
        db.commit()
        db.refresh(patient)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to create patient",
        )

    return patient


# GET ALL PATIENTS WITH FILTERING AND PAGINATION
@router.get("", response_model=PaginatedPatients)
def list_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    name: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Patient).filter(Patient.is_active.is_(True))

    # Doctors can only view their assigned patients.
    # Admins can view all active patients.
    if current_user.role == "doctor":
        doctor = get_current_doctor(db, current_user)
        query = query.filter(Patient.doctor_id == doctor.id)

    # Filter patients by name
    if name:
        query = query.filter(Patient.name.ilike(f"%{name}%"))

    total = query.count()

    items = (
        query.order_by(Patient.id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": items,
    }


# GET PATIENT BY ID
@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
            detail="Patient not found",
        )

    if current_user.role == "doctor":
        doctor = get_current_doctor(db, current_user)

        if patient.doctor_id != doctor.id:
            raise HTTPException(
                status_code=403,
                detail="You can only view your assigned patients",
            )

    return patient


# UPDATE PATIENT
@router.put("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
            detail="Patient not found",
        )

    if current_user.role == "doctor":
        doctor = get_current_doctor(db, current_user)

        if patient.doctor_id != doctor.id:
            raise HTTPException(
                status_code=403,
                detail="You can only update your assigned patients",
            )

    update_data = payload.model_dump(exclude_unset=True)
    patient.updated_by = current_user.username

    for key, value in update_data.items():
        setattr(patient, key, value)

    try:
        db.commit()
        db.refresh(patient)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to update patient",
        )

    return patient


# SOFT DELETE PATIENT
@router.delete("/{patient_id}")
def delete_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
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
            detail="Patient not found",
        )

    if current_user.role == "doctor":
        doctor = get_current_doctor(db, current_user)

        if patient.doctor_id != doctor.id:
            raise HTTPException(
                status_code=403,
                detail="You can only delete your assigned patients",
            )

    # Soft delete: patient remains in the database
    patient.is_active = False
    patient.updated_by = current_user.username

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to delete patient",
        )

    return {"message": "Patient deleted successfully"}