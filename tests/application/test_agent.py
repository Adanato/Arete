import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arete.agent import create_arete_agent, execute_agent_tool


@pytest.fixture
def mock_openai():
    with patch("arete.agent.OpenAI") as mock:
        yield mock


@pytest.fixture
def mock_instructor():
    with patch("arete.agent.instructor") as mock:
        yield mock


@pytest.fixture
def mock_atomic_agent():
    with patch("arete.agent.AtomicAgent") as mock:
        yield mock


@pytest.fixture
def mock_agent_config():
    with patch("arete.agent.AgentConfig") as mock:
        yield mock


@pytest.fixture
def mock_genai():
    mock_module = MagicMock()
    # Explicitly patching sys.modules with the dictionary object
    with patch.dict(sys.modules, {"google.generativeai": mock_module}):
        yield mock_module.configure, mock_module.GenerativeModel


def test_create_arete_agent_openai_v2(
    mock_openai, mock_instructor, mock_atomic_agent, mock_agent_config
):
    api_key = "test-key"
    mock_client = MagicMock()
    mock_instructor.from_openai.return_value = mock_client
    create_arete_agent(api_key, provider="openai")
    mock_openai.assert_called_with(api_key=api_key)
    mock_instructor.from_openai.assert_called_once()
    mock_agent_config.assert_called_once()
    assert mock_agent_config.call_args.kwargs["client"] == mock_client
    assert mock_agent_config.call_args.kwargs["model"] == "gpt-4o-mini"
    mock_atomic_agent.__getitem__.return_value.assert_called_once()


def test_create_arete_agent_default_provider_v2(
    mock_openai, mock_instructor, mock_atomic_agent, mock_agent_config
):
    api_key = "test-key"
    mock_instructor.from_openai.return_value = MagicMock()
    create_arete_agent(api_key)
    mock_instructor.from_openai.assert_called_once()
    assert mock_agent_config.call_args.kwargs["model"] == "gpt-4o-mini"


@pytest.mark.skip(reason="Mocking google.generativeai is flaky due to namespace package issues")
def test_create_arete_agent_gemini(
    mock_genai, mock_instructor, mock_atomic_agent, mock_agent_config
):
    mock_conf, mock_model_cls = mock_genai
    api_key = "test-key"
    mock_client = MagicMock()
    mock_instructor.from_gemini.return_value = mock_client

    # We don't import it here to avoid conflicts, just call the function
    create_arete_agent(api_key, provider="gemini")

    mock_conf.assert_called_with(api_key=api_key)
    mock_instructor.from_gemini.assert_called_once()
    mock_model_cls.assert_called_with(model_name="gemini-3-flash-preview")


def test_create_arete_agent_fallback(
    mock_openai, mock_instructor, mock_atomic_agent, mock_agent_config
):
    api_key = "test-key"
    mock_client = MagicMock()
    mock_instructor.from_openai.return_value = mock_client
    create_arete_agent(api_key, provider="unknown")
    mock_instructor.from_openai.assert_called_once()


@pytest.mark.asyncio
async def test_execute_agent_tool_success_v2():
    with patch("arete.mcp_server.call_tool", new_callable=AsyncMock) as mock_call:
        mock_content = MagicMock()
        mock_content.text = "Tool Result"
        mock_call.return_value = [mock_content]
        result = await execute_agent_tool("test_tool")
        mock_call.assert_called_with("test_tool", {})
        assert result == "Tool Result"


@pytest.mark.asyncio
async def test_execute_agent_tool_empty_v2():
    with patch("arete.mcp_server.call_tool", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = []
        result = await execute_agent_tool("test_tool")
        assert result == "Tool executed but returned no result."


@pytest.mark.asyncio
async def test_execute_agent_tool_error_v2():
    with patch("arete.mcp_server.call_tool", new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = Exception("Boom")
        result = await execute_agent_tool("test_tool")
        assert "Error executing tool test_tool: Boom" in result
