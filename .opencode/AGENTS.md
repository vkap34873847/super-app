## Goal
Build a mass TikTok downloader (CLI + web) with OpenCode/Ollama integration.

## Progress

### Done
- CLI TikTok downloader: `tiktok_downloader/downloader.py` using yt-dlp + tikwm.com API
- Flask web app: `tiktok_downloader_web/app.py` with Tailwind CSS frontend
- OpenCode installed at `/Users/B0338614/.opencode/bin/opencode`
- Ollama installed at `/usr/local/bin/ollama`, service running on :11434
- tinyllama model pulled (637MB)
- OpenCode launches with Ollama: `ollama launch opencode --model tinyllama`

### Known Issues
- TikTok connections blocked from this network (yt-dlp: "Connection timed out")
- Web app frontend buttons not responding ("nothing getting clicked")
- Port 5000 occupied (Chrome was using it), web app on port 5001
- OpenCode PATH not set in default shell (binary at ~/.opencode/bin/opencode)
- `opencode run "message" -m ollama/tinyllama` fails with "Session not found" (need to use `ollama launch` instead)

### Key Commands
- Launch OpenCode with local Ollama: `ollama launch opencode --model tinyllama`
- Start Ollama: `ollama serve`
- List Ollama models: `ollama list`
- Start web app: `python tiktok_downloader_web/app.py`
- Run CLI: `python tiktok_downloader/downloader.py <url>`

### Relevant Files
- `tiktok_downloader_web/app.py`: Flask backend
- `tiktok_downloader_web/templates/index.html`: Web UI
- `tiktok_downloader/downloader.py`: CLI downloader
