#!/usr/bin/env python3
"""
Web-based TikTok Downloader
Flask web interface for the TikTok downloader
"""

import json
import os
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import imageio_ffmpeg as ffmpeg

from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, url_for, Response
from flask_cors import CORS

# Import YouTube uploader
sys.path.insert(0, str(Path(__file__).parent))
try:
    from youtube_uploader import upload_video
    YOUTUBE_UPLOAD_AVAILABLE = True
except ImportError:
    YOUTUBE_UPLOAD_AVAILABLE = False
    print("YouTube uploader not available. Install google-api-python-client, google-auth-oauthlib, google-auth-httplib2")

# Import the downloader functions from our CLI tool
import sys
sys.path.append(str(Path(__file__).parent.parent / "tiktok_downloader"))

from downloader import (
    extract_tiktok_id,
    get_hashtag_videos,
    get_user_info,
    get_user_videos,
    resolve_short_url,
    download_video_tikwm,
    sanitize_filename,
)

app = Flask(__name__)
app.secret_key = "tiktok_downloader_secret_key_change_in_production"
CORS(app)

# Configuration
DOWNLOAD_BASE = Path(__file__).resolve().parent.parent / "downloads"
DOWNLOAD_BASE.mkdir(exist_ok=True)
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max file upload
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# In-memory task storage (for demo - use Redis/DB in production)
tasks = {}


COUNTER_FILE = DOWNLOAD_BASE / ".task_counter"


def generate_task_id():
    num = 1
    if COUNTER_FILE.exists():
        try:
            num = int(COUNTER_FILE.read_text().strip()) + 1
        except (ValueError, OSError):
            num = len([d for d in DOWNLOAD_BASE.iterdir() if d.is_dir() and d.name[0].isdigit()]) + 1
    COUNTER_FILE.write_text(str(num))
    uid = str(uuid.uuid4())[:8]
    return f"{num}_{uid}"


def get_download_dir(task_id):
    return DOWNLOAD_BASE / task_id


from download_manager import DownloadManager


def background_download(task_id, download_type, identifier, options=None):
    if options is None:
        options = {}
    
    task_dir = get_download_dir(task_id)
    task_dir.mkdir(exist_ok=True)
    
    tasks[task_id] = {
        "id": task_id,
        "status": "processing",
        "progress": 0,
        "total": 0,
        "completed": 0,
        "failed": 0,
        "message": "Starting...",
        "files": [],
        "error": None,
    }
    
    try:
        urls = []
        
        if download_type == "url":
            raw_urls = [u.strip() for u in identifier.split("\n") if u.strip()]
            valid = []
            for u in raw_urls:
                video_id = extract_tiktok_id(u)
                if video_id:
                    valid.append(u)
            if not valid:
                raise ValueError("No valid TikTok URLs found")
            urls = valid
            tasks[task_id]["total"] = len(urls)
            tasks[task_id]["message"] = f"Found {len(urls)} valid URL(s)"
                
        elif download_type == "user":
            username = identifier.strip("@")
            user_info = get_user_info(username)
            if not user_info:
                raise ValueError(f"User @{username} not found or private")
            
            nickname = sanitize_filename(user_info.get("nickname", username))
            tasks[task_id]["message"] = f"Fetching videos for @{username}..."
            
            count = options.get("count", 0)
            videos = get_user_videos(username, count)
            
            if not videos:
                raise ValueError(f"No videos found for @{username}")
            
            for v in videos:
                if v.get("video_id"):
                    uid = v.get("author", {}).get("unique_id", username)
                    urls.append(f"https://www.tiktok.com/@{uid}/video/{v['video_id']}")
                    
        elif download_type == "hashtag":
            tag = identifier.lstrip("#")
            tasks[task_id]["message"] = f"Searching hashtag #{tag}..."
            
            count = options.get("count", 50)
            videos = get_hashtag_videos(tag, count)
            
            if not videos:
                raise ValueError(f"No videos found for hashtag #{tag}")
            
            for v in videos:
                if v.get("video_id") and v.get("author", {}).get("unique_id"):
                    uid = v["author"]["unique_id"]
                    urls.append(f"https://www.tiktok.com/@{uid}/video/{v['video_id']}")
        
        elif download_type == "file":
            pass
        
        mgr = DownloadManager(task_id, str(task_dir), urls, lambda s: tasks.update({task_id: s}))
        tasks[task_id] = mgr.get_state()
        mgr.run()
        tasks[task_id] = mgr.get_state()

        # Auto-dub all downloaded files
        if tasks[task_id]["status"] == "completed":
            names = [f["name"] for f in tasks[task_id].get("files", [])]
            auto_dub_all(task_id, task_dir, names)
    
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["message"] = str(e)
        tasks[task_id]["error"] = str(e)
        print(f"Task {task_id} failed: {e}")


