// upload_videos_mcp.js
// Automates uploading Hindi‑dubbed videos (with background music) to YouTube Studio via Chrome DevTools MCP.
// This version runs headless‑style: it does NOT pause for user input between videos.

const { spawn } = require('child_process');
const fetch = require('node-fetch');
const fs = require('fs');
const path = require('path');

// ------------------------------------------------------------------
// CONFIGURATION – edit if you move folders
// ------------------------------------------------------------------
const VIDEO_DIR = '/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a/with_background_music';
const META_DIR  = '/Users/B0338614/Desktop/Programming /super-app/downloads/14_5ba5429a';
const MCP_PORT = 9222; // default MCP port

// ------------------------------------------------------------------
// Launch Chrome‑DevTools‑MCP (unsandboxed)
// ------------------------------------------------------------------
// Launch MCP is optional – we assume an MCP server is already running.
function launchMCP() {
  // No operation; return a dummy child process placeholder.
  const dummy = require('child_process').spawn('sleep', ['0']);
  return dummy;
}

let rpcId = 1;
async function mcpCall(method, params = {}) {
  const payload = { jsonrpc: '2.0', id: rpcId++, method, params };
  const res = await fetch(`http://localhost:${MCP_PORT}/jsonrpc`, {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'Content-Type': 'application/json' },
  });
  const json = await res.json();
  if (json.error) throw new Error(JSON.stringify(json.error));
  return json.result;
}

async function click(selector) {
  await mcpCall('evaluate_script', { pageId, expression: `document.querySelector(${JSON.stringify(selector)})?.click();` });
  await new Promise(r => setTimeout(r, 1500));
}

async function setFileInput(selector, files) {
  const node = await mcpCall('evaluate_script', { pageId, expression: `document.querySelector(${JSON.stringify(selector)})` });
  const nodeId = node.nodeId;
  await mcpCall('set_file_input_files', { pageId, nodeId, files });
  await new Promise(r => setTimeout(r, 3000));
}

(async () => {
  console.log('🔧 Launching Chrome with remote debugging...');
  const chromeProc = spawn('open', ['-a', 'Google Chrome', '--args', '--remote-debugging-port=9222'], { detached: true, stdio: 'ignore' });
  console.log('🚀 Connecting to existing Chrome‑DevTools‑MCP…');
  // Initial pause to give MCP server time to start (Chrome needs a moment).
  await new Promise(r => setTimeout(r, 10000)); // 30 seconds
  // Ensure MCP is ready – retry connection up to 20 times with exponential backoff.
  let connected = false;
  for (let attempt = 1; attempt <= 20 && !connected; attempt++) {
    try {
      await new Promise(r => setTimeout(r, attempt * 3000)); // backoff: 3s,6s,9s,...
      // Verify MCP is responding and has at least one target (browser).
      const targets = await mcpCall('list_targets');
      if (Array.isArray(targets) && targets.length > 0) {
        connected = true;
      } else {
        throw new Error('No targets yet');
      }
    } catch (e) {
      console.warn(`⚠️ MCP not ready (attempt ${attempt}), retrying...`);
    }
  }
  if (!connected) {
    console.error('❌ Unable to connect to MCP after multiple attempts. Exiting.');
    process.exit(1);
  }
  // Create a fresh page for the upload workflow.
  const pageId = await mcpCall('new_page', { url: 'about:blank' });
  console.log('🗒️ Page ID:', pageId);

  // Navigate to YouTube Studio – assume you are already logged in.
  await mcpCall('navigate_page', { pageId, url: 'https://studio.youtube.com' });
  console.log('🔗 Opened YouTube Studio – waiting for UI to settle…');
  await new Promise(r => setTimeout(r, 25000)); // 25 s for any login / load

  const videos = fs.readdirSync(VIDEO_DIR).filter(f => f.endsWith('_hindi.mp4'));

  for (const vid of videos) {
    const videoPath = path.join(VIDEO_DIR, vid);
    const baseId = vid.replace('_hindi.mp4', ''); // numeric part
    const metaPath = path.join(META_DIR, `${baseId}_metadata.json`);
    let meta = {};
    if (fs.existsSync(metaPath)) {
      try { meta = JSON.parse(fs.readFileSync(metaPath, 'utf8')); } catch (_) { console.warn('⚠️ Bad JSON for', metaPath); }
    } else {
      console.warn('⚠️ No metadata for', vid);
    }

    console.log(`📤 Uploading ${vid}`);

    // 1️⃣ Click Create → Upload videos
    await click('tp-yt-paper-button#create-button'); // top‑right "Create" button
    await click('ytcp-button[aria-label="Upload videos"]'); // menu item

    // 2️⃣ Choose the file via hidden input
    await setFileInput('input[type="file"]', [videoPath]);

    // 3️⃣ Wait for the edit panel to appear
    await new Promise(r => setTimeout(r, 8000));

    // 4️⃣ Fill title, description, tags, privacy
    if (meta.title) {
      await mcpCall('evaluate_script', { pageId, expression: `document.querySelector('input#title')?.value = ${JSON.stringify(meta.title)};` });
    }
    if (meta.description) {
      await mcpCall('evaluate_script', { pageId, expression: `document.querySelector('textarea#description')?.value = ${JSON.stringify(meta.description)};` });
    }
    if (meta.tags && Array.isArray(meta.tags)) {
      await mcpCall('evaluate_script', { pageId, expression: `document.querySelector('input#tags')?.value = ${JSON.stringify(meta.tags.join(', '))};` });
    }
    const privacy = meta.privacyStatus || 'private';
    await mcpCall('evaluate_script', { pageId, expression: `Array.from(document.querySelectorAll('tp-yt-paper-radio-button')).find(b=>b.value==='${privacy}')?.click();` });

    // 5️⃣ Click Done / Publish
    await click('ytcp-button#done-button');

    console.log('✅ Uploaded – waiting for processing (≈30 s)');
    await new Promise(r => setTimeout(r, 30000));
    // No manual pause – continue to next video automatically
  }

  console.log('🎉 All videos uploaded. Closing page.');
  await mcpCall('close_page', { pageId });
// No MCP process to kill (handled externally)
})();
