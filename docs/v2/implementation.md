# Arete v2: Orchestration for Power Implementation Plan

## Goal
Transform Arete into a powerful multi-agent system with deep vault context and autonomous learning optimization.

---

## Phase 14: The Librarian (Note Search) 📚
Give the agent the ability to search your *entire* vault for context, not just leeches.

### [arete] [vault_service.py](file:///Users/adam/Research/arete/src/arete/application/vault_service.py) [MODIFY]
- Implement a search method that scans filenames and content for a query string.

### [arete] [mcp_server.py](file:///Users/adam/Research/arete/src/arete/mcp_server.py) [NEW TOOL]
- `search_notes(query: str)`: Returns a list of note names and snippets matching the query.

### [arete] [agent.py](file:///Users/adam/Research/arete/src/arete/agent.py) [MODIFY]
- Add `search_notes` to the list of available tools in the system prompt.
- Instruct the agent to use this tool when the user asks about general vault content.

---

## Phase 15: Specialized Orchestration (Sub-Agents) 🎭
Transition from a single-brain agent to a "General" with specialized "Specialists".

### [arete] [agent.py](file:///Users/adam/Research/arete/src/arete/agent.py) [MODIFY]
- Create specialized `SystemPromptGenerator` configs for:
    - **Librarian**: Focuses on finding and organizing notes.
    - **Study Coach**: Focuses on Anki performance analysis.
    - **Sync Architect**: Focuses on metadata and card structure.
- Update `Orchestrator` agent to decide which "personality" to adopt or which sub-tool to call based on the goal.

### [arete] [server.py](file:///Users/adam/Research/arete/src/arete/server.py) [MODIFY]
- Support multi-stepReAct loops where the agent can call multiple tools in sequence (e.g., `search_notes` -> `get_stats` -> `summarize`).

---

## Phase 16: Deep Study Analytics 📊
Leverage direct database access for richer insights.

### [arete] [infrastructure/adapters/anki_direct.py](file:///Users/adam/Research/arete/src/arete/infrastructure/adapters/anki_direct.py) [MODIFY]
- Implement `get_study_history()` to fetch lapse trends over the last 30 days.

### [arete] [stats_service.py](file:///Users/adam/Research/arete/src/arete/application/stats_service.py) [MODIFY]
- Add complexity analysis (e.g., "Note contains too many bullet points per card").

---

## Verification Plan
### Automated Tests
- Test `search_notes` tool via `mcp_server.py` and verify it finds existing notes.
- Verify multi-step agents can successfully chain two tool calls in the server.

### Manual Verification
- **Test Case**: Ask Arete, "What do I have about [Subject]?" and verify it uses the Librarian tool.
- **Test Case**: Verify leeches are still accurately reported and linked.

---

## Phase 17: Operational Excellence (Hooks & Retries) ⚓
Use Atomic Agent Hooks for building a resilient background service.

### [arete] [agent.py](file:///Users/adam/Research/arete/src/arete/agent.py) [MODIFY]
- Implement a `SyncMonitoringHook` that logs tool execution time and status.
- Add an intelligent retry mechanism if the Anki database is locked (especially common with `AnkiDirectAdapter`).

---

## Phase 18: Native Orchestration & Vision 👁️
Move to the advanced multi-agent patterns for maximum power.

### [arete] [agent.py](file:///Users/adam/Research/arete/src/arete/agent.py) [MODIFY]
- Define a `MasterToolSchema` as a `Union` of all tool input schemas.
- Refactor the `Orchestrator` to use native tool calling (letting the LLM populate the schema directly).
- **Experimental**: Add Vision support to the `SyncArchitect` to analyze local images/diagrams in Obsidian notes for card generation.
