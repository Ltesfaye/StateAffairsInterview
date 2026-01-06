"""Video download service"""

from pathlib import Path
from typing import Optional

from ..models import VideoMetadata, ProcessingStatus, DownloadStatus, DownloadResult
from ..downloaders import VideoDownloader, BlobHandler
from ..services.state_service import StateService
from ..utils import get_logger

logger = get_logger(__name__)


class DownloadService:
    """Manages video downloads with state tracking"""
    
    def __init__(
        self,
        state_service: StateService,
        output_directory: Path,
        max_retries: int = 3,
        timeout: int = 300,
        use_blob_handler: bool = False,
    ):
        """Initialize download service"""
        self.state_service = state_service
        self.output_directory = Path(output_directory)
        self.downloader = VideoDownloader(
            max_retries=max_retries,
            timeout=timeout,
        )
        self.blob_handler = BlobHandler(use_browser=use_blob_handler)
    
    def download_video(
        self,
        video: VideoMetadata,
    ) -> DownloadResult:
        """
        Download a video if not already downloaded
        
        Args:
            video: VideoMetadata to download
        
        Returns:
            DownloadResult with success status
        """
        # Check if already downloaded
        if self.state_service.is_video_processed(video.video_id, video.source):
            existing_path = self.state_service.get_download_path(video.video_id, video.source)
            if existing_path and existing_path.exists():
                return DownloadResult(
                    success=True,
                    video_id=video.video_id,
                    file_path=existing_path,
                )
        
        # Mark as in progress
        status = ProcessingStatus(download_status=DownloadStatus.IN_PROGRESS)
        self.state_service.mark_video_processed(video, status)
        
        print(f"📥 Downloading: {video.video_id} ({video.source})")
        
        try:
            # Determine best URL to use for download
            # If stream_url is already resolved, use it directly (Turbo mode)
            if video.stream_url:
                video_url = video.stream_url
                logger.info(f"[DOWNLOAD_SERVICE] Using already resolved stream URL: {video_url}")
            else:
                # Resolve stream URL if not set (needed for House videos especially)
                logger.info(f"[DOWNLOAD_SERVICE] Stream URL not set, resolving for {video.video_id} ({video.source})")
                video.stream_url = self._resolve_stream_url(video)
                
                if video.stream_url:
                    video_url = video.stream_url
                    logger.info(f"[DOWNLOAD_SERVICE] Resolved stream URL: {video_url}")
                    # Update stream URL in database
                    self.state_service.db.update_stream_url(video.video_id, video.source, video.stream_url)
                else:
                    # Fallback to original URL or try to resolve
                    logger.warning(f"[DOWNLOAD_SERVICE] Could not resolve stream URL, using original URL: {video.url}")
                    # Skip blob handler for known player pages - yt-dlp/aria2c will handle direct URLs
                    if "blob:" in video.url:
                        logger.debug(f"[DOWNLOAD_SERVICE] Using blob handler for URL extraction")
                        video_url = self.blob_handler.extract_video_url(video.url)
                    else:
                        video_url = video.url
                    
                    # Normalize URL
                    video_url = self.downloader.get_direct_video_url(video_url)
            
            # Determine output filename
            output_filename = self._generate_filename(video)
            output_path = self.output_directory / output_filename
            logger.debug(f"[DOWNLOAD_SERVICE] Output path: {output_path}")
            
            # Download video
            logger.debug(f"[DOWNLOAD_SERVICE] Calling downloader.download() with URL: {video_url}")
            result = self.downloader.download(
                url=video_url,
                output_path=output_path,
                video_id=video.video_id,
            )
            logger.debug(f"[DOWNLOAD_SERVICE] Download result: success={result.success}, error={result.error_message if not result.success else None}")
            
            # Update state
            if result.success:
                status = ProcessingStatus(download_status=DownloadStatus.DOWNLOADED)
                self.state_service.mark_video_processed(
                    video,
                    status,
                    download_path=result.file_path,
                )
                file_size_mb = result.bytes_downloaded / (1024 * 1024)
                print(f"✅ Success: {video.video_id} ({file_size_mb:.1f} MB)")
            else:
                status = ProcessingStatus(download_status=DownloadStatus.FAILED)
                self.state_service.mark_video_processed(video, status)
                print(f"❌ Failed: {video.video_id} - {result.error_message}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error downloading video {video.video_id}: {e}", exc_info=True)
            status = ProcessingStatus(download_status=DownloadStatus.FAILED)
            self.state_service.mark_video_processed(video, status)
            
            return DownloadResult(
                success=False,
                video_id=video.video_id,
                error_message=str(e),
            )
    
    def _resolve_stream_url(self, video: VideoMetadata) -> Optional[str]:
        """Resolve stream URL using appropriate scraper"""
        try:
            if video.source == "house":
                from ..scrapers import HouseScraper
                scraper = HouseScraper()
                stream_url = scraper.resolve_stream_url(video)
                return stream_url
            elif video.source == "senate":
                from ..scrapers import SenateScraper
                scraper = SenateScraper()
                stream_url = scraper.resolve_stream_url(video)
                return stream_url
            else:
                logger.warning(f"[DOWNLOAD_SERVICE] Unknown source: {video.source}, cannot resolve stream URL")
                return None
        except Exception as e:
            logger.error(f"[DOWNLOAD_SERVICE] Error resolving stream URL for {video.video_id}: {e}", exc_info=True)
            return None
    
    def _generate_filename(self, video: VideoMetadata) -> str:
        """Generate safe filename for video"""
        # Use video_id as base, ensure .mp4 extension
        base_name = video.video_id
        if not base_name.endswith(".mp4"):
            base_name = f"{base_name}.mp4"
        
        # Sanitize filename (remove invalid characters)
        import re
        base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)
        
        return base_name
    
    def download_videos(
        self,
        videos: list[VideoMetadata],
    ) -> list[DownloadResult]:
        """Download multiple videos"""
        results = []
        for video in videos:
            result = self.download_video(video)
            results.append(result)
        return results

