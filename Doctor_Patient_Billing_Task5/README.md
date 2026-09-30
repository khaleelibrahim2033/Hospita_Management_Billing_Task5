# Doctor-Patient Management API — Billing Levels 27–29

An enhancement of the existing Doctor-Patient Management FastAPI project. This version retains authentication, doctors, patients and appointments, and adds Billing, Revenue Reports, authorization, filtering, pagination and transactional consistency.

## Features

- JWT authentication and Admin/Doctor roles (existing project)
- Doctor, patient and appointment APIs (existing project)
- Billing records linked to patients, doctors and optional appointments
- Automatic `total_amount = consultation_fee + additional_charges`
- Payment statuses: `pending`, `paid`, `cancelled`; payment modes: `cash`, `card`, `upi`
- Active-doctor, patient and appointment ownership validation
- Reject cancelled appointments and prevent duplicate bills per appointment
- Admin-only billing create/update/soft-delete; doctors can view their own patient billings
- Filtering by status, doctor, patient and date range, with pagination
- Admin-only revenue summary, revenue per doctor and revenue per day
- Atomic billing creation and appointment completion in one database commit
- SQLite foreign keys, unique and check constraints

## Project structure

```text
app/
  main.py
  database.py
  models.py
  schemas.py
  auth.py
  routers/
    auth.py
    doctors.py
    patients.py
    appointments.py
    billings.py
tests/
.env.example
.gitignore
Dockerfile
requirements.txt
README.md
```

## Setup (Windows PowerShell)

Open PowerShell in this project directory:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set a strong `SECRET_KEY` and your desired `DATABASE_URL` in `.env`. This package uses SQLite by default. Back up your existing database before running the updated application. The application calls `Base.metadata.create_all()` at startup, which creates the new `billings` table without deleting existing tables. For existing non-SQLite schemas or production deployments, use a migration tool such as Alembic.

Run the server:

```powershell
uvicorn app.main:app --reload
```

Swagger: http://127.0.0.1:8000/docs

Run tests:

```powershell
pytest
```

## Billing data model

| Field | Type / rule |
|---|---|
| `id` | Integer primary key |
| `patient_id` | Required FK to patients |
| `doctor_id` | Required FK to doctors |
| `appointment_id` | Optional FK to appointments; unique when present |
| `consultation_fee` | Non-negative decimal, 2 decimal places |
| `additional_charges` | Non-negative decimal, defaults to 0 |
| `total_amount` | Calculated by API; never accepted from client |
| `payment_status` | `pending`, `paid`, or `cancelled` |
| `payment_mode` | `cash`, `card`, `upi`, or null while pending |
| `is_active` | Boolean; soft delete sets false |
| `created_at`, `updated_at` | Audit timestamps |

A payment marked `paid` requires a payment mode. Revenue reports include only active billings with `payment_status=paid`. Date filters apply to the billing record's `created_at`, inclusive of the `to_date`.

## Authorization

| Action | Admin | Doctor |
|---|---:|---:|
| Create billing | Yes | 403 |
| View billing by ID | Yes | Own doctor billings only |
| List billings | All | Own doctor billings only |
| View patient's billings | Yes | Only assigned patients |
| View doctor's billings | Any doctor | Own doctor ID only |
| Replace/update billing | Yes | 403 |
| Patch billing | Yes | 403 |
| Soft-delete billing | Yes | 403 |
| Revenue reports | Yes | 403 |

All billing endpoints require a valid JWT. In Swagger, use **Authorize** and provide `Bearer <access_token>`.

## API reference

