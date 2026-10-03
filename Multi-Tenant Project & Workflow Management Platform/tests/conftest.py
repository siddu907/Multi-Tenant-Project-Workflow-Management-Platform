import os
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB_PATH = Path(tempfile.gettempdir()) / f"test_multitenant_{uuid.uuid4().hex}.sqlite3"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DB_PATH}")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")
os.environ.setdefault("UPLOAD_DIRECTORY", "uploads")
os.environ.setdefault("MAX_UPLOAD_SIZE_BYTES", "10485760")
os.environ["ALLOW_PUBLIC_REGISTRATION"] = "true"

from app.database import Base, SessionLocal, engine
from app.main import app
from app.services.auth_service import create_user

if TEST_DB_PATH.exists():
    try:
        TEST_DB_PATH.unlink()
    except PermissionError:
        pass
Base.metadata.create_all(bind=engine)


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client


def provision_test_user(client, *, name, email, password="Secret123!", role="team_member"):
    with SessionLocal() as db:
        user = create_user(db, name=name, email=email, password=password, role_name=role)
        db.commit()
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return login.json()
