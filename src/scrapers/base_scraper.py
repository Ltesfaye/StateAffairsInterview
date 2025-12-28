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
        limit: int = None,
    ) -> List[VideoMetadata]:
        """
        Discover videos from archive after cutoff date
        
        Args:
            cutoff_date: Only return videos recorded after this date
            limit: Maximum number of videos to return (None for all)
        
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

