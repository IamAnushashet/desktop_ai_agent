"""Comprehensive unit and failure propagation tests for NVIDIA AI Desktop Agent."""

import time
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.config.settings import settings
from backend.agent.agent import desktop_ai_agent
from backend.llm.nvidia import classify_nvidia_error, check_nvidia_health


@pytest.fixture
def client():
    return TestClient(app)


def test_agent_health_check_endpoint(client):
    res = client.get("/api/agent/health")
    assert res.status_code == 200
    data = res.json()
    assert "success" in data
    assert "status" in data
    assert "model" in data
    # Ensure API Key is NEVER returned in response
    assert "NVIDIA_API_KEY" not in str(data)
    assert "nvapi-" not in str(data)


def test_error_classification():
    # 410 Gone / retired model
    err_410 = Exception("HTTP 410 Gone: The model 'meta/llama-3.3-70b-instruct' has reached its end of life")
    etype, msg = classify_nvidia_error(err_410)
    assert etype == "MODEL_UNAVAILABLE"

    # 401 Unauthorized / auth error
    err_401 = Exception("Error code: 401 - Unauthorized: Invalid API key")
    etype, msg = classify_nvidia_error(err_401)
    assert etype == "AUTHENTICATION_ERROR"

    # 429 Rate Limit
    err_429 = Exception("Error code: 429 - Rate limit exceeded")
    etype, msg = classify_nvidia_error(err_429)
    assert etype == "RATE_LIMITED"


def test_failed_task_response_format(client):
    # Mock LLM call to simulate a 410 model retirement error
    with patch("backend.agent.graph.agent_graph.get_nvidia_llm") as mock_get_llm:
        mock_get_llm.side_effect = Exception("HTTP 410 Gone: The model 'meta/llama-3.3-70b-instruct' has reached end of life")
        
        res = client.post("/api/agent/task", json={"task": "Open Chrome and search for test"})
        assert res.status_code == 200
        task_id = res.json()["task_id"]

        # Poll status until background task completes or fails
        data = None
        for _ in range(100):
            time.sleep(0.1)
            status_res = client.get(f"/api/agent/status/{task_id}")
            assert status_res.status_code == 200
            data = status_res.json()
            if data["status"] in ["completed", "failed"]:
                break

        # CRITICAL ASSERTIONS: A failed NVIDIA call MUST NEVER produce success=true or status=completed
        assert data["success"] is False
        assert data["status"] == "failed"
        assert data["completed"] is False
        assert data["error_type"] == "MODEL_UNAVAILABLE"
        assert "retired" in data["error"].lower() or "unavailable" in data["error"].lower() or "gone" in data["error"].lower()


def test_successful_task_response_format(client):
    # Test tool calling endpoint submission
    res = client.post("/api/agent/task", json={"task": "Open Chrome and search for artificial intelligence"})
    assert res.status_code == 200
    data = res.json()
    assert "task_id" in data
    assert data["task_description"] == "Open Chrome and search for artificial intelligence"


def test_list_tools_endpoint(client):
    res = client.get("/api/agent/tools")
    assert res.status_code == 200
    data = res.json()
    assert "tools" in data
    assert len(data["tools"]) >= 10
