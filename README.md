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