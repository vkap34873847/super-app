#!/usr/bin/env python3
"""
Batch upload Hindi‑dubbed videos (with background music) to YouTube.

Assumptions:
- `client_secret.json` (OAuth 2.0 desktop credentials) is located in the same directory as this script.
- VIDEO_DIR points to the folder containing the *hindi.mp4 files.
- META_DIR points to the folder containing the matching *_metadata.json files.
- Each video filename follows the pattern `<ID>_hindi.mp4` where the same `<ID>` is used for `<ID>_metadata.json`.
- The metadata JSON contains at least: title, description, tags (list), privacyStatus.

The script will:
1. Perform OAuth flow (opens a browser for the first run).
2. For each video, load its metadata JSON.
3. Upload the video with the provided metadata via the YouTube Data API v3.
4. Write a simple `upload_log.json` with the video IDs.
"""
import os, json, re, sys
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from tqdm import tqdm

# ----- CONFIG -----
VIDEO_DIR = "/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/with_background_music"
META_DIR = "/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a"
CLIENT_SECRETS = "client_secret.json"  # placed beside this script
TOKEN_FILE = "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_youtube_service():
    if os.path.exists(TOKEN_FILE):
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
        creds = flow.run_local_server(port=0)
        # Save the credentials for future runs
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def load_metadata(vid_id: str):
    meta_path = Path(META_DIR) / f"{vid_id}_metadata.json"
    if not meta_path.is_file():
        print(f"[⚠️] Metadata missing for {vid_id}, using defaults.")
        return {}
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)

def upload_video(youtube, video_path: Path, meta: dict):
    body = {
        "snippet": {
            "title": meta.get("title", video_path.stem),
            "description": meta.get("description", ""),
            "tags": meta.get("tags", []),
            "categoryId": "22"  # People & Blogs – change as needed
        },
        "status": {
            "privacyStatus": meta.get("privacyStatus", "private")
        }
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/*")
    request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
    response = None
    with tqdm(total=100, desc=video_path.name, unit="%", leave=False) as pbar:
        while response is None:
            status, response = request.next_chunk()
            if status:
                pbar.n = int(status.progress() * 100)
                pbar.refresh()
    return response["id"]

def main():
    youtube = get_youtube_service()
    video_dir = Path(VIDEO_DIR)
    log = []
    for vid_file in sorted(video_dir.iterdir()):
        if not vid_file.is_file() or not vid_file.name.endswith("_hindi.mp4"):
            continue
        # extract numeric ID before the first underscore
        match = re.search(r"(\d+)_hindi", vid_file.name)
        if not match:
            print(f"[⚠️] Cannot parse ID from {vid_file.name}, skipping.")
            continue
        vid_id = match.group(1)
        meta = load_metadata(vid_id)
        try:
            yt_id = upload_video(youtube, vid_file, meta)
            print(f"[✅] Uploaded {vid_file.name} → https://youtu.be/{yt_id}")
            log.append({"local": str(vid_file), "youtube_id": yt_id})
        except Exception as e:
            print(f"[❌] Failed {vid_file.name}: {e}")
    # write a tiny log file for reference
    with open("upload_log.json", "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
    print("All done. Log written to upload_log.json")

if __name__ == "__main__":
    main()