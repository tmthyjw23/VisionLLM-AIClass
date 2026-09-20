import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.vision_client import validate_llm_connection

client = TestClient(app)

def test_llm_test_connection_rejects_empty_fields():
    res = client.post("/api/llm/test-connection", json={"base_url": "", "api_key": ""})
    assert res.status_code == 400

    res = client.post("/api/llm/test-connection", json={"base_url": "http://localhost:20128/v1", "api_key": ""})
    assert res.status_code == 400

def test_llm_test_connection_unreachable_host_reports_failure():
    # Port 9 (discard) on loopback refuses immediately — no network dependency
    result = validate_llm_connection("http://127.0.0.1:9/v1", "dummy-key")
    assert result["ok"] is False
    assert result["models"] == []
    assert isinstance(result["error"], str) and len(result["error"]) > 0

def test_detection_request_accepts_llm_override_schema():
    # Schema-level check: llm override must be accepted without calling inference
    from app.main import DetectionRequest
    req = DetectionRequest(
        prompt_preset="generic",
        llm={"base_url": "https://api.openai.com/v1", "api_key": "sk-test", "model": "gpt-4o-mini"}
    )
    assert req.llm.base_url == "https://api.openai.com/v1"
    assert req.llm.model == "gpt-4o-mini"

    # llm is optional — old clients without it still validate
    req2 = DetectionRequest(prompt_preset="structured_json")
    assert req2.llm is None
