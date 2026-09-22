import os

import asyncpg
from pgvector.asyncpg import register_vector

from .embeddings import EMBEDDING_DIM

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://research:research@postgres:5432/research"
)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, init=_init_connection)
        await _ensure_schema(_pool)
    return _pool


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    await register_vector(conn)


async def _ensure_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS papers (
                id SERIAL PRIMARY KEY,
                query TEXT NOT NULL,
                title TEXT NOT NULL,
                authors TEXT NOT NULL,
                summary TEXT NOT NULL,
                url TEXT NOT NULL,
                embedding vector({EMBEDDING_DIM}) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )


async def insert_paper(query: str, title: str, authors: str, summary: str, url: str, embedding: list[float]) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO papers (query, title, authors, summary, url, embedding)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            query,
            title,
            authors,
            summary,
            url,
            embedding,
        )


async def search_similar(embedding: list[float], limit: int = 5) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT title, authors, summary, url, embedding <-> $1 AS distance
            FROM papers
            ORDER BY embedding <-> $1
            LIMIT $2
            """,
            embedding,
            limit,
        )
    return [dict(row) for row in rows]
