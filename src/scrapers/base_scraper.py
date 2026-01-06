"""Base scraper interface"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from ..models import VideoMetadata


class BaseScraper(ABC):
    """Abstract base class for archive scrapers"""
    
    @abstractmethod
    def discover_videos(
        self,
        cutoff_date: datetime,
        limit: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[VideoMetadata]:
        """
        Discover videos from archive
        
        Args:
            cutoff_date: Only return videos recorded after this date (used if start_date/end_date not provided)
            limit: Maximum number of videos to return (None for all)
            start_date: Start of date range (if provided with end_date, uses date range instead of cutoff_date)
            end_date: End of date range (if provided with start_date, uses date range instead of cutoff_date)
        
        Returns:
            List of VideoMetadata objects
        """
        pass

    def resolve_stream_url(self, video: VideoMetadata) -> Optional[str]:
        """
        Resolve the final stream URL for a video (optional)
        
        Args:
            video: VideoMetadata object
            
        Returns:
            Direct stream URL (m3u8 or mp4) if resolvable, else None
        """
        return None

