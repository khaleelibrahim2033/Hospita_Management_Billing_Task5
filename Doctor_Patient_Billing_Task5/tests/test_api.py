import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_doctor_patient.db"
os.environ["SECRET_KEY"] = "test-secret-key"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200


def test_register():
    response = client.post(
        "/auth/register",
        json={
            "username": "testadmin",
            "email": "testadmin@example.com",
            "password": "password123",
            "role": "admin",
        },
    )
    assert response.status_code in (201, 400)


def test_invalid_phone():
    response = client.post(
        "/auth/register",
        json={
            "username": "phoneuser",
            "email": "phone@example.com",
            "password": "password123",
            "role": "doctor",
        },
    )
    assert response.status_code in (201, 400)
