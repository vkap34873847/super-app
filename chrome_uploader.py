#!/usr/bin/env python3
"""
YouTube Uploader — connects to your existing Chrome so you stay logged in.
"""
import json, os, time, re, sys
from pathlib import Path
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

VIDEO_DIR = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/with_background_music")
META_DIR = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a")
PROGRESS_FILE = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/upload_progress.json")

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

def do_upload(page, video_path, meta):
    print("  Opening YouTube Studio...")
    page.goto("https://studio.youtube.com", wait_until="domcontentloaded")
    time.sleep(5)

    # Click CREATE button
    create_btn = page.locator("#create-icon, [aria-label='Create']").first
    create_btn.wait_for(timeout=15000)
    create_btn.click()
    time.sleep(2)

    # Click "Upload videos"
    upload_opt = page.locator("text=Upload videos").first
    upload_opt.wait_for(timeout=10000)
    upload_opt.click()
    time.sleep(2)

    # Upload file
    file_input = page.locator("input[type=file]").first
    file_input.set_input_files(str(video_path))
    print("  File selected, waiting for processing...")

    # Wait for upload to process (title field appears)
    title_sel = "#title-textarea, [aria-label='Title'], [aria-label='Add a title that describes your video']"
    page.wait_for_selector(title_sel, timeout=300000)
    print("  Upload processed, filling details...")
    time.sleep(2)

    # Title
    title = ((meta.get("title", "") or "")[:100] if meta else video_path.stem[:100])
    tf = page.locator(title_sel).first
    tf.click()
    time.sleep(0.5)
    page.keyboard.press("Meta+a")
    page.keyboard.type(title, delay=15)

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
        page.keyboard.type(desc, delay=10)

    # Show more (for tags)
    sm = page.locator("text=Show more").first
    if sm.is_visible(timeout=2000):
        sm.click()
        time.sleep(1)

    # Tags
    if meta and meta.get("tags"):
        ti = page.locator("#tags-input, [aria-label='Tags']").first
        if ti.is_visible(timeout=2000):
            for tag in meta["tags"][:5]:
                ti.click()
                page.keyboard.type(tag, delay=10)
                page.keyboard.press("Enter")
                time.sleep(0.3)

    # Not made for kids
    nmfk = page.locator("[name='VIDEO_MADE_FOR_KIDS'][value='NOT_MADE_FOR_KIDS']").first
    if nmfk.is_visible(timeout=3000):
        nmfk.click()

    # Next → Visibility
    nb = page.locator("#next-button, text=Next").first
    if nb.is_visible(timeout=3000):
        nb.click()
        time.sleep(2)

    # Private
    priv = page.locator("[name='VIDEO_VISIBILITY'][value='PRIVATE']").first
    if priv.is_visible(timeout=3000):
        priv.click()
        time.sleep(1)

    # Next again → Save
    nb2 = page.locator("#next-button, text=Next").first
    if nb2.is_visible(timeout=3000):
        nb2.click()
        time.sleep(2)

    # Save
    save = page.locator("#save-button, text=Save, [aria-label='Save']").first
    if save.is_visible(timeout=3000):
        save.click()
        print("  ✅ Uploaded!")
        time.sleep(5)
        return True

    print("  ❌ Could not find Save button")
    return False

def main():
    print("=== YouTube Uploader (via your Chrome) ===")
    progress = load_progress()
    videos = find_videos()
    pending = [(v,i,m) for v,i,m in videos if i not in progress["uploaded"] and i not in progress["failed"]]
    
    if not pending:
        print("All videos already uploaded!")
        return

    # Kill Chrome so we can reuse the profile
    os.system('pkill -f "Google Chrome" 2>/dev/null')
    time.sleep(2)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            "/Users/B0338614/Library/Application Support/Google/Chrome",
            channel="chrome",
            headless=False,
            args=["--profile-directory=Default", "--start-maximized"],
            no_viewport=True,
        )
        page = context.new_page()
        page.goto("https://studio.youtube.com")
        
        print("\n⚠️  Chrome opened with YOUR profile.")
        print("   If you see the YouTube login screen:")
        print(f"     → Log in with work.2003.2023@gmail.com")
        print("   If you're already logged in, the uploads start now.\n")
        time.sleep(5)

        for idx, (vp, vid_id, meta) in enumerate(pending):
            print(f"[{idx+1}/{len(pending)}] {vp.name}")
            try:
                ok = do_upload(page, vp, meta)
                if ok:
                    progress["uploaded"].append(vid_id)
                else:
                    progress["failed"].append(vid_id)
            except Exception as e:
                print(f"  ❌ {e}")
                progress["failed"].append(vid_id)
            save_progress(progress)

            if idx < len(pending) - 1:
                wt = 2 * 24 * 60 * 60
                nt = datetime.now() + timedelta(seconds=wt)
                print(f"\n  ⏳ Next upload at {nt.strftime('%Y-%m-%d %H:%M')}")
                time.sleep(wt)

        context.close()

    print(f"\nDone! {len(progress['uploaded'])} uploaded, {len(progress['failed'])} failed")

if __name__ == "__main__":
    main()
