import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """
    Create a TestClient fixture for testing the FastAPI app.
    
    Returns:
        TestClient: FastAPI test client instance
    """
    return TestClient(app)


def test_health_endpoint_status_code(client):
    """
    Test that the /health endpoint returns a 200 status code.
    
    Args:
        client: FastAPI TestClient fixture
    """
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_response_body(client):
    """
    Test that the /health endpoint returns the correct response body.
    
    Args:
        client: FastAPI TestClient fixture
    """
    response = client.get("/health")
    assert response.json() == {"status": "ok"}


def test_health_endpoint_content_type(client):
    """
    Test that the /health endpoint returns JSON content type.
    
    Args:
        client: FastAPI TestClient fixture
    """
    response = client.get("/health")
    assert "application/json" in response.headers["content-type"]
