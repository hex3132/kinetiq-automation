"""
research_topic.py
Once a topic is picked, this pulls real background facts from a free,
keyless source (Wikipedia's REST API) so script generation is grounded in
actual facts instead of the LLM inventing plausible-sounding details.
"""

import requests

WIKI_SEARCH = "https://en.wikipedia.org/w/api.php"
WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
HEADERS = {"User-Agent": "kinetiq-story-bot/1.0 (personal free automation project)"}


def _wiki_search_title(query):
    params = {"action": "opensearch", "search": query, "limit": 1, "namespace": 0, "format": "json"}
    resp = requests.get(WIKI_SEARCH, params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    titles = resp.json()[1]
    return titles[0] if titles else None


def _wiki_summary(title):
    resp = requests.get(WIKI_SUMMARY.format(title.replace(" ", "_")), headers=HEADERS, timeout=10)
    if resp.ok:
        return resp.json().get("extract", "")
    return ""


def research_topic(topic):
    notes = []
    try:
        title = _wiki_search_title(topic)
        if title:
            summary = _wiki_summary(title)
            if summary:
                notes.append(f"Background on '{title}': {summary}")
    except Exception as e:
        print(f"[research_topic] Wikipedia lookup failed: {e}")

    research_notes = "\n\n".join(notes)
    if research_notes:
        print(f"[research_topic] Found grounding research ({len(research_notes)} chars)")
    else:
        print("[research_topic] No grounding research found — script will rely on general knowledge")
    return research_notes


if __name__ == "__main__":
    print(research_topic("Starlink satellite constellation"))
