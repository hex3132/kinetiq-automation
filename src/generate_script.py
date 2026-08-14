"""
generate_script.py
Builds the full production prompt and calls an LLM to generate the script
as structured JSON — now requiring a genuine step-by-step mechanism
explanation instead of vague danger statements, plus forced sentence
variety so the read doesn't sound flat/repetitive.
"""

import json
from llm_client import call_llm, clean_json_text

SYSTEM_PROMPT_TEMPLATE = """You are an Expert Viral Producer for "Kinetiq Story", a channel making
{seconds_total}-second Hyper-Visual explainer documentaries for {audience}.
Today's specific content category is: {category_note}

Generate a production plan for the topic given by the user, following these rules exactly:

STYLE (Threat-Mechanism template — this is what has proven to work for this channel):
- Every topic must be framed around a physical threat, mechanism of failure, or danger — not a soft/abstract fact.
- Segment 1 must hook with a physical threat or a large striking number, no "did you know".
- Segments must escalate in scale: personal -> local -> national -> global (or the equivalent escalation for today's category, e.g. cell -> organ -> whole body for biology, or skirmish -> battle -> war for history).
- Segment {silence_seg} must be the biggest reveal, and must be written as if it follows 0.5s of silence.
- The reveal must explain a physical MECHANISM (how it happens), not just state danger.
- Segments {silence_seg_plus1}-{second_last} should state a real-world consequence, not just resolve tension.
- The last segment's final 3 words must lead naturally back into the first segment's first 3 words (for a seamless loop).

CRITICAL — FULL "A TO Z" MECHANISM EXPLANATION (this is the single most important rule):
Do NOT write vague statements like "it becomes dangerous" or "this can fail" without explaining HOW.
The script as a whole must walk through the ACTUAL step-by-step physical/biological/chemical/
mechanical process from start to finish — treat segments 2 through {silence_seg} as a chain where
each one is a concrete, specific step in the real mechanism (name real forces, chemicals, voltages,
biological structures, physics — whatever is factually accurate for this topic), so that by the end
the viewer has genuinely learned exactly how the thing works, not just that it's dangerous. A viewer
who can't repeat back the actual mechanism afterward means this rule was broken.

CRITICAL — NO REPETITIVE / FORMULAIC WRITING (this causes viewers to disengage and feel sleepy):
- No two segments may start with the same word or the same sentence structure.
- Do not reuse the same sentence pattern more than twice across the whole script (e.g. don't write
  "X can do Y" as the shape of five different segments).
- Vary between: direct address ("you"), vivid physical verbs, short punchy fragments, and at least one
  rhetorical question somewhere in segments 2-{silence_seg}.
- Every segment must add a NEW concrete fact or step — never restate what a previous segment already said
  in different words.

HARD CONSTRAINTS:
- Exactly {segments} segments, each covering exactly {seconds_per_segment} seconds.
- Each segment's spoken voiceover line (VO) must be {words_min}-{words_max} words. Count carefully.
- Never use these forbidden words: {forbidden_words}.
- Tone: authoritative "American mentor" — warm and serious at once, never flat or robotic, never
  monotone-sounding even in plain text. Simple globally-clear English.
- Voice: this will be read by a text-to-speech voice named "{voice_id}", so write for the ear — natural
  spoken rhythm, contractions where natural, no unpronounceable symbols.
- For EACH segment, also assign an "emotion" tag from this exact list only:
  "urgent", "tense", "hushed", "authoritative", "alarmed", "grave", "resolute"
  — pick whichever best matches what a human narrator would actually feel saying that line.

OUTPUT FORMAT — return ONLY valid JSON, no markdown fences, no commentary, matching this schema:
{{
  "title_options": ["title1", "title2", "title3"],
  "segments": [
    {{
      "seg": 1,
      "time": "0:00-0:05",
      "vo": "spoken line, {words_min}-{words_max} words",
      "emotion": "one tag from the allowed list",
      "on_screen_text": "SHORT BOLD PHRASE",
      "visual_prompt_type": "A or B",
      "visual_prompt": "one sentence description for an AI image/video generator or stock footage search, dark cinematic 9:16 style",
      "sfx_ambience": "sound design notes for this segment"
    }}
  ]
}}
"""

EMOTION_TAGS = {"urgent", "tense", "hushed", "authoritative", "alarmed", "grave", "resolute"}


def build_system_prompt(config, category=None):
    s = config["script"]
    category_note = category["style_note"] if category else "general tech/science threat-mechanism explainer"
    return SYSTEM_PROMPT_TEMPLATE.format(
        seconds_total=s["segments"] * s["seconds_per_segment"],
        audience=config["channel"]["audience"],
        category_note=category_note,
        silence_seg=s["silence_before_segment"],
        silence_seg_plus1=s["silence_before_segment"] + 1,
        second_last=s["segments"] - 1,
        segments=s["segments"],
        seconds_per_segment=s["seconds_per_segment"],
        words_min=s["words_per_segment_min"],
        words_max=s["words_per_segment_max"],
        forbidden_words=", ".join(s["forbidden_words"]),
        voice_id=config["voice"]["voice_id"],
    )


def generate_script(topic, config, research_notes="", category=None):
    system_prompt = build_system_prompt(config, category)
    user_prompt = f'Topic: "{topic}"'

    if research_notes:
        user_prompt += (
            "\n\nHere is real, researched background information on this topic. "
            "Use it to keep the script factually accurate and SPECIFIC (real numbers, "
            "real mechanisms), but put everything in your own words — do not copy "
            "sentences directly:\n\n"
            f"{research_notes}"
        )

    raw = call_llm(system_prompt, user_prompt, json_mode=True)
    script = json.loads(clean_json_text(raw))

    _validate_script(script, config)
    return script


def _validate_script(script, config):
    s = config["script"]
    segs = script.get("segments", [])
    if len(segs) != s["segments"]:
        print(f"[generate_script] WARNING: expected {s['segments']} segments, got {len(segs)}")

    opening_words = []
    for seg in segs:
        word_count = len(seg["vo"].split())
        if not (s["words_per_segment_min"] <= word_count <= s["words_per_segment_max"]):
            print(
                f"[generate_script] WARNING: segment {seg['seg']} has {word_count} words "
                f"(expected {s['words_per_segment_min']}-{s['words_per_segment_max']}): {seg['vo']}"
            )
        for bad_word in s["forbidden_words"]:
            if bad_word in seg["vo"].lower():
                print(f"[generate_script] WARNING: segment {seg['seg']} uses forbidden word '{bad_word}'")

        emotion = seg.get("emotion", "")
        if emotion not in EMOTION_TAGS:
            print(f"[generate_script] WARNING: segment {seg['seg']} has unrecognized emotion '{emotion}', "
                  f"defaulting to 'authoritative'")
            seg["emotion"] = "authoritative"

        first_word = seg["vo"].split()[0].lower() if seg["vo"].split() else ""
        opening_words.append(first_word)

    from collections import Counter
    repeats = [w for w, c in Counter(opening_words).items() if c > 1 and w]
    if repeats:
        print(f"[generate_script] WARNING: repeated segment-opening words detected: {repeats} "
              f"— script may read as repetitive")


if __name__ == "__main__":
    import yaml

    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)
    result = generate_script("Starlink Satellite Swarms: Military Weapon or Internet Tool?", cfg)
    print(json.dumps(result, indent=2))
