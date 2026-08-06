"""
generate_ai_visuals.py
Generates an AI image per segment using Pollinations.ai — a free,
keyless image-generation API — as a closer match to Kinetiq Story's
original AI-art visual style than stock footage.

Important honesty note: Pollinations returns STATIC images, not video
clips. There is no free API that generates short AI video clips reliably
today. To keep things feeling "kinetic," assemble_video.py applies a
Ken Burns (slow zoom/pan) effect to each image instead of showing a
plain still frame.

Quality/consistency will vary more than a paid model like Midjourney or
Meta AI would give you — treat this as a free first draft, and swap in
manually-made visuals for segments that come out looking off.
"""

import os
import time
import urllib.parse
import requests

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"


def _build_url(prompt, width, height, seed=None):
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"{POLLINATIONS_BASE}/{encoded_prompt}?width={width}&height={height}&nologo=true"
    if seed is not None:
        url += f"&seed={seed}"
    return url


def generate_image(prompt, out_path, width=1080, height=1920, seed=None, retries=2):
    url = _build_url(prompt, width, height, seed)
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=45)
            resp.raise_for_status()
            with open(out_path, "wb") as f:
                f.write(resp.content)
            return out_path
        except Exception as e:
            print(f"[generate_ai_visuals] attempt {attempt}/{retries} failed for prompt "
                  f"'{prompt[:60]}...': {e}")
            time.sleep(3)
    return None


def generate_ai_visuals_for_script(script, config, out_dir="output/visuals"):
    os.makedirs(out_dir, exist_ok=True)
    style_suffix = config["visuals"].get("style_query_suffix", "photorealistic 8K cinematic dark")

    image_paths = {}
    for seg in script["segments"]:
        seg_num = seg["seg"]
        full_prompt = f"{seg['visual_prompt']}, {style_suffix}, vertical 9:16 composition"
        out_path = os.path.join(out_dir, f"seg_{seg_num:02d}.png")

        result = generate_image(full_prompt, out_path, seed=seg_num)
        if result:
            image_paths[seg_num] = result
            print(f"[generate_ai_visuals] Generated segment {seg_num} -> {result}")
        else:
            print(f"[generate_ai_visuals] WARNING: could not generate image for segment {seg_num}, "
                  f"will fall back to a plain background")
            image_paths[seg_num] = None

    return image_paths


if __name__ == "__main__":
    import yaml
    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)
    fake_script = {"segments": [{"seg": 1, "visual_prompt": "satellite orbiting Earth at night, holographic HUD overlay"}]}
    print(generate_ai_visuals_for_script(fake_script, cfg))