def verify_dub(video_path):
    if not video_path.exists() or video_path.stat().st_size == 0:
        return False, "File missing or empty"
    result = subprocess.run(
        [ffmpeg.get_ffmpeg_exe(), "-i", str(video_path), "-f", "null", "-"],
        capture_output=True, text=True, timeout=30
    )
    has_audio = "Audio" in result.stderr
    if not has_audio:
        return False, "No audio stream in output"
    return True, "OK"


def auto_dub_all(task_id, task_dir, filenames=None):
    dub_dir = task_dir / "dubbed"
    dub_dir.mkdir(exist_ok=True)
    if filenames:
        files = sorted([task_dir / n for n in filenames])
    else:
        files = sorted(task_dir.glob("*.mp4"))
    if not files:
        return

    tasks[task_id]["status"] = "dubbing"
    tasks[task_id]["message"] = f"Starting auto-dub for {len(files)} video(s)..."
    tasks[task_id]["dub_files"] = {}

    for f in files:
        tasks[task_id]["dub_files"][f.name] = {
            "status": "pending",
            "message": "Waiting...",
            "retries": 0,
            "output_name": None,
        }

    for f in files:
        if tasks[task_id].get("status") == "cancelled":
            return
        dub_single_with_retry(task_id, f, dub_dir)

    done = sum(1 for s in tasks[task_id]["dub_files"].values() if s["status"] == "completed")
    failed = sum(1 for s in tasks[task_id]["dub_files"].values() if s["status"] == "failed")
    
    # Auto-upload dubbed videos to YouTube if available
    if YOUTUBE_UPLOAD_AVAILABLE and done > 0:
        tasks[task_id]["status"] = "uploading"
        tasks[task_id]["message"] = f"Starting YouTube upload for {done} dubbed video(s)..."
        tasks[task_id]["youtube_uploads"] = {}
        
        uploaded_count = 0
        failed_count = 0
        
        for filename, status in tasks[task_id]["dub_files"].items():
            if status["status"] == "completed":
                video_path = dub_dir / status["output_name"]
                try:
                    # Generate YouTube metadata from original TikTok data
                    # We need to get the original TikTok data for this file
                    # For now, use basic metadata - in future could store original data with task
                    title = f"{filename.replace('_hindi.mp4', '')} - Hindi Dub"
                    description = "Hindi dubbed video from TikTok downloader\n\nUploaded via Super-App"
                    category = "22"  # People & Blogs
                    keywords = "TikTok, Hindi, Dubbed, Viral"
                    
                    video_id = upload_video(
                        file_path=str(video_path),
                        title=title,
                        description=description,
                        category=category,
                        keywords=keywords,
                        privacy_status="private"  # Start as private, user can change later
                    )
                    
                    tasks[task_id]["youtube_uploads"][filename] = {
                        "status": "completed",
                        "video_id": video_id,
                        "url": f"https://www.youtube.com/watch?v={video_id}"
                    }
                    uploaded_count += 1
                    
                except Exception as e:
                    tasks[task_id]["youtube_uploads"][filename] = {
                        "status": "failed",
                        "error": str(e)
                    }
                    failed_count += 1
        
        tasks[task_id]["youtube_uploaded_count"] = uploaded_count
        tasks[task_id]["youtube_failed_count"] = failed_count
        tasks[task_id]["message"] = f"Dubbing complete: {done} done, {failed} failed. YouTube upload: {uploaded_count} uploaded, {failed_count} failed"
    
    tasks[task_id]["status"] = "completed"
    tasks[task_id]["message"] = f"Dubbing complete: {done} done, {failed} failed"


