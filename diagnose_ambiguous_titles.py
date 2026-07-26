"""
Standalone diagnostic script — NOT part of the main notebook (01_fetch_raw_data.ipynb).

Purpose: observe real TMDB API behavior on a set of deliberately ambiguous titles
to check whether "popularity as tie-breaker" is a robust disambiguation rule,
before deciding whether to change the matching logic in the main notebook.

This script only observes and compares two candidate rules; it does not modify
the main notebook or write any output file.
"""

import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
if not TMDB_API_KEY:
    raise RuntimeError(
        "TMDB_API_KEY is not set. Copy .env.example to .env and fill in your TMDB API key."
    )

TMDB_BASE_URL = "https://api.themoviedb.org/3"
YEAR_TOLERANCE = 1
REQUEST_TIMEOUT = 10

# Deliberately ambiguous (title, expected_year) pairs, plus a couple of control cases.
TEST_TITLES = [
    ("Chernobyl", 2019),     # known bug: indie movie vs HBO mini-series, both year_diff=0
    ("Dune", 2021),          # also a 1984 movie (Lynch), plus a spin-off series
    ("The Office", 2005),    # control case, must stay tv
    ("It", 2017),            # remake vs 1990 mini-series vs other homonyms
    ("Titanic", 1997),       # very high popularity, should be an easy/control case
    ("The Crown", 2016),     # well-known Netflix series, check for homonymous docs/movies
    ("Utopia", 2020),        # generic title, high risk of multiple homonyms
]


def search_tmdb(title, media_type):
    """Query TMDB search endpoint. Returns raw results list, or [] on error."""
    url = f"{TMDB_BASE_URL}/search/{media_type}"
    params = {"api_key": TMDB_API_KEY, "query": title}

    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json().get("results", [])
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] search_tmdb failed for '{title}' ({media_type}): {e}")
        return []


def extract_year(result, media_type):
    """Extract release year from a TMDB result, or None if unavailable."""
    date_field = "release_date" if media_type == "movie" else "first_air_date"
    date_value = result.get(date_field)

    if not date_value:
        return None

    try:
        return int(date_value[:4])
    except (ValueError, TypeError):
        return None


def build_candidates(title, expected_year, media_type):
    """Turn raw search results into normalized candidate dicts, preserving API order."""
    candidates = []

    for result in search_tmdb(title, media_type):
        name = result.get("title") if media_type == "movie" else result.get("name")
        date_value = result.get("release_date") if media_type == "movie" else result.get("first_air_date")
        year = extract_year(result, media_type)
        year_diff = abs(year - expected_year) if year is not None else None

        candidates.append({
            "media_type": media_type,
            "id": result.get("id"),
            "name": name,
            "date": date_value,
            "popularity": result.get("popularity", 0),
            "year_diff": year_diff,
        })

    return candidates


def print_candidates(candidates, media_type):
    """Print every raw candidate for one endpoint (movie or tv)."""
    label = "Movie" if media_type == "movie" else "TV"
    print(f"{label} search results:")

    if not candidates:
        print("  (no results)")
        return

    for c in candidates:
        print(
            f"  id={c['id']!s:<10} name={c['name']!r:<45} date={c['date']!s:<12} "
            f"popularity={c['popularity']:<8} year_diff={c['year_diff']}"
        )


def pick_current_rule(candidates):
    """
    Current rule (as implemented in the main notebook):
    among candidates within YEAR_TOLERANCE, take the lowest year_diff.
    Ties are broken by list order only (movie results come first) -- popularity
    is NOT considered when there is a tie. If none are within tolerance, fall
    back to the most popular candidate overall.
    """
    within_tolerance = [c for c in candidates if c["year_diff"] is not None and c["year_diff"] <= YEAR_TOLERANCE]

    if within_tolerance:
        return min(within_tolerance, key=lambda c: c["year_diff"])

    if candidates:
        return max(candidates, key=lambda c: c["popularity"])

    return None


def pick_proposed_rule(candidates):
    """
    Proposed rule: among candidates within YEAR_TOLERANCE, take the lowest year_diff;
    if several candidates share that same lowest year_diff, break the tie using
    the highest popularity. If none are within tolerance, fall back to the most
    popular candidate overall (same as current rule).
    """
    within_tolerance = [c for c in candidates if c["year_diff"] is not None and c["year_diff"] <= YEAR_TOLERANCE]

    if within_tolerance:
        best_year_diff = min(c["year_diff"] for c in within_tolerance)
        tied = [c for c in within_tolerance if c["year_diff"] == best_year_diff]
        return max(tied, key=lambda c: c["popularity"])

    if candidates:
        return max(candidates, key=lambda c: c["popularity"])

    return None


def describe(candidate):
    if candidate is None:
        return "no candidate found"
    return (
        f"media_type={candidate['media_type']} id={candidate['id']} "
        f"name={candidate['name']!r} year_diff={candidate['year_diff']} "
        f"popularity={candidate['popularity']}"
    )


def main():
    summary_rows = []

    for title, expected_year in TEST_TITLES:
        print("=" * 90)
        print(f"TITLE: {title!r}  (expected year: {expected_year})")
        print("-" * 90)

        movie_candidates = build_candidates(title, expected_year, "movie")
        print_candidates(movie_candidates, "movie")
        print()

        tv_candidates = build_candidates(title, expected_year, "tv")
        print_candidates(tv_candidates, "tv")
        print()

        all_candidates = movie_candidates + tv_candidates

        current_winner = pick_current_rule(all_candidates)
        proposed_winner = pick_proposed_rule(all_candidates)

        same_result = (
            current_winner is not None
            and proposed_winner is not None
            and current_winner["media_type"] == proposed_winner["media_type"]
            and current_winner["id"] == proposed_winner["id"]
        )

        print(f"Current rule winner:  {describe(current_winner)}")
        print(f"Proposed rule winner: {describe(proposed_winner)}")
        print(f"Same result? {'YES' if same_result else 'NO - DIVERGENCE'}")
        print()

        summary_rows.append({
            "title": f"{title} ({expected_year})",
            "current_media_type": current_winner["media_type"] if current_winner else "none",
            "proposed_media_type": proposed_winner["media_type"] if proposed_winner else "none",
            "same": "yes" if same_result else "NO",
        })

        time.sleep(0.1)  # stay polite with TMDB's rate limit

    print("=" * 90)
    print("SUMMARY")
    print("=" * 90)
    header = f"{'Title':<25} {'Current rule':<15} {'Proposed rule':<15} {'Same?':<10}"
    print(header)
    print("-" * len(header))
    for row in summary_rows:
        print(
            f"{row['title']:<25} {row['current_media_type']:<15} "
            f"{row['proposed_media_type']:<15} {row['same']:<10}"
        )


if __name__ == "__main__":
    main()
