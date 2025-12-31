"""Processing status enums for tracking video states"""

from enum import Enum


class DownloadStatus(str, Enum):
    """Status of video download"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DOWNLOADED = "downloaded"
    FAILED = "failed"


class AudioStatus(str, Enum):
    """Status of audio extraction"""
    PENDING = "pending"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    FAILED = "failed"


class TranscriptionStatus(str, Enum):
    """Status of video transcription"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStatus:
    """Container for all processing statuses of a video"""
    
    def __init__(
        self,
        download_status: DownloadStatus = DownloadStatus.PENDING,
        audio_status: AudioStatus = AudioStatus.PENDING,
        transcription_status: TranscriptionStatus = TranscriptionStatus.PENDING,
    ):
        self.download_status = download_status
        self.audio_status = audio_status
        self.transcription_status = transcription_status
    
    def __repr__(self):
        return (
            f"ProcessingStatus("
            f"download={self.download_status.value}, "
            f"audio={self.audio_status.value}, "
            f"transcription={self.transcription_status.value})"
        )
