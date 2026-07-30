"""
fetch_topics.py
Pulls candidate topics from free, keyless sources (Reddit JSON endpoints,
Hacker News API) and scores them against the channel's topic filter so the
highest-scoring "threat mechanism" style topic gets picked first.
"""

import os
import requests
import yaml

from fetch_channel_history import get_channel_derived_keywords

HEADERS = {"User-Agent": "kinetiq-story-bot/1.0"}

REDDIT_SOURCES = [
    "https://www.reddit.com/r/technology/top/.json?limit=25&t=day",
    "https://www.reddit.com/r/science/top/.json?limit=25&t=day",
    "https://www.reddit.com/r/space/top/.json?limit=25&t=day",
]

HN_SOURCE = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"


def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def fetch_reddit_titles():
    titles = []
    for url in REDDIT_SOURCES:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            for post in data["data"]["children"]:
                titles.append(post["data"]["title"])
        except Exception as e:
            print(f"[fetch_topics] Reddit fetch failed for {url}: {e}")
    return titles


def fetch_hn_titles(limit=25):
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


def score_topic(title, config, channel_keywords):
    title_lower = title.lower()
    score = 0
    for word in config["topic_filter"]["keywords_boost"]:
        if word in title_lower:
            score += 3
    for word in config["topic_filter"]["keywords_avoid"]:
        if word in title_lower:
            score -= 3
    # Extra weight for words that have historically performed on THIS channel
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


def get_best_topic(config_path="config.yaml"):
    config = load_config(config_path)
    all_titles = fetch_reddit_titles() + fetch_hn_titles()

    if not all_titles:
        # Fallback so the pipeline never hard-fails if both sources are down
        return "Why Do Satellites Suddenly Fall Out of Orbit?"

    channel_keywords = get_channel_keywords(config)

    scored = [(score_topic(t, config, channel_keywords), t) for t in all_titles]
    scored.sort(key=lambda x: x[0], reverse=True)

    best_score, best_title = scored[0]
    print(f"[fetch_topics] Picked topic (score {best_score}): {best_title}")
    return best_title


if __name__ == "__main__":
    print(get_best_topic())
