# Hospita_Management_Billing_Task5
# Doctor-Patient Management System – Billing Module
## Technologies Used

* **Python** – Backend programming
* **FastAPI** – REST API development
* **Pydantic** – Request validation and data schemas
* **SQLAlchemy** – Database operations and ORM
* **SQLite / Existing Project Database** – Data storage
* **JWT Authentication** – Secure API access
* **Uvicorn** – ASGI server
* **Swagger UI** – API testing and documentation

## Project Structure

```text
Doctor_Patient_Billing_Level27_29/
│
├── app/
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   │
│   └── routers/
│       ├── __init__.py
│       ├── auth.py
│       ├── doctors.py
│       ├── patients.py
│       ├── appointments.py
│       └── billings.py
│
├── requirements.txt
├── README.md
└── .env
```

*The structure above describes the main files; additional project files may be present.*

## Billing Flow

The Billing Module follows a structured process to create and manage patient bills.

### 1. User Authentication

* Admin and Doctor users log in using their registered credentials.
* JWT authentication is used to protect authorized API endpoints.
* The system checks the user's role before allowing access to restricted operations.

### 2. Patient and Doctor Selection

* The billing process uses an existing patient record.
* An existing doctor record is associated with the billing.
* An appointment can also be linked to the billing record.

### 3. Create Billing Record

**Endpoint:** `POST /billings`

* Admin users can create billing records.
* The system validates the patient, doctor and appointment information.
* Duplicate billing for the same appointment is prevented.
* The total amount is calculated by the backend according to the billing logic.
* The appointment status is updated to completed when billing is successfully created, where applicable.

### 4. View Billing Details

**Endpoint:** `GET /billings/{billing_id}`

* Retrieves a specific billing record using its ID.
* Displays the associated patient, doctor, appointment and payment information, subject to access permissions.

### 5. Patient Billing History

**Endpoint:** `GET /patients/{patient_id}/billings`

* Retrieves billing records associated with a particular patient.
* Helps track a patient's previous bills and payment information.

### 6. Doctor Billing History

**Endpoint:** `GET /doctors/{doctor_id}/billings`

* Retrieves billing records associated with a particular doctor.
* Doctors can access billing information within their permitted scope.

### 7. Update Billing

**PUT:** `/billings/{billing_id}`

* Updates a billing record using a complete update request.
* Validates the supplied information before saving changes.

**PATCH:** `/billings/{billing_id}`

* Updates selected fields of an existing billing record.
* Allows partial modification without resending the complete record.

### 8. Soft Delete Billing

**Endpoint:** `DELETE /billings/{billing_id}`

* Deactivates a billing record instead of permanently removing it from the database.
* Maintains historical records for reference and reporting.

### 9. Billing List, Filtering and Pagination

**Endpoint:** `GET /billings`

* Retrieves billing records.
* Supports the filters and pagination parameters implemented in the API.
* Helps manage large sets of billing information.

## Revenue Reports

### 1. Total Revenue

**Endpoint:** `GET /reports/revenue`

Retrieves the overall revenue information from billing records according to the implemented report logic.

### 2. Revenue Per Doctor

**Endpoint:** `GET /reports/revenue/doctor`

Provides revenue information grouped by doctor, allowing administrators to review billing totals associated with each doctor.

### 3. Daily Revenue

**Endpoint:** `GET /reports/revenue/daily`

Provides daily revenue information grouped by date to help track billing activity over time.

## Role-Based Access Control

| Operation                    | Admin   | Doctor                          |
| ---------------------------- | ------- | ------------------------------- |
| Create billing               | Allowed | Restricted                      |
| View billing                 | Allowed | Permitted within assigned scope |
| Update billing               | Allowed | Restricted                      |
| Delete billing               | Allowed | Restricted                      |
| View patient billing history | Allowed | Subject to access permissions   |
| View doctor billing history  | Allowed | Subject to assigned scope       |
| Access revenue reports       | Allowed | Restricted                      |

Unauthorized users receive appropriate HTTP error responses based on authentication and authorization checks.

## Validation and Error Handling

The Billing Module includes validation and error handling for common scenarios.

| Scenario                          | HTTP Status |
| --------------------------------- | ----------: |
| Successful billing creation       |         201 |
| Successful retrieval              |         200 |
| Invalid or missing input          |         422 |
| Unauthenticated request           |         401 |
| Unauthorized role                 |         403 |
| Billing record not found          |         404 |
| Duplicate appointment billing     |         409 |
| Billing for cancelled appointment |         400 |

## Database Design

The Billing model stores billing-related information and connects to existing system entities.

Key fields include:

* `id` – Unique billing record ID
* `patient_id` – Associated patient ID
* `doctor_id` – Associated doctor ID
* `appointment_id` – Optional linked appointment ID
* `total_amount` – Calculated billing amount
* `payment_status` – Payment status
* `payment_mode` – Payment method
* `is_active` – Indicates whether the billing record is active
* `created_at` – Record creation timestamp
* `updated_at` – Last update timestamp

Foreign keys, constraints and indexes help maintain data integrity and support queries.

## Installation and Setup

### 1. Clone the Repository

```bash
git clone <your-github-repository-url>
cd Doctor_Patient_Billing_Level27_29
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Set the required database URL and authentication configuration in the `.env` file, according to the existing project settings.

### 5. Run the Application

```bash
uvicorn app.main:app --reload
```

### 6. Open Swagger UI

Visit:

```text
http://127.0.0.1:8000/docs
```

Swagger UI can be used to register or log in, authorize requests and test the Billing and Reports endpoints.

## Testing Workflow

1. Register an Admin and a Doctor account, if required.
2. Log in and authorize Swagger using the appropriate credentials.
3. Ensure that valid patient and doctor records exist.
4. Create an appointment that can be billed.
5. Create a billing record using `POST /billings`.
6. Retrieve billing details using `GET /billings/{billing_id}`.
7. Test patient and doctor billing history.
8. Test PUT and PATCH operations.
9. Test soft deletion.
10. Verify filtering and pagination.
11. Test total, doctor-wise and daily revenue reports.
12. Verify restricted Doctor access returns `403 Forbidden`.
13. Test duplicate appointment billing for `409 Conflict`.
14. Test cancelled appointment billing for `400 Bad Request`.

## Security

* JWT-based authentication protects secured routes.
* Role-based access control restricts Admin-only operations.
* Doctor access is scoped according to assigned permissions.
* Passwords and secret keys should not be exposed in source code or screenshots.
* Environment variables should be used for sensitive configuration.

## Conclusion

The Billing Module extends the existing Doctor-Patient Management System by introducing billing record management, payment tracking, access control and revenue reporting.

It connects patients, doctors and appointments with billing information while supporting validation, secure access, soft deletion and structured reporting through REST APIs.

## Author

**Vishnu Vardhan Reddy**

**Project:** Doctor-Patient Management System – Billing Module
**Levels:** 27–29
**Framework:** FastAPI
**Language:** Python
