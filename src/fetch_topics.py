"""
fetch_topics.py
Rotates through topic categories by day of week (see config.yaml's
topic_rotation), pulls candidate topics from that day's category-specific
subreddits (via Reddit's free OAuth API — optional, see below) plus
Hacker News and GDELT (both fully keyless, no account/signup needed at
all), scores them, then hands the top candidates to an LLM to pick and
REFRAME the single most viral-potential one into a punchy, on-theme title.

Reddit needs a free developer app (reddit.com/prefs/apps), which some
accounts/regions have trouble creating. That's fine — Reddit is entirely
OPTIONAL here: if REDDIT_CLIENT_ID/SECRET aren't set, or Reddit fails for
any reason, the pipeline just uses Hacker News + GDELT instead, no
account or API key required for either.
"""

import os
import random
import urllib.parse
from datetime import datetime, timedelta, timezone

import requests
import yaml

from fetch_channel_history import get_channel_derived_keywords
from llm_client import call_llm

HEADERS = {"User-Agent": "kinetiq-story-bot/1.0 by u/kinetiq_automation"}

REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_API_BASE = "https://oauth.reddit.com"

HN_SOURCE = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"

GDELT_SOURCE = "https://api.gdeltproject.org/api/v2/doc/doc"

BANGLADESH_OFFSET = timedelta(hours=6)

FALLBACK_TOPIC_POOL = [
    "Why Do Satellites Suddenly Fall Out of Orbit?",
    "The Hidden Kill Switch Inside Every Smartphone",
    "How One Wrong Command Could Blackout a City",
    "The Silent Failure Mode Hiding in Every Jet Engine",
    "What Happens When a Nuclear Reactor Loses Coolant",
    "The Structural Flaw That Sank an 'Unsinkable' Ship",
    "How Hackers Could Physically Destroy a Power Grid",
    "The Chain Reaction That Could Fill Orbit With Debris",
]


def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_todays_category(config):
    rotation = config.get("topic_rotation", {})
    categories = rotation.get("categories", [])
    if not rotation.get("enabled", False) or not categories:
        return None

    bd_now = datetime.now(timezone.utc) + BANGLADESH_OFFSET
    day_index = bd_now.timetuple().tm_yday
    category = categories[day_index % len(categories)]
    print(f"[fetch_topics] Today's category: {category['name']}")
    return category


def _get_reddit_token():
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("[fetch_topics] No REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET set — skipping Reddit")
        return None
    try:
        resp = requests.post(
            REDDIT_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]
    except Exception as e:
        print(f"[fetch_topics] Reddit OAuth token fetch failed: {e}")
        return None


def fetch_reddit_titles(subreddits):
    token = _get_reddit_token()
    if not token:
        return []

    titles = []
    auth_headers = {**HEADERS, "Authorization": f"bearer {token}"}
    for subreddit in subreddits:
        url = f"{REDDIT_API_BASE}/r/{subreddit}/top?limit=20&t=day"
        try:
            resp = requests.get(url, headers=auth_headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            for post in data["data"]["children"]:
                titles.append(post["data"]["title"])
        except Exception as e:
            print(f"[fetch_topics] Reddit fetch failed for r/{subreddit}: {e}")
    return titles


def fetch_hn_titles(limit=15):
    titles = []
    try:
        resp = requests.get(HN_SOURCE, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        ids = resp.json()[:limit]
        for story_id in ids:
            item_resp = requests.get(HN_ITEM.format(story_id), headers=HEADERS, timeout=10)
            if item_resp.ok:
                title = item_resp.json().get("title")
                if title:
                    titles.append(title)
    except Exception as e:
        print(f"[fetch_topics] HN fetch failed: {e}")
    return titles


def fetch_gdelt_titles(category, limit=20):
    if not category:
        query = "technology OR science"
    else:
        query = " OR ".join(category["keywords_boost"][:8])

    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": str(limit),
        "format": "json",
        "sort": "hybridrel",
        "timespan": "1d",
    }
    url = f"{GDELT_SOURCE}?{urllib.parse.urlencode(params)}"

    titles = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for article in data.get("articles", []):
            title = article.get("title")
            if title:
                titles.append(title)
    except Exception as e:
        print(f"[fetch_topics] GDELT fetch failed: {e}")
    return titles


def score_topic(title, config, category, channel_keywords):
    title_lower = title.lower()
    score = 0

    boost_words = category["keywords_boost"] if category else config["topic_filter"].get("keywords_boost", [])
    for word in boost_words:
        if word in title_lower:
            score += 3
    for word in config["topic_filter"].get("keywords_avoid", []):
        if word in title_lower:
            score -= 3
    for word in channel_keywords:
        if word in title_lower:
            score += 4
    return score


def get_channel_keywords(config):
    if not config["topic_filter"].get("use_channel_history", False):
        return []
    channel_id = config["channel"].get("youtube_channel_id")
    if not channel_id or not os.environ.get("YOUTUBE_API_KEY"):
        print("[fetch_topics] Skipping channel-history boost — no channel ID or YOUTUBE_API_KEY set")
        return []
    return get_channel_derived_keywords(channel_id)


REFRAME_SYSTEM_PROMPT = """You are a viral video topic strategist for "Kinetiq Story". Today's
content category is: {category_style_note}

Every topic must center on a physical danger, failure mode, or mechanism
— something that could hurt, destroy, kill, or malfunction — explained
through a specific real mechanism, not vague statements. Stay strictly
within today's category above.

You will be given a list of candidate topics/headlines. Pick the ONE
with the strongest viral potential for this category and style, then
REWRITE it as a sharp, specific, curiosity-driving title — do not just
copy the raw headline. The rewritten title should:
- Fit today's category exactly
- Imply a physical threat, failure, or hidden danger
- Be specific enough to promise a real mechanism will be explained
- Create an open loop (the viewer needs to know what happens)
- Be 6-12 words

Output ONLY the single rewritten title as plain text. No quotes, no
explanation, no numbering — just the title itself.
"""


def reframe_topic_for_virality(top_candidates, category):
    style_note = category["style_note"] if category else "physical danger, failure, or mechanism, any tech/science topic"
    system_prompt = REFRAME_SYSTEM_PROMPT.format(category_style_note=style_note)
    candidates_text = "\n".join(f"- {t}" for t in top_candidates)
    try:
        raw = call_llm(system_prompt, candidates_text, json_mode=False)
        reframed = raw.strip().strip('"')
        if reframed:
            print(f"[fetch_topics] Reframed topic: {reframed}")
            return reframed
    except Exception as e:
        print(f"[fetch_topics] Topic reframing failed, using top raw candidate instead: {e}")
    return top_candidates[0]


def get_best_topic(config_path="config.yaml"):
    config = load_config(config_path)
    category = get_todays_category(config)

    subreddits = category["subreddits"] if category else ["technology", "science", "space"]
    all_titles = fetch_reddit_titles(subreddits) + fetch_hn_titles() + fetch_gdelt_titles(category)

    if not all_titles:
        topic = random.choice(FALLBACK_TOPIC_POOL)
        print(f"[fetch_topics] Both sources failed — using fallback pool topic: {topic}")
        return topic

    channel_keywords = get_channel_keywords(config)

    scored = [(score_topic(t, config, category, channel_keywords), t) for t in all_titles]
    scored.sort(key=lambda x: x[0], reverse=True)

    top_candidates = [title for _, title in scored[:10]]
    print(f"[fetch_topics] Top candidates: {top_candidates}")

    best_topic = reframe_topic_for_virality(top_candidates, category)
    return best_topic


if __name__ == "__main__":
    print(get_best_topic())
