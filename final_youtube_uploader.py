#!/usr/bin/env python3
"""
YouTube Uploader - Automated uploads via Chrome
After one-time login, runs fully automatic.
"""
import json, os, time, re, sys
from pathlib import Path
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

VIDEO_DIR = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/with_background_music")
META_DIR = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a")
PROGRESS_FILE = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/upload_progress.json")
USER_DATA_DIR = "/Users/B0338614/.config/yt-uploader-chrome"

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
        if not m: continue
        vid_id = m.group(1)
        meta_file = META_DIR / f"{vid_id}_metadata.json"
        meta = None
        if meta_file.exists():
            with open(meta_file) as f:
                meta = json.load(f)
        result.append((v, vid_id, meta))
    return result

def upload_video(page, video_path, meta):
    print(f"  Processing: {video_path.name}")
    page.goto("https://studio.youtube.com", wait_until="domcontentloaded")
    time.sleep(3)

    # CREATE button
    create_btn = page.locator("#create-icon, [aria-label='Create']").first
    create_btn.wait_for(timeout=15000)
    create_btn.click()
    time.sleep(2)

    # Upload videos
    upload_opt = page.locator("text=Upload videos").first
    upload_opt.wait_for(timeout=10000)
    upload_opt.click()
    time.sleep(2)

    # File input
    file_input = page.locator("input[type=file]").first
    file_input.set_input_files(str(video_path))
    print("  Uploading...", end="", flush=True)

    # Wait for processing (title field appears)
    title_sel = "#title-textarea, [aria-label='Title'], [aria-label='Add a title that describes your video']"
    try:
        page.wait_for_selector(title_sel, timeout=300000)
        print(" processed!")
    except PwTimeout:
        print(" ❌ Timeout waiting for upload")
        return False
    time.sleep(2)

    # Title
    title = ((meta.get("title", "") or "")[:100] if meta else video_path.stem[:100])
    tf = page.locator(title_sel).first
    tf.click()
    time.sleep(0.5)
    page.keyboard.press("Meta+a")
    page.keyboard.type(title, delay=10)

    # Description
    desc = ""
    if meta:
        desc = meta.get("description", "") or ""
        author = meta.get("author", "")
        aname = meta.get("author_name", author)
        desc += f"\n\nCreator: @{author} ({aname})"
        htags = meta.get("hashtags", [])
        if htags:
            desc += "\n\n" + " ".join(f"#{h}" for h in htags)
    desc_sel = "#description-textarea, [aria-label='Description']"
    df = page.locator(desc_sel).first
    if df.is_visible(timeout=3000):
        df.click()
        time.sleep(0.5)
        page.keyboard.press("Meta+a")
        page.keyboard.type(desc, delay=5)

    # Show more (for tags)
    sm = page.locator("text=Show more").first
    if sm.is_visible(timeout=2000):
        sm.click()
        time.sleep(0.5)

    # Tags
    if meta and meta.get("tags"):
        ti = page.locator("#tags-input, [aria-label='Tags']").first
        if ti.is_visible(timeout=2000):
            for tag in meta["tags"][:5]:
                ti.click()
                page.keyboard.type(tag, delay=5)
                page.keyboard.press("Enter")
                time.sleep(0.2)

    # Not made for kids
    nmfk = page.locator("[name='VIDEO_MADE_FOR_KIDS'][value='NOT_MADE_FOR_KIDS']").first
    if nmfk.is_visible(timeout=3000):
        nmfk.click()

    # Next → Visibility
    next_btn = page.locator("#next-button, text=Next").first
    if next_btn.is_visible(timeout=3000):
        next_btn.click()
        time.sleep(2)

    # Private
    priv = page.locator("[name='VIDEO_VISIBILITY'][value='PRIVATE']").first
    if priv.is_visible(timeout=3000):
        priv.click()
        time.sleep(1)

    # Next → Save
    next_btn2 = page.locator("#next-button, text=Next").first
    if next_btn2.is_visible(timeout=3000):
        next_btn2.click()
        time.sleep(2)

    # Save
    save_btn = page.locator("#save-button, text=Save, [aria-label='Save']").first
    if save_btn.is_visible(timeout=3000):
        save_btn.click()
        print("  ✅ Uploaded!")
        time.sleep(5)
        return True

    print("  ❌ Could not complete upload")
    return False

def main():
    print("=== YouTube Auto-Uploader ===")
    progress = load_progress()
    videos = find_videos()
    print(f"Found {len(videos)} videos to process")
    
    pending = [(v, i, m) for v, i, m in videos 
               if i not in progress["uploaded"] and i not in progress["failed"]]
    print(f"Pending: {len(pending)} (Uploaded: {len(progress['uploaded'])}, Failed: {len(progress['failed'])})")
    
    if not pending:
        print("✅ All videos processed!")
        return

    print("\n🚀 Starting upload process...")
    print("💡 Tip: After first login, everything is automatic\n")

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
            try:
                success = upload_video(page, video_path, meta)
                if success:
                    progress["uploaded"].append(vid_id)
                else:
                    progress["failed"].append(vid_id)
            except Exception as e:
                print(f"  ❌ Error: {e}")
                progress["failed"].append(vid_id)
            
            save_progress(progress)

            # Wait 2 days between uploads (except after last video)
            if idx < len(pending) - 1:
                wait_hours = 48  # 2 days
                wait_seconds = wait_hours * 3600
                next_time = datetime.now() + timedelta(seconds=wait_seconds)
                print(f"\n  ⏳ Waiting {wait_hours} hours until {next_time.strftime('%Y-%m-%d %H:%M')}")
                print(f"  (Browser will stay open - do not close it)")
                time.sleep(wait_seconds)

        context.close()

    print(f"\n🎉 Upload session complete!")
    print(f"   Successfully uploaded: {len(progress['uploaded'])}")
    print(f"   Failed: {len(progress['failed'])}")
    save_progress(progress)

if __name__ == "__main__":
    main()