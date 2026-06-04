#!/usr/bin/env python3
import sys, json
from playwright.sync_api import sync_playwright

VID = '/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/with_background_music/7622766236874689805_hindi.mp4'
META = '/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/7622766236874689805_metadata.json'
with open(META) as f:
    meta = json.load(f)

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    ctx = browser.contexts[0]
    page = ctx.new_page()
    print('Connected', flush=True)

    page.goto('https://studio.youtube.com', wait_until='domcontentloaded')
    page.wait_for_timeout(2000)
    print('Studio loaded', flush=True)

    page.evaluate("document.querySelector('[aria-label=Create]').click()")
    page.wait_for_timeout(1500)
    print('Clicked Create', flush=True)

    page.evaluate("""
    (() => {
        var items = document.querySelectorAll('tp-yt-paper-item, [role=menuitem]');
        for (var i = 0; i < items.length; i++) {
            if (items[i].textContent.includes('Upload videos')) {
                items[i].click();
                return true;
            }
        }
        return false;
    })()
    """)
    page.wait_for_timeout(2000)
    print('Clicked Upload videos', flush=True)

    page.set_input_files('input[type=file]', VID)
    print('File selected', flush=True)

    title_sel = '[aria-label="Title"], #title-textarea'
    try:
        page.wait_for_selector(title_sel, timeout=600000)
        print('Upload processed!', flush=True)
    except:
        print('Timeout waiting for upload', flush=True)
        ctx.close()
        exit()
    page.wait_for_timeout(3000)

    title = (meta.get('title', '') or '')[:100]
    if title:
        el = page.locator(title_sel).first
        el.click()
        page.wait_for_timeout(500)
        page.keyboard.press('Meta+a')
        page.wait_for_timeout(200)
        page.keyboard.type(title, delay=15)
        print('Title filled', flush=True)

    raw_desc = meta.get('description', '') or ''
    lines = raw_desc.split('\n')
    clean_lines = []
    for line in lines:
        lower = line.lower()
        if 'tiktok.com' in lower or 'tiktok' in lower and len(line) < 50:
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
    desc = '\n'.join(clean_lines)
    desc_sel = '[aria-label="Description"], #description-textarea'
    df = page.locator(desc_sel).first
    if df.is_visible(timeout=3000):
        df.click()
        page.wait_for_timeout(500)
        page.keyboard.press('Meta+a')
        page.wait_for_timeout(200)
        page.keyboard.type(desc, delay=10)
        print('Description filled', flush=True)

    print('SUCCESS!', flush=True)
    ctx.close()
