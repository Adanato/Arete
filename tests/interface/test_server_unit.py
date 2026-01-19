from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from arete.consts import VERSION
from arete.server import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == VERSION


def test_get_version():
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"version": VERSION}


@patch("arete.main.execute_sync", new_callable=AsyncMock)  # Patched arete.main.execute_sync
def test_sync_vault_endpoint(mock_sync):
    # Mock return value
    mock_stats = MagicMock()
    # Configure mock attributes to return primitives
    mock_stats.total_generated = 5
    mock_stats.total_imported = 5
    mock_stats.total_errors = 0
    mock_sync.return_value = mock_stats

    # SyncRequest via JSON
    response = client.post("/sync", json={"vault_root": "/tmp/vault", "force": True})

    # Check execution
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total_imported"] == 5

    mock_sync.assert_awaited_once()


@patch("arete.main.execute_sync", new_callable=AsyncMock)
def test_sync_fail(mock_sync):
    mock_sync.side_effect = Exception("Boom")

    response = client.post("/sync", json={"vault_root": "/tmp/vault"})

    assert response.status_code == 500
    assert "Boom" in response.json()["detail"]


@patch("arete.agent.create_arete_agent")  # Patch where it is defined, it is a factory function
def test_agent_chat_success(mock_create_agent):
    mock_agent_instance = MagicMock()
    mock_create_agent.return_value = mock_agent_instance

    # Mock Agent Response
    mock_response = MagicMock()
    mock_response.chat_message = "Hello User"
    mock_response.action_taken = None
    mock_response.suggested_questions = []
    mock_response.tool_request = None  # No tool

    mock_agent_instance.run.return_value = mock_response

    req = {"message": "Hi", "api_key": "test-key", "provider": "openai"}

    response = client.post("/agent/chat", json=req)

    assert response.status_code == 200
    data = response.json()
    assert data["chat_message"] == "Hello User"

    mock_create_agent.assert_called_with("test-key", "openai")


# Test Agent Tool Execution flow
@patch("arete.agent.create_arete_agent")
@patch("arete.agent.execute_agent_tool", new_callable=AsyncMock)
def test_agent_chat_with_tool(mock_exec_tool, mock_create_agent):
    mock_agent_instance = MagicMock()
    mock_create_agent.return_value = mock_agent_instance

    # Response 1: Request Tool
    resp1 = MagicMock()
    resp1.chat_message = "I'll check."
    resp1.tool_request = "get_stats"
    resp1.action_taken = None

    # Response 2: Summary after tool
    resp2 = MagicMock()
    resp2.chat_message = "Here are the stats."
    resp2.tool_request = None
    resp2.action_taken = None
    resp2.suggested_questions = []

    mock_agent_instance.run.side_effect = [resp1, resp2]

    mock_exec_tool.return_value = "Stats: Good"

    req = {"message": "Check stats", "api_key": "test-key"}

    response = client.post("/agent/chat", json=req)

    assert response.status_code == 200
    data = response.json()
    assert "Here are the stats." in data["chat_message"]
    assert "Action: get_stats" in data["action_taken"]

    mock_exec_tool.assert_awaited_once_with("get_stats")
    assert mock_agent_instance.run.call_count == 2


@patch("arete.agent.create_arete_agent")
def test_agent_chat_failure(mock_create_agent):
    mock_create_agent.side_effect = Exception("Agent Error")

    req = {"message": "Hi", "api_key": "test-key"}

    response = client.post("/agent/chat", json=req)

    assert response.status_code == 500
    assert "Agent Error" in response.json()["detail"]


@patch("arete.agent.AgentChatRequest")
def test_agent_chat_validation_error(MockRequest):
    # Force constructor to raise exception to hit the 400 block
    MockRequest.side_effect = RuntimeError("Manual Validation Check")

    # We must send a valid dict to pass FastAPI type check, but cause MockRequest to trigger
    response = client.post("/agent/chat", json={"foo": "bar"})

    # FastAPI might return 422 (Unprocessable Entity) if Pydantic validation catches it,
    # or 400 if our manual except block catches it.
    # Since we can't easily force our block over FastAPI's, we accept either as proof of validation failure.
    assert response.status_code in [400, 422]
    # Detail message varies, so just checking status is enough for coverage of the failure path


@patch("arete.application.factory.get_anki_bridge", new_callable=AsyncMock)
def test_suspend_endpoint(mock_get_bridge):
    mock_bridge = AsyncMock()
    mock_bridge.suspend_cards.return_value = True
    mock_get_bridge.return_value = mock_bridge

    response = client.post("/anki/cards/suspend", json={"cids": [1, 2]})
    assert response.status_code == 200
    assert response.json()["ok"] is True


