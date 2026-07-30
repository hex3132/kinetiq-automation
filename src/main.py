"""
main.py
Orchestrates the full daily pipeline:
  1. Pick a topic (Reddit/HN, scored by channel history + Threat-Mechanism filter)
  2. Research the topic (Wikipedia, free)
  3. Generate the 20-segment script (free LLM API), with per-segment emotion tags
  4. Generate humanized voiceovers (edge-tts, free, emotion-modulated)
  5. Generate visuals — AI-generated images (Pollinations, free) by default,
     or stock footage (Pexels/Pixabay) if configured
  6. Assemble the final video (moviepy, local/free)
  7. Generate Google Flow prompt set (manual-paste, optional higher-quality upgrade path)
  8. Generate platform metadata (YouTube/TikTok/Instagram/Facebook)
  9. Upload video + script + Flow prompts + platform metadata to Google Drive

Run manually with:  python src/main.py
Run automatically every morning via .github/workflows/daily-video.yml
"""

import json
import os
import sys
import traceback
import yaml

from fetch_topics import get_best_topic
from research_topic import research_topic
from generate_script import generate_script
from tts import generate_voiceovers
from generate_ai_visuals import generate_ai_visuals_for_script
from fetch_visuals import fetch_visuals_for_script
from assemble_video import assemble_video
from generate_flow_prompts import generate_flow_prompts, write_flow_prompts_file
from generate_platform_metadata import generate_platform_metadata, write_platform_metadata_file
from upload_drive import upload_to_drive


def main():
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    os.makedirs("output", exist_ok=True)

    print("=== Step 1: Picking topic (scored against channel history) ===")
    topic = get_best_topic()

    print("=== Step 2: Researching topic ===")
    research_notes = research_topic(topic)

    print("=== Step 3: Generating script ===")
    script = generate_script(topic, config, research_notes)
    with open("output/script.json", "w") as f:
        json.dump(script, f, indent=2)

    print("=== Step 4: Generating humanized voiceovers ===")
    audio_paths = generate_voiceovers(script, config)

    print("=== Step 5: Generating visuals ===")
    if config["visuals"]["provider"] == "ai":
        visual_paths = generate_ai_visuals_for_script(script, config)
    else:
        visual_paths = fetch_visuals_for_script(script, config)

    print("=== Step 6: Assembling video ===")
    video_path = assemble_video(script, visual_paths, audio_paths, config)

    print("=== Step 7: Generating Google Flow prompt set (optional manual upgrade) ===")
    try:
        flow_prompts = generate_flow_prompts(topic, script, config)
        write_flow_prompts_file(flow_prompts)
    except Exception as e:
        print(f"[main] Flow prompt generation failed (non-fatal, skipping): {e}")

    print("=== Step 8: Generating platform metadata ===")
    try:
        platform_metadata = generate_platform_metadata(topic, script)
        write_platform_metadata_file(platform_metadata)
    except Exception as e:
        print(f"[main] Platform metadata generation failed (non-fatal, skipping): {e}")

    print("=== Step 9: Uploading to Google Drive ===")
    upload_to_drive(video_path, script, config)

    print("=== DONE ===")
    print(f"Topic: {topic}")
    print(f"Video: {video_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("[main] Pipeline failed:")
        traceback.print_exc()
        sys.exit(1)
