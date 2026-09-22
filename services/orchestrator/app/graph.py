"""The six-stage research lifecycle, modeled as a LangGraph StateGraph.

Each node is a real call to one of the other services (retrieval, gateway,
simulation) — nothing here is mock data. The graph is linear (each stage
feeds the next), which mirrors the lifecycle walked in the mock demo, but
every node's output is produced live.

Every node also appends a trace event describing exactly what it did —
which service/provider/model it called, the request it sent, the response
it got back, and how long it took — so the frontend's observability view
can show the full, real execution history of a run, not just its final
output.
"""

import operator
import time
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from . import clients
from .prompts import derivation_prompt, review_prompt, writeup_prompt


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_trace_event(stage: str, started_at: str, calls: list[dict], summary: str) -> dict:
    started = datetime.fromisoformat(started_at)
    ended_at = now_iso()
    ended = datetime.fromisoformat(ended_at)
    return {
        "stage": stage,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": int((ended - started).total_seconds() * 1000),
        "summary": summary,
        "calls": calls,
    }


class ResearchState(TypedDict, total=False):
    question: str
    default_model: dict[str, str]
    comparison_models: list[dict[str, str]]
    lam: float
    basis_size: int

    literature: list[dict[str, Any]]
    derivation: str
    derivation_error: str | None
    comparisons: list[dict[str, Any]]
    simulation: dict[str, Any]
    review: str
    writeup: str
    # Reducer: each node's trace event is appended, not overwritten, so the
    # full run history accumulates across the six stages.
    trace: Annotated[list[dict], operator.add]


async def literature_node(state: ResearchState) -> dict:
    started_at = now_iso()
    t0 = time.monotonic()
    result = await clients.retrieval_ingest(state["question"], max_results=5)
    latency_ms = int((time.monotonic() - t0) * 1000)

    call = {
        "target": "retrieval",
        "endpoint": "POST /v1/ingest",
        "request": {"query": state["question"], "max_results": 5},
        "response_summary": f"{result['ingested']} papers ingested from arXiv and embedded via Ollama",
        "latency_ms": latency_ms,
        "error": None,
    }
    event = make_trace_event(
        "literature", started_at, [call], f"Retrieved {result['ingested']} papers from arXiv"
    )
    return {"literature": result["papers"], "trace": [event]}


async def derivation_node(state: ResearchState) -> dict:
    started_at = now_iso()
    model = state.get("default_model") or {"provider": "ollama", "model": "llama3.2:1b"}
    prompt = derivation_prompt(state["question"])
    result = await clients.gateway_generate(model["provider"], model["model"], prompt)

    call = {
        "target": "gateway",
        "endpoint": "POST /v1/generate",
        "provider": model["provider"],
        "model": model["model"],
        "request": {"prompt": prompt},
        "response": result.get("text", ""),
        "latency_ms": result.get("latency_ms"),
        "error": result.get("error"),
    }
    summary = (
        f"{model['provider']}/{model['model']} failed: {result.get('error')}"
        if result.get("error")
        else f"{model['provider']}/{model['model']} produced {len(result.get('text', ''))} chars"
    )
    event = make_trace_event("derivation", started_at, [call], summary)
    return {"derivation": result.get("text", ""), "derivation_error": result.get("error"), "trace": [event]}


async def comparison_node(state: ResearchState) -> dict:
    started_at = now_iso()
    models = state.get("comparison_models") or [{"provider": "ollama", "model": "llama3.2:1b"}]
    prompt = derivation_prompt(state["question"])
    result = await clients.gateway_compare(prompt, models)

    calls = [
        {
            "target": "gateway",
            "endpoint": "POST /v1/compare",
            "provider": r["provider"],
            "model": r["model"],
            "request": {"prompt": prompt},
            "response": r.get("text", ""),
            "latency_ms": r.get("latency_ms"),
            "error": r.get("error"),
        }
        for r in result["results"]
    ]
    ok = sum(1 for r in result["results"] if not r.get("error"))
    event = make_trace_event(
        "comparisons", started_at, calls, f"{ok}/{len(result['results'])} models answered successfully"
    )
    return {"comparisons": result["results"], "trace": [event]}


