from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_correlation_id_header_in_responses():
    """Verify that successful requests include the X-Request-ID response header."""
    response = client.get("/")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    # Ensure it's a valid non-empty string
    assert len(response.headers["x-request-id"]) > 0


def test_correlation_id_propagated_from_request():
    """Verify that if a correlation ID is passed, it is propagated in the response."""
    test_id = "test-correlation-id-12345"
    response = client.get("/", headers={"X-Request-ID": test_id})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == test_id


def test_404_error_schema():
    """Verify that a 404 HTTP Exception matches the custom uniform error schema."""
    response = client.get("/non-existent-endpoint")
    assert response.status_code == 404
    data = response.json()

    assert data["success"] is False
    assert data["error"]["code"] == "HTTP_404"
    assert "Not Found" in data["error"]["message"]
    assert "correlation_id" in data
    assert data["correlation_id"] == response.headers["x-request-id"]


def test_validation_error_schema():
    """Verify that Pydantic/FastAPI validation errors return the custom schema."""
    response = client.get("/api/test-validation?value=not-an-integer")
    assert response.status_code == 422
    data = response.json()

    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "validation failed" in data["error"]["message"]
    assert "details" in data["error"]
    assert len(data["error"]["details"]) > 0
    assert data["correlation_id"] == response.headers["x-request-id"]


def test_unhandled_exception_schema():
    """Verify that unhandled exceptions (500) return the custom schema."""
    response = client.get("/api/trigger-error")
    assert response.status_code == 500
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert data["error"]["message"] == "An unexpected server error occurred."
    assert "correlation_id" in data
