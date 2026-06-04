#!/usr/bin/env python3
"""
Batch YouTube Uploader for Hindi Dubbed Videos
Scans downloads directory for *_hindi.mp4 files and uploads them to YouTube
using metadata from corresponding JSON files, with 2-day scheduling between uploads.
"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

# Add the tiktok_downloader_web directory to path so we can import youtube_uploader
sys.path.insert(0, str(Path(__file__).parent / "tiktok_downloader_web"))

from youtube_uploader import upload_video

def find_hindi_videos_and_metadata(base_dir):
    """
    Find all Hindi dubbed videos and their corresponding metadata JSON files.
    
    Returns:
        list of tuples: (video_path, metadata_dict)
    """
    videos_to_upload = []
    base_path = Path(base_dir)
    
    # Find all *_hindi.mp4 files
    for hindi_video in base_path.rglob("*_hindi.mp4"):
        # Look for corresponding metadata JSON
        # The metadata JSON should be in the same directory as the original video
        # Original video name is the hindi video name without "_hindi"
        original_video_name = hindi_video.stem.replace("_hindi", "")
        metadata_file = hindi_video.parent / f"{original_video_name}_metadata.json"
        
        # If not found in same directory, check parent directories for task folders
        if not metadata_file.exists():
            # Check if we're in a dubbed subdirectory
            if "dubbed" in str(hindi_video):
                # Go up to find the task directory, then look for metadata there
                task_dir = hindi_video.parent.parent  # Remove /dubbed
                metadata_file = task_dir / f"{original_video_name}_metadata.json"
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                videos_to_upload.append((hindi_video, metadata))
                print(f"Found: {hindi_video.name} -> {metadata_file.name}")
            except Exception as e:
                print(f"Error reading metadata {metadata_file}: {e}")
        else:
            print(f"No metadata found for {hindi_video.name}")
    
    return videos_to_upload

def prepare_youtube_metadata(metadata):
    """
    Convert TikTok metadata to YouTube upload parameters.
    """
    # Use the title from metadata, or create a default one
    title = metadata.get("title", "").strip()
    if not title:
        # Fallback: use author and first few hashtags
        author = metadata.get("author", "unknown")
        hashtags = metadata.get("hashtags", [])[:3]
        if hashtags:
            title = f"{author} {' '.join([f'#{tag}' for tag in hashtags])}"
        else:
            title = f"TikTok Video by @{author}"
    
    # Limit title to 100 characters (YouTube limit)
    title = title[:100]
    
    # Build description
    description_parts = []
    
    # Add title/description from TikTok
    tiktok_desc = metadata.get("description", "").strip()
    if tiktok_desc:
        description_parts.append(tiktok_desc)
    
    # Add creator info
    author = metadata.get("author", "")
    author_name = metadata.get("author_name", author)
    if author:
        description_parts.append(f"Creator: @{author} ({author_name})")
    
    # Add music info if available
    music = metadata.get("music", "")
    if music:
        description_parts.append(f"Music: {music}")
    
    # Add hashtags
    hashtags = metadata.get("hashtags", [])
    if hashtags:
        description_parts.append("")  # Empty line
        description_parts.append(" ".join([f"#{tag}" for tag in hashtags]))
    
    # Add standard footer
    description_parts.append("")
    description_parts.append("Follow for more!")
    description_parts.append(f"https://www.tiktok.com/@{author}" if author else "https://www.tiktok.com/")
    
    description = "\n".join(description_parts)
    
    # Tags for YouTube (from hashtags + standard tags)
    tags = list(set([tag.lower() for tag in hashtags] + ["tiktok", "hindi", "dubbed", "viral", "trending"]))
    
    return {
        "title": title,
        "description": description,
        "tags": tags,
        "categoryId": "22",  # People & Blogs
        "privacyStatus": "private"  # Start as private for safety
    }

def upload_with_scheduling(videos_metadata_list):
    """
    Upload videos with 2-day gap between each upload.
    """
    total_videos = len(videos_metadata_list)
    print(f"Found {total_videos} Hindi dubbed videos to upload")
    
    if total_videos == 0:
        print("No videos found to upload.")
        return
    
    for i, (video_path, metadata) in enumerate(videos_metadata_list):
        print(f"\n[{i+1}/{total_videos}] Processing: {video_path.name}")
        
        # Prepare YouTube metadata
        yt_metadata = prepare_youtube_metadata(metadata)
        
        print(f"Title: {yt_metadata['title']}")
        print(f"Description preview: {yt_metadata['description'][:100]}...")
        
        try:
            # Upload to YouTube
            video_id = upload_video(
                file_path=str(video_path),
                title=yt_metadata['title'],
                description=yt_metadata['description'],
                category=yt_metadata['categoryId'],
                keywords=", ".join(yt_metadata['tags']),
                privacy_status=yt_metadata['privacyStatus']
            )
            
            print(f"✅ Upload successful! Video ID: {video_id}")
            print(f"   URL: https://www.youtube.com/watch?v={video_id}")
            
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            # Continue with next video even if this one fails
        
        # If this isn't the last video, wait 2 days before next upload
        if i < total_videos - 1:
            print(f"\n⏳ Waiting 2 days before next upload...")
            print(f"   Next upload scheduled for: {(datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Sleep for 2 days (in seconds)
            # Note: For testing, you might want to reduce this
            # time.sleep(2 * 24 * 60 * 60)  # 2 days in seconds
            
            # For immediate testing, use a shorter delay (e.g., 30 seconds)
            # Uncomment the line below for testing with short delays
            time.sleep(30)  # 30 seconds for testing
            
            # For production 2-day delay, use:
            # time.sleep(2 * 24 * 60 * 60)  # 2 days

def main():
    """
    Main function to scan for videos and initiate batch upload.
    """
    print("=== Super-App Hindi Dubbed Video YouTube Uploader ===")
    print("Scanning for *_hindi.mp4 videos and metadata JSON files...\n")
    
    # Base directory is the downloads folder
    downloads_dir = Path(__file__).parent / "downloads"
    
    if not downloads_dir.exists():
        print(f"Error: Downloads directory not found at {downloads_dir}")
        return 1
    
    # Find all videos and their metadata
    videos_metadata = find_hindi_videos_and_metadata(downloads_dir)
    
    if not videos_metadata:
        print("No Hindi dubbed videos with metadata found.")
        print("Make sure you have:")
        print("1. *_hindi.mp4 files in your downloads/task*/dubbed/ directories")
        print("2. Corresponding *_metadata.json files in the task directories")
        return 1
    
    # Ask for confirmation before starting
    print(f"\nFound {len(videos_metadata)} videos ready for upload.")
    response = input("Do you want to start the upload process? (y/N): ").strip().lower()
    
    if response != 'y' and response != 'yes':
        print("Upload cancelled.")
        return 0
    
    # Start uploading with scheduling
    upload_with_scheduling(videos_metadata)
    
    print("\n=== Upload process completed ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())