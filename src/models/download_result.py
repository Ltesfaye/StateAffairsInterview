"""Download result model"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DownloadResult:
    """Result of a video download operation"""
    
    success: bool
    video_id: str
    file_path: Optional[Path] = None
    error_message: Optional[str] = None
    bytes_downloaded: int = 0
    
    def __repr__(self):
        if self.success:
            return f"DownloadResult(success=True, path={self.file_path})"
        else:
            return f"DownloadResult(success=False, error={self.error_message})"

