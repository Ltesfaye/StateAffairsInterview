#!/usr/bin/env python3
"""Reset invalid downloads and test the fix"""

import sys
from pathlib import Path
from src.database.db_manager import get_db_manager

def reset_invalid_downloads():
    """Reset videos with invalid files back to pending"""
    db = get_db_manager('./data/database/videos.db')
    all_videos = db.get_all_videos()
    
    print(f"Found {len(all_videos)} total videos in database")
    
    reset_count = 0
    for video in all_videos:
        # Reset videos that are marked as downloaded or failed but have invalid files
        if video.download_status in ("downloaded", "failed"):
            if video.download_path:
                file_path = Path(video.download_path)
                # Check if file is invalid (doesn't exist or is too small)
                if not file_path.exists():
                    print(f"Resetting {video.id} ({video.source}): file missing (status: {video.download_status})")
                    db.update_download_status(video.id, video.source, "pending", None)
                    reset_count += 1
                elif file_path.stat().st_size < 10000:  # Less than 10KB is invalid
                    print(f"Resetting {video.id} ({video.source}): file size {file_path.stat().st_size} bytes (status: {video.download_status})")
                    db.update_download_status(video.id, video.source, "pending", None)
                    try:
                        file_path.unlink()  # Delete invalid file
                    except:
                        pass
                    reset_count += 1
            elif video.download_status == "failed":
                # Reset failed videos without paths
                print(f"Resetting {video.id} ({video.source}): failed status, no path")
                db.update_download_status(video.id, video.source, "pending", None)
                reset_count += 1
    
    print(f"\nReset {reset_count} invalid downloads back to pending status")
    return reset_count

if __name__ == "__main__":
    reset_invalid_downloads()

