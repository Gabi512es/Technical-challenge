# AI-Powered Content Discovery — Technical Test

## Overview

Welcome! This technical test is designed to evaluate your ability to design and implement AI solutions for real-world problems.

**Time expectation:** ~3–6 hours. No hard limit, but manage your scope
**Format:** take-home prototype + a short follow-up interview to walk us through it

## The Challenge

Rakuten TV has thousands of movies and TV shows in its catalog. Currently, the metadata (descriptions, tags, mood, themes) is inconsistent and often incomplete. This affects content discovery quality.

**Your task:** build a prototype that takes a list of titles, enriches them with AI, and makes them searchable through natural language.

This is intentionally broad, we don't expect every piece perfect. 
Get the pipeline working end-to-end and tell us what you'd do with more time.

## What You Need to Build

A pipeline with three stages. **All three should run as automated code**, including data gathering. Please don't hand-collect the data. 
We should be able to clone/unzip your project, follow your README, and run the whole thing end-to-end ourselves.

### 1. Get the data
Start from the seed list in `content_sample.csv` (title, year). For each title, automatically fetch a **movie/show description** plus anything else useful you want. 

### 2. Enrich it with AI
Use AI to turn that raw data into clean, **structured, consistent** enriched metadata for each title:
- Extract or generate: eg detailed genres, mood, target audience, key themes, similar-content suggestions
- Ensure outputs are structured and consistent across all items

### 3. Make it searchable
Expose a **runnable API endpoint** that takes a natural-language query and returns the best-matching titles. For example:
- *"movies about dreams or alternate realities"* → Inception, Coherence, Spirited Away
- *"something funny and real"* -> The Office, Fleabag

**You choose:**
- **Language:** Python, JS/Node, or whatever you're comfortable with
- **Data source:** a public API, scraping, as long as you stay in the legal space :)
- **Enrichment & search approach:**  LLM call/chain, an agent, embeddings, LLM-based ranking, whatever works
- **LLM provider:** OpenAI, Anthropic, open-source models, or any AI service

AI coding assistants are welcome!

**Technical requirements:**
- Must actually call an AI/LLM API
- All three stages must be automated and runnable
- The search must be exposed as a working API endpoint we can call
- Code should be readable and structured
- Provide clear instructions so we can run the whole pipeline end-to-end

## Input

We've provided sample content data in two formats (use whichever you prefer):
- `content_sample.json` — JSON format
- `content_sample.csv` — CSV format

Each entry contains:
- `content_id`: Unique identifier
- `title`: Movie/show title
- `year`: Movie/show year

## Deliverables

**1. Your implementation**
- Code/scripts/workflow files, ideally split by stage so the pipeline is easy to follow
- Dependencies file if applicable
- Configuration files if needed

**2. Output file**
A file containing, for all sample items: (1) the raw fetched description, and (2) the enriched metadata. The exact structure is up to you.

Example output structure:
```json
{
  "content_id": "1001",
  "title": "The Shawshank Redemption",
  "year": "1994",
  "description": "A wrongfully convicted banker forms a close friendship with a hardened convict over a quarter century while retaining his humanity through simple acts of compassion.",
  "enriched_metadata": {
    "detailed_genres": ["Drama", "Prison Drama", "Hope & Redemption"],
    "mood": ["Inspiring", "Emotional", "Thoughtful"],
    "themes": ["friendship", "hope", "injustice", "perseverance"],
    "target_audience": ["Adults", "Drama enthusiasts"],
    "similar_content_suggestions": ["The Green Mile", "Escape from Alcatraz"],
    "content_warnings": ["Violence", "Prison setting"],
    "viewing_context": ["Evening watch", "Thoughtful viewing"]
  }
}
```

**3. Documentation**
- A `README.md` with:
  - Setup and how to run it
  - How to query the search endpoint and 2–3 sample queries with their results
- Your prompt templates (in code, separate file, or documented in the README.md file)

**4. Submission**
- Share via GitHub repository (add francesca.andretta1@gmail GitHUb account), zip file, or any method that works for you
- Ensure we can run your solution

## Evaluation Criteria

We'll evaluate based on:

- **Data sourcing** — How you source the data and how you handle missing and messy results, whether the fetching is properly automated and runs cleanly
- **AI engineering** — Quality of prompts, consistency of outputs, handling of edge cases
- **Search** — Relevancy of query results, clean and runnable endpoint
- **Technical implementation** — Code quality and organization, technology choices and justification, actually works when we run it, appropriate use of chosen tools/APIs
- **Documentation** — clarity of the provided documentation, ability to explain and justify decisions

