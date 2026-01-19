"""Arete AI Agent Module
Uses Atomic Agents framework to provide AI-powered learning insights and tool execution.
"""

from __future__ import annotations

import logging

import instructor
from atomic_agents import AgentConfig, AtomicAgent, BaseIOSchema
from atomic_agents import BasicChatInputSchema as BasicChatInputSchema
from atomic_agents.context import ChatHistory, SystemPromptGenerator
from openai import OpenAI
from pydantic import Field

from arete.consts import VERSION

logger = logging.getLogger(__name__)


class AreteOutputSchema(BaseIOSchema):
    """Structured output for the Arete AI Agent."""

    chat_message: str = Field(..., description="The response message from the agent.")
    suggested_questions: list[str] = Field(
        default_factory=list, description="Suggested follow-up questions for the user."
    )
    tool_request: str | None = Field(
        None, description="Request to execute a tool (e.g., 'sync_vault', 'get_stats')."
    )
    action_taken: str | None = Field(
        None, description="A brief description of any tool or action performed."
    )


# System Prompt Configuration
system_prompt_generator = SystemPromptGenerator(
    background=[
        "You are Arete, a professional learning assistant specializing in Spaced Repetition (SRS) "
        "and Obsidian-to-Anki synchronization.",
        f"You are part of Arete v{VERSION}.",
        "Your goal is to help users manage their flashcards, optimize their learning velocity, "
        "and identify weak spots in their knowledge.",
        "When identifying specific notes or files that need attention, ALWAYS format them as "
        "Obsidian wiki links, e.g., [[My Note Name]].",
        "This applies to EVERY mention of a note, whether in a list or in your normal "
        "conversation text.",
        "CRITICAL: Do NOT guess or hallucinate note names. Only mention notes that are "
        "explicitly returned by your tools (e.g., in the response from get_stats).",
    ],
    steps=[
        "Analyze the user's input to understand if they want to sync data, "
        "get statistics, or advice.",
        "If they want to sync, set 'tool_request' to 'sync_vault'.",
        "If they want statistics or analysis of weaknesses, set 'tool_request' to 'get_stats'.",
        "Identify specific files that need improvement and refer to them using "
        "[[wiki link]] syntax ONLY IF they were returned by the get_stats tool.",
        "Formulate a helpful, concise, and encouraging response.",
        "If the tools return an error or empty data, inform the user honestly without "
        "speculating on note names.",
    ],
    output_instructions=[
        "Always be concise and prioritize utility.",
        "Confirm any requested actions to the user.",
        "Ensure all file references use the [[filename]] format.",
        "Conclude with relevant follow-up questions.",
        "If you mention a note name like 'Complex Analysis', you MUST write it as "
        "[[Complex Analysis]]. Never write the name without brackets.",
        "This is especially important for the conversational summary after tool execution. "
        "Ensure EVERY mention of a note name is bracketed.",
    ],
)


def create_arete_agent(api_key: str, provider: str = "openai") -> AtomicAgent:
    """Creates and configures an AtomicAgent for Arete."""
    if provider == "gemini":
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=api_key)  # type: ignore
        client = instructor.from_gemini(
            client=genai.GenerativeModel(model_name="gemini-3-flash-preview"),  # type: ignore
        )

        # Atomic Agents always passes 'model' to create(), but instructor's Gemini client
        # handles the model internally and raises an error if 'model' is passed again.
        # We patch the create method to filter out 'model'.
        original_create = client.chat.completions.create

        def patched_create(*args, **kwargs):
            kwargs.pop("model", None)
            return original_create(*args, **kwargs)

        # Replace the method on the instance
        client.chat.completions.create = patched_create
    elif provider == "openai":
        client = instructor.from_openai(OpenAI(api_key=api_key))
    else:
        # Fallback to OpenAI
        client = instructor.from_openai(OpenAI(api_key=api_key))

    agent = AtomicAgent[BasicChatInputSchema, AreteOutputSchema](
        config=AgentConfig(
            client=client,
            model="gpt-4o-mini" if provider == "openai" else "gemini-3-flash-preview",
            system_prompt_generator=system_prompt_generator,
            history=ChatHistory(),
            model_api_parameters={},  # type: ignore
        )
    )

    return agent


class AgentChatRequest(BaseIOSchema):
    """Schema for the chat endpoint request."""

    message: str = Field(..., description="The user's message.")
    api_key: str = Field(..., description="The LLM API key.")
    provider: str = Field("openai", description="The LLM provider.")


# --- Internal Tool Helpers (used by server) ---


async def execute_agent_tool(tool_name: str) -> str:
    """Core logic for executing tools requested by the agent."""
    from arete.mcp_server import call_tool

    # Map agent tool names to MCP tool names if they differ
    # For now they are the same: 'sync_vault', 'get_stats'

    try:
        # call_tool(name, arguments) returns list[TextContent]
        results = await call_tool(tool_name, {})

        if not results:
            return "Tool executed but returned no result."

        # Combine all text content from MCP response
        return "\n".join([c.text for c in results])  # type: ignore
    except Exception as e:
        logger.error(f"MCP tool execution failed: {e}", exc_info=True)
        return f"Error executing tool {tool_name}: {str(e)}"
