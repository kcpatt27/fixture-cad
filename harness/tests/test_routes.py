from __future__ import annotations

from fastapi.testclient import TestClient

from fixture_cad.main import app


def test_tools_bad_app_uses_error_envelope() -> None:
    response = TestClient(app).get("/tools", params={"app": "kicad"})
    assert response.status_code == 400
    body = response.json()
    assert "detail" not in body
    assert body["error"]["code"] == "validation_error"


def test_tools_lists_freecad_catalog() -> None:
    response = TestClient(app).get("/tools", params={"app": "freecad"})
    assert response.status_code == 200
    body = response.json()
    assert body["app"] == "freecad"
    assert any(tool["name"] == "create_body" for tool in body["tools"])


def test_chat_invalid_envelope_uses_error_envelope() -> None:
    response = TestClient(app).post("/chat", json={"app": "freecad"})
    assert response.status_code == 400
    body = response.json()
    assert "detail" not in body
    assert body["error"]["code"] == "validation_error"
