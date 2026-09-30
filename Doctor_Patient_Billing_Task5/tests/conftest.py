import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.database import Base, get_db
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread":False}, poolclass=StaticPool)
@event.listens_for(engine, "connect")
def fk_on(conn, record):
    cur=conn.cursor(); cur.execute("PRAGMA foreign_keys=ON"); cur.close()
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
def override_db():
    db=TestingSession()
    try: yield db
    finally: db.close()
app.dependency_overrides[get_db] = override_db
@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine); Base.metadata.create_all(bind=engine)
    yield
@pytest.fixture
def client():
    with TestClient(app) as c: yield c
@pytest.fixture
def accounts(client):
    def register(username,email,role):
        r=client.post('/auth/register',json={'username':username,'email':email,'password':'TestPass123!','role':role})
        assert r.status_code==201, r.text
        token=client.post('/auth/login',json={'email':email,'password':'TestPass123!'}).json()['access_token']
        return {'Authorization':f'Bearer {token}'}
    admin=register('admin','admin@example.com','admin')
    doctor=register('doc','doc@example.com','doctor')
    d=client.post('/doctors/',headers=admin,json={'name':'Dr Doc','specialization':'ENT','email':'doc@example.com','is_active':True}).json()
    p=client.post('/patients/',headers=admin,json={'name':'Patient One','age':30,'gender':'other','doctor_id':d['id']}).json()
    return admin,doctor,d,p
