# backend/tests/test_health.py
"""Tests for the health endpoint."""


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_status_ok(client):
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
