#!/usr/bin/env python3
"""
Schedule all uploaded Private videos from YouTube Studio Content page
"""
import json, os, time, re, sys
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright

META_DIR = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a")
PROGRESS_FILE = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/upload_progress.json")
SCHEDULE_PROGRESS = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/schedule_progress.json")
CDP_URL = "http://localhost:9222"

def get_titles(video_ids):
    titles = []
    for vid in video_ids:
        meta_file = META_DIR / f"{vid}_metadata.json"
        if meta_file.exists():
            with open(meta_file) as f:
                meta = json.load(f)
            titles.append(meta.get("title", "") or vid)
        else:
            titles.append(vid)
    return titles

def schedule_one(page, title, date_str, time_str, vid_id):
    print(f"\n  Scheduling: {title[:50]}... -> {date_str}")
    
    # Go to Content page
    page.goto("https://studio.youtube.com/channel/UCjOW_FRr1ZJ5rjo_3kg4Nqg/videos", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    
    # Search for the video by title
    search_sel = '#search-input, [aria-label="Search"], input[aria-label="Search"], input[placeholder*="Search"]'
    try:
        search_box = page.locator(search_sel).first
        search_box.click(force=True, timeout=5000)
        page.wait_for_timeout(500)
        page.keyboard.press("Meta+a")
        page.keyboard.type(title, delay=10)
        page.wait_for_timeout(2000)
    except:
        print("  Search box not found")
        return False
    
    # Check if video appears in results
    page.wait_for_timeout(2000)
    
    # Find the video row and click visibility
    visibility_clicked = False
    
    # Try clicking the visibility badge/label
    try:
        # The visibility label might say "Private", "Public", etc.
        visibility = page.locator("text=Private").first
        if visibility.is_visible(timeout=3000):
            visibility.click(force=True)
            visibility_clicked = True
            print("  Clicked Private badge")
    except:
        pass
    
    if not visibility_clicked:
        try:
            # Try ytcp-video-cell-visibility or similar
            cell = page.locator("ytcp-video-cell-visibility, [test-id='video-cell-visibility']").first
            if cell.is_visible(timeout=3000):
                cell.click(force=True)
                visibility_clicked = True
                print("  Clicked visibility cell")
        except:
            pass
    
    if not visibility_clicked:
        print("  Could not find visibility control")
        # Take screenshot for debugging
        page.screenshot(path="/tmp/sched_debug.png")
        return False
    
    page.wait_for_timeout(2000)
    
    # Now the visibility dialog should be open
    # Select Schedule
    sched_clicked = page.evaluate("""
    (() => {
        var radios = document.querySelectorAll('input[name="VIDEO_VISIBILITY"]');
        for (var i = 0; i < radios.length; i++) {
            if (radios[i].value === 'SCHEDULE' || radios[i].value === 'schedule') {
                radios[i].click();
                return true;
            }
        }
        // Try labels
        var labels = document.querySelectorAll('label, span, div, tp-yt-paper-radio-button');
        for (var i = 0; i < labels.length; i++) {
            if (labels[i].textContent.trim().toLowerCase() === 'schedule') {
                labels[i].click();
                return true;
            }
        }
        return false;
    })()
    """)
    print(f"  Schedule selected: {sched_clicked}")
    page.wait_for_timeout(1000)
    
    # Set date
    page.evaluate(f"""
    (() => {{
        var inputs = document.querySelectorAll('input[type="date"]');
        for (var i = 0; i < inputs.length; i++) {{
            inputs[i].value = '{date_str}';
            inputs[i].dispatchEvent(new Event('input', {{bubbles: true}}));
            inputs[i].dispatchEvent(new Event('change', {{bubbles: true}}));
            return true;
        }}
        return false;
    }})()
    """)
    page.wait_for_timeout(500)
    
    # Set time
    page.evaluate(f"""
    (() => {{
        var inputs = document.querySelectorAll('input[type="time"]');
        for (var i = 0; i < inputs.length; i++) {{
            inputs[i].value = '{time_str}';
            inputs[i].dispatchEvent(new Event('input', {{bubbles: true}}));
            inputs[i].dispatchEvent(new Event('change', {{bubbles: true}}));
            return true;
        }}
        return false;
    }})()
    """)
    page.wait_for_timeout(500)
    print(f"  Date/time set")
    
    # Save/Schedule button
    saved = False
    for a in range(5):
        done = page.evaluate("""
        (() => {
            var b = document.querySelectorAll('#save-button, button');
            for (var i = 0; i < b.length; i++) {
                if (b[i].offsetParent === null) continue;
                var txt = b[i].textContent.trim().toLowerCase();
                if (b[i].id === 'save-button' || txt === 'save' || txt === 'schedule') {
                    b[i].click(); return true;
                }
            }
            return false;
        })()
        """)
        if done:
            saved = True
            break
        page.wait_for_timeout(500)
    
    page.wait_for_timeout(2000)
    if saved:
        print(f"  Scheduled!")
        return True
    print("  Done")
    return True

def main():
    print("=== Schedule Videos from Content ===")
    
    # Load uploaded videos (in order)
    if not PROGRESS_FILE.exists():
        print("No upload progress found")
        return
    with open(PROGRESS_FILE) as f:
        progress = json.load(f)
    
    video_ids = progress.get("uploaded", [])
    if not video_ids:
        print("No videos to schedule")
        return
    
    # Load scheduling progress
    scheduled = []
    if SCHEDULE_PROGRESS.exists():
        with open(SCHEDULE_PROGRESS) as f:
            sp = json.load(f)
            scheduled = sp.get("scheduled", [])
    
    pending = [(vid, idx) for idx, vid in enumerate(video_ids) if vid not in scheduled]
    print(f"Total uploaded: {len(video_ids)}, Already scheduled: {len(scheduled)}, Pending: {len(pending)}")
    
    if not pending:
        print("All videos already scheduled!")
        return
    
    titles = get_titles([v for v, _ in pending])
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        print("Connected to Chrome")
        
        for (vid, orig_idx), title in zip(pending, titles):
            # Calculate schedule date: tomorrow + (orig_idx * 2 days)
            sched_date = datetime.now() + timedelta(days=1 + orig_idx * 2)
            date_str = sched_date.strftime("%Y-%m-%d")
            time_str = "08:00"
            
            print(f"\n{'='*60}")
            print(f"[Video {orig_idx+1}/{len(video_ids)}] {vid}")
            
            try:
                ok = schedule_one(page, title, date_str, time_str, vid)
                if ok:
                    scheduled.append(vid)
                    with open(SCHEDULE_PROGRESS, "w") as f:
                        json.dump({"scheduled": scheduled}, f, indent=2)
            except Exception as e:
                print(f"  Error: {e}")
                import traceback
                traceback.print_exc()
            
            if len(scheduled) < len(video_ids):
                print("  5s pause...")
                time.sleep(5)
        
        ctx.close()
    
    print(f"\nDone! Scheduled: {len(scheduled)}")

if __name__ == "__main__":
    main()
