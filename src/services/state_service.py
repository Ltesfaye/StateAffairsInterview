"""State management service for tracking processed videos"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..database import DatabaseManager
from ..models import VideoMetadata, ProcessingStatus, DownloadStatus


class StateService:
    """Manages state of processed videos"""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize state service with database manager"""
        self.db = db_manager
    
    def get_download_path(self, video_id: str, source: str) -> Optional[Path]:
        """Get download path for a video if it exists"""
        from pathlib import Path
        record = self.db.get_video_record(video_id, source)
        if record and record.download_path:
            return Path(record.download_path)
        return None
    
    def is_video_processed(self, video_id: str, source: str) -> bool:
        """Check if video has been processed (downloaded)"""
        record = self.db.get_video_record(video_id, source)
        if not record:
            return False
        
        return record.download_status == "downloaded"
    
    def mark_video_discovered(self, video: VideoMetadata) -> None:
        """Mark video as discovered (add to database if not exists)"""
        if not self.db.video_exists(video.video_id, video.source):
            self.db.create_video_record(
                video_id=video.video_id,
                source=video.source,
                filename=video.filename,
                url=video.url,
                date_recorded=video.date_recorded,
                committee=video.committee,
                title=video.title,
            )
    
    def mark_video_processed(
        self,
        video: VideoMetadata,
        status: ProcessingStatus,
        download_path: Optional[Path] = None,
    ) -> None:
        """Mark video as processed with given status"""
        download_status = status.download_status.value
        
        self.db.update_download_status(
            video_id=video.video_id,
            source=video.source,
            status=download_status,
            download_path=str(download_path) if download_path else None,
        )
    
    def get_unprocessed_videos(
        self,
        cutoff_date: Optional[datetime] = None,
        source: Optional[str] = None,
    ) -> List[VideoMetadata]:
        """Get list of videos that haven't been downloaded"""
        records = self.db.get_unprocessed_videos(
            cutoff_date=cutoff_date,
            download_status="pending",
            source=source,
        )
        
        videos = []
        for record in records:
            video = VideoMetadata(
                video_id=record.id,
                source=record.source,
                filename=record.filename,
                url=record.url,
                date_recorded=record.date_recorded,
                committee=record.committee,
                title=record.title,
                date_discovered=record.date_discovered,
            )
            videos.append(video)
        
        return videos
    
    def get_all_videos(
        self,
        cutoff_date: Optional[datetime] = None,
    ) -> List[VideoMetadata]:
        """Get all videos, optionally filtered by date"""
        records = self.db.get_all_videos(cutoff_date=cutoff_date)
        
        videos = []
        for record in records:
            video = VideoMetadata(
                video_id=record.id,
                source=record.source,
                filename=record.filename,
                url=record.url,
                date_recorded=record.date_recorded,
                committee=record.committee,
                title=record.title,
                date_discovered=record.date_discovered,
            )
            videos.append(video)
        
        return videos

