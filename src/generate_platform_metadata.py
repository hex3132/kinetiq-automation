"""
generate_platform_metadata.py
Generates platform-optimized title + description + hashtags for YouTube,
TikTok, Instagram, and Facebook from the finished script — saved as one
doc in Drive alongside the video, so you have ready-to-paste text for
every platform instead of writing it manually each time.
"""

import json
from llm_client import call_llm, clean_json_text

METADATA_SYSTEM_PROMPT = """You are a social media copywriter for "Kinetiq Story", a tech/science
explainer channel for CSE students and tech enthusiasts, using a
"Threat-Mechanism" style (physical danger + real mechanism + stakes).

Given a video's topic, title options, and full script, write platform-
optimized upload metadata for FOUR platforms: YouTube, TikTok, Instagram,
and Facebook. Each platform has different norms:
- YouTube: negative-curiosity title, keyword-rich description (2-3
  sentences), 10-15 relevant tags.
- TikTok: short punchy caption (under 150 characters), 4-6 hashtags mixing
  broad + niche.
- Instagram: slightly longer caption with a hook line + 1-2 sentences,
  8-12 hashtags.
- Facebook: conversational caption that invites comments/shares, 2-3
  sentences, minimal or no hashtags.

Output ONLY valid JSON, no markdown fences, no commentary, matching this schema:
{
  "youtube": {"title": "...", "description": "...", "tags": ["...", "..."]},
  "tiktok": {"caption": "...", "hashtags": ["#...", "#..."]},
  "instagram": {"caption": "...", "hashtags": ["#...", "#..."]},
  "facebook": {"caption": "..."}
}
"""


def generate_platform_metadata(topic, script):
    user_prompt = (
        f'Topic: "{topic}"\n\n'
        f'Title options already considered: {json.dumps(script.get("title_options", []))}\n\n'
        "Full script segments (VO + on-screen text):\n" +
        "\n".join(f"- {seg['vo']} | on-screen: {seg['on_screen_text']}" for seg in script["segments"])
    )
    raw = call_llm(METADATA_SYSTEM_PROMPT, user_prompt, json_mode=True)
    return json.loads(clean_json_text(raw))


def write_platform_metadata_file(metadata, out_path="output/platform_metadata.txt"):
    lines = ["PLATFORM UPLOAD METADATA — ready to copy-paste per platform", "=" * 60]

    yt = metadata.get("youtube", {})
    lines += [
        "\n--- YOUTUBE ---",
        f"Title: {yt.get('title', '')}",
        f"Description: {yt.get('description', '')}",
        f"Tags: {', '.join(yt.get('tags', []))}",
    ]

    tt = metadata.get("tiktok", {})
    lines += [
        "\n--- TIKTOK ---",
        f"Caption: {tt.get('caption', '')}",
        f"Hashtags: {' '.join(tt.get('hashtags', []))}",
    ]

    ig = metadata.get("instagram", {})
    lines += [
        "\n--- INSTAGRAM ---",
        f"Caption: {ig.get('caption', '')}",
        f"Hashtags: {' '.join(ig.get('hashtags', []))}",
    ]

    fb = metadata.get("facebook", {})
    lines += [
        "\n--- FACEBOOK ---",
        f"Caption: {fb.get('caption', '')}",
    ]

    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    print(f"[generate_platform_metadata] Wrote platform metadata -> {out_path}")
    return out_path


if __name__ == "__main__":
    print("Run via main.py — this module expects a generated script.")
