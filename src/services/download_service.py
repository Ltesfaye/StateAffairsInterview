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
            # Extract direct video URL if needed
            logger.debug(f"[DOWNLOAD_SERVICE] Original video URL: {video.url}")
            # Skip blob handler for VideoArchivePlayer URLs - yt-dlp will handle them
            if "VideoArchivePlayer" not in video.url and "blob:" not in video.url:
                # Only use blob handler for actual blob URLs
                logger.debug(f"[DOWNLOAD_SERVICE] Using blob handler for URL extraction")
                video_url = self.blob_handler.extract_video_url(video.url)
                if not video_url:
                    video_url = video.url
            else:
                logger.debug(f"[DOWNLOAD_SERVICE] Skipping blob handler, using original URL")
                video_url = video.url
            
            logger.debug(f"[DOWNLOAD_SERVICE] After blob handler: {video_url}")
            
            # Use downloader's method to normalize URLs (but keep player pages for yt-dlp)
            logger.debug(f"[DOWNLOAD_SERVICE] Calling downloader.get_direct_video_url()")
            video_url = self.downloader.get_direct_video_url(video_url)
            logger.debug(f"[DOWNLOAD_SERVICE] After get_direct_video_url: {video_url}")
            
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

