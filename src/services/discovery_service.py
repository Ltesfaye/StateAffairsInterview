"""Video discovery service"""

from datetime import datetime, timedelta
from typing import List, Optional

from ..models import VideoMetadata
from ..scrapers import HouseScraper, SenateScraper
from ..utils import get_logger

logger = get_logger(__name__)


class DiscoveryService:
    """Orchestrates video discovery from multiple archives"""
    
    def __init__(
        self,
        house_scraper: Optional[HouseScraper] = None,
        senate_scraper: Optional[SenateScraper] = None,
        house_archive_url: Optional[str] = None,
        senate_api_url: Optional[str] = None,
    ):
        """Initialize discovery service"""
        self.house_scraper = house_scraper or HouseScraper(
            archive_url=house_archive_url or "https://house.mi.gov/VideoArchive"
        )
        self.senate_scraper = senate_scraper or SenateScraper(
            api_url=senate_api_url or "https://tf4pr3wftk.execute-api.us-west-2.amazonaws.com/default/api/all"
        )
    
    def discover_videos(
        self,
        cutoff_date: Optional[datetime] = None,
        cutoff_days: int = 60,
        limit: Optional[int] = None,
        source: Optional[str] = None,
    ) -> List[VideoMetadata]:
        """
        Discover videos from all archives
        
        Args:
            cutoff_date: Only return videos after this date (if None, uses cutoff_days)
            cutoff_days: Number of days to look back (default: 60)
            limit: Maximum number of videos per source (None for all)
            source: Filter by source ("house" or "senate", None for all)
        
        Returns:
            List of VideoMetadata objects from all sources
        """
        if cutoff_date is None:
            cutoff_date = datetime.now() - timedelta(days=cutoff_days)
        
        logger.info(f"Discovering videos after {cutoff_date.date()}")
        
        all_videos = []
        
        # Discover from House archive
        if source is None or source.lower() == "house":
            try:
                logger.info("Discovering from House archive...")
                house_videos = self.house_scraper.discover_videos(
                    cutoff_date=cutoff_date,
                    limit=limit,
                )
                all_videos.extend(house_videos)
                logger.info(f"Found {len(house_videos)} videos from House")
            except Exception as e:
                logger.error(f"Error discovering House videos: {e}", exc_info=True)
        
        # Discover from Senate archive
        if source is None or source.lower() == "senate":
            try:
                logger.info("Discovering from Senate archive...")
                senate_videos = self.senate_scraper.discover_videos(
                    cutoff_date=cutoff_date,
                    limit=limit,
                )
                all_videos.extend(senate_videos)
                logger.info(f"Found {len(senate_videos)} videos from Senate")
            except Exception as e:
                logger.error(f"Error discovering Senate videos: {e}", exc_info=True)
        
        logger.info(f"Total videos discovered: {len(all_videos)}")
        return all_videos

