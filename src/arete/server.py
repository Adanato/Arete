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
