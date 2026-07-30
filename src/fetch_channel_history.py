"""
fetch_channel_history.py
Pulls YOUR channel's own past video titles + view/like counts via the free
YouTube Data API (read-only, API-key auth, no OAuth login needed), so the
topic scorer learns from what has actually performed on Kinetiq Story
instead of only guessing from generic trending keywords.
"""

import os
import re
import requests
from collections import Counter

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "in", "on", "to", "is", "are",
    "how", "what", "why", "this", "that", "for", "your", "you", "it",
    "its", "vs", "with", "was", "never", "explained",
}


def _get(endpoint, params):
    params = dict(params)
    params["key"] = os.environ["YOUTUBE_API_KEY"]
    resp = requests.get(f"{YOUTUBE_API_BASE}/{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_uploads_playlist_id(channel_id):
    data = _get("channels", {"part": "contentDetails", "id": channel_id})
    items = data.get("items", [])
    if not items:
        raise ValueError(f"No channel found for ID '{channel_id}' — check config.yaml")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def get_all_video_ids(uploads_playlist_id, max_videos=50):
    video_ids = []
    page_token = None
    while len(video_ids) < max_videos:
        params = {"part": "contentDetails", "playlistId": uploads_playlist_id, "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token
        data = _get("playlistItems", params)
        for item in data.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return video_ids[:max_videos]


def get_video_stats(video_ids):
    results = []
    for i in range(0, len(video_ids), 50):  # API allows max 50 IDs per call
        batch = video_ids[i:i + 50]
        data = _get("videos", {"part": "snippet,statistics", "id": ",".join(batch)})
        for item in data.get("items", []):
            results.append({
                "title": item["snippet"]["title"],
                "views": int(item["statistics"].get("viewCount", 0)),
                "likes": int(item["statistics"].get("likeCount", 0)),
            })
    return results


def extract_keywords(title):
    words = re.findall(r"[a-zA-Z]+", title.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 3]


def get_channel_derived_keywords(channel_id, top_n=15):
    """
    Returns keywords weighted toward your ABOVE-AVERAGE performing videos
    (by view count) — words your audience has actually responded to,
    not a static guess list.
    """
    try:
        uploads_id = get_uploads_playlist_id(channel_id)
        video_ids = get_all_video_ids(uploads_id)
        videos = get_video_stats(video_ids)
    except Exception as e:
        print(f"[fetch_channel_history] Could not fetch channel history: {e}")
        return []

    if not videos:
        return []

    avg_views = sum(v["views"] for v in videos) / len(videos)
    counter = Counter()
    for v in videos:
        weight = 2 if v["views"] >= avg_views else 1
        for kw in extract_keywords(v["title"]):
            counter[kw] += weight

    top_keywords = [kw for kw, _ in counter.most_common(top_n)]
    print(f"[fetch_channel_history] Channel-derived boost keywords: {top_keywords}")
    return top_keywords


if __name__ == "__main__":
    import yaml
    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)
    cid = cfg["channel"].get("youtube_channel_id")
    print(get_channel_derived_keywords(cid) if cid else "No youtube_channel_id set in config.yaml")
