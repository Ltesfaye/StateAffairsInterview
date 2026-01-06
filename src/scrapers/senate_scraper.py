"""Senate archive scraper"""

import json
import re
import urllib3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

import requests

from .base_scraper import BaseScraper
from ..models import VideoMetadata
from ..utils import parse_senate_date, get_logger

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = get_logger(__name__)

# Debug log path
DEBUG_LOG_PATH = Path("/Users/leultesfaye/Desktop/StateAffair-Interview/.cursor/debug.log")


class SenateScraper(BaseScraper):
    """Scraper for Michigan Senate archive"""
    
    def __init__(
        self,
        api_url: str = "https://2kbyogxrg4.execute-api.us-west-2.amazonaws.com/61b3adc8124d7d000891ca5c/home/recent",
    ):
        """Initialize Senate scraper"""
        self.api_url = api_url
    
    def discover_videos(
        self,
        cutoff_date: datetime,
        limit: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[VideoMetadata]:
        """Discover videos from Senate archive"""
        # Determine date filtering approach
        if start_date and end_date:
            logger.info(f"Discovering videos from Senate archive between {start_date.date()} and {end_date.date()}")
            use_date_range = True
        else:
            logger.info(f"Discovering videos from Senate archive after {cutoff_date.date()}")
            use_date_range = False
        
        try:
            # Call API to get all videos
            # Note: verify=False is used here due to SSL certificate issues on some systems
            # The API requires browser-like headers to return data
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Origin': 'https://cloud.castus.tv',
                'Referer': 'https://cloud.castus.tv/vod/misenate/',
            }
            response = requests.get(
                self.api_url,
                headers=headers,
                timeout=30,
                verify=False,  # Disable SSL verification (fix certificates in production)
            )
            
            response.raise_for_status()
            
            data = response.json()
            
            response.raise_for_status()
            
            # Parse response (structure may vary, adjust as needed)
            videos = []
            video_list = self._extract_video_list(data)
            
            # #region agent log
            try:
                with open(DEBUG_LOG_PATH, "a") as f:
                    f.write(json.dumps({
                        "sessionId": "senate-api-debug",
                        "runId": "post-fix",
                        "hypothesisId": "E",
                        "location": "senate_scraper.py:100",
                        "message": "Extracted video list",
                        "data": {
                            "video_list_length": len(video_list),
                            "first_item_keys": list(video_list[0].keys()) if video_list and isinstance(video_list[0], dict) else "no_items",
                            "first_item_sample": str(video_list[0])[:300] if video_list else "empty"
                        },
                        "timestamp": int(datetime.now().timestamp() * 1000)
                    }) + "\n")
            except: pass
            # #endregion
            
            if not video_list:
                logger.warning(
                    f"Senate API returned empty video list. "
                    f"Response structure: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}. "
                    f"This may indicate the API requires authentication or different parameters."
                )
            
            for video_data in video_list:
                if use_date_range:
                    video = self._parse_video_data(
                        video_data=video_data,
                        cutoff_date=cutoff_date,  # Used as fallback
                        start_date=start_date,
                        end_date=end_date,
                    )
                else:
                    video = self._parse_video_data(
                        video_data=video_data,
                        cutoff_date=cutoff_date,
                    )
                
                if video:
                    videos.append(video)
                    
                    if limit and len(videos) >= limit:
                        break
            
            logger.info(f"Discovered {len(videos)} videos from Senate archive")
            return videos
            
        except Exception as e:
            logger.error(f"Error discovering Senate videos: {e}", exc_info=True)
            return []
    
    def _extract_video_list(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract video list from API response"""
        # API response structure: {'record': ..., 'allFiles': [...], 'count': ...}
        # Videos are in 'allFiles'
        
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Try common keys (order matters - check allFiles first as it's the actual key)
            for key in ["allFiles", "items", "videos", "results", "data"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
            # If no list found, return empty
            return []
        else:
            return []
    
    def _parse_video_data(
        self,
        video_data: Dict[str, Any],
        cutoff_date: datetime,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Optional[VideoMetadata]:
        """Parse video data from API response into VideoMetadata"""
        try:
            # Extract video ID (API uses _id)
            video_id = video_data.get("_id") or video_data.get("id") or ""
            
            if not video_id:
                return None
            
            # Extract title from metadata or search
            metadata = video_data.get("metadata", {})
            title = (
                metadata.get("title") if isinstance(metadata, dict) else None
            ) or video_data.get("title") or video_data.get("name") or ""
            
            # Extract date - API provides 'date' field in ISO format
            date_string = video_data.get("date") or video_data.get("original_date")
            if date_string:
                try:
                    # Parse ISO format date: "2025-12-23T17:01:05.730Z"
                    from dateutil import parser as date_parser
                    date_recorded = date_parser.parse(date_string)
                except:
                    date_recorded = parse_senate_date(str(date_string))
            else:
                date_recorded = None
            
            if not date_recorded:
                logger.warning(f"Could not parse date from: {date_string}")
                return None
            
            # Apply date filtering
            if start_date and end_date:
                # Date range filtering
                # Normalize timezones for comparison - make all aware or all naive
                from datetime import timezone
                
                # Normalize date_recorded
                if date_recorded.tzinfo is None:
                    date_to_compare = date_recorded.replace(tzinfo=timezone.utc)
                else:
                    date_to_compare = date_recorded
                
                # Normalize start_date
                if start_date.tzinfo is None:
                    start_date_normalized = start_date.replace(tzinfo=timezone.utc)
                else:
                    start_date_normalized = start_date
                
                # Normalize end_date
                if end_date.tzinfo is None:
                    end_date_normalized = end_date.replace(tzinfo=timezone.utc)
                else:
                    end_date_normalized = end_date
                
                # Filter by date range
                if not (start_date_normalized <= date_to_compare <= end_date_normalized):
                    return None
            else:
                # Cutoff date filtering (backward compatible)
                # Normalize timezones for comparison
                if date_recorded.tzinfo is not None and cutoff_date.tzinfo is None:
                    # date_recorded is aware, cutoff_date is naive - make cutoff_date aware (UTC)
                    from datetime import timezone
                    cutoff_date_aware = cutoff_date.replace(tzinfo=timezone.utc)
                    date_to_compare = date_recorded
                elif date_recorded.tzinfo is None and cutoff_date.tzinfo is not None:
                    # date_recorded is naive, cutoff_date is aware - make date_recorded aware (UTC)
                    from datetime import timezone
                    date_to_compare = date_recorded.replace(tzinfo=timezone.utc)
                    cutoff_date_aware = cutoff_date
                else:
                    # Both same type, use as-is
                    date_to_compare = date_recorded
                    cutoff_date_aware = cutoff_date
                
                # Filter by cutoff date
                if date_to_compare < cutoff_date_aware:
                    return None
            
            # Extract video URL - resolve using the pattern or API
            stream_url = self._construct_cloudfront_url(str(video_id))
            player_url = f"https://cloud.castus.tv/vod/misenate/video/{video_id}"
            
            # Extract committee/playlist from agenda or metadata
            agenda = video_data.get("agenda", {})
            committee = None
            if isinstance(agenda, dict):
                committee = agenda.get("name") or agenda.get("title")
            if not committee and isinstance(metadata, dict):
                committee = metadata.get("committee") or metadata.get("playlist")
            
            # Extract filename
            filename = f"{video_id}.mp4"
            
            return VideoMetadata(
                video_id=str(video_id),
                source="senate",
                filename=filename,
                url=player_url,
                stream_url=stream_url,
                date_recorded=date_recorded,
                committee=committee,
                title=title,
            )
        except Exception as e:
            logger.error(f"Error parsing video data: {e}", exc_info=True)
            return None

    def resolve_stream_url(self, video: VideoMetadata) -> Optional[str]:
        """Resolve the Senate stream URL (already handled during discovery, but added for consistency)"""
        return self._construct_cloudfront_url(video.video_id)

    def _construct_cloudfront_url(self, video_id: str) -> str:
        """Resolve the actual stream URL using the Castus API"""
        # Primary resolution method: Call the Castus upload/get API
        # This matches the logic used by the web player
        try:
            url = "https://imd0mxanj2.execute-api.us-west-2.amazonaws.com/upload/get"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Content-Type': 'application/json',
                'Referer': 'https://cloud.castus.tv/vod/misenate/',
                'Origin': 'https://cloud.castus.tv'
            }
            data = {
                "file": video_id,
                "type": "HLS",
                "user": "61b3adc8124d7d000891ca5c" # Michigan Senate Org ID
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=10, verify=False)
            if response.status_code == 200:
                res_data = response.json()
                stream_url = res_data.get("response", {}).get("payload", {}).get("data")
                if stream_url:
                    # Clean up any query parameters
                    return stream_url.split("?")[0]
        except Exception as e:
            logger.warning(f"Failed to resolve Senate stream via API: {e}")

        # Fallback to the discovered pattern if API fails
        base_url = "https://dlttx48mxf9m3.cloudfront.net/outputs"
        return f"{base_url}/{video_id}/Default/HLS/out.m3u8"