## Notes
- **Keep it simple** — this is a prototype, not production-ready code
- **Scope smartly** — if you're running long, stop and note what you'd do next in the README
- **Be ready to discuss** — we'll ask you to walk through your solution and explain your decisions in the follow-up interview

## Questions?

If you have any questions about the test, please reach out to us.

Good luck! We're excited to see your approach.

---

## Stage 3 — Running the Search API

Stage 3 is a standalone FastAPI application (not a notebook) exposing a single `POST /search`
endpoint. It implements a hybrid retrieve-then-rerank pipeline over the 21-item catalog produced
by stages 1 and 2 (`data/enriched_final.json`):

1. **Embedding retrieval** (local `sentence-transformers` model, `all-MiniLM-L6-v2`) narrows the
   catalog down to the top `TOP_K_RETRIEVAL` (12) candidates by cosine similarity. Embeddings are
   computed once at server startup, not per request — this is the piece designed to scale to a
   real catalog of thousands of titles.
   `TOP_K_RETRIEVAL` was raised from an initial value of 8 to 12 after an audit found that
   *Inception* ranked 10th of 21 for the query `"movies about dreams or alternate realities"`
   (similarity score 0.291), just outside the old top-8 cutoff — so the LLM reranker never even
   saw it as a candidate. 12 was the smallest round number that reliably includes it without
   changing the embedding model or retrieval architecture.
2. **LLM reranking** (Claude, via a forced `submit_ranked_results` tool call) refines those
   candidates down to between 1 and 5 results for the specific query, with a short justification
   per result — this is the piece that captures nuanced query intent that pure vector similarity
   can miss. The reranker is explicitly instructed to be selective rather than exhaustive: it
   returns only genuinely relevant titles, and will return just one result (as observed for the
   Chernobyl/disaster-documentary query below) rather than padding the list with weak matches.

### Install dependencies

```bash
python3 -m pip install -r api/requirements.txt
```

### Start the server

Make sure `.env` has `ANTHROPIC_API_KEY` set (same `.env` used by stages 1-2), then run from the
project root:

```bash
uvicorn api.main:app --reload
```

The first startup downloads the `all-MiniLM-L6-v2` model (a few dozen MB, cached afterwards) and
precomputes embeddings for all 21 items before the server starts accepting requests.

### Call the search endpoint

With curl:

```bash
curl -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "movies about dreams or alternate realities"}'
```

With [HTTPie](https://httpie.io/):

```bash
http POST http://127.0.0.1:8000/search query="movies about dreams or alternate realities"
```

### Example queries and verified results

These are the actual results returned by a live run against the real Anthropic API (see
`audit_stage3.py` for the full, reproducible audit — embedding scores, exact JSON responses, and
whether the LLM reranker changed the embedding-only order):

- **`"movies about dreams or alternate realities"`** → *Inception*, *Coherence*, *8½*,
  *Spirited Away*, *Suspiria* (5 results). *Inception* was retrieved at rank 10/21 by embedding
  similarity alone and was not in the reranker's candidate set before `TOP_K_RETRIEVAL` was raised
  to 12; the reranker now places it first.
- **`"something funny and real"`** → *Fleabag*, *The Office*, *Parasite*, *Amélie* (4 results —
  *Moonlight* was retrieved by embedding similarity but the reranker judged it less "funny" than
  the other four and dropped it).
- **`"true crime documentary about a disaster"`** → *Chernobyl* only (1 result). Both the
  embedding retrieval and the LLM reranker agree there is exactly one genuine match in this
  21-item catalog; the reranker does not pad the response with weaker titles to reach a higher
  count.

Each result includes a `relevance_reason` explaining, in plain language, why the LLM reranker
selected that title for the query — useful for a Content team member auditing why a given result
surfaced.

### Error handling and fallback behavior (verified)

- An empty or whitespace-only `query` returns `400 Bad Request` with a clear error message.
- **If `ANTHROPIC_API_KEY` is missing entirely**, the application still starts normally (a message
  is printed noting that LLM reranking is disabled, without ever printing the key itself), and
  `POST /search` still returns `200` using the embedding-only fallback: the top 3 retrieved
  candidates, each with `relevance_reason: "Matched by semantic similarity (LLM reranking
  unavailable)."` Verified live by temporarily moving `.env` aside, starting the server, confirming
  a `200` response with fallback results, then restoring `.env`.
- **If the LLM call itself fails** (API error, malformed tool output, or an invalid `content_id`
  in the response) after the server has started with a valid key, the same embedding-only fallback
  is used for that request — the endpoint never crashes or returns an error to the caller because
  of an LLM failure.