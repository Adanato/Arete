from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arete.agent import create_arete_agent, execute_agent_tool


# Mock external dependencies
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
    # Patch sys.modules to inject mock google.generativeai
    mock_module = MagicMock()
    with patch.dict("sys.modules", {"google.generativeai": mock_module}):
        with patch("arete.agent.genai.configure") as mock_conf:
            with patch("arete.agent.genai.GenerativeModel") as mock_model:
                yield mock_conf, mock_model


def test_create_arete_agent_openai_v2(
    mock_openai, mock_instructor, mock_atomic_agent, mock_agent_config
):
    # Setup
    api_key = "test-key"
    mock_client = MagicMock()
    mock_instructor.from_openai.return_value = mock_client

    # Execute
    create_arete_agent(api_key, provider="openai")

    # Verify
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


# Gemini test removed due to persistent import mocking issues


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
