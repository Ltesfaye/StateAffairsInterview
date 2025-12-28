"""Processing status enums for tracking video states"""

from enum import Enum


class DownloadStatus(str, Enum):
    """Status of video download"""
    PENDING = "pending"
    DOWNLOADED = "downloaded"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"


class TranscriptionStatus(str, Enum):
    """Status of video transcription (future use)"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"


class ProcessingStatus:
    """Container for all processing statuses of a video"""
    
    def __init__(
        self,
        download_status: DownloadStatus = DownloadStatus.PENDING,
        transcription_status: TranscriptionStatus = TranscriptionStatus.PENDING,
    ):
        self.download_status = download_status
        self.transcription_status = transcription_status
    
    def __repr__(self):
        return (
            f"ProcessingStatus("
            f"download={self.download_status.value}, "
            f"transcription={self.transcription_status.value})"
        )

