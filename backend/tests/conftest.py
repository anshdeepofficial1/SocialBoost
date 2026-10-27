"""Test configuration.

The environment is configured *before* the application is imported so that
settings, the database engine and the model directory all point at temporary
locations. Tests never touch the developer's real database or uploads.
"""

import os
import shutil
import sys
import tempfile

import pytest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

TMP_ROOT = tempfile.mkdtemp(prefix="socialboost-tests-")
UPLOAD_DIR = os.path.join(TMP_ROOT, "uploads")
MODEL_DIR = os.path.join(TMP_ROOT, "models")
DB_PATH = os.path.join(TMP_ROOT, "test.db")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["UPLOAD_DIR"] = UPLOAD_DIR
os.environ["MODEL_DIR"] = MODEL_DIR
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["MIN_TRAINING_ROWS"] = "10"


@pytest.fixture(scope="session")
def app_client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
def admin(app_client):
    """A signed-in user with a workspace, unique per test session."""
    email = "owner@example.com"
    r = app_client.post("/auth/signup", json={"email": email, "password": "pass123", "full_name": "Owner"})
    if r.status_code == 400 and "already" in r.text:
        r = app_client.post("/auth/login", json={"email": email, "password": "pass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def other_user(app_client):
    email = "other@example.com"
    r = app_client.post("/auth/signup", json={"email": email, "password": "pass123", "full_name": "Other"})
    if r.status_code == 400 and "already" in r.text:
        r = app_client.post("/auth/login", json={"email": email, "password": "pass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def sample_csv() -> str:
    rows = ["platform,published_at,duration_seconds,views,likes,comments,shares,followers_at_publish,caption,title,hashtags"]
    for i in range(24):
        platform = "instagram" if i % 2 == 0 else "youtube"
        views = 5000 + i * 900
        rows.append(
            f"{platform},2026-0{1 + (i % 8)}-1{i % 9 + 1}T10:00:00,{20 + i},{views},{int(views * 0.05)},"
            f"{int(views * 0.01)},{int(views * 0.004)},{3000 + i * 100},Caption number {i},Title {i},#tag{i}"
        )
    return "\n".join(rows)


def pytest_sessionfinish(session, exitstatus):  # pragma: no cover - cleanup only
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
