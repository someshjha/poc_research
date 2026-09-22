from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .arxiv import search_arxiv
from .db import insert_paper, search_similar
from .embeddings import embed

app = FastAPI(title="Research Assistant — Retrieval Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestRequest(BaseModel):
    query: str
    max_results: int = 5


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/v1/ingest")
async def ingest(request: IngestRequest):
    """Fetch real papers from arXiv for `query`, embed them locally via
    Ollama, and store them in pgvector."""
    papers = await search_arxiv(request.query, max_results=request.max_results)
    stored = []
    for paper in papers:
        text_to_embed = f"{paper['title']}\n\n{paper['summary']}"
        vector = await embed(text_to_embed)
        await insert_paper(
            query=request.query,
            title=paper["title"],
            authors=paper["authors"],
            summary=paper["summary"],
            url=paper["url"],
            embedding=vector,
        )
        stored.append(paper)
    return {"ingested": len(stored), "papers": stored}


@app.post("/v1/search")
async def search(request: SearchRequest):
    """Semantic search over whatever has been ingested so far."""
    vector = await embed(request.query)
    results = await search_similar(vector, limit=request.limit)
    return {"results": results}
