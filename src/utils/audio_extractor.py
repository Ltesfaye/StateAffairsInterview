import subprocess
import os
from pathlib import Path
from typing import Optional
from .logger import get_logger

logger = get_logger(__name__, service_name="audio-extractor")

def extract_audio(video_path: str, output_dir: Optional[str] = None) -> Optional[str]:
    """
    Extract audio from video file using FFmpeg.
    Optimized for transcription (16kHz, mono, 16-bit PCM).
    """
    video_path_obj = Path(video_path)
    if not video_path_obj.exists():
        logger.error(f"Video file not found: {video_path}")
        return None

    if output_dir:
        audio_path = Path(output_dir) / f"{video_path_obj.stem}.wav"
    else:
        audio_path = video_path_obj.with_suffix(".wav")

    logger.info(f"Extracting audio: {video_path} -> {audio_path}")
    
    try:
        command = [
            "ffmpeg", "-i", str(video_path_obj),
            "-vn",              # Disable video
            "-acodec", "pcm_s16le", # 16-bit PCM
            "-ar", "16000",     # 16kHz
            "-ac", "1",          # Mono
            str(audio_path),
            "-y"                # Overwrite
        ]
        
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg failed: {result.stderr}")
            return None
            
        logger.info(f"Audio extraction successful: {audio_path}")
        return str(audio_path)
        
    except Exception as e:
        logger.error(f"Unexpected error during audio extraction: {e}")
        return None

