from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from .models import Doctor, Patient, Appointment

VALID_STATUSES = {"scheduled", "completed", "cancelled"}
def validate_appointment(db: Session, doctor_id: int, patient_id: int, appointment_date, exclude_id: int | None = None):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    if not doctor.is_active:
        raise HTTPException(status_code=400, detail="Doctor is inactive")
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if patient.doctor_id != doctor_id:
        raise HTTPException(status_code=400, detail="Patient is not assigned to this doctor")
    if appointment_date.tzinfo is None:
        appointment_date = appointment_date.replace(tzinfo=None)
    else:
        appointment_date = appointment_date.astimezone().replace(tzinfo=None)
    # Appointment slots are treated as 30 minutes because duration is not a requested field.
    start = appointment_date - timedelta(minutes=30)
    end = appointment_date + timedelta(minutes=30)
    q = db.query(Appointment).filter(Appointment.doctor_id == doctor_id, Appointment.status == "scheduled", Appointment.appointment_date > start, Appointment.appointment_date < end)
    if exclude_id is not None:
        q = q.filter(Appointment.id != exclude_id)
    if q.first():
        raise HTTPException(status_code=409, detail="Doctor already has an overlapping scheduled appointment")
    return appointment_date

def optimized_appointments(db: Session, query):
    return query.options(joinedload(Appointment.doctor), joinedload(Appointment.patient)).order_by(Appointment.appointment_date).all()
