"""
fetch_visuals.py
Since Meta AI has no public API to automate, this module pulls free stock
video clips matching each segment's visual_prompt from Pexels (or Pixabay
as a fallback), oriented for 9:16 vertical.

Get a free API key at:
  - Pexels:  https://www.pexels.com/api/
  - Pixabay: https://pixabay.com/api/docs/
"""

import os
import requests

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
PIXABAY_SEARCH_URL = "https://pixabay.com/api/videos/"


def _search_pexels(query, api_key, per_page=3):
    headers = {"Authorization": api_key}
    params = {"query": query, "orientation": "portrait", "per_page": per_page}
    resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    videos = []
    for video in data.get("videos", []):
        # Pick the highest-res vertical file available
        files = sorted(video["video_files"], key=lambda f: f.get("width", 0), reverse=True)
        if files:
            videos.append(files[0]["link"])
    return videos


def _search_pixabay(query, api_key, per_page=3):
    params = {"key": api_key, "q": query, "per_page": per_page}
    resp = requests.get(PIXABAY_SEARCH_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return [hit["videos"]["medium"]["url"] for hit in data.get("hits", [])]


def download_file(url, out_path):
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


def fetch_visuals_for_script(script, config, out_dir="output/visuals"):
    os.makedirs(out_dir, exist_ok=True)
    provider = config["visuals"]["provider"]
    suffix = config["visuals"]["style_query_suffix"]

    pexels_key = os.environ.get("PEXELS_API_KEY")
    pixabay_key = os.environ.get("PIXABAY_API_KEY")

    visual_paths = {}

    for seg in script["segments"]:
        seg_num = seg["seg"]
        query = f"{seg['visual_prompt']} {suffix}"

        clip_urls = []
        try:
            if provider == "pexels" and pexels_key:
                clip_urls = _search_pexels(query, pexels_key)
            elif pixabay_key:
                clip_urls = _search_pixabay(query, pixabay_key)
        except Exception as e:
            print(f"[fetch_visuals] search failed for segment {seg_num}: {e}")

        if not clip_urls:
            print(f"[fetch_visuals] WARNING: no clip found for segment {seg_num}, query='{query}'")
            visual_paths[seg_num] = None
            continue

        out_path = os.path.join(out_dir, f"seg_{seg_num:02d}.mp4")
        try:
            download_file(clip_urls[0], out_path)
            visual_paths[seg_num] = out_path
            print(f"[fetch_visuals] Downloaded segment {seg_num} visual -> {out_path}")
        except Exception as e:
            print(f"[fetch_visuals] download failed for segment {seg_num}: {e}")
            visual_paths[seg_num] = None

    return visual_paths


if __name__ == "__main__":
    import yaml

    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)
    fake_script = {"segments": [{"seg": 1, "visual_prompt": "satellite orbiting earth at night"}]}
    print(fetch_visuals_for_script(fake_script, cfg))