def dub_single_with_retry(task_id, video_path, dub_dir, max_retries=3):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from dubber import dub_video

    filename = video_path.name
    out_name = video_path.stem + "_hindi.mp4"
    out_path = dub_dir / out_name

    for attempt in range(1, max_retries + 1):
        tasks[task_id]["dub_files"][filename] = {
            "status": "processing",
            "message": f"Step 1/7: extracting audio (attempt {attempt}/{max_retries})...",
            "retries": attempt - 1,
            "output_name": out_name,
        }

        try:
            dub_video(str(video_path), str(out_path), tmp_dir=str(dub_dir / "tmp" / filename))

            tasks[task_id]["dub_files"][filename] = {
                "status": "verifying",
                "message": "Verifying dubbed output...",
                "retries": attempt - 1,
                "output_name": out_name,
            }

            ok, msg = verify_dub(out_path)
            if ok:
                tasks[task_id]["dub_files"][filename] = {
                    "status": "completed",
                    "message": "Done",
                    "retries": attempt - 1,
                    "output_name": out_name,
                }
                return
            else:
                if attempt < max_retries:
                    tasks[task_id]["dub_files"][filename] = {
                        "status": "processing",
                        "message": f"Verification failed ({msg}), retrying ({attempt}/{max_retries})...",
                        "retries": attempt,
                        "output_name": out_name,
                    }
                else:
                    tasks[task_id]["dub_files"][filename] = {
                        "status": "failed",
                        "message": f"Verification failed after {max_retries} attempts: {msg}",
                        "retries": attempt - 1,
                        "output_name": out_name,
                    }

        except Exception as e:
            if attempt < max_retries:
                tasks[task_id]["dub_files"][filename] = {
                    "status": "processing",
                    "message": f"Failed (attempt {attempt}/{max_retries}), retrying...",
                    "retries": attempt,
                    "output_name": out_name,
                }
            else:
                tasks[task_id]["dub_files"][filename] = {
                    "status": "failed",
                    "message": f"Failed after {max_retries} attempts: {str(e)[:80]}",
                    "retries": attempt - 1,
                    "output_name": out_name,
                }


@app.route("/")
def index():
    return render_template("index.html")




@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.json
    download_type = data.get("type")
    identifier = data.get("identifier")
    options = data.get("options", {})
    
    if not download_type or not identifier:
        return jsonify({"error": "Missing type or identifier"}), 400
    
    task_id = generate_task_id()
    
    # Start background thread
    thread = threading.Thread(
        target=background_download,
        args=(task_id, download_type, identifier, options),
        daemon=True,
    )
    thread.start()
    
    return jsonify({"task_id": task_id})


@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    
    if not file.filename.endswith(".txt"):
        return jsonify({"error": "Only .txt files allowed"}), 400
    
    # Save uploaded file temporarily
    task_id = generate_task_id()
    task_dir = get_download_dir(task_id)
    task_dir.mkdir(exist_ok=True)
    
    filepath = task_dir / "urls.txt"
    file.save(str(filepath))
    
    # Read URLs
    try:
        with open(filepath) as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        
        if not urls:
            return jsonify({"error": "No valid URLs found in file"}), 400
            
    except Exception as e:
        return jsonify({"error": f"Failed to read file: {str(e)}"}), 400
    
    # Start download
    thread = threading.Thread(
        target=background_download_file,
        args=(task_id, str(filepath)),
        daemon=True,
    )
    thread.start()
    
    return jsonify({"task_id": task_id})