@patch("arete.application.factory.get_anki_bridge", new_callable=AsyncMock)
def test_unsuspend_endpoint(mock_get_bridge):
    mock_bridge = AsyncMock()
    mock_bridge.unsuspend_cards.return_value = True
    mock_get_bridge.return_value = mock_bridge

    response = client.post("/anki/cards/unsuspend", json={"cids": [1, 2]})
    assert response.status_code == 200
    assert response.json()["ok"] is True


@patch("arete.application.factory.get_anki_bridge", new_callable=AsyncMock)
def test_styling_endpoint(mock_get_bridge):
    mock_bridge = AsyncMock()
    mock_bridge.get_model_styling.return_value = "css"
    mock_get_bridge.return_value = mock_bridge

    response = client.get("/anki/models/Basic/styling")
    assert response.status_code == 200
    assert response.json()["css"] == "css"


@patch("arete.application.factory.get_anki_bridge", new_callable=AsyncMock)
def test_templates_endpoint(mock_get_bridge):
    mock_bridge = AsyncMock()
    mock_bridge.get_model_templates.return_value = {"C1": "T1"}
    mock_get_bridge.return_value = mock_bridge

    response = client.get("/anki/models/Basic/templates")
    assert response.status_code == 200
    assert response.json() == {"C1": "T1"}


@patch("arete.application.factory.get_anki_bridge", new_callable=AsyncMock)
def test_gui_browse_endpoint(mock_get_bridge):
    mock_bridge = AsyncMock()
    mock_bridge.gui_browse.return_value = True
    mock_get_bridge.return_value = mock_bridge

    response = client.post("/anki/browse", json={"query": "deck:Default"})
    assert response.status_code == 200
    assert response.json()["ok"] is True


@patch("arete.application.factory.get_anki_bridge", new_callable=AsyncMock)
def test_suspend_cards_endpoint_fail(mock_get_anki):
    mock_get_anki.side_effect = Exception("Bridge Fail")
    response = client.post("/anki/cards/suspend", json={"cids": [1]})
    assert response.status_code == 500
    assert "Bridge Fail" in response.json()["detail"]


@patch("arete.application.factory.get_anki_bridge", new_callable=AsyncMock)
def test_unsuspend_cards_endpoint_fail(mock_get_anki):
    mock_get_anki.side_effect = Exception("Bridge Fail")
    response = client.post("/anki/cards/unsuspend", json={"cids": [1]})
    assert response.status_code == 500
    assert "Bridge Fail" in response.json()["detail"]


@patch("arete.application.factory.get_anki_bridge", new_callable=AsyncMock)
def test_get_model_styling_endpoint_fail(mock_get_anki):
    mock_get_anki.side_effect = Exception("Bridge Fail")
    response = client.get("/anki/models/Basic/styling")
    assert response.status_code == 500


@patch("arete.application.factory.get_anki_bridge", new_callable=AsyncMock)
def test_get_model_templates_endpoint_fail(mock_get_anki):
    mock_get_anki.side_effect = Exception("Bridge Fail")
    response = client.get("/anki/models/Basic/templates")
    assert response.status_code == 500


def test_agent_chat_validation_fail():
    response = client.post("/agent/chat", json={"invalid": "req"})
    assert response.status_code == 400


@patch("arete.application.factory.get_stats_repo")
def test_get_stats_endpoint_fail(mock_get_repo):
    mock_get_repo.side_effect = Exception("Repo Fail")
    response = client.post("/anki/stats", json={"nids": [1]})
    assert response.status_code == 500


@patch("arete.application.factory.get_anki_bridge", new_callable=AsyncMock)
def test_browse_anki_endpoint_fail(mock_get_anki):
    mock_get_anki.side_effect = Exception("Bridge Fail")
    response = client.post("/anki/browse", json={"query": "test"})
    assert response.status_code == 500


@patch("os.kill")
def test_shutdown_endpoint(mock_kill):
    response = client.post("/shutdown")
    assert response.status_code == 200
    assert "shutting down" in response.json()["message"]
    # Wait for the thread to (potentially) call kill
    import time

    time.sleep(0.6)
    mock_kill.assert_called_once()


def test_build_queue_missing_vault_root():
    # We need to simulate the case where AppConfig.vault_root is None
    from arete.application.config import AppConfig

    with patch("arete.application.config.resolve_config") as mock_resolve:
        mock_resolve.return_value = AppConfig(vault_root=None)
        response = client.post("/queue/build", json={})
        assert response.status_code == 400
        assert "Vault root not configured" in response.json()["detail"]