### Billing (Level 27)

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/billings` | Create a bill (Admin only) |
| GET | `/billings/{billing_id}` | Get a bill |
| GET | `/billings` | Filtered, paginated billing list |
| GET | `/patients/{patient_id}/billings` | Patient billing history |
| GET | `/doctors/{doctor_id}/billings` | Doctor billing history |
| PUT | `/billings/{billing_id}` | Replace bill financial/payment fields (Admin only) |
| PATCH | `/billings/{billing_id}` | Partially update bill (Admin only) |
| DELETE | `/billings/{billing_id}` | Soft-delete (Admin only) |

Example create body:

```json
{
  "patient_id": 1,
  "doctor_id": 1,
  "appointment_id": 1,
  "consultation_fee": "750.00",
  "additional_charges": "150.00",
  "payment_status": "pending",
  "payment_mode": null
}
```

`total_amount` is calculated as `900.00`. Do not send it in the request. If an appointment is supplied, it must belong to the selected patient and doctor and must not be cancelled. When the billing is committed, that appointment is marked `completed` in the same transaction. If the transaction fails, both changes roll back. An appointment can have only one billing record; a duplicate returns HTTP 409. For bills without an appointment, multiple bills are allowed.

Example update body for PUT:

```json
{
  "consultation_fee": "800.00",
  "additional_charges": "100.00",
  "payment_status": "paid",
  "payment_mode": "upi"
}
```

Example PATCH body:

```json
{
  "payment_status": "paid",
  "payment_mode": "card"
}
```

### Filtering and pagination (Level 28)

`GET /billings` supports:

- `payment_status=pending|paid|cancelled`
- `doctor_id=1`
- `patient_id=1`
- `from_date=2026-01-01`
- `to_date=2026-01-31`
- `skip=0`
- `limit=20` (maximum 100)

Example:

```text
GET /billings?payment_status=paid&doctor_id=1&from_date=2026-01-01&to_date=2026-01-31&skip=0&limit=10
```

The patient and doctor billing-history endpoints also support pagination, date filters and payment-status filtering. All list responses contain `total`, `skip`, `limit` and `items`.

### Revenue reports (Level 28)

All report endpoints are Admin-only and calculate collected revenue from active, paid bills:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/reports/revenue` | Revenue total, optionally filtered by doctor/date |
| GET | `/reports/revenue/doctor` | Revenue grouped by doctor |
| GET | `/reports/revenue/daily` | Revenue grouped by calendar day |

Example:

```text
GET /reports/revenue?doctor_id=1&from_date=2026-01-01&to_date=2026-01-31
```

Note: API uses `from_date` and `to_date` (not `from` and `to`) to make date filter names consistent across list and report endpoints.

### Transactions and consistency (Level 29)

- Billing creation and optional appointment status update are committed together.
- Failed commits call `rollback()` and return an error; no partial write is intentionally left committed.
- A unique database constraint on `appointment_id` protects against duplicate billing, including concurrent requests.
- Foreign keys use `ON DELETE RESTRICT`; bills are soft-deleted, preserving audit history.
- Check constraints enforce non-negative amounts and allowed payment status/mode values.
- Application-level validation checks that patient and doctor exist and are active, and that an optional appointment belongs to both.

## Suggested Swagger testing flow

1. Register and log in as Admin using existing `/auth/register` and `/auth/login`.
2. Click **Authorize** in Swagger and enter the Admin bearer token.
3. Create a doctor, patient and appointment using the existing APIs (or use existing records).
4. Create a billing record using `POST /billings`.
5. Verify `total_amount` is automatically calculated and the appointment is marked `completed`.
6. Call `GET /billings/{billing_id}`, `GET /patients/{patient_id}/billings`, `GET /doctors/{doctor_id}/billings` and `GET /billings`.
7. Test filtering and pagination.
8. Patch payment status to `paid` and supply a payment mode.
9. Check `/reports/revenue`, `/reports/revenue/doctor` and `/reports/revenue/daily`.
10. Try creating a second bill for the same appointment (expect 409).
11. Try billing a cancelled appointment (expect 400).
12. Log in as a Doctor and verify that only own-patient billing records are visible. Try write and report APIs (expect 403).
13. Delete a bill as Admin and verify it no longer appears in active billing lists, while the database row remains with `is_active=false`.

## Common status codes

- `201`: billing created
- `200`: successful read/update/soft delete
- `401`: missing or invalid JWT
- `403`: insufficient role or doctor scope
- `404`: patient, doctor, appointment or bill not found
- `400`: cancelled appointment or mismatched appointment ownership
- `409`: duplicate appointment billing / database integrity conflict
- `422`: invalid field, enum, amount or date range
- `500`: database failure after rollback

## Submission checklist

- [ ] Run existing and billing tests locally (`pytest`)
- [ ] Verify Swagger endpoints and authorization
- [ ] Capture real screenshots of Billing APIs and reports in Swagger/Postman
- [ ] Review `.env` and never commit real secrets
- [ ] Commit and push updated source, requirements and README to GitHub
