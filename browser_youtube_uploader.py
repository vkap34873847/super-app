#!/usr/bin/env python3
"""
Playwright-based YouTube Uploader for Hindi Dubbed Videos
Uploads directly via browser — NO Google Cloud Console, NO API keys, FREE.
"""
import json
import os
import time
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

VIDEO_DIR = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/with_background_music")
META_DIR = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a")
PROGRESS_FILE = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/upload_progress.json")
USER_DATA_DIR = "/Users/B0338614/.config/youtube-uploader-profile"


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"uploaded": [], "failed": []}


def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def find_videos():
    videos = sorted(VIDEO_DIR.glob("*_hindi.mp4"))
    result = []
    for v in videos:
        m = re.match(r"(\d+)", v.stem)
        if not m:
            continue
        vid_id = m.group(1)
        meta_file = META_DIR / f"{vid_id}_metadata.json"
        meta = None
        if meta_file.exists():
            with open(meta_file) as f:
                meta = json.load(f)
        result.append((v, vid_id, meta))
    return result


def do_upload(page, video_path, meta):
    print(f"  Opening YouTube Studio...")
    page.goto("https://studio.youtube.com", wait_until="networkidle")
    time.sleep(3)

    # Click CREATE button (top-right, "+" icon)
    create_btn = page.locator("topbar-button-wrapper #create-icon, [aria-label='Create'], button:has-text('Create')").first
    if not create_btn.is_visible(timeout=5000):
        create_btn = page.locator("ytcp-button#create-icon, #create-icon").first
    create_btn.click()
    time.sleep(2)

    # Click "Upload videos"
    upload_opt = page.locator("[aria-label='Upload videos'], text=Upload videos").first
    upload_opt.click()
    time.sleep(2)

    # --- FILE DIALOG ---
    file_input = page.locator("input[type=file]").first
    file_input.set_input_files(str(video_path))
    print(f"  File selected, waiting for processing...")

    # Wait for processing to complete — look for the title field to appear
    title_selector = "[aria-label='Title'], #title-textarea, [aria-label='Add a title that describes your video'], .title-textarea"
    page.wait_for_selector(title_selector, timeout=300000)  # 5 min timeout for upload
    print(f"  Upload processed, filling metadata...")
    time.sleep(2)

    # --- TITLE ---
    title = (meta.get("title", "") or "")[:100] if meta else video_path.stem[:100]
    title_field = page.locator(title_selector).first
    title_field.click()
    time.sleep(0.5)
    # Select all and type
    page.keyboard.press("Meta+a")
    page.keyboard.type(title, delay=20)

    # --- DESCRIPTION ---
    desc = ""
    if meta:
        desc = meta.get("description", "") or ""
        author = meta.get("author", "")
        author_name = meta.get("author_name", author)
        desc += f"\n\nCreator: @{author} ({author_name})"
        hashtags = meta.get("hashtags", [])
        if hashtags:
            desc += "\n\n" + " ".join(f"#{h}" for h in hashtags)

    desc_selector = "[aria-label='Description'], #description-textarea, [aria-label='Tell viewers about your video']"
    desc_field = page.locator(desc_selector).first
    if desc_field.is_visible(timeout=3000):
        desc_field.click()
        time.sleep(0.5)
        page.keyboard.press("Meta+a")
        page.keyboard.type(desc, delay=10)

    # --- SHOW MORE (for tags) ---
    show_more = page.locator("text=Show more, [aria-label='Show more'], #toggle-button").first
    if show_more.is_visible(timeout=2000):
        show_more.click()
        time.sleep(1)

    # --- TAGS ---
    if meta and meta.get("tags"):
        tags_input = page.locator("[aria-label='Tags'], #tags-input, input[placeholder='Tags']").first
        if tags_input.is_visible(timeout=2000):
            tags_to_add = meta["tags"][:5]
            for tag in tags_to_add:
                tags_input.click()
                page.keyboard.type(tag, delay=10)
                page.keyboard.press("Enter")
                time.sleep(0.3)

    # --- MADE FOR KIDS: "No, it's not made for kids" ---
    not_for_kids = page.locator("[name='VIDEO_MADE_FOR_KIDS'][value='NOT_MADE_FOR_KIDS'], [aria-label='No, it\\'s not made for kids'], text=No, it's not made for kids").first
    if not_for_kids.is_visible(timeout=3000):
        not_for_kids.click()

    # --- NEXT / VISIBILITY ---
    next_btn = page.locator("text=Next, [aria-label='Next'], #next-button").first
    if next_btn.is_visible(timeout=3000):
        next_btn.click()
        time.sleep(2)

    # --- VISIBILITY: Private (safe default) ---
    private_radio = page.locator("[name='VIDEO_VISIBILITY'][value='PRIVATE'], [aria-label='Private'], #radio-private").first
    if private_radio.is_visible(timeout=3000):
        private_radio.click()
        time.sleep(1)

    more_next = page.locator("text=Next, [aria-label='Next'], #next-button").first
    if more_next.is_visible(timeout=3000):
        more_next.click()
        time.sleep(2)

    # --- SAVE ---
    save_btn = page.locator("#save-button, [aria-label='Save'], button:has-text('Save'), [aria-label='Publish']").first
    if save_btn.is_visible(timeout=3000):
        save_btn.click()
        print(f"  ✅ Upload submitted!")
        time.sleep(5)
        return True

    print(f"  ❌ Could not find Save button. YouTube UI may have changed.")
    return False


