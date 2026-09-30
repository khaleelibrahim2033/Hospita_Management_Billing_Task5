from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Appointment, Doctor, Patient, User
from app.schemas import AppointmentCreate, AppointmentUpdate, AppointmentResponse, AppointmentStatus

router = APIRouter(prefix="/appointments", tags=["Appointments"])

def doctor_for_user(db: Session, user: User):
    doctor = db.query(Doctor).filter(Doctor.email == user.email, Doctor.is_active.is_(True)).first()
    if not doctor:
        raise HTTPException(status_code=403, detail="Active doctor profile not found")
    return doctor

def ensure_no_overlap(db: Session, doctor_id: int, appointment_date: datetime, exclude_id=None):
    q = db.query(Appointment).filter(Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == appointment_date, Appointment.status == "scheduled")
    if exclude_id is not None: q = q.filter(Appointment.id != exclude_id)
    if q.first():
        raise HTTPException(status_code=409, detail="Doctor already has a scheduled appointment at this time")

@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED, summary="Create an appointment", description="Admin may book any active doctor. Doctors may book only themselves for patients assigned to them.")
def create_appointment(payload: AppointmentCreate, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    doctor=db.query(Doctor).filter(Doctor.id==payload.doctor_id, Doctor.is_active.is_(True)).first()
    patient=db.query(Patient).filter(Patient.id==payload.patient_id, Patient.is_active.is_(True)).first()
    if not doctor: raise HTTPException(404, "Active doctor not found")
    if not patient: raise HTTPException(404, "Active patient not found")
    if user.role == "doctor":
        own=doctor_for_user(db,user)
        if own.id != doctor.id or patient.doctor_id != own.id:
            raise HTTPException(403, "Doctors may book only their assigned patients")
    ensure_no_overlap(db, doctor.id, payload.appointment_date)
    obj=Appointment(doctor_id=doctor.id, patient_id=patient.id, appointment_date=payload.appointment_date,
        status=payload.status.value, created_by=user.username, updated_by=user.username)
    try:
        db.add(obj); db.commit(); db.refresh(obj)
    except SQLAlchemyError:
        db.rollback(); raise HTTPException(500, "Unable to create appointment")
    return obj

@router.get("", response_model=list[AppointmentResponse], summary="List appointments")
def list_appointments(doctor_id: int|None=None, patient_id: int|None=None, skip:int=Query(0,ge=0), limit:int=Query(20,ge=1,le=100), db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    q=db.query(Appointment).options(joinedload(Appointment.doctor), joinedload(Appointment.patient))
    if user.role == "doctor": q=q.filter(Appointment.doctor_id==doctor_for_user(db,user).id)
    elif doctor_id is not None: q=q.filter(Appointment.doctor_id==doctor_id)
    if patient_id is not None: q=q.filter(Appointment.patient_id==patient_id)
    return q.order_by(Appointment.appointment_date).offset(skip).limit(limit).all()

@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(appointment_id:int, db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    q=db.query(Appointment).filter(Appointment.id==appointment_id)
    if user.role=="doctor": q=q.filter(Appointment.doctor_id==doctor_for_user(db,user).id)
    obj=q.first()
    if not obj: raise HTTPException(404,"Appointment not found")
    return obj

@router.put("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(appointment_id:int, payload:AppointmentUpdate, db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    q=db.query(Appointment).filter(Appointment.id==appointment_id)
    if user.role=="doctor": q=q.filter(Appointment.doctor_id==doctor_for_user(db,user).id)
    obj=q.first()
    if not obj: raise HTTPException(404,"Appointment not found")
    changes=payload.model_dump(exclude_unset=True)
    dt=changes.get("appointment_date",obj.appointment_date); st=changes.get("status",obj.status)
    if st == AppointmentStatus.scheduled.value or getattr(st,"value",st)=="scheduled": ensure_no_overlap(db,obj.doctor_id,dt,obj.id)
    for k,v in changes.items(): setattr(obj,k,v.value if hasattr(v,"value") else v)
    obj.updated_by=user.username
    try: db.commit(); db.refresh(obj)
    except SQLAlchemyError: db.rollback(); raise HTTPException(500,"Unable to update appointment")
    return obj

@router.delete("/{appointment_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_appointment(appointment_id:int, db:Session=Depends(get_db)):
    obj=db.query(Appointment).filter(Appointment.id==appointment_id).first()
    if not obj: raise HTTPException(404,"Appointment not found")
    try: db.delete(obj); db.commit()
    except SQLAlchemyError: db.rollback(); raise HTTPException(500,"Unable to delete appointment")
    return None
