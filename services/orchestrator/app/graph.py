"""The six-stage research lifecycle, modeled as a LangGraph StateGraph.

Each node is a real call to one of the other services (retrieval, gateway,
simulation) — nothing here is mock data. The graph is linear (each stage
feeds the next), which mirrors the lifecycle walked in the mock demo, but
every node's output is produced live.
"""

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from . import clients
from .prompts import derivation_prompt, review_prompt, writeup_prompt


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


async def literature_node(state: ResearchState) -> dict:
    result = await clients.retrieval_ingest(state["question"], max_results=5)
    return {"literature": result["papers"]}


async def derivation_node(state: ResearchState) -> dict:
    model = state.get("default_model") or {"provider": "ollama", "model": "llama3.2:1b"}
    prompt = derivation_prompt(state["question"])
    result = await clients.gateway_generate(model["provider"], model["model"], prompt)
    return {"derivation": result.get("text", ""), "derivation_error": result.get("error")}


async def comparison_node(state: ResearchState) -> dict:
    models = state.get("comparison_models") or [{"provider": "ollama", "model": "llama3.2:1b"}]
    prompt = derivation_prompt(state["question"])
    result = await clients.gateway_compare(prompt, models)
    return {"comparisons": result["results"]}


async def simulation_node(state: ResearchState) -> dict:
    lam = state.get("lam", 0.02)
    basis_size = state.get("basis_size", 40)
    result = await clients.simulation_run(lam, basis_size)
    return {"simulation": result}


async def review_node(state: ResearchState) -> dict:
    model = state.get("default_model") or {"provider": "ollama", "model": "llama3.2:1b"}
    prompt = review_prompt(state["question"], state.get("derivation", ""), state.get("simulation", {}))
    result = await clients.gateway_generate(model["provider"], model["model"], prompt)
    return {"review": result.get("text", "")}


async def writeup_node(state: ResearchState) -> dict:
    model = state.get("default_model") or {"provider": "ollama", "model": "llama3.2:1b"}
    prompt = writeup_prompt(
        state["question"],
        state.get("derivation", ""),
        state.get("simulation", {}),
        state.get("literature", []),
        state.get("review", ""),
    )
    result = await clients.gateway_generate(model["provider"], model["model"], prompt)
    return {"writeup": result.get("text", "")}


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
