from fastapi.testclient import TestClient

from app.main import app


def test_create_project():
    with TestClient(app) as client:
        response = client.post(
            "/projects/",
            json={
                "name": "Test Project",
                "description": "Test description",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["description"] == "Test description"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_project_with_too_long_name():
    with TestClient(app) as client:
        response = client.post(
            "/projects/",
            json={
                "name": "A" * 256,
                "description": "Test description",
            },
        )

    assert response.status_code == 422


def test_create_project_with_empty_name():
    with TestClient(app) as client:
        response = client.post(
            "/projects/",
            json={
                "name": "",
                "description": "Test description",
            },
        )

    assert response.status_code == 422


def test_create_project_without_description():
    with TestClient(app) as client:
        response = client.post(
            "/projects/",
            json={
                "name": "Project Without Description",
            },
        )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Project Without Description"
    assert data["description"] is None


def test_get_projects():
    with TestClient(app) as client:
        create_response = client.post(
            "/projects/",
            json={
                "name": "Test Project",
                "description": "Test description",
            },
        )

        assert create_response.status_code == 201

        response = client.get("/projects/")

    assert response.status_code == 200
    data = response.json()
    assert any(project["name"] == "Test Project" for project in data)


def test_delete_project():
    with TestClient(app) as client:
        create_response = client.post(
            "/projects/",
            json={
                "name": "Project to Delete",
                "description": "Test description",
            },
        )

        assert create_response.status_code == 201

        project_id = create_response.json()["id"]

        delete_response = client.delete(f"/projects/{project_id}/")

    assert delete_response.status_code == 204
