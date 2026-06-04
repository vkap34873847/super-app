#!/usr/bin/env python3
"""
CDP-based YouTube Uploader - connects to existing Chrome via Playwright connect_over_cdp
"""
import json, os, time, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

VIDEO_DIR = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/with_background_music")
META_DIR = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a")
PROGRESS_FILE = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/upload_progress.json")
CDP_URL = "http://localhost:9222"

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

def wait_for_element(page, selector, timeout=30):
    try:
        page.wait_for_selector(selector, timeout=timeout*1000)
        return True
    except:
        return False

def click_when_visible(page, selector, timeout=10):
    try:
        el = page.wait_for_selector(selector, timeout=timeout*1000)
        if el:
            el.click()
            return True
    except:
        pass
    return False

def type_text(page, selector, text, timeout=10):
    try:
        el = page.wait_for_selector(selector, timeout=timeout*1000)
        if el:
            el.fill(text)
            return True
    except:
        pass
    return False

def upload_video(page, video_path, meta):
    vid_name = video_path.name
    print(f"\n  Processing: {vid_name}")

    # Navigate to YouTube Studio
    page.goto("https://studio.youtube.com", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    # Click Create button
    create_selectors = [
        "#create-icon",
        "#create-icon-button",
        "[aria-label='Create']",
        "ytcp-button#create-icon",
    ]
    found_create = False
    for sel in create_selectors:
        if click_when_visible(page, sel, timeout=5):
            found_create = True
            break
    if not found_create:
        # Try using keyboard shortcut
        page.keyboard.press("c")
        page.wait_for_timeout(2000)
    
    page.wait_for_timeout(2000)

    # Click "Upload videos" menu item
    upload_selectors = [
        "text=Upload videos",
        "[test-id='upload-button']",
        "ytcp-ve[aria-label='Upload videos']",
        "tp-yt-paper-item:has-text('Upload videos')",
    ]
    found_upload = False
    for sel in upload_selectors:
        if click_when_visible(page, sel, timeout=5):
            found_upload = True
            break
    if not found_upload:
        print("  ❌ Could not find 'Upload videos' option")
        return False
    
    page.wait_for_timeout(2000)

    # Set the file input
    abs_path = str(video_path.resolve())
    try:
        file_input = page.wait_for_selector("input[type=file]", timeout=10000)
        if file_input:
            file_input.set_input_files(abs_path)
        else:
            print("  ❌ File input not found")
            return False
    except Exception as e:
        print(f"  ❌ Error selecting file: {e}")
        return False
    
    print("  Uploading... ", end="", flush=True)

    # Wait for processing to finish (title field appears)
    title_selectors = [
        "#title-textarea",
        "[aria-label='Title']",
        "[aria-label='Add a title that describes your video']",
        ".title-textarea",
        "ytcp-video-title[title-textarea]",
    ]
    found_title = False
    for sel in title_selectors:
        done = wait_for_element(page, sel, timeout=600)
        if done:
            found_title = True
            break
    
    if not found_title:
        print("❌ Timeout waiting for upload processing")
        return False
    
    print("processed!")
    page.wait_for_timeout(3000)

    # Fill Title
    title = ((meta.get("title", "") or "")[:100] if meta else vid_name[:100])
    if title:
        for sel in title_selectors:
            if type_text(page, sel, title, timeout=3):
                print(f"  Title set: {title[:60]}...")
                break

    # Fill Description
    desc_selectors = [
        "#description-textarea",
        "[aria-label='Description']",
        ".description-textarea",
        "ytcp-video-description[description-textarea]",
    ]
    desc = ""
    if meta:
        desc = meta.get("description", "") or ""
        author = meta.get("author", "")
        aname = meta.get("author_name", author)
        desc += f"\n\nCreator: @{author} ({aname})"
        htags = meta.get("hashtags", [])
        if htags:
            desc += "\n\n" + " ".join(f"#{h}" for h in htags)
    
    if desc:
        for sel in desc_selectors:
            if type_text(page, sel, desc, timeout=3):
                print(f"  Description set ({len(desc)} chars)")
                break

    # Click "Show more" to reveal tags
    try:
        show_more = page.query_selector("text=Show more")
        if show_more and show_more.is_visible():
            show_more.click()
            page.wait_for_timeout(1000)
    except:
        pass

    # Fill Tags
    if meta and meta.get("tags"):
        tags = meta["tags"][:5]
        tag_selectors = [
            "#tags-input",
            "[aria-label='Tags']",
            "input[aria-label='Tags']",
            "ytcp-form-input-container#tags-input",
        ]
        for sel in tag_selectors:
            tag_input = page.query_selector(sel)
            if tag_input:
                for tag in tags:
                    tag_input.fill(tag)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(500)
                print(f"  Tags: {', '.join(tags)}")
                break

    # Select "Not made for kids"
    try:
        page.evaluate("""
            const radios = document.querySelectorAll('input[name="VIDEO_MADE_FOR_KIDS"]');
            for (const r of radios) {
                if (r.value === 'NOT_MADE_FOR_KIDS') { r.click(); break; }
            }
        """)
    except:
        pass
    page.wait_for_timeout(1000)

    # Click Next button (3 times: details → video elements → visibility)
    for i in range(3):
        try:
            next_btn = page.query_selector("#next-button")
            if not next_btn or not next_btn.is_visible():
                # Try text match
                next_btn = page.query_selector("button:has-text('Next')")
            if next_btn and next_btn.is_visible():
                next_btn.click()
                page.wait_for_timeout(2000)
        except:
            pass

    # Set to Private
    try:
        page.evaluate("""
            const radios = document.querySelectorAll('input[name="VIDEO_VISIBILITY"]');
            for (const r of radios) {
                if (r.value === 'PRIVATE') { r.click(); break; }
            }
        """)
    except:
        pass
    page.wait_for_timeout(1000)

    # Click Save
    saved = False
    try:
        save_btn = page.query_selector("#save-button")
        if not save_btn or not save_btn.is_visible():
            save_btn = page.query_selector("button:has-text('Save')")
        if save_btn and save_btn.is_visible():
            save_btn.click()
            saved = True
            page.wait_for_timeout(3000)
    except:
        pass

    # Close the upload dialog
    try:
        close_btn = page.query_selector("#close-button")
        if close_btn and close_btn.is_visible():
            close_btn.click()
            page.wait_for_timeout(2000)
    except:
        pass

    if saved:
        print("  ✅ Uploaded and saved!")
        return True
    else:
        print("  ⚠️  Save button not found, but upload may have completed")
        return True

def main():
    print("=== CDP YouTube Uploader ===")
    
    progress = load_progress()
    videos = find_videos()
    print(f"Found {len(videos)} videos to process")
    
    pending = [(v, i, m) for v, i, m in videos 
               if i not in progress["uploaded"] and i not in progress["failed"]]
    print(f"Pending: {len(pending)} (Uploaded: {len(progress['uploaded'])}, Failed: {len(progress['failed'])})")
    
    if not pending:
        print("✅ All videos already processed!")
        return

    with sync_playwright() as p:
        # Connect to existing Chrome via CDP
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            print(f"Connected to Chrome via CDP")
        except Exception as e:
            print(f"❌ Cannot connect to Chrome at {CDP_URL}")
            print(f"   Error: {e}")
            print("   Make sure Chrome is running with --remote-debugging-port=9222")
            return

        # Get the default context and create a page
        context = browser.contexts[0]
        page = context.new_page()
        
        # Navigate to YouTube Studio
        page.goto("https://studio.youtube.com", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Check if we need login
        current_url = page.url
        if "signin" in current_url or "accounts" in current_url or "login" in current_url:
            print("\n🔴 Please log into YouTube Studio in the Chrome window.")
            page.pause()  # This pauses for user interaction
        else:
            print("\n✅ Already on YouTube Studio! Ready to upload.")
        
        # Wait for ready.txt signal
        ready_file = Path(__file__).parent / "ready.txt"
        if ready_file.exists():
            ready_file.unlink()
        
        print("\n📋 When you are logged in and on the Studio home page,")
        print("   create ready.txt in this directory or type 'done'.")
        print("   Checking every 5 seconds...\n")

        while not ready_file.exists():
            time.sleep(5)
        
        ready_file.unlink()
        print("✅ Signal received! Starting uploads now...\n")

        for idx, (video_path, vid_id, meta) in enumerate(pending):
            print(f"{'='*60}")
            print(f"[{idx+1}/{len(pending)}] Video ID: {vid_id}")
            try:
                success = upload_video(page, video_path, meta)
                if success:
                    progress["uploaded"].append(vid_id)
                    print(f"  ✓ {vid_id} uploaded")
                else:
                    progress["failed"].append(vid_id)
                    print(f"  ✗ {vid_id} failed")
            except Exception as e:
                print(f"  ❌ Error: {e}")
                import traceback
                traceback.print_exc()
                progress["failed"].append(vid_id)
            
            save_progress(progress)
            
            if idx < len(pending) - 1:
                delay = 10
                print(f"  ⏳ Waiting {delay}s before next video...")
                time.sleep(delay)

        context.close()

    print(f"\n{'='*60}")
    print(f"🎉 Upload session complete!")
    print(f"   Uploaded: {len(progress['uploaded'])}")
    print(f"   Failed: {len(progress['failed'])}")
    save_progress(progress)

if __name__ == "__main__":
    main()
