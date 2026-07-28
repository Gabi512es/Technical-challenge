"""
Stage 3 — hybrid retrieve-then-rerank search logic.

1. Embedding-based retrieval narrows the catalog down to a handful of
   candidates. This is the piece designed to scale to a large catalog:
   embeddings are computed once per item (see embed_all_items) and compared
   via cosine similarity, independent of catalog size.
2. LLM-based reranking refines those candidates for the specific query and
   adds a short justification per result. This is the piece that captures
   nuanced query intent that pure vector similarity can miss.
"""

import os

import numpy as np
from anthropic import Anthropic
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

MODEL = "claude-sonnet-5"
REQUEST_TIMEOUT = 30  # seconds

# The Anthropic client is optional: this prototype must still start and serve
# /search (via the embedding-only fallback) when no key is configured. Never
# log the key value itself, only whether one was found.
if ANTHROPIC_API_KEY:
    _anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
else:
    _anthropic_client = None
    print(
        "[api.search] ANTHROPIC_API_KEY is not set: LLM reranking is disabled. "
        "Falling back to embedding-only retrieval for every query."
    )

# ---------------------------------------------------------------------------
# A. Embedding setup
# ---------------------------------------------------------------------------

# "all-MiniLM-L6-v2" is a small, local sentence-transformers model: no extra
# API key, no network call at query time, and more than good enough for a
# 21-item prototype catalog. Using a hosted embeddings API here would mean
# adding a third API key and a third external dependency just to embed a
# handful of short text blobs.
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

_embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

# Descriptive fields only: programming_slot_fit and content_warnings are
# operational/scheduling metadata, not content describing what the title is
# about, so they are excluded from the embedding text.
DESCRIPTIVE_METADATA_FIELDS = ["detailed_genres", "mood", "themes", "target_audience", "viewing_context"]


def build_embedding_text(item: dict) -> str:
    """
    Concatenate the description and descriptive enriched_metadata fields of
    an item into a single clean string for embedding.
    """
    parts = [item.get("description") or ""]

    metadata = item.get("enriched_metadata") or {}
    for field in DESCRIPTIVE_METADATA_FIELDS:
        values = metadata.get(field) or []
        if values:
            parts.append(", ".join(values))

    return "\n".join(part for part in parts if part)


def embed_all_items(items: list) -> dict:
    """
    Compute one embedding per item, keyed by content_id.

    Intended to be called ONCE at startup, not per request: at real catalog
    scale (thousands of titles), recomputing embeddings on every search
    request would make each request as slow as a full re-indexing pass.
    Embeddings only need to be recomputed when the catalog itself changes.
    """
    texts = [build_embedding_text(item) for item in items]
    vectors = _embedding_model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

    return {item["content_id"]: vector for item, vector in zip(items, vectors)}


# ---------------------------------------------------------------------------
# B. Retrieval step
# ---------------------------------------------------------------------------

TOP_K_RETRIEVAL = 12


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def retrieve_candidates(query: str, item_embeddings: dict, items: list) -> list:
    """
    Embed the query with the same model used for items, score every item by
    cosine similarity against its precomputed embedding, and return the top
    TOP_K_RETRIEVAL items sorted by similarity score (highest first).

    If the catalog has fewer than TOP_K_RETRIEVAL items, all available items
    are returned instead of crashing.
    """
    query_vector = _embedding_model.encode(query, convert_to_numpy=True, normalize_embeddings=True)

    scored = []
    for item in items:
        embedding = item_embeddings.get(item["content_id"])
        if embedding is None:
            continue
        similarity = _cosine_similarity(query_vector, embedding)
        # similarity_score is kept on the candidate dict for debugging/audit
        # purposes; it is not exposed in the final API response.
        scored.append({**item, "similarity_score": similarity})

    scored.sort(key=lambda entry: entry["similarity_score"], reverse=True)

    top_k = min(TOP_K_RETRIEVAL, len(scored))
    return scored[:top_k]


# ---------------------------------------------------------------------------
# C. Re-ranking step
# ---------------------------------------------------------------------------

RERANK_TOOL = {
    "name": "submit_ranked_results",
    "description": (
        "Submit the final ranked list of search results for the user's query, selecting "
        "and ordering only the candidates that genuinely match the query's intent."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "minItems": 1,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "content_id": {
                            "type": "string",
                            "description": "The content_id of a selected candidate, exactly as given in the input.",
                        },
                        "relevance_reason": {
                            "type": "string",
                            "description": "A 1-2 sentence justification for why this title matches the query.",
                        },
                    },
                    "required": ["content_id", "relevance_reason"],
                },
            },
        },
        "required": ["results"],
    },
}

