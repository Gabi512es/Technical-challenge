"""
Stage 3 — FastAPI application exposing the natural-language search endpoint.

Run with: uvicorn api.main:app --reload
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from api.search import embed_all_items, search

ENRICHED_JSON_PATH = Path("data/enriched_final.json")

app = FastAPI(title="Rakuten TV Content Discovery — Search API")

# In-memory catalog state, populated once at startup (see load_catalog below).
state = {"items": [], "item_embeddings": {}}


class SearchRequest(BaseModel):
    query: str


class SearchResult(BaseModel):
    content_id: str
    title: str
    year: Optional[int] = None
    description: Optional[str] = None
    relevance_reason: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


@app.on_event("startup")
def load_catalog() -> None:
    """
    Load the stage 1+2 output and precompute embeddings for every item ONCE
    at startup. At real catalog scale (thousands of titles), recomputing
    embeddings on every /search request would make each request as slow as
    a full re-indexing pass -- embeddings only need to change when the
    catalog itself changes, not on every query.
    """
    with open(ENRICHED_JSON_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)

    state["items"] = items
    state["item_embeddings"] = embed_all_items(items)
    print(f"Loaded {len(items)} items and precomputed their embeddings.")


@app.post("/search", response_model=SearchResponse)
def search_endpoint(request: SearchRequest) -> SearchResponse:
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query string must not be empty.")

    results = search(query, state["items"], state["item_embeddings"])
    return SearchResponse(query=query, results=results)
