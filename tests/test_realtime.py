"""Tests for SkillProof Real-Time WebSocket and Streaming Capabilities."""
import pytest
import json


def test_websocket_connection_and_ping(client):
    """Test connecting to /ws and sending a ping message."""
    with client.websocket_connect("/ws") as websocket:
        # First message is connection acknowledgment
        data = websocket.receive_json()
        assert data["type"] == "connection_established"
        assert "active_clients" in data

        # Send ping
        websocket.send_json({"type": "ping"})
        response = websocket.receive_json()
        assert response["type"] == "pong"
        assert "timestamp" in response


def test_websocket_simulate_activity(client):
    """Test simulating activity over WebSocket."""
    with client.websocket_connect("/ws") as websocket:
        _ = websocket.receive_json()  # connection_established

        websocket.send_json({"type": "simulate_activity"})
        broadcast = websocket.receive_json()
        assert broadcast["type"] == "activity_event"
        assert "Marcus Johnson" in broadcast["data"]["detail"]


def test_rate_limit_endpoint(client):
    """Test the GitHub rate limit status endpoint."""
    response = client.get("/api/import/github/rate-limit")
    assert response.status_code == 200
    data = response.json()
    assert "limit" in data
    assert "remaining" in data
    assert "authenticated" in data


def test_simulate_endpoint_http(client):
    """Test the HTTP endpoint that triggers simulated WebSocket events."""
    response = client.post("/api/realtime/simulate")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "broadcasted"
    assert "event" in data


def test_live_scan_invalid_url(client):
    """Test validation on real-time live-scan endpoint."""
    response = client.post("/api/import/live-scan", json={"repo_url": "invalid-url"})
    assert response.status_code == 400
    assert "Invalid GitHub repo URL" in response.json()["detail"]