RERANK_SYSTEM_PROMPT = """You are a content search assistant for an internal catalog tool used \
by a streaming platform's Content team (catalog curation and channel programming, not a \
consumer-facing feature). Given a natural-language search query and a shortlist of candidate \
titles already retrieved by semantic similarity, select and order between 1 and 5 candidates \
that genuinely match the query's specific intent, and provide a short justification for each.

Be selective, not exhaustive. Only include a candidate if it truly matches the query. If just \
one or two candidates genuinely match, return only those -- do not pad the response with weaker \
or tangentially related titles just to reach a higher count.

Only select from the candidates provided to you. Never invent a title or a content_id that is \
not in the given list.

You must always respond by calling the submit_ranked_results tool. Never respond in plain text."""


def build_rerank_prompt(query: str, candidates: list) -> str:
    """
    Build the user message presenting the query and the retrieved candidates
    (title, year, description, enriched_metadata) to the LLM for reranking.
    """
    lines = [f'User query: "{query}"', "", "Candidates:"]

    for candidate in candidates:
        metadata = candidate.get("enriched_metadata") or {}
        lines.append(
            f"- content_id: {candidate['content_id']}\n"
            f"  Title: {candidate['title']} ({candidate.get('year')})\n"
            f"  Description: {candidate.get('description') or 'not available'}\n"
            f"  Detailed genres: {', '.join(metadata.get('detailed_genres') or []) or 'not available'}\n"
            f"  Mood: {', '.join(metadata.get('mood') or []) or 'not available'}\n"
            f"  Themes: {', '.join(metadata.get('themes') or []) or 'not available'}\n"
            f"  Target audience: {', '.join(metadata.get('target_audience') or []) or 'not available'}\n"
            f"  Viewing context: {', '.join(metadata.get('viewing_context') or []) or 'not available'}"
        )

    lines.append(
        "\nSelect and order between 1 and 5 candidates for this query -- only the ones that "
        "genuinely match. Do not pad the response with weak matches just to reach a higher count."
    )

    return "\n".join(lines)


def rerank_with_llm(query: str, candidates: list) -> list:
    """
    Ask Claude to select and order the most relevant candidates for the
    query, with a short justification per result.

    On any failure (API error, malformed output, or a returned content_id
    that isn't one of the candidates), falls back to the top 3 embedding-
    retrieved candidates directly -- the endpoint must always return
    something rather than crash. The same fallback is used immediately,
    with no API call attempted, when no Anthropic client is configured.
    """
    if not candidates:
        return []

    fallback = [
        {
            "content_id": candidate["content_id"],
            "relevance_reason": "Matched by semantic similarity (LLM reranking unavailable).",
        }
        for candidate in candidates[:3]
    ]

    if _anthropic_client is None:
        print(f"[rerank_with_llm] No Anthropic client configured for query '{query}': using embedding fallback.")
        return fallback

    prompt = build_rerank_prompt(query, candidates)

    try:
        response = _anthropic_client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=RERANK_SYSTEM_PROMPT,
            tools=[RERANK_TOOL],
            tool_choice={"type": "tool", "name": "submit_ranked_results"},
            messages=[{"role": "user", "content": prompt}],
            timeout=REQUEST_TIMEOUT,
        )

        tool_use_block = next(
            (block for block in response.content if block.type == "tool_use"), None
        )
        if tool_use_block is None:
            raise ValueError("No tool_use block found in the response")

        results = tool_use_block.input.get("results")
        if not isinstance(results, list) or not (1 <= len(results) <= 5):
            raise ValueError(f"submit_ranked_results returned an invalid results list: {results!r}")

        valid_content_ids = {candidate["content_id"] for candidate in candidates}
        seen_content_ids = set()
        for result in results:
            content_id = result.get("content_id")
            relevance_reason = result.get("relevance_reason")

            if not content_id or content_id not in valid_content_ids:
                raise ValueError(f"LLM returned an unknown or empty content_id: {content_id!r}")
            if content_id in seen_content_ids:
                raise ValueError(f"LLM returned a duplicate content_id: {content_id!r}")
            if not isinstance(relevance_reason, str) or not relevance_reason.strip():
                raise ValueError(f"LLM returned an empty or invalid relevance_reason for content_id {content_id!r}")

            seen_content_ids.add(content_id)

        return results

    except Exception as e:
        print(f"[rerank_with_llm] LLM reranking failed for query '{query}': {e}")
        return fallback


# ---------------------------------------------------------------------------
# D. Orchestration
# ---------------------------------------------------------------------------


def search(query: str, items: list, item_embeddings: dict) -> list:
    """
    Full stage 3 pipeline for one query: retrieve top candidates by embedding
    similarity, rerank them with the LLM, then merge the LLM's ranked
    content_ids back with the full item data for the final response.
    """
    candidates = retrieve_candidates(query, item_embeddings, items)
    ranked = rerank_with_llm(query, candidates)

    items_by_id = {item["content_id"]: item for item in items}

    results = []
    for entry in ranked:
        item = items_by_id.get(entry["content_id"])
        if item is None:
            continue
        results.append({
            "content_id": item["content_id"],
            "title": item["title"],
            "year": item.get("year"),
            "description": item.get("description"),
            "relevance_reason": entry["relevance_reason"],
        })

    return results
