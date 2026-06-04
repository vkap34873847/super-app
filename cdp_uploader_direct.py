#!/usr/bin/env python3
import json, os, time, re, sys
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright

VIDEO_DIR = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/with_background_music")
META_DIR = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a")
PROGRESS_FILE = Path("/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/upload_progress.json")
CDP_URL = "http://localhost:9222"

def build_description(meta):
    raw_desc = meta.get('description', '') or ''
    lines = raw_desc.split('\n')
    clean_lines = []
    for line in lines:
        lower = line.lower()
        if 'tiktok.com' in lower or ('tiktok' in lower and len(line) < 50):
            continue
        if 'creator:' in lower:
            clean_lines.append('Creator: Fruit World')
            continue
        clean_lines.append(line)
    if not any('Creator: Fruit World' in l for l in clean_lines):
        clean_lines.append('Creator: Fruit World')
    htags = meta.get('hashtags', [])
    if htags:
        clean_lines.append('')
        clean_lines.append(' '.join('#' + h for h in htags))
    return '\n'.join(clean_lines)

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

def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"uploaded": [], "failed": []}

def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

def do_js(page, js):
    try:
        return page.evaluate(js)
    except:
        return None

def upload_one(page, video_path, meta, video_index):
    vid_name = video_path.name
    print(f"\n  >> {vid_name}")

    page.goto("https://studio.youtube.com", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    print(f"  On: Studio Dashboard")

    # Click Create
    do_js(page, "document.querySelector('[aria-label=Create]')?.click()")
    page.wait_for_timeout(1500)

    # Click Upload videos
    do_js(page, """
    (() => {
        var items = document.querySelectorAll('tp-yt-paper-item, [role=menuitem]');
        for (var i = 0; i < items.length; i++) {
            if (items[i].textContent.includes('Upload videos')) {
                items[i]?.click();
                return true;
            }
        }
        return false;
    })()
    """)
    page.wait_for_timeout(2000)

    # Select file
    page.set_input_files("input[type=file]", str(video_path.resolve()))
    print("  Uploading...", end="", flush=True)

    # Wait for processing
    ts = '[aria-label="Title"], #title-textarea'
    try:
        page.wait_for_selector(ts, timeout=600000)
        print(" processed!")
    except:
        print(" timeout")
        return False
    page.wait_for_timeout(2000)

    # Title (force=True bypasses dialog scrim)
    title = ((meta.get("title", "") or "")[:100] if meta else vid_name[:100])
    if title:
        page.locator(ts).first.click(force=True, timeout=10000)
        page.wait_for_timeout(300)
        page.keyboard.press("Meta+a")
        page.wait_for_timeout(200)
        page.keyboard.type(title, delay=10)
        print("  Title done")

    # Description
    desc = build_description(meta) if meta else ""
    if desc:
        ds = '[aria-label="Description"], #description-textarea'
        df = page.locator(ds).first
        if df.is_visible(timeout=5000):
            df.click(force=True)
            page.wait_for_timeout(300)
            page.keyboard.press("Meta+a")
            page.wait_for_timeout(200)
            page.keyboard.type(desc, delay=5)
            print("  Description done")

    # Tags - clear then add (max 500 chars)
    if meta and meta.get("tags"):
        do_js(page, """
        (() => {
            var chips = document.querySelectorAll('#tags-input .ytcp-chip, [aria-label="Tags"] .ytcp-chip');
            for (var i = chips.length - 1; i >= 0; i--) {
                var close = chips[i].querySelector('[aria-label="Remove"]');
                if (close) close.click();
            }
            return chips.length;
        })()
        """)
        page.wait_for_timeout(1000)
        skip_words = ['tiktok', 'viral', 'trending', 'fyp', 'foryou']
        raw_tags = [t for t in meta["tags"] if not any(w in t.lower() for w in skip_words)][:5]
        all_tags = []
        total_len = 0
        for t in raw_tags:
            tlen = len(t) + 1
            if total_len + tlen <= 500:
                all_tags.append(t)
                total_len += tlen
            else:
                break
        for tag in all_tags:
            do_js(page, f"""document.querySelector('[aria-label="Tags"], #tags-input').value = '{tag}'; document.querySelector('[aria-label="Tags"], #tags-input')?.dispatchEvent(new Event('input', {{bubbles:true}}))""")
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)
        print(f"  Tags: {len(all_tags)}")

    # Not made for kids
    do_js(page, """
    (() => {
        var r = document.querySelectorAll('input[name="VIDEO_MADE_FOR_KIDS"]');
        for (var i = 0; i < r.length; i++) {
            if (r[i].value === 'NOT_MADE_FOR_KIDS') { r[i].click(); return true; }
        }
        return false;
    })()
    """)
    page.wait_for_timeout(1000)

    # === NAVIGATE: Details → Video elements → Checks → Visibility ===
    sched_date = datetime.now() + timedelta(days=1 + video_index * 2)
    date_str = sched_date.strftime("%Y-%m-%d")
    time_str = "08:00"

    for step in range(4):  # max 4 Next clicks
        # Check if on Visibility page (has visibility radios)
        on_vis = do_js(page, "document.querySelectorAll('input[name=\"VIDEO_VISIBILITY\"]').length > 0")
        if on_vis:
            print("  Visibility page!")
            page.wait_for_timeout(500)
            # Select Schedule
            do_js(page, """
            (() => {
                var r = document.querySelectorAll('input[name="VIDEO_VISIBILITY"]');
                for (var i = 0; i < r.length; i++) {
                    if (r[i].value === 'SCHEDULE') { r[i].click(); return true; }
                }
                return false;
            })()
            """)
            page.wait_for_timeout(500)
            # Set date
            do_js(page, f"""
            (() => {{
                var d = document.querySelectorAll('input[type="date"]');
                for (var i = 0; i < d.length; i++) {{
                    d[i].value = '{date_str}';
                    d[i].dispatchEvent(new Event('input', {{bubbles: true}}));
                    d[i].dispatchEvent(new Event('change', {{bubbles: true}}));
                    return true;
                }}
                return false;
            }})()
            """)
            page.wait_for_timeout(300)
            # Set time
            do_js(page, f"""
            (() => {{
                var t = document.querySelectorAll('input[type="time"]');
                for (var i = 0; i < t.length; i++) {{
                    t[i].value = '{time_str}';
                    t[i].dispatchEvent(new Event('input', {{bubbles: true}}));
                    t[i].dispatchEvent(new Event('change', {{bubbles: true}}));
                    return true;
                }}
                return false;
            }})()
            """)
            page.wait_for_timeout(300)
            print(f"  Schedule: {date_str} {time_str}")
            # Save
            for a in range(5):
                s = do_js(page, """
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
                if s:
                    print("  Saved!")
                    break
                page.wait_for_timeout(500)
            page.wait_for_timeout(3000)
            # Close dialog
            do_js(page, """
            (() => {
                var b = document.querySelectorAll('#close-button, button[aria-label="Close"]');
                for (var i = 0; i < b.length; i++) {
                    if (b[i].offsetParent !== null) { b[i].click(); return true; }
                }
                return false;
            })()
            """)
            page.wait_for_timeout(2000)
            return True

        # Not on Visibility - click Next
        try:
            page.locator('#next-button').first.click(force=True, timeout=3000)
            print(f"  Next clicked ({step+1})")
            page.wait_for_timeout(2000)
        except:
            # Fallback: evaluate
            c = do_js(page, """
            (() => {
                var n = document.querySelector('#next-button');
                if (n && n.offsetParent !== null) { n.click(); return true; }
                var b = document.querySelectorAll('button');
                for (var i = 0; i < b.length; i++) {
                    if (b[i].offsetParent !== null && b[i].textContent.trim() === 'Next') {
                        b[i].click(); return true;
                    }
                }
                return false;
            })()
            """)
            if c:
                print(f"  Next clicked ({step+1}) [js]")
                page.wait_for_timeout(2000)
            else:
                print(f"  No Next button (step {step+1})")
                break

    print("  Done (save may have happened)")
    return True

def main():
    print("=== YouTube Uploader v2 ===")
    progress = load_progress()
    videos = find_videos()
    pending = [(v,i,m) for v,i,m in videos if i not in progress["uploaded"]]
    print(f"Total: {len(videos)}, Pending: {len(pending)}, Uploaded: {len(progress['uploaded'])}")
    if not pending:
        print("All done!")
        return

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]
        studio_page = None
        for pg in ctx.pages:
            if "studio.youtube.com" in pg.url:
                studio_page = pg
                break
        if not studio_page:
            studio_page = ctx.new_page()

        for idx, (vp, vid, meta) in enumerate(pending):
            print(f"\n{'='*60}")
            print(f"[{idx+1}/{len(pending)}] {vid}")
            try:
                ok = upload_one(studio_page, vp, meta, idx)
                if ok:
                    progress["uploaded"].append(vid)
                else:
                    progress.setdefault("failed", []).append(vid)
            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback; traceback.print_exc()
                progress.setdefault("failed", []).append(vid)
            save_progress(progress)
            if idx < len(pending)-1:
                print("  10s pause...")
                time.sleep(10)

    print(f"\nDone! Uploaded: {len(progress['uploaded'])}, Failed: {len(progress.get('failed', []))}")
    save_progress(progress)

if __name__ == "__main__":
    main()
