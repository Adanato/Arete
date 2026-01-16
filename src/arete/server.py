import logging
import os
import signal
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from arete.consts import VERSION

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("arete.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Arete Server v{VERSION} starting up...")
    yield
    # Shutdown
    logger.info("Arete Server shutting down...")


app = FastAPI(
    title="Arete Server",
    description="Background server for Arete Obsidian plugin.",
    version=VERSION,
    lifespan=lifespan,
)


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float


start_time = time.time()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Simple health check to verify server is reachable.
    """
    return HealthResponse(status="ok", version=VERSION, uptime_seconds=time.time() - start_time)


@app.get("/version")
async def get_version():
    return {"version": VERSION}


# Request model for sync parameters (subset of AppConfig settings)
class SyncRequest(BaseModel):
    # If None, use defaults/config file.
    vault_root: str | None = None
    file_path: str | None = None  # sync single file
    backend: str | None = None  # auto, direct, ankiconnect
    force: bool | None = None
    prune: bool | None = None
    clear_cache: bool | None = None
    dry_run: bool | None = None
    anki_connect_url: str | None = None
    workers: int | None = None


class SyncStatsResponse(BaseModel):
    total_generated: int
    total_imported: int
    total_errors: int
    success: bool
    # We could include error list, but might be too large.
    # Just return count/status for now.


@app.post("/sync", response_model=SyncStatsResponse)
async def trigger_sync(req: SyncRequest):
    """
    Trigger a sync operation.
    """

    from arete.application.config import resolve_config
    from arete.main import execute_sync

    logger.info(f"Sync requested via API: {req}")

    # Map request to overrides dict
    overrides = {
        "vault_root": req.vault_root,
        "root_input": req.file_path,  # single file sync basically sets root input
        "backend": req.backend,
        "force": req.force,
        "prune": req.prune,
        "clear_cache": req.clear_cache,
        "dry_run": req.dry_run,
        "anki_connect_url": req.anki_connect_url,
        "workers": req.workers,
    }
    # Filter Nones
    overrides = {k: v for k, v in overrides.items() if v is not None}

    try:
        # Resolve config
        config = resolve_config(overrides)

        # Execute
        stats = await execute_sync(config)

        return SyncStatsResponse(
            total_generated=stats.total_generated,
            total_imported=stats.total_imported,
            total_errors=stats.total_errors,
            success=stats.total_errors == 0,
        )
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


class CardsRequest(BaseModel):
    cids: list[int]
    backend: str | None = None
    anki_connect_url: str | None = None
    anki_base: str | None = None


@app.post("/anki/cards/suspend")
async def suspend_cards(req: CardsRequest):
    """Suspend cards by Card IDs."""
    from arete.application.config import resolve_config
    from arete.infrastructure.adapters.factory import get_anki_bridge

    try:
        overrides = {
            "backend": req.backend,
            "anki_connect_url": req.anki_connect_url,
            "anki_base": req.anki_base,
        }
        config = resolve_config({k: v for k, v in overrides.items() if v is not None})
        anki = await get_anki_bridge(config)
        return {"ok": await anki.suspend_cards(req.cids)}
    except Exception as e:
        logger.error(f"Suspend failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/anki/cards/unsuspend")
async def unsuspend_cards(req: CardsRequest):
    """Unsuspend cards by Card IDs."""
    from arete.application.config import resolve_config
    from arete.infrastructure.adapters.factory import get_anki_bridge

    try:
        overrides = {
            "backend": req.backend,
            "anki_connect_url": req.anki_connect_url,
            "anki_base": req.anki_base,
        }
        config = resolve_config({k: v for k, v in overrides.items() if v is not None})
        anki = await get_anki_bridge(config)
        return {"ok": await anki.unsuspend_cards(req.cids)}
    except Exception as e:
        logger.error(f"Unsuspend failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/anki/models/{name}/styling")
async def get_model_styling(
    name: str,
    backend: str | None = None,
    anki_connect_url: str | None = None,
    anki_base: str | None = None,
):
    from arete.application.config import resolve_config
    from arete.infrastructure.adapters.factory import get_anki_bridge

    try:
        overrides = {
            "backend": backend,
            "anki_connect_url": anki_connect_url,
            "anki_base": anki_base,
        }
        config = resolve_config({k: v for k, v in overrides.items() if v is not None})
        anki = await get_anki_bridge(config)
        css = await anki.get_model_styling(name)
        return {"css": css}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/anki/models/{name}/templates")
async def get_model_templates(
    name: str,
    backend: str | None = None,
    anki_connect_url: str | None = None,
    anki_base: str | None = None,
):
    from arete.application.config import resolve_config
    from arete.infrastructure.adapters.factory import get_anki_bridge

    try:
        overrides = {
            "backend": backend,
            "anki_connect_url": anki_connect_url,
            "anki_base": anki_base,
        }
        config = resolve_config({k: v for k, v in overrides.items() if v is not None})
        anki = await get_anki_bridge(config)
        templates = await anki.get_model_templates(name)
        return templates
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/shutdown")
async def shutdown_server():
    """
    Gracefully shuts down the server.
    Useful for plugins to kill the process when they unload.
    """
    logger.info("Received shutdown request.")

    # Schedule the kill provided we are running in Uvicorn
    # There isn't a standard "fastapi shutdown" method, but we can kill the process
    # or rely on uvicorn's handling if we can access the server instance.
    # A simple reliable way for a CLI tool is to exit the process.

    def kill():
        time.sleep(0.5)  # Give time to return response
        logger.info("Exiting process...")
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=kill).start()
    return {"message": "Server shutting down..."}


@app.post("/agent/chat")
async def agent_chat(req: dict):
    # Using Any for req to avoid complex Pydantic import issues if they arise
    # but we'll import the real class inside for type safety.
    from arete.agent import AgentChatRequest, BasicChatInputSchema, create_arete_agent

    # Validate manually for now to keep it flexible
    logger.info(f"Agent chat raw request: {req}")
    try:
        data = req if isinstance(req, dict) else req.dict()
        chat_req = AgentChatRequest(**data)
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid request: {e}") from None

    logger.info(f"Agent chat request validated: {chat_req.message}")

    try:
        agent = create_arete_agent(chat_req.api_key, chat_req.provider)

        # Pass 1: Initial user query
        response = agent.run(BasicChatInputSchema(chat_message=chat_req.message))

        message = response.chat_message
        action_desc = response.action_taken
        suggested_questions = response.suggested_questions

        # Handle tool execution if requested
        if response.tool_request:
            from arete.agent import execute_agent_tool

            tool_name = response.tool_request
            logger.info(f"Agent requested tool: {tool_name}")

            tool_result = await execute_agent_tool(tool_name)
            action_desc = f"Action: {tool_name} | Result: {tool_result}"

            # Pass 2: Give tool result back to agent so it can summarize/explain
            # We add a hidden instruction to the agent to summarize the results.
            follow_up_msg = (
                f"The tool '{tool_name}' returned the following result:\n{tool_result}\n\n"
                "Please provide a helpful, conversational summary of these results to the user. "
                "Highlight what they need to know and identify specific notes "
                "(using [[wiki link]]) if applicable."
            )

            # Atomic Agents maintains history in its current session.
            # We run it again with the follow-up.
            final_response = agent.run(BasicChatInputSchema(chat_message=follow_up_msg))

            message = final_response.chat_message
            suggested_questions = final_response.suggested_questions

        return {
            "chat_message": message,
            "suggested_questions": suggested_questions,
            "action_taken": action_desc,
        }
    except Exception as e:
        logger.error(f"Agent failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


class StatsRequest(BaseModel):
    nids: list[int]
    backend: str | None = None
    anki_connect_url: str | None = None
    anki_base: str | None = None


@app.post("/anki/stats")
async def get_stats(req: StatsRequest):
    """
    Get stats for a list of Note IDs.
    Uses the configured backend (Auto/Direct/Connect).
    """
    from arete.application.config import resolve_config
    from arete.infrastructure.adapters.factory import get_anki_bridge

    try:
        # Pass overrides from request to config
        overrides = {
            "backend": req.backend,
            "anki_connect_url": req.anki_connect_url,
            "anki_base": req.anki_base,
        }
        # Filter Nones
        overrides = {k: v for k, v in overrides.items() if v is not None}

        config = resolve_config(overrides)
        anki = await get_anki_bridge(config)
        stats = await anki.get_card_stats(req.nids)
        return stats
    except Exception as e:
        logger.error(f"Stats fetch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


class BrowseRequest(BaseModel):
    query: str
    backend: str | None = None
    anki_connect_url: str | None = None
    anki_base: str | None = None


@app.post("/anki/browse")
async def browse_anki(req: BrowseRequest):
    """
    Open the Anki browser with a query.
    """
    from arete.application.config import resolve_config
    from arete.infrastructure.adapters.factory import get_anki_bridge

    try:
        overrides = {
            "backend": req.backend,
            "anki_connect_url": req.anki_connect_url,
            "anki_base": req.anki_base,
        }
        config = resolve_config({k: v for k, v in overrides.items() if v is not None})
        anki = await get_anki_bridge(config)
        return {"ok": await anki.gui_browse(req.query)}
    except Exception as e:
        logger.error(f"Browse failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
