import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://healthmate:healthmate@localhost:5432/healthmate_test")
os.environ["ENVIRONMENT"] = "test"
os.environ["LLM_PROVIDER"] = "demo"
os.environ["REMINDER_ENGINE_ENABLED"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import ensure_catalog  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    ensure_catalog(db)
    db.commit()
    db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def register(client: TestClient, email: str, role: str = "patient", name: str = "Asha Verma") -> dict:
    r = client.post("/api/auth/register", json={"email": email, "password": "supersecret1", "full_name": name, "role": role, "accept_terms": True})
    assert r.status_code == 200, r.text
    return r.json()["user"]


def onboard(client: TestClient) -> None:
    r = client.post("/api/profile/onboarding", json={
        "date_of_birth": "1955-03-02", "gender": "female", "conditions": ["Type 2 diabetes"], "allergies": [], "food_preference": "vegetarian",
        "meals": [{"meal": "breakfast", "time": "08:00"}, {"meal": "lunch", "time": "13:00"}, {"meal": "snack", "time": "17:00"}, {"meal": "dinner", "time": "20:00"}],
        "ai_processing_consent": True})
    assert r.status_code == 200, r.text
