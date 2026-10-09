"""FastAPI service: serves the chat interface and the API behind it.

    python app.py            # then open http://localhost:8000

Endpoints:
    GET  /              the chat interface
    GET  /health        liveness probe (used by Docker and k8s)
    GET  /api/tools     the MCP tools currently loaded
    POST /api/chat      {"message": str, "session_id": str?} -> answer
    POST /api/reset     {"session_id": str} -> clears that conversation
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent import JobHuntingAgent
from config import STATIC_DIR

logger = logging.getLogger(__name__)

# One agent (one MCP subprocess) shared by every request, plus the per-session
# conversation histories. Histories live in memory, so they reset when the
# process restarts; a real deployment would put them in Redis or Postgres.
state: dict[str, Any] = {"agent": None, "sessions": {}, "lock": asyncio.Lock()}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the MCP connection once at boot and close it on shutdown."""
    logging.basicConfig(level=logging.INFO)
    agent = JobHuntingAgent()
    await agent.connect()
    state["agent"] = agent
    logger.info("Agent ready with tools: %s", [t["name"] for t in agent.tools])
    try:
        yield
    finally:
        await agent.close()
        logger.info("Agent connection closed")


app = FastAPI(
    title="Job Hunting AI Agent",
    description=(
        "AI agent for job hunting that analyzes job postings and my CV, "
        "built with the Claude API, RAG and MCP."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    tools_used: list[str]
    session_id: str


class ResetRequest(BaseModel):
    session_id: str


@app.get("/health")
def health() -> dict[str, Any]:
    agent = state["agent"]
    return {
        "status": "ok" if agent else "starting",
        "tools": [tool["name"] for tool in agent.tools] if agent else [],
    }


@app.get("/api/tools")
def tools() -> dict[str, Any]:
    agent = state["agent"]
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent is still starting up.")
    return {"tools": agent.tools}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Answer one message inside a conversation, creating it if needed."""
    agent = state["agent"]
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent is still starting up.")

    session_id = request.session_id or str(uuid.uuid4())
    history = state["sessions"].setdefault(session_id, [])

    # The MCP connection and each history are shared mutable state, so one
    # question is answered at a time. Fine for a personal assistant; a
    # multi-user deployment would hold one agent per worker instead.
    async with state["lock"]:
        try:
            result = await agent.ask(request.message, history)
        except Exception as error:  # noqa: BLE001 - surfaced to the caller
            logger.exception("Failed to answer")
            raise HTTPException(status_code=500, detail=str(error)) from error

    return ChatResponse(
        reply=result["reply"],
        tools_used=result["tools_used"],
        session_id=session_id,
    )


@app.post("/api/reset")
def reset(request: ResetRequest) -> dict[str, str]:
    state["sessions"].pop(request.session_id, None)
    return {"status": "cleared"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
