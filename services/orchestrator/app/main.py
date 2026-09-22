from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import db
from .graph import STAGE_ORDER, research_graph

app = FastAPI(title="Research Assistant — Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateSessionRequest(BaseModel):
    question: str


class ModelSpec(BaseModel):
    provider: str
    model: str


class RunRequest(BaseModel):
    default_model: ModelSpec | None = None
    comparison_models: list[ModelSpec] | None = None
    lam: float = 0.02
    basis_size: int = 40


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/v1/sessions")
async def create_session(request: CreateSessionRequest):
    session_id = await db.create_session(request.question)
    return {"id": session_id, "question": request.question}


@app.get("/v1/sessions")
async def list_sessions():
    return await db.list_sessions()


@app.get("/v1/sessions/{session_id}")
async def get_session(session_id: int):
    session = await db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@app.post("/v1/sessions/{session_id}/run")
async def run_session(session_id: int, request: RunRequest):
    """Runs the full six-stage LangGraph pipeline, persisting state after
    every stage completes so GET /v1/sessions/{id} shows live progress even
    while later stages are still running."""
    session = await db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    initial_state = {
        "question": session["question"],
        "default_model": (request.default_model or ModelSpec(provider="ollama", model="llama3.2:1b")).model_dump(),
        "comparison_models": [m.model_dump() for m in request.comparison_models]
        if request.comparison_models
        else [{"provider": "ollama", "model": "llama3.2:1b"}],
        "lam": request.lam,
        "basis_size": request.basis_size,
    }

    await db.update_session_state(session_id, initial_state, status="running")

    accumulated = initial_state
    async for stage_state in research_graph.astream(initial_state, stream_mode="values"):
        # stream_mode="values" yields the full merged state after each node.
        accumulated = stage_state
        completed = [s for s in STAGE_ORDER if s in stage_state]
        status = "running" if len(completed) < len(STAGE_ORDER) else "complete"
        await db.update_session_state(session_id, accumulated, status=status)

    return await db.get_session(session_id)
