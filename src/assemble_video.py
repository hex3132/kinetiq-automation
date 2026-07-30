"""
assemble_video.py
Stitches per-segment visuals + voiceovers + a continuous brown-noise/drone
ambience track + bold on-screen text into one finished 9:16 video, using
moviepy (free, local, no API needed).

If a segment's visual failed to download, a plain dark placeholder clip is
used instead so the pipeline never crashes on one missing asset — check
the run log / GitHub Actions summary for which segments need a manual
visual swap.
"""

import os
from moviepy.editor import (
    VideoFileClip,
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
    TextClip,
    ColorClip,
    concatenate_videoclips,
    afx,
)

FRAME_SIZE = (1080, 1920)  # 9:16 vertical
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def _ken_burns_clip(image_path, duration, zoom_amount=0.12):
    """
    Turns a static AI-generated image into a slow zoom/pan clip so it
    doesn't feel like a plain still frame. Starts slightly oversized so
    there's room to zoom without exposing edges.
    """
    base = ImageClip(image_path).set_duration(duration)
    # Fit to frame first, oversized by zoom_amount for headroom
    base = base.resize(height=int(FRAME_SIZE[1] * (1 + zoom_amount)))
    if base.w < FRAME_SIZE[0]:
        base = base.resize(width=FRAME_SIZE[0] * (1 + zoom_amount))

    def zoom(t):
        return 1 + (zoom_amount * (t / duration))

    zoomed = base.resize(zoom)
    zoomed = zoomed.set_position(("center", "center"))
    # Composite onto the target frame size, center-cropping any overhang
    return CompositeVideoClip([zoomed], size=FRAME_SIZE).set_duration(duration)


def _build_segment_clip(seg, visual_path, audio_path, seconds_per_segment):
    audio_clip = AudioFileClip(audio_path)

    if visual_path and os.path.exists(visual_path) and visual_path.lower().endswith(IMAGE_EXTENSIONS):
        video_clip = _ken_burns_clip(visual_path, seconds_per_segment)
    elif visual_path and os.path.exists(visual_path):
        video_clip = VideoFileClip(visual_path).without_audio()
        video_clip = video_clip.resize(height=FRAME_SIZE[1])
        # Center-crop to 1080 width if the source is wider than that (safe zone)
        if video_clip.w > FRAME_SIZE[0]:
            x_center = video_clip.w / 2
            video_clip = video_clip.crop(x_center=x_center, width=FRAME_SIZE[0])
        video_clip = video_clip.loop(duration=seconds_per_segment).subclip(0, seconds_per_segment)
    else:
        video_clip = ColorClip(size=FRAME_SIZE, color=(10, 10, 10), duration=seconds_per_segment)

    text_clip = (
        TextClip(
            seg["on_screen_text"],
            fontsize=70,
            color="white",
            font="DejaVu-Sans-Bold",
            method="caption",
            size=(FRAME_SIZE[0] - 120, None),
            align="center",
        )
        .set_position(("center", "center"))
        .set_duration(seconds_per_segment)
    )

    composite = CompositeVideoClip([video_clip, text_clip], size=FRAME_SIZE)
    composite = composite.set_audio(audio_clip.set_duration(seconds_per_segment))
    return composite


def assemble_video(script, visual_paths, audio_paths, config, out_path="output/final_video.mp4"):
    seconds_per_segment = config["script"]["seconds_per_segment"]
    clips = []

    for seg in script["segments"]:
        seg_num = seg["seg"]
        clip = _build_segment_clip(
            seg,
            visual_paths.get(seg_num),
            audio_paths[seg_num],
            seconds_per_segment,
        )
        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")

    # Layer in continuous ambience (brown noise / drone) under the voiceovers,
    # per the halal-audio constraint: no instruments, synths, or drums.
    ambience_path = os.path.join("assets", "ambience", f"{config['audio']['ambience']}.mp3")
    if os.path.exists(ambience_path):
        ambience = AudioFileClip(ambience_path).fx(afx.audio_loop, duration=final.duration)
        ambience = ambience.volumex(0.15)  # low-volume, sits under the voiceover
        mixed_audio = CompositeAudioClip([final.audio, ambience])
        final = final.set_audio(mixed_audio)
    else:
        print(f"[assemble_video] No ambience file found at {ambience_path} — shipping without it. "
              f"Add a free brown-noise / drone mp3 there to enable this.")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    final.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac")
    print(f"[assemble_video] Final video written to {out_path}")
    return out_path


if __name__ == "__main__":
    print("Run via main.py — this module expects a generated script and downloaded assets.")
