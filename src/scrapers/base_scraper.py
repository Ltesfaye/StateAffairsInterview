"""Base scraper interface"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List

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