def background_download_file(task_id, filepath):
    task_dir = get_download_dir(task_id)
    try:
        with open(filepath) as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        
        mgr = DownloadManager(task_id, str(task_dir), urls, lambda s: tasks.update({task_id: s}))
        tasks[task_id] = mgr.get_state()
        mgr.run()
        tasks[task_id] = mgr.get_state()

        if tasks[task_id]["status"] == "completed":
            names = [f["name"] for f in tasks[task_id].get("files", [])]
            auto_dub_all(task_id, task_dir, names)
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["message"] = str(e)
        tasks[task_id]["error"] = str(e)


@app.route("/api/task/<task_id>")
def get_task_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task)


@app.route("/api/task/<task_id>/cancel", methods=["POST"])
def cancel_task(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    task["status"] = "cancelled"
    task["message"] = "Cancelled, sending files..."
    import download_manager as dm
    if task_id in dm.managers:
        dm.managers[task_id].cancel()
    return jsonify(task)


@app.route("/api/task/<task_id>/file/<path:filename>")
def download_file(task_id, filename):
    """Serve a downloaded file"""
    task_dir = get_download_dir(task_id)
    file_path = task_dir / filename
    
    if not file_path.exists() or not file_path.is_file():
        return jsonify({"error": "File not found"}), 404
    
    return send_file(str(file_path), as_attachment=True)


@app.route("/api/task/<task_id>/zip")
def download_zip(task_id):
    """Create and serve a ZIP of all downloaded files"""
    import shutil
    
    task_dir = get_download_dir(task_id)
    if not task_dir.exists():
        return jsonify({"error": "Task not found"}), 404
    
    files = list(task_dir.iterdir())
    if not files:
        return jsonify({"error": "No files to download"}), 400
    
    zip_path = (task_dir.parent / f"{task_id}.zip").resolve()
    shutil.make_archive(str(task_dir.resolve()), "zip", str(task_dir.resolve()))

    if not zip_path.exists():
        return jsonify({"error": "Failed to create zip"}), 500

    return send_file(str(zip_path), as_attachment=True, download_name=f"tiktok_downloads_{task_id}.zip")


dub_states = {}


@app.route("/api/task/<task_id>/dub", methods=["POST"])
def start_dub(task_id):
    data = request.json
    filename = data.get("filename")
    if not filename:
        return jsonify({"error": "Missing filename"}), 400

    task_dir = get_download_dir(task_id)
    video_path = task_dir / filename
    if not video_path.exists():
        return jsonify({"error": "Video file not found"}), 404

    dub_id = str(uuid.uuid4())
    dub_dir = task_dir / "dubbed"
    dub_dir.mkdir(exist_ok=True)

    dub_states[dub_id] = {
        "status": "processing",
        "progress": 0,
        "message": "Starting dubbing pipeline...",
        "output_filename": None,
        "output_path": None,
        "error": None,
    }

    thread = threading.Thread(
        target=run_dub,
        args=(dub_id, video_path, dub_dir),
        daemon=True,
    )
    thread.start()
    return jsonify({"dub_id": dub_id})


def run_dub(dub_id, video_path, dub_dir):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    try:
        from dubber import dub_video
        out_name = video_path.stem + "_hindi.mp4"
        out_path = dub_dir / out_name
        dub_states[dub_id]["message"] = "1/7 Extracting audio..."
        dub_states[dub_id]["progress"] = 10
        dub_video(str(video_path), str(out_path), tmp_dir=str(dub_dir / "tmp"))
        dub_states[dub_id].update({
            "status": "completed",
            "progress": 100,
            "message": "Dubbing complete!",
            "output_filename": out_name,
            "output_path": str(out_path.resolve()),
        })
    except Exception as e:
        dub_states[dub_id].update({
            "status": "failed",
            "message": str(e),
            "error": str(e),
        })


@app.route("/api/dub/<dub_id>")
def get_dub_status(dub_id):
    state = dub_states.get(dub_id)
    if not state:
        return jsonify({"error": "Dub task not found"}), 404
    return jsonify(state)


@app.route("/api/dub/<dub_id>/file")
def download_dubbed(dub_id):
    state = dub_states.get(dub_id)
    if not state or state["status"] != "completed":
        return jsonify({"error": "Dub not ready"}), 400
    return send_file(state["output_path"], as_attachment=True)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)