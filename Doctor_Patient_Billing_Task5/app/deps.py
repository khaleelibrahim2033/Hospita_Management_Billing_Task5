from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, Doctor
from .security import decode_token

bearer = HTTPBearer(auto_error=False)
def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    payload = decode_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token", headers={"WWW-Authenticate": "Bearer"})
    user = db.query(User).filter(User.email == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User for token not found", headers={"WWW-Authenticate": "Bearer"})
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def doctor_for_user(db: Session, user: User) -> Doctor:
    doctor = db.query(Doctor).filter(Doctor.email == user.email).first()
    if not doctor:
        raise HTTPException(status_code=403, detail="Doctor profile not found")
    return doctor
