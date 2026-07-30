"""
generate_flow_prompts.py
Generates ready-to-paste JSON prompts for Google Flow (Veo 3), following
your exact "Expert AI Video Producer" template — one JSON block per
10-second chunk of the video (Flow's own generation limit).

IMPORTANT — read this before relying on it:
  - Google Flow has NO public API for a script to call automatically.
    It's a browser product tied to a Google AI Pro/Ultra subscription
    (paid beyond a small free monthly allowance). There is no safe or
    free way for this pipeline to submit prompts into Flow for you.
  - Browser-automation tools exist that fake clicks inside Flow, but
    that means putting your personal Google login into a public GitHub
    Actions log — a real account-security risk — for a product you'd
    still be paying for. That's why this script does NOT attempt that:
    it generates the exact JSON prompts, you paste them into Flow
    yourself, in your own browser, under your own login.
  - Each chunk is grounded in your ACTUAL script's VO/on-screen text for
    that time window, so the generated scene will genuinely match what
    the voiceover is saying at that moment (not a generic guess).
  - All 10 chunks are generated in a SINGLE LLM call so the model can
    keep the main subject, color palette, and style consistent across
    the whole video — copy them into Flow in order.
"""

import json
from llm_client import call_llm, clean_json_text

FLOW_SYSTEM_PROMPT_TEMPLATE = """Act as an expert AI Video Producer and Prompt Engineer for advanced 3D video generation models (Google Flow / Veo 3).

You will be given the topic "{topic}" and a full narration script broken into {num_chunks} sequential 10-second time windows. For EACH time window, generate one detailed, structured JSON prompt for a high-quality 3D explainer scene, optimized for 9:16 vertical format.

Strictly follow these rules for the ENTIRE output:
1. Output ONLY a valid JSON array containing exactly {num_chunks} objects — no markdown fences, no commentary before or after.
2. Each object represents exactly 10 seconds, structured into exactly 3 rapid, highly detailed scene sequences that together explain that window's content within exactly 10 seconds.
3. Keep explanations SHORT, SIMPLE, and VISUAL — strip jargon, focus on the most striking, easy-to-grasp visual concepts.
4. Visual tone: futuristic, highly detailed, cinematic — fast-paced high-end science documentary mixed with Pixar-quality CGI.
5. CONSISTENCY IS CRITICAL: use the EXACT SAME "main_subject.type" description and the EXACT SAME "visual_style.colors" hex values across ALL {num_chunks} objects, so the finished video looks like one continuous production, not disjointed clips. Only vary pose/animation/camera per chunk.
6. Each chunk's scene_sequence and text_overlay MUST accurately depict and match the specific narration content given for that chunk below — this is the single most important rule. A Flow-generated scene that doesn't match its narration is a failed output.

Use this exact JSON object structure for every chunk in the array:
{{
  "video_type": "cinematic educational 3D [insert niche] animation",
  "topic": "{topic} Explained Simply",
  "duration": "10 seconds",
  "aspect_ratio": "9:16",
  "style": "hyper realistic CGI visualization",
  "quality": "ultra detailed 4K",
  "camera_style": "rapid cinematic dynamic camera movements",
  "environment": {{
    "background": "dark futuristic educational environment",
    "lighting": "vibrant volumetric glows with realistic subject highlights",
    "atmosphere": "Scientific documentary meets high-end cinematic animation"
  }},
  "main_subject": {{
    "type": "[describe the main model or object being shown — KEEP IDENTICAL across all chunks]",
    "pose": "[starting pose or framing for THIS chunk]",
    "visibility": "[special visibility details like transparency, glowing parts, or cross-sections for THIS chunk]"
  }},
  "scene_sequence": [
    {{
      "scene": 1,
      "title": "[Simple Scene Title]",
      "duration": "[e.g., 3 seconds]",
      "animation": "[detailed description of what moves, matching this chunk's narration]",
      "camera": "[camera shot type, e.g., macro close-up, fast zoom-in]",
      "effects": ["[visual effect 1]", "[visual effect 2]"],
      "text_overlay": "[Very short, punchy text matching this chunk's on-screen text]"
    }}
  ],
  "visual_style": {{
    "colors": ["[Hex Color 1 — KEEP IDENTICAL across all chunks]", "[Hex Color 2]", "[Hex Color 3]"],
    "graphics": "interactive infographic style",
    "motion_graphics": true,
    "floating_labels": true,
    "animated_arrows": true
  }},
  "render_keywords": [
    "Pixar quality CGI",
    "scientific documentary visuals",
    "hyper realistic textures",
    "cinematic educational graphics",
    "3D animation",
    "fast-paced fluid motion",
    "easy to understand visual breakdown"
  ]
}}
"""


