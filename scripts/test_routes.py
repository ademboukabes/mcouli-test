from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    resp = client.get("/user/photos")
    print(f"/user/photos -> {resp.status_code} {resp.text}")
    resp2 = client.get("/user/photos/")
    print(f"/user/photos/ -> {resp2.status_code} {resp2.text}")