async def simulation_node(state: ResearchState) -> dict:
    started_at = now_iso()
    lam = state.get("lam", 0.02)
    basis_size = state.get("basis_size", 40)
    t0 = time.monotonic()
    result = await clients.simulation_run(lam, basis_size)
    latency_ms = int((time.monotonic() - t0) * 1000)

    call = {
        "target": "simulation",
        "endpoint": "POST /v1/simulate",
        "request": {"lambda": lam, "basis_size": basis_size},
        "response_summary": f"numerical ground state {result['numerical_ground_state']:.5f} ħω",
        "latency_ms": latency_ms,
        "error": None,
    }
    event = make_trace_event(
        "simulation", started_at, [call], f"Diagonalized a {basis_size}x{basis_size} Hamiltonian"
    )
    return {"simulation": result, "trace": [event]}


async def review_node(state: ResearchState) -> dict:
    started_at = now_iso()
    model = state.get("default_model") or {"provider": "ollama", "model": "llama3.2:1b"}
    prompt = review_prompt(state["question"], state.get("derivation", ""), state.get("simulation", {}))
    result = await clients.gateway_generate(model["provider"], model["model"], prompt)

    call = {
        "target": "gateway",
        "endpoint": "POST /v1/generate",
        "provider": model["provider"],
        "model": model["model"],
        "request": {"prompt": prompt},
        "response": result.get("text", ""),
        "latency_ms": result.get("latency_ms"),
        "error": result.get("error"),
    }
    summary = (
        f"{model['provider']}/{model['model']} failed: {result.get('error')}"
        if result.get("error")
        else f"{model['provider']}/{model['model']} produced {len(result.get('text', ''))} chars"
    )
    event = make_trace_event("review", started_at, [call], summary)
    return {"review": result.get("text", ""), "trace": [event]}


async def writeup_node(state: ResearchState) -> dict:
    started_at = now_iso()
    model = state.get("default_model") or {"provider": "ollama", "model": "llama3.2:1b"}
    prompt = writeup_prompt(
        state["question"],
        state.get("derivation", ""),
        state.get("simulation", {}),
        state.get("literature", []),
        state.get("review", ""),
    )
    result = await clients.gateway_generate(model["provider"], model["model"], prompt)

    call = {
        "target": "gateway",
        "endpoint": "POST /v1/generate",
        "provider": model["provider"],
        "model": model["model"],
        "request": {"prompt": prompt},
        "response": result.get("text", ""),
        "latency_ms": result.get("latency_ms"),
        "error": result.get("error"),
    }
    summary = (
        f"{model['provider']}/{model['model']} failed: {result.get('error')}"
        if result.get("error")
        else f"{model['provider']}/{model['model']} produced {len(result.get('text', ''))} chars"
    )
    event = make_trace_event("writeup", started_at, [call], summary)
    return {"writeup": result.get("text", ""), "trace": [event]}


def build_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("literature", literature_node)
    graph.add_node("derivation", derivation_node)
    graph.add_node("comparison", comparison_node)
    graph.add_node("simulation", simulation_node)
    graph.add_node("review", review_node)
    graph.add_node("writeup", writeup_node)

    graph.set_entry_point("literature")
    graph.add_edge("literature", "derivation")
    graph.add_edge("derivation", "comparison")
    graph.add_edge("comparison", "simulation")
    graph.add_edge("simulation", "review")
    graph.add_edge("review", "writeup")
    graph.add_edge("writeup", END)

    return graph.compile()


research_graph = build_graph()

STAGE_ORDER = ["literature", "derivation", "comparisons", "simulation", "review", "writeup"]
