"""Video metadata model"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class VideoMetadata:
    """Standardized video metadata from archive sources"""
    
    video_id: str  # Unique identifier (filename or API ID)
    source: str  # 'house' or 'senate'
    filename: str  # Original filename
    url: str  # Original player page URL or archive link
    date_recorded: datetime  # Date when video was recorded
    stream_url: Optional[str] = None  # Resolved HLS/MP4 URL for direct download
    committee: Optional[str] = None  # Committee name
    title: Optional[str] = None  # Video title/description
    date_discovered: Optional[datetime] = None  # When we discovered it
    
    def __post_init__(self):
        """Set default values"""
        if self.date_discovered is None:
            self.date_discovered = datetime.now()
    
    def __repr__(self):
        return (
            f"VideoMetadata("
            f"id={self.video_id}, "
            f"source={self.source}, "
            f"date={self.date_recorded.date()})"
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database storage"""
        return {
            "id": self.video_id,
            "source": self.source,
            "filename": self.filename,
            "url": self.url,
            "stream_url": self.stream_url,
            "date_recorded": self.date_recorded,
            "committee": self.committee,
            "title": self.title,
            "date_discovered": self.date_discovered,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "VideoMetadata":
        """Create from dictionary"""
        return cls(
            video_id=data["id"],
            source=data["source"],
            filename=data["filename"],
            url=data["url"],
            stream_url=data.get("stream_url"),
            date_recorded=data["date_recorded"],
            committee=data.get("committee"),
            title=data.get("title"),
            date_discovered=data.get("date_discovered"),
        )

