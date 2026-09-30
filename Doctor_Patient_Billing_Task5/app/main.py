
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from collections import defaultdict, deque
from time import monotonic
from sqlalchemy.exc import SQLAlchemyError
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import auth, doctors, patients, appointments, billings

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Doctor-Patient Management & Billing API",
    description=(
        "End-to-end FastAPI backend with JWT authentication, "
        "role-based access control, doctors, patients, appointments, billing and revenue reports."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "Authentication", "description": "Register and login"},
        {"name": "Health", "description": "API health check"},
        {"name": "Doctors", "description": "Doctor management"},
        {"name": "Patients", "description": "Patient management"},
        {"name": "Appointments", "description": "Appointment management"},
        {"name": "Billing", "description": "Billing and payments"},
        {"name": "Billing Reports", "description": "Revenue reports"},
        
    ],
)

# CORS configuration
# Restrict allowed origins to your frontend URL when known.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(doctors.router)
app.include_router(patients.router)
app.include_router(appointments.router)
app.include_router(billings.router)
app.include_router(billings.reports_router)


# Health check
@app.get("/", tags=["Health"])
def root():
    return {"message": "Doctor-Patient Management API is running"}

# Uniform API error format
@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.status_code, "message": exc.detail}}, headers=exc.headers)

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(x) for x in e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"error": {"code": 422, "message": "Validation failed", "details": details}})

@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(status_code=500, content={"error": {"code": 500, "message": "A database operation failed"}})

@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": {"code": 500, "message": "Internal server error"}})

# Simple per-process rate limit: 120 requests per client per minute.
_rate_hits = defaultdict(deque)
@app.middleware("http")
async def basic_rate_limit(request: Request, call_next):
    now=monotonic(); key=request.client.host if request.client else "unknown"; hits=_rate_hits[key]
    while hits and now-hits[0] > 60: hits.popleft()
    if len(hits) >= 120:
        return JSONResponse(status_code=429, content={"error":{"code":429,"message":"Rate limit exceeded; retry shortly"}}, headers={"Retry-After":"60"})
    hits.append(now)
    return await call_next(request)