def main():
    print("=== YouTube Browser Uploader (Playwright) ===")
    print()

    progress = load_progress()
    videos = find_videos()
    print(f"Found {len(videos)} Hindi dubbed videos in with_background_music/")
    print()

    pending = [(v, i, m) for v, i, m in videos if i not in progress["uploaded"] and i not in progress["failed"]]
    print(f"Already uploaded: {len(progress['uploaded'])}")
    print(f"Already failed: {len(progress['failed'])}")
    print(f"Pending: {len(pending)}")

    if not pending:
        print("All done!")
        return

    print("\nLaunching browser...")
    print(f"  Profile saved at: {USER_DATA_DIR}")
    print(f"  ⚠️  FIRST TIME ONLY: When Chromium opens:")
    print(f"      1. Log into YouTube with your account")
    print(f"      2. Go to https://studio.youtube.com")
    print(f"      3. Keep the browser open — the script will handle everything")
    print(f"  After that, it's fully automatic (no login needed ever again)\n")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            channel="chrome",
            headless=False,
            args=["--start-maximized"],
            no_viewport=True,
        )
        page = context.new_page()

        for idx, (video_path, vid_id, meta) in enumerate(pending):
            print(f"[{idx+1}/{len(pending)}] {video_path.name}")
            print(f"  Title: {(meta.get('title', '')[:60] if meta else 'N/A')}")

            try:
                ok = do_upload(page, video_path, meta)
                if ok:
                    progress["uploaded"].append(vid_id)
                else:
                    progress["failed"].append(vid_id)
            except Exception as e:
                print(f"  ❌ Error: {e}")
                progress["failed"].append(vid_id)

            save_progress(progress)

            # Wait 2 days before next upload
            if idx < len(pending) - 1:
                wait_seconds = 2 * 24 * 60 * 60
                next_time = datetime.now() + timedelta(seconds=wait_seconds)
                print(f"\n  ⏳ Waiting 2 days until {next_time.strftime('%Y-%m-%d %H:%M')}...")
                print(f"  (Browser will stay open, don't close it)")
                time.sleep(wait_seconds)

        context.close()

    print("\n=== All uploads processed! ===")
    print(f"Success: {len(progress['uploaded'])}")
    print(f"Failed: {len(progress['failed'])}")
    save_progress(progress)


if __name__ == "__main__":
    main()
