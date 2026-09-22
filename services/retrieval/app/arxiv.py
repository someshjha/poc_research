"""Real retrieval against the public arXiv API — no key required."""

import xml.etree.ElementTree as ET

import httpx

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


async def search_arxiv(query: str, max_results: int = 5) -> list[dict]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.get(
            ARXIV_API,
            params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": max_results,
            },
        )
    response.raise_for_status()

    root = ET.fromstring(response.text)
    papers = []
    for entry in root.findall("atom:entry", ATOM_NS):
        title = entry.findtext("atom:title", default="", namespaces=ATOM_NS).strip()
        summary = entry.findtext("atom:summary", default="", namespaces=ATOM_NS).strip()
        link = entry.findtext("atom:id", default="", namespaces=ATOM_NS).strip()
        authors = [
            author.findtext("atom:name", default="", namespaces=ATOM_NS)
            for author in entry.findall("atom:author", ATOM_NS)
        ]
        papers.append(
            {
                "title": " ".join(title.split()),
                "summary": " ".join(summary.split()),
                "authors": ", ".join(a for a in authors if a),
                "url": link,
            }
        )
    return papers
