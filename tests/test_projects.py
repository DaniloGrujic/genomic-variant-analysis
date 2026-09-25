from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_project_requires_name():
    response = client.post(
        "/projects/",
        json={
            "description": "Test project",
        },
    )

    assert response.status_code == 422
