"""
tts.py
Generates voiceover audio for each segment using edge-tts. Emotion deltas
widened — the original nudges were too subtle to read as anything but
flat/monotone.
"""

import asyncio
import os
import re
import edge_tts

EMOTION_ADJUSTMENTS = {
    "urgent":        {"rate_delta": 20, "pitch_delta": 8,  "volume_delta": 18},
    "tense":         {"rate_delta": 8,  "pitch_delta": -4, "volume_delta": 5},
    "hushed":        {"rate_delta": -18, "pitch_delta": -12, "volume_delta": -22},
    "authoritative": {"rate_delta": 0,  "pitch_delta": 0,  "volume_delta": 0},
    "alarmed":       {"rate_delta": 25, "pitch_delta": 12, "volume_delta": 20},
    "grave":         {"rate_delta": -14, "pitch_delta": -10, "volume_delta": -8},
    "resolute":      {"rate_delta": 5,  "pitch_delta": 3,  "volume_delta": 8},
}


def _parse_signed_unit(value, unit):
    match = re.match(r"([+-]?\d+)", str(value))
    return int(match.group(1)) if match else 0


def _apply_emotion(base_rate, base_pitch, emotion):
    adj = EMOTION_ADJUSTMENTS.get(emotion, EMOTION_ADJUSTMENTS["authoritative"])

    base_rate_num = _parse_signed_unit(base_rate, "%")
    base_pitch_num = _parse_signed_unit(base_pitch, "Hz")

    new_rate = base_rate_num + adj["rate_delta"]
    new_pitch = base_pitch_num + adj["pitch_delta"]
    new_volume = adj["volume_delta"]

    rate_str = f"{'+' if new_rate >= 0 else ''}{new_rate}%"
    pitch_str = f"{'+' if new_pitch >= 0 else ''}{new_pitch}Hz"
    volume_str = f"{'+' if new_volume >= 0 else ''}{new_volume}%"
    return rate_str, pitch_str, volume_str


async def _generate_one(text, out_path, voice_id, rate, pitch, volume):
    communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch, volume=volume)
    await communicate.save(out_path)


def generate_voiceovers(script, config, out_dir="output/audio"):
    os.makedirs(out_dir, exist_ok=True)
    voice_cfg = config["voice"]
    audio_paths = {}

    for seg in script["segments"]:
        seg_num = seg["seg"]
        emotion = seg.get("emotion", "authoritative")
        rate, pitch, volume = _apply_emotion(voice_cfg["rate"], voice_cfg["pitch"], emotion)

        out_path = os.path.join(out_dir, f"seg_{seg_num:02d}.mp3")
        asyncio.run(
            _generate_one(seg["vo"], out_path, voice_cfg["voice_id"], rate, pitch, volume)
        )
        audio_paths[seg_num] = out_path
        print(f"[tts] Segment {seg_num} ({emotion}): rate={rate} pitch={pitch} volume={volume} -> {out_path}")

    return audio_paths


if __name__ == "__main__":
    import yaml
    import json

    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)

    fake_script = {"segments": [
        {"seg": 1, "vo": "Eight thousand silent watchers orbit quietly above your head right now.", "emotion": "alarmed"},
    ]}
    print(json.dumps(generate_voiceovers(fake_script, cfg), indent=2))
