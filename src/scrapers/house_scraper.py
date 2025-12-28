"""House archive scraper"""

import re
import urllib3
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper
from ..models import VideoMetadata
from ..utils import parse_house_date, get_logger

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = get_logger(__name__)


class HouseScraper(BaseScraper):
    """Scraper for Michigan House archive"""
    
    def __init__(self, archive_url: str = "https://house.mi.gov/VideoArchive"):
        """Initialize House scraper"""
        self.archive_url = archive_url
        self.base_url = "https://house.mi.gov"
    
    def discover_videos(
        self,
        cutoff_date: datetime,
        limit: Optional[int] = None,
    ) -> List[VideoMetadata]:
        """Discover videos from House archive"""
        logger.info(f"Discovering videos from House archive after {cutoff_date.date()}")
        
        try:
            # Fetch the archive page
            # Note: verify=False is used here due to SSL certificate issues on some systems
            # In production, you may want to fix SSL certificates or use verify=True
            response = requests.get(
                self.archive_url,
                timeout=30,
                verify=False,  # Disable SSL verification (fix certificates in production)
            )
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Find all committee sections
            videos = []
            committee_items = soup.find_all("li")
            
            for item in committee_items:
                # Find committee name and video count
                strong_tag = item.find("strong")
                if not strong_tag:
                    continue
                
                committee_text = strong_tag.get_text(strip=True)
                committee_name = committee_text.split("|")[0].strip()
                
                # Find video links in this committee
                video_links = item.find_all("a", href=True)
                
                for link in video_links:
                    href = link.get("href", "")
                    link_text = link.get_text(strip=True)
                    
                    # Check if this is a video link
                    if "/VideoArchivePlayer?video=" in href:
                        video = self._parse_video_link(
                            href=href,
                            link_text=link_text,
                            committee=committee_name,
                            cutoff_date=cutoff_date,
                        )
                        
                        if video:
                            videos.append(video)
                            
                            if limit and len(videos) >= limit:
                                break
                
                if limit and len(videos) >= limit:
                    break
            
            logger.info(f"Discovered {len(videos)} videos from House archive")
            return videos
            
        except Exception as e:
            logger.error(f"Error discovering House videos: {e}", exc_info=True)
            return []
    
    def _parse_video_link(
        self,
        href: str,
        link_text: str,
        committee: str,
        cutoff_date: datetime,
    ) -> Optional[VideoMetadata]:
        """Parse a video link into VideoMetadata"""
        try:
            # Extract video filename from URL
            # Format: /VideoArchivePlayer?video=HAGRI-022025.mp4
            match = re.search(r"video=([^&]+)", href)
            if not match:
                return None
            
            filename = match.group(1)
            video_id = filename.replace(".mp4", "")
            
            # Parse date from link text
            # Format: "Thursday, February 20, 2025"
            date_recorded = parse_house_date(link_text)
            if not date_recorded:
                logger.warning(f"Could not parse date from: {link_text}")
                return None
            
            # Filter by cutoff date
            if date_recorded < cutoff_date:
                return None
            
            # Construct full URL
            video_url = urljoin(self.base_url, href)
            
            # Extract committee code from filename (e.g., HAGRI from HAGRI-022025.mp4)
            committee_code = filename.split("-")[0] if "-" in filename else None
            
            return VideoMetadata(
                video_id=video_id,
                source="house",
                filename=filename,
                url=video_url,
                date_recorded=date_recorded,
                committee=committee,
                title=f"{committee} - {link_text}",
            )
            
        except Exception as e:
            logger.error(f"Error parsing video link {href}: {e}", exc_info=True)
            return None

