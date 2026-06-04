import csv
import json
import re
from pathlib import Path


def generate_youtube_metadata(tikwm_data: dict) -> dict:
    title = tikwm_data.get("title", "") or ""
    author = tikwm_data.get("author", {}) or {}
    author_id = author.get("unique_id", "unknown") if isinstance(author, dict) else "unknown"
    author_name = author.get("nickname", author_id) if isinstance(author, dict) else author_id
    music_raw = tikwm_data.get("music", "")
    if isinstance(music_raw, dict):
        music_title = music_raw.get("title", "")
    elif isinstance(music_raw, str) and not music_raw.startswith("http"):
        music_title = music_raw
    else:
        music_title = ""

    hashtags = re.findall(r"#(\w+)", title)

    clean_title = re.sub(r"#\S+\s*", "", title).strip()
    clean_title = re.sub(r"\s+", " ", clean_title).strip()
    clean_title = clean_title[:100]
    if not clean_title and hashtags:
        clean_title = " ".join(f"#{h}" for h in hashtags[:3])[:100]
    if not clean_title:
        clean_title = f"TikTok Video by @{author_id}"
    tags = list(dict.fromkeys([t.lower() for t in hashtags] + ["tiktok", "viral", "trending"]))

    desc_parts = [clean_title, ""]
    desc_parts.append(f"Creator: @{author_id} ({author_name})")
    if music_title:
        desc_parts.append(f"Music: {music_title}")
    desc_parts.append("")
    if hashtags:
        desc_parts.append(" ".join(f"#{h}" for h in hashtags))
    desc_parts.append("")
    desc_parts.append("Follow for more!")
    desc_parts.append(f"https://www.tiktok.com/@{author_id}")

    return {
        "title": clean_title,
        "description": "\n".join(desc_parts),
        "tags": tags,
        "author": author_id,
        "author_name": author_name,
        "music": music_title,
        "hashtags": hashtags,
    }


def save_video_metadata(video_path: Path, tikwm_data: dict):
    meta = generate_youtube_metadata(tikwm_data)
    meta_path = video_path.with_name(video_path.stem + "_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return meta_path


def save_batch_csv(task_dir: Path, all_metadata: list[dict]):
    if not all_metadata:
        return
    csv_path = task_dir / "youtube_upload.csv"
    fieldnames = ["filename", "title", "description", "tags", "author", "music"]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for m in all_metadata:
            w.writerow({
                "filename": m.get("filename", ""),
                "title": m.get("title", ""),
                "description": m.get("description", ""),
                "tags": ", ".join(m.get("tags", [])),
                "author": m.get("author", ""),
                "music": m.get("music", ""),
            })