def _group_into_chunks(script, seconds_per_segment, chunk_seconds=10):
    segments_per_chunk = chunk_seconds // seconds_per_segment
    segs = script["segments"]
    chunks = [segs[i:i + segments_per_chunk] for i in range(0, len(segs), segments_per_chunk)]
    return chunks


def _describe_chunk_for_grounding(chunk_index, chunk_segments):
    lines = [f"--- Chunk {chunk_index + 1} (narration content to match visually) ---"]
    for seg in chunk_segments:
        lines.append(
            f"Seg {seg['seg']} [{seg.get('emotion', 'authoritative')}]: "
            f'VO: "{seg["vo"]}" | On-screen text: "{seg["on_screen_text"]}" | '
            f'Intended visual: {seg["visual_prompt"]}'
        )
    return "\n".join(lines)


def generate_flow_prompts(topic, script, config):
    seconds_per_segment = config["script"]["seconds_per_segment"]
    chunks = _group_into_chunks(script, seconds_per_segment, chunk_seconds=10)
    num_chunks = len(chunks)

    system_prompt = FLOW_SYSTEM_PROMPT_TEMPLATE.format(topic=topic, num_chunks=num_chunks)

    grounding_blocks = [
        _describe_chunk_for_grounding(i, chunk) for i, chunk in enumerate(chunks)
    ]
    user_prompt = (
        f'Topic: "{topic}"\n\n'
        "Here is the actual narration script, split into the time windows you must match:\n\n"
        + "\n\n".join(grounding_blocks)
    )

    raw = call_llm(system_prompt, user_prompt, json_mode=True)
    flow_prompts = json.loads(clean_json_text(raw))

    if not isinstance(flow_prompts, list):
        # Some models wrap it in a key despite instructions — try to recover
        flow_prompts = flow_prompts.get("prompts") or flow_prompts.get("chunks") or [flow_prompts]

    if len(flow_prompts) != num_chunks:
        print(f"[generate_flow_prompts] WARNING: expected {num_chunks} chunks, got {len(flow_prompts)}")

    return flow_prompts


def write_flow_prompts_file(flow_prompts, out_path="output/google_flow_prompts.txt"):
    lines = [
        "GOOGLE FLOW PROMPTS — paste each block below into Google Flow, ONE AT A TIME, in order.",
        "Each block generates a 10-second clip. Stitch the clips together in the order shown.",
        "Note: Google Flow (Veo 3) requires a Google account and, beyond the free monthly",
        "allowance, a paid Google AI Pro/Ultra plan — this file does not submit anything for you.",
        "=" * 70,
    ]
    for i, prompt in enumerate(flow_prompts, start=1):
        lines.append(f"\n--- PROMPT {i} of {len(flow_prompts)} (seconds {(i-1)*10}-{i*10}) ---\n")
        lines.append(json.dumps(prompt, indent=2))
    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    print(f"[generate_flow_prompts] Wrote {len(flow_prompts)} prompts -> {out_path}")
    return out_path


if __name__ == "__main__":
    print("Run via main.py — this module expects a generated script.")
