#!/usr/bin/env python3
"""
Mass TikTok Downloader
Supports: single URLs, user profiles, hashtags, and batch files.
"""

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import requests
import yt_dlp
from tqdm import tqdm


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

HEADERS = {"User-Agent": USER_AGENT}
TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name.strip().replace(" ", "_"))[:100]


def extract_tiktok_id(url: str) -> Optional[str]:
    patterns = [
        r"tiktok\.com/@[\w.-]+/video/(\d+)",
        r"tiktok\.com/video/(\d+)",
        r"vm\.tiktok\.com/([\w-]+)",
        r"vt\.tiktok\.com/([\w-]+)",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def resolve_short_url(url: str) -> str:
    try:
        r = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        return r.url
    except requests.RequestException:
        return url


def get_user_info(username: str) -> Optional[dict]:
    api_url = f"https://www.tikwm.com/api/user/info?unique_id=@{username}"
    try:
        r = requests.get(api_url, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        if data.get("code") == 0:
            return data["data"]["user"]
    except Exception:
        pass
    return None


def get_user_videos(username: str, count: int = 0) -> list[dict]:
    videos = []
    cursor = 0
    while True:
        api_url = (
            f"https://www.tikwm.com/api/user/posts"
            f"?unique_id=@{username}&count=50&cursor={cursor}"
        )
        try:
            r = requests.get(api_url, headers=HEADERS, timeout=TIMEOUT)
            data = r.json()
            if data.get("code") != 0:
                break
            videos.extend(data["data"]["videos"])
            if count and len(videos) >= count:
                return videos[:count]
            if not data["data"].get("has_more"):
                break
            cursor = data["data"].get("cursor", 0)
        except Exception:
            break
        time.sleep(0.5)
    return videos


def get_hashtag_videos(hashtag: str, count: int = 50) -> list[dict]:
    videos = []
    cursor = 0
    while len(videos) < count:
        api_url = (
            f"https://www.tikwm.com/api/hashtag/search"
            f"?keyword={hashtag}&count=50&cursor={cursor}"
        )
        try:
            r = requests.get(api_url, headers=HEADERS, timeout=TIMEOUT)
            data = r.json()
            if data.get("code") != 0:
                break
            for item in data["data"].get("videos", []):
                videos.append(item)
            if not data["data"].get("has_more"):
                break
            cursor = data["data"].get("cursor", 0)
        except Exception:
            break
        time.sleep(0.5)
    return videos[:count]


def download_video_ytdlp(url: str, output_dir: str, filename: str) -> bool:
    output_path = Path(output_dir) / f"{filename}.%(ext)s"
    ydl_opts = {
        "outtmpl": str(output_path),
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "headers": HEADERS,
        "http_headers": HEADERS,
        "format": "best[ext=mp4]/best",
        "retries": MAX_RETRIES,
        "socket_timeout": TIMEOUT,
    }
    for attempt in range(MAX_RETRIES):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                print(f"  FAILED after {MAX_RETRIES} attempts: {e}")
    return False


def download_video_tikwm(url: str, output_dir: str, filename: str) -> tuple[bool, Optional[dict]]:
    api_url = f"https://www.tikwm.com/api/?url={url}"
    try:
        r = requests.get(api_url, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        if data.get("code") != 0:
            return False, None
        video_data = data.get("data", {})
        download_url = video_data.get("play")
        if not download_url:
            download_url = video_data.get("wmplay")
        if not download_url:
            download_url = video_data.get("hdplay")
        if not download_url:
            return False, None

        video_r = requests.get(download_url, headers=HEADERS, timeout=60, stream=True)
        if video_r.status_code != 200:
            return False, None

        output_path = Path(output_dir) / f"{filename}.mp4"
        with open(output_path, "wb") as f:
            for chunk in video_r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        ok = output_path.exists() and output_path.stat().st_size > 0
        return ok, video_data if ok else None
    except Exception as e:
        print(f"  tikwm download failed: {e}")
    return False, None


def download_single_video(
    url: str, output_dir: str, index: Optional[int] = None
) -> tuple[str, bool]:
    url = resolve_short_url(url)
    video_id = extract_tiktok_id(url)
    if not video_id:
        return (url, False)

    prefix = f"{index:04d}_" if index is not None else ""
    filename = f"{prefix}{video_id}"

    success, _ = download_video_tikwm(url, output_dir, filename)
    return (url, success)


def download_videos_batch(
    urls: list[str], output_dir: str, max_workers: int = 4
) -> tuple[int, int]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    successful = 0
    failed = 0

    with tqdm(total=len(urls), desc="Downloading", unit="video") as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for i, url in enumerate(urls, 1):
                future = executor.submit(
                    download_single_video, url.strip(), str(output_dir), i
                )
                futures[future] = url.strip()

            for future in as_completed(futures):
                url, success = future.result()
                if success:
                    successful += 1
                else:
                    failed += 1
                pbar.set_postfix(ok=successful, fail=failed)
                pbar.update(1)

    return successful, failed


def read_urls_from_file(file_path: str) -> list[str]:
    with open(file_path) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def cmd_single(args):
    print(f"Downloading: {args.url}")
    success, _ = download_single_video(args.url, args.output)
    if success:
        print("DONE")
    else:
        print("FAILED")
        sys.exit(1)


def cmd_batch(args):
    urls = read_urls_from_file(args.file)
    if not urls:
        print("No URLs found in file.")
        return
    print(f"Downloading {len(urls)} videos from file...")
    ok, fail = download_videos_batch(urls, args.output, args.workers)
    print(f"\nDone: {ok} OK, {fail} Failed")


def cmd_user(args):
    username = args.username.strip("@")
    print(f"Fetching videos for @{username}...")
    info = get_user_info(username)
    if info:
        nickname = sanitize_filename(info.get("nickname", username))
        print(f"User: {info.get('nickname', username)} ({info.get('uniqueId', '')})")
        print(f"Followers: {info.get('followerCount', '?')}, Videos: {info.get('videoCount', '?')}")
    else:
        nickname = username

    user_dir = Path(args.output) / f"@{username}"
    user_dir.mkdir(parents=True, exist_ok=True)

    videos = get_user_videos(username, args.count)
    if not videos:
        print("No videos found or user is private.")
        return

    print(f"Found {len(videos)} videos. Downloading...")
    urls = []
    for i, v in enumerate(videos, 1):
        if v.get("video_id"):
            urls.append(f"https://www.tiktok.com/@{username}/video/{v['video_id']}")

    ok, fail = download_videos_batch(urls, str(user_dir), args.workers)
    print(f"\nDone: {ok} OK, {fail} Failed (saved to {user_dir})")


def cmd_hashtag(args):
    tag = args.hashtag.lstrip("#")
    print(f"Searching hashtag: #{tag}")
    videos = get_hashtag_videos(tag, args.count)
    if not videos:
        print("No videos found.")
        return

    tag_dir = Path(args.output) / f"#{tag}"
    tag_dir.mkdir(parents=True, exist_ok=True)

    print(f"Found {len(videos)} videos. Downloading...")
    urls = []
    for v in videos:
        if v.get("video_id") and v.get("author", {}).get("unique_id"):
            uid = v["author"]["unique_id"]
            urls.append(f"https://www.tiktok.com/@{uid}/video/{v['video_id']}")

    ok, fail = download_videos_batch(urls, str(tag_dir), args.workers)
    print(f"\nDone: {ok} OK, {fail} Failed (saved to {tag_dir})")


def cmd_urls(args):
    urls = list(dict.fromkeys([u.strip() for u in args.urls if u.strip()]))
    print(f"Downloading {len(urls)} videos...")
    ok, fail = download_videos_batch(urls, args.output, args.workers)
    print(f"\nDone: {ok} OK, {fail} Failed")


def main():
    parser = argparse.ArgumentParser(
        description="Mass TikTok Video Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s single https://vm.tiktok.com/XXXX\n"
            "  %(prog)s user therock --count 20\n"
            "  %(prog)s hashtag fyp --count 50\n"
            "  %(prog)s urls https://tiktok.com/... https://tiktok.com/...\n"
            "  %(prog)s batch urls.txt\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_single = sub.add_parser("single", help="Download a single video by URL")
    p_single.add_argument("url", help="TikTok video URL")
    p_single.add_argument("-o", "--output", default="./downloads", help="Output directory")
    p_single.set_defaults(func=cmd_single)

    p_batch = sub.add_parser("batch", help="Download from a text file of URLs")
    p_batch.add_argument("file", help="Path to text file with URLs (one per line)")
    p_batch.add_argument("-o", "--output", default="./downloads", help="Output directory")
    p_batch.add_argument("-w", "--workers", type=int, default=4, help="Parallel downloads")
    p_batch.set_defaults(func=cmd_batch)

    p_user = sub.add_parser("user", help="Download all videos from a user")
    p_user.add_argument("username", help="TikTok username (with or without @)")
    p_user.add_argument("-c", "--count", type=int, default=0, help="Max videos (0 = all)")
    p_user.add_argument("-o", "--output", default="./downloads", help="Output directory")
    p_user.add_argument("-w", "--workers", type=int, default=4, help="Parallel downloads")
    p_user.set_defaults(func=cmd_user)

    p_tag = sub.add_parser("hashtag", help="Download videos by hashtag")
    p_tag.add_argument("hashtag", help="Hashtag (with or without #)")
    p_tag.add_argument("-c", "--count", type=int, default=50, help="Number of videos")
    p_tag.add_argument("-o", "--output", default="./downloads", help="Output directory")
    p_tag.add_argument("-w", "--workers", type=int, default=4, help="Parallel downloads")
    p_tag.set_defaults(func=cmd_hashtag)

    p_urls = sub.add_parser("urls", help="Download one or more specific URLs")
    p_urls.add_argument("urls", nargs="+", help="TikTok video URLs")
    p_urls.add_argument("-o", "--output", default="./downloads", help="Output directory")
    p_urls.add_argument("-w", "--workers", type=int, default=4, help="Parallel downloads")
    p_urls.set_defaults(func=cmd_urls)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
