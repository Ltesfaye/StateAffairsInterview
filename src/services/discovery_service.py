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
        import os
        
        # Priority: 1. Argument, 2. Env Var, 3. Hardcoded default
        h_url = house_archive_url or os.getenv("HOUSE_ARCHIVE_URL") or "https://house.mi.gov/VideoArchive"
        s_url = senate_api_url or os.getenv("SENATE_API_URL") or "https://2kbyogxrg4.execute-api.us-west-2.amazonaws.com/61b3adc8124d7d000891ca5c/home/recent"
        
        self.house_scraper = house_scraper or HouseScraper(archive_url=h_url)
        self.senate_scraper = senate_scraper or SenateScraper(api_url=s_url)
    
    def discover_videos(
        self,
        cutoff_date: Optional[datetime] = None,
        cutoff_days: int = 60,
        limit: Optional[int] = None,
        source: Optional[str] = None,
        resolve_streams: bool = True,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[VideoMetadata]:
        """
        Discover videos from all archives
        
        Args:
            cutoff_date: Only return videos after this date (if None and no start_date, uses cutoff_days)
            cutoff_days: Number of days to look back (default: 60) - used if cutoff_date and start_date are None
            limit: Maximum number of videos per source (None for all)
            source: Filter by source ("house" or "senate", None for all)
            resolve_streams: Whether to resolve final stream URLs (expensive)
            start_date: Start of date range (if provided with end_date, uses date range instead of cutoff_date)
            end_date: End of date range (if provided with start_date, uses date range instead of cutoff_date)
        
        Returns:
            List of VideoMetadata objects from all sources
        """
        # Determine date filtering approach
        if start_date and end_date:
            logger.info(f"Discovering videos between {start_date.date()} and {end_date.date()}")
            use_date_range = True
        else:
            if cutoff_date is None:
                cutoff_date = datetime.now() - timedelta(days=cutoff_days)
            logger.info(f"Discovering videos after {cutoff_date.date()}")
            use_date_range = False
        
        all_videos = []
        house_count = 0
        senate_count = 0
        
        # Discover from House archive
        if source is None or source.lower() == "house":
            try:
                logger.info("Discovering from House archive...")
                if use_date_range:
                    house_videos = self.house_scraper.discover_videos(
                        cutoff_date=start_date,  # Used as fallback
                        start_date=start_date,
                        end_date=end_date,
                        limit=limit,
                    )
                else:
                    house_videos = self.house_scraper.discover_videos(
                        cutoff_date=cutoff_date,
                        limit=limit,
                    )
                
                if resolve_streams:
                    logger.info(f"Resolving stream URLs for {len(house_videos)} House videos...")
                    for video in house_videos:
                        stream_url = self.house_scraper.resolve_stream_url(video)
                        if stream_url:
                            video.stream_url = stream_url
                            
                all_videos.extend(house_videos)
                house_count = len(house_videos)
                logger.info(f"Found {house_count} videos from House")
            except Exception as e:
                logger.error(f"Error discovering House videos: {e}", exc_info=True)
        
        # Discover from Senate archive
        if source is None or source.lower() == "senate":
            try:
                logger.info("Discovering from Senate archive...")
                if use_date_range:
                    senate_videos = self.senate_scraper.discover_videos(
                        cutoff_date=start_date,  # Used as fallback
                        start_date=start_date,
                        end_date=end_date,
                        limit=limit,
                    )
                else:
                    senate_videos = self.senate_scraper.discover_videos(
                        cutoff_date=cutoff_date,
                        limit=limit,
                    )
                
                if resolve_streams:
                    logger.info(f"Resolving stream URLs for {len(senate_videos)} Senate videos...")
                    for video in senate_videos:
                        stream_url = self.senate_scraper.resolve_stream_url(video)
                        if stream_url:
                            video.stream_url = stream_url
                            
                all_videos.extend(senate_videos)
                senate_count = len(senate_videos)
                logger.info(f"Found {senate_count} videos from Senate")
            except Exception as e:
                logger.error(f"Error discovering Senate videos: {e}", exc_info=True)
        
        logger.info(f"Total videos discovered: {len(all_videos)} (House: {house_count}, Senate: {senate_count})")
        return all_videos

