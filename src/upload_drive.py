"""
upload_drive.py
Uploads the finished video + all generated text docs (editing checklist,
Google Flow prompts, platform metadata) to a Google Drive folder using a
free Google Cloud service account (Drive API has a generous free quota
for personal use).

Setup (one-time, see README):
  1. Create a Google Cloud project (free) and enable the Drive API.
  2. Create a service account, download its JSON key.
  3. Share your target Drive folder with the service account's email
     (looks like xxxx@yyyy.iam.gserviceaccount.com) as an Editor.
  4. Put the JSON key content in the GOOGLE_SERVICE_ACCOUNT_JSON secret,
     and the folder's ID in the GDRIVE_FOLDER_ID secret.
"""

import os
import tempfile

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _get_drive_service():
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(creds_json)
        creds_path = f.name

    credentials = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
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


def upload_to_drive(video_path, script, config):
    if not config["output"].get("upload_to_drive", True):
        print("[upload_drive] Skipping Drive upload (disabled in config.yaml)")
        return

    folder_id = os.environ["GDRIVE_FOLDER_ID"]
    service = _get_drive_service()

    metadata_path = write_metadata_file(script)

    video_filename = os.path.basename(video_path)
    upload_file(service, video_path, video_filename, folder_id, "video/mp4")
    upload_file(service, metadata_path, "metadata.txt", folder_id, "text/plain")

    # These two are optional / best-effort (generated in steps 7-8 of main.py) —
    # upload them if they exist, but never fail the whole run if they don't.
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
