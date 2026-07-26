"""Audit Stage 3 search quality, reranking impact, and fallback behavior.

Run from the project root after starting from a valid environment:
    python audit_stage3.py

The script uses the FastAPI app in-process, so a separate uvicorn server is not required.
It prints:
- raw embedding retrieval order and similarity scores;
- the exact JSON returned by POST /search;
- whether the LLM changed selection/order;
- an exact forced-fallback JSON response.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

import api.main as main_module
import api.search as search_module


QUERIES = [
    "movies about dreams or alternate realities",
    "something funny and real",
    "true crime documentary about a disaster",
]


class _FailingMessages:
    def create(self, **_: Any) -> Any:
        raise RuntimeError("forced Claude failure for fallback audit")


class _FailingAnthropicClient:
    def __init__(self) -> None:
        self.messages = _FailingMessages()


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _titles_from_response(payload: dict) -> list[str]:
    return [result["title"] for result in payload.get("results", [])]


def main() -> None:
    any_rerank_change = False

    with TestClient(main_module.app) as client:
        print("=" * 100)
        print("LIVE QUERY AUDIT")
        print("=" * 100)

        for query in QUERIES:
            candidates = search_module.retrieve_candidates(
                query,
                main_module.state["item_embeddings"],
                main_module.state["items"],
            )
            retrieval_titles = [candidate["title"] for candidate in candidates]

            print(f"\nQUERY: {query!r}")
            print("\nEmbedding retrieval order:")
            for index, candidate in enumerate(candidates, start=1):
                print(
                    f"  {index}. {candidate['title']} ({candidate.get('year')}) "
                    f"score={candidate['similarity_score']:.6f}"
                )

            response = client.post("/search", json={"query": query})
            print(f"\nPOST /search status: {response.status_code}")
            payload = response.json()
            print("POST /search JSON:")
            _print_json(payload)

            reranked_titles = _titles_from_response(payload)
            baseline_same_length = retrieval_titles[: len(reranked_titles)]
            changed = reranked_titles != baseline_same_length
            any_rerank_change = any_rerank_change or changed

            print("\nComparison:")
            print(f"  Retrieval top-{len(reranked_titles)}: {baseline_same_length}")
            print(f"  Final reranked results: {reranked_titles}")
            print(f"  LLM changed selection/order: {'YES' if changed else 'NO'}")
            print("-" * 100)

        print("\nRERANKING VALUE CHECK")
        print(
            "PASS: at least one query changed after LLM reranking."
            if any_rerank_change
            else "FAIL: none of the tested queries changed after LLM reranking."
        )

        print("\n" + "=" * 100)
        print("FORCED FALLBACK AUDIT")
        print("=" * 100)

        original_client = search_module._anthropic_client
        search_module._anthropic_client = _FailingAnthropicClient()
        try:
            fallback_query = QUERIES[0]
            response = client.post("/search", json={"query": fallback_query})
            print(f"POST /search status: {response.status_code}")
            print("Forced-fallback JSON:")
            _print_json(response.json())

            fallback_ok = (
                response.status_code == 200
                and bool(response.json().get("results"))
                and all(
                    result.get("relevance_reason")
                    == "Matched by semantic similarity (LLM reranking unavailable)."
                    for result in response.json()["results"]
                )
            )
            print(f"Fallback endpoint stayed available: {'PASS' if fallback_ok else 'FAIL'}")
        finally:
            search_module._anthropic_client = original_client

    print("\nIMPORTANT CONFIGURATION NOTE")
    print(
        "The current api/search.py raises RuntimeError during import when "
        "ANTHROPIC_API_KEY is absent. Therefore, an entirely missing key prevents "
        "the API from starting; the fallback only protects failures occurring after startup."
    )


if __name__ == "__main__":
    main()
