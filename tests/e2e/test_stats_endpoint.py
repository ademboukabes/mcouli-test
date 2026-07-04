import pytest
import os
if os.getenv("MULTAI_RUN_E2E") != "1":
    pytest.skip("set MULTAI_RUN_E2E=1 to run live e2e tests", allow_module_level=True)

import uuid
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from app.main import app
from app.deps.cookie_auth import require_admin_staff
from db.generated.models import StaffUser, StaffRole
from typing import Generator

@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    import os
    if os.getenv("MULTAI_RUN_E2E") != "1":
        pytest.skip("set MULTAI_RUN_E2E=1 to run live e2e tests")
    # Override the dependency to bypass cookie auth
    mock_admin = StaffUser(
        id=uuid.uuid4(),
        email="test_admin@multai.com",
        role=StaffRole.ADMIN,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        password="hashed_password"
    )
    app.dependency_overrides[require_admin_staff] = lambda: mock_admin

    # Using 'with' triggers the FastAPI lifespan (initializes Redis and DB pools)
    with TestClient(app) as c:
        yield c

def test_dashboard_stats(client: TestClient) -> None:
    resp = client.get("/admin/stats/dashboard")
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "active_events" in data

def test_processing_load(client: TestClient) -> None:
    resp = client.get("/admin/stats/processing-load")
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "completed" in data

def test_storage(client: TestClient) -> None:
    resp = client.get("/admin/stats/storage")
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "used_bytes" in data

def test_alerts(client: TestClient) -> None:
    resp = client.get("/admin/stats/alerts")
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "alerts" in data
