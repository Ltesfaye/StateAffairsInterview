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
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[VideoMetadata]:
        """Discover videos from House archive"""
        # Determine date range for filtering
        if start_date and end_date:
            logger.info(f"Discovering videos from House archive between {start_date.date()} and {end_date.date()}")
            filter_start = start_date
            filter_end = end_date
        else:
            logger.info(f"Discovering videos from House archive after {cutoff_date.date()}")
            filter_start = cutoff_date
            filter_end = None
        
        try:
            # Calculate which years to fetch based on date range
            if filter_end:
                years_to_fetch = list(range(filter_start.year, filter_end.year + 1))
            else:
                years_to_fetch = list(range(filter_start.year, datetime.now().year + 1))
            
            logger.info(f"Fetching House archive for years: {years_to_fetch}")
            
            all_videos = []
            
            # Fetch each year's archive
            for year in years_to_fetch:
                try:
                    html_content = self._fetch_archive_for_year(year)
                    if html_content:
                        year_videos = self._parse_archive_html(html_content, filter_start, filter_end, limit, len(all_videos))
                        all_videos.extend(year_videos)
                        
                        if limit and len(all_videos) >= limit:
                            break
                except Exception as e:
                    logger.warning(f"Failed to fetch archive for year {year}: {e}")
                    continue
            
            # Apply final date filtering
            if filter_end:
                filtered_videos = [
                    v for v in all_videos
                    if filter_start <= v.date_recorded <= filter_end
                ]
            else:
                filtered_videos = [
                    v for v in all_videos
                    if v.date_recorded >= filter_start
                ]
            
            # Apply limit if specified
            if limit and len(filtered_videos) > limit:
                filtered_videos = filtered_videos[:limit]
            
            logger.info(f"Discovered {len(filtered_videos)} videos from House archive")
            return filtered_videos
            
        except Exception as e:
            logger.error(f"Error discovering House videos: {e}", exc_info=True)
            return []
    
    def _fetch_archive_for_year(self, year: int) -> Optional[str]:
        """Fetch archive HTML for a specific year using handler endpoint"""
        try:
            handler_url = f"{self.archive_url}?handler=ArchiveVideoPartial&Year={year}&Type=All&Date="
            logger.debug(f"Fetching House archive for year {year}: {handler_url}")
            
            response = requests.get(
                handler_url,
                timeout=30,
                verify=False,  # Disable SSL verification (fix certificates in production)
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            response.raise_for_status()
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error fetching archive for year {year}: {e}", exc_info=True)
            return None
    
    def _parse_archive_html(
        self,
        html_content: str,
        filter_start: datetime,
        filter_end: Optional[datetime],
        limit: Optional[int],
        current_count: int,
    ) -> List[VideoMetadata]:
        """Parse HTML content and extract video metadata"""
        soup = BeautifulSoup(html_content, "html.parser")
        videos = []
        
        # Find all committee sections
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
                        cutoff_date=filter_start,
                    )
                    
                    if video:
                        # Apply end date filter if specified
                        if filter_end and video.date_recorded > filter_end:
                            continue
                        
                        videos.append(video)
                        
                        if limit and (current_count + len(videos)) >= limit:
                            break
            
            if limit and (current_count + len(videos)) >= limit:
                break
        
        return videos
    
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
            
            # Filter by cutoff date (basic filter, more filtering happens in discover_videos)
            if date_recorded < cutoff_date:
                return None
            
            # Construct full URL
            video_url = urljoin(self.base_url, href)
            
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

    def resolve_stream_url(self, video: VideoMetadata) -> Optional[str]:
        """Resolve the final stream URL for House videos - direct MP4 URL"""
        try:
            from urllib.parse import urlparse, parse_qs
            
            player_url = video.url
            logger.info(f"Resolving House stream URL: {player_url}")
            
            # Extract video filename from URL
            # Format: /VideoArchivePlayer?video=HCOMT-022525.mp4
            parsed_query = parse_qs(urlparse(player_url).query)
            video_param = parsed_query.get('video', [None])[0]
            
            if not video_param:
                logger.warning(f"Could not extract video parameter from URL: {player_url}")
                return None
            
            # Construct direct MP4 URL
            direct_url = f"https://www.house.mi.gov/ArchiveVideoFiles/{video_param}"
            logger.info(f"Using direct MP4 URL: {direct_url}")
            
            # Verify the file exists with a HEAD request
            try:
                response = requests.head(
                    direct_url,
                    timeout=10,
                    verify=False,
                    allow_redirects=True,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                )
                
                # Check if the URL is valid
                if response.status_code == 200:
                    content_type = response.headers.get('Content-Type', '').lower()
                    content_length = response.headers.get('Content-Length', '0')
                    
                    # Verify it's actually a video file, not HTML error page
                    if 'video' in content_type or 'mp4' in content_type or int(content_length) > 0:
                        logger.info(f"✅ Direct MP4 URL verified: {direct_url} (size: {content_length} bytes)")
                        return direct_url
                    else:
                        logger.warning(f"Direct URL returned non-video content type: {content_type}")
                elif response.status_code in [301, 302, 303, 307, 308]:
                    # Follow redirect and check final URL
                    final_url = response.headers.get('Location', direct_url)
                    logger.info(f"Direct URL redirects to: {final_url}")
                    # Try the redirect URL
                    redirect_check = requests.head(final_url, timeout=10, verify=False, allow_redirects=True)
                    if redirect_check.status_code == 200:
                        content_type = redirect_check.headers.get('Content-Type', '').lower()
                        if 'video' in content_type or 'mp4' in content_type:
                            logger.info(f"✅ Redirect URL verified: {final_url}")
                            return final_url
                else:
                    logger.warning(f"Direct URL returned status {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Failed to verify direct MP4 URL: {e}")
            
            # If verification fails, still return the URL (let downloader handle it)
            logger.warning(f"Could not verify URL, but returning direct URL anyway: {direct_url}")
            return direct_url
                    
        except Exception as e:
            logger.error(f"Error in House stream resolution: {e}", exc_info=True)
            return None

