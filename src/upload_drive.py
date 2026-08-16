"""
upload_drive.py
Uploads the finished video + all generated text docs + the raw humanized
voiceover audio files to Google Drive, using YOUR OWN Google account (via
a refresh token) instead of a Service Account.
"""

import os
import zipfile

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _get_drive_service():
    credentials = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri=TOKEN_URI,
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    return build("drive", "v3", credentials=credentials)


def upload_file(service, local_path, filename, folder_id, mime_type):
    file_metadata = {"name": filename, "parents": [folder_id]}
    media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
    uploaded = service.files().create(body=file_metadata, media_body=media, fields="id, webViewLink").execute()
    print(f"[upload_drive] Uploaded {filename} -> {uploaded.get('webViewLink')}")
    return uploaded


def write_metadata_file(script, out_path="output/metadata.txt"):
    lines = ["TITLE OPTIONS:\n"]
    for t in script.get("title_options", []):
        lines.append(f"- {t}\n")
    lines.append("\nSEGMENT SCRIPT / EDITING CHECKLIST:\n")
    for seg in script["segments"]:
        lines.append(
            f"\nSeg {seg['seg']} ({seg['time']}) [{seg.get('emotion', 'authoritative')}]\n"
            f"  VO: {seg['vo']}\n"
            f"  On-screen text: {seg['on_screen_text']}\n"
            f"  Visual: [{seg['visual_prompt_type']}] {seg['visual_prompt']}\n"
            f"  SFX/Ambience: {seg['sfx_ambience']}\n"
        )
    with open(out_path, "w") as f:
        f.writelines(lines)
    return out_path


def zip_voiceovers(audio_paths, out_path="output/voiceovers.zip"):
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for seg_num, path in sorted(audio_paths.items()):
            if path and os.path.exists(path):
                zf.write(path, arcname=os.path.basename(path))
    return out_path


def upload_to_drive(video_path, script, config, audio_paths=None):
    if not config["output"].get("upload_to_drive", True):
        print("[upload_drive] Skipping Drive upload (disabled in config.yaml)")
        return

    folder_id = os.environ["GDRIVE_FOLDER_ID"]
    service = _get_drive_service()

    metadata_path = write_metadata_file(script)

    video_filename = os.path.basename(video_path)
    upload_file(service, video_path, video_filename, folder_id, "video/mp4")
    upload_file(service, metadata_path, "metadata.txt", folder_id, "text/plain")

    if audio_paths:
        zip_path = zip_voiceovers(audio_paths)
        upload_file(service, zip_path, "voiceovers.zip", folder_id, "application/zip")
    else:
        print("[upload_drive] No audio_paths provided — skipping voiceovers.zip")

    optional_files = [
        ("output/google_flow_prompts.txt", "google_flow_prompts.txt"),
        ("output/platform_metadata.txt", "platform_metadata.txt"),
    ]
    for local_path, drive_name in optional_files:
        if os.path.exists(local_path):
            upload_file(service, local_path, drive_name, folder_id, "text/plain")
        else:
            print(f"[upload_drive] Skipping {drive_name} — not generated this run")


if __name__ == "__main__":
    print("Run via main.py — this module expects a finished video + script.")
