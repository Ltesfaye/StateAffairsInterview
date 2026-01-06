import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from .celery_app import app

from ..services.discovery_service import DiscoveryService
from ..services.download_service import DownloadService
from ..services.state_service import StateService
from ..database.db_manager import get_db_manager
from ..utils.audio_extractor import extract_audio
from ..utils.logger import get_logger, generate_trace_id
from ..services.transcription_service import get_provider
from ..models.processing_status import DownloadStatus, AudioStatus, TranscriptionStatus

logger = get_logger(__name__, service_name="celery-tasks")

@app.task(name="src.workers.tasks.discover_videos_task", queue="discovery")
def discover_videos_task(
    source: Optional[str] = None,
    days: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Discovery task to find and resolve videos"""
    trace_id = generate_trace_id()
    
    # Determine date parameters
    if start_date and end_date:
        # Parse ISO format date strings (YYYY-MM-DD format from date_input)
        if isinstance(start_date, str):
            try:
                # Handle date-only strings (YYYY-MM-DD)
                if len(start_date) == 10:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                else:
                    # Handle datetime strings with timezone
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                start_dt = datetime.fromisoformat(start_date)
        else:
            start_dt = start_date
        
        if isinstance(end_date, str):
            try:
                # Handle date-only strings (YYYY-MM-DD)
                if len(end_date) == 10:
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                    # Set to end of day
                    end_dt = end_dt.replace(hour=23, minute=59, second=59)
                else:
                    # Handle datetime strings with timezone
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                end_dt = datetime.fromisoformat(end_date)
        else:
            end_dt = end_date
        
        logger.info(f"Starting discovery task for source={source}, date_range={start_dt.date()} to {end_dt.date()}", extra={"trace_id": trace_id})
    else:
        # Fallback to days-based discovery
        days = days or 2
        logger.info(f"Starting discovery task for source={source}, days={days}", extra={"trace_id": trace_id})
        start_dt = None
        end_dt = None
    
    db_manager = get_db_manager()
    discovery_service = DiscoveryService()
    state_service = StateService(db_manager)
    
    # Discover videos
    if start_dt and end_dt:
        videos = discovery_service.discover_videos(
            start_date=start_dt,
            end_date=end_dt,
            source=source,
        )
    else:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        videos = discovery_service.discover_videos(cutoff_date=cutoff_date, source=source)
    
    for video in videos:
        # Mark as discovered in DB
        state_service.mark_video_discovered(video)
        # Dispatch download task to download queue
        download_video_task.apply_async(args=[video.video_id, video.source], queue="download")
        
    logger.info(f"Discovery complete. Dispatched {len(videos)} download tasks.", extra={"trace_id": trace_id})

@app.task(name="src.workers.tasks.download_video_task", queue="download")
def download_video_task(video_id: str, source: str):
    """Download video and extract audio"""
    trace_id = generate_trace_id()
    logger.info(f"Starting download task for {video_id} ({source})", extra={"trace_id": trace_id})
    
    db_manager = get_db_manager()
    state_service = StateService(db_manager)
    
    # Get metadata from DB
    record = db_manager.get_video_record(video_id, source)
    if not record:
        logger.error(f"Video record not found in DB: {video_id}", extra={"trace_id": trace_id})
        return

    from ..models.video_metadata import VideoMetadata
    video_meta = VideoMetadata.from_dict({
        "id": record.id,
        "source": record.source,
        "filename": record.filename,
        "url": record.url,
        "stream_url": record.stream_url,
        "date_recorded": record.date_recorded,
        "committee": record.committee,
        "title": record.title
    })

    # Download Service
    output_dir = Path(os.getenv("STORAGE_PATH", "./data")) / "videos"
    download_service = DownloadService(state_service=state_service, output_directory=output_dir)
    
    db_manager.update_video_status(video_id, source, download_status=DownloadStatus.IN_PROGRESS)
    result = download_service.download_video(video_meta)
    
    if result.success:
        logger.info(f"Download successful: {result.file_path}", extra={"trace_id": trace_id})
        db_manager.update_video_status(video_id, source, download_status=DownloadStatus.DOWNLOADED, download_path=str(result.file_path))
        
        # Audio Extraction
        db_manager.update_video_status(video_id, source, audio_status=AudioStatus.EXTRACTING)
        audio_dir = Path(os.getenv("STORAGE_PATH", "./data")) / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        audio_path = extract_audio(str(result.file_path), output_dir=str(audio_dir))
        if audio_path:
            db_manager.update_video_status(video_id, source, audio_status=AudioStatus.EXTRACTED, audio_path=audio_path)
            # Dispatch transcription task to transcription queue
            transcribe_audio_task.apply_async(args=[video_id, source], queue="transcription")
        else:
            db_manager.update_video_status(video_id, source, audio_status=AudioStatus.FAILED)
    else:
        logger.error(f"Download failed: {result.error_message}", extra={"trace_id": trace_id})
        db_manager.update_video_status(video_id, source, download_status=DownloadStatus.FAILED)

@app.task(name="src.workers.tasks.transcribe_audio_task", queue="transcription")
def transcribe_audio_task(video_id: str, source: str):
    """Transcribe extracted audio using configured provider"""
    trace_id = generate_trace_id()
    logger.info(f"Starting transcription task for {video_id} ({source})", extra={"trace_id": trace_id})
    
    db_manager = get_db_manager()
    record = db_manager.get_video_record(video_id, source)
    
    if not record or not record.audio_path:
        logger.error(f"Audio path not found for {video_id}", extra={"trace_id": trace_id})
        return

    db_manager.update_video_status(video_id, source, transcription_status=TranscriptionStatus.IN_PROGRESS)
    
    try:
        # Get provider settings from env
        provider_type = os.getenv("TRANSCRIPTION_PROVIDER", "local")
        kwargs = {
            "whisper_model": os.getenv("WHISPER_MODEL", "base"),
            "openai_api_key": os.getenv("OPENAI_API_KEY"),
            "google_api_key": os.getenv("GOOGLE_API_KEY"),
            "gemini_model": os.getenv("GEMINI_MODEL")
        }
        
        provider = get_provider(provider_type, **kwargs)
        result = provider.transcribe(Path(record.audio_path))
        
        # Save transcript to disk (VTT placeholder logic here)
        transcript_dir = Path(os.getenv("STORAGE_PATH", "./data")) / "transcripts"
        transcript_dir.mkdir(parents=True, exist_ok=True)
        
        # In a real app, we'd generate VTT here. For now, we save text/json
        text_path = transcript_dir / f"{video_id}.txt"
        with open(text_path, "w") as f:
            f.write(result["text"])
            
        # Register in Postgres Registry
        db_manager.add_transcript(
            video_id=video_id,
            provider=provider_type,
            content=result["text"],
            raw_data=result.get("segments") or result, # Save segments if available
            vtt_path=str(text_path) # Placeholder
        )
        
        db_manager.update_video_status(video_id, source, transcription_status=TranscriptionStatus.COMPLETED)
        logger.info(f"Transcription complete for {video_id}", extra={"trace_id": trace_id})
        
    except Exception as e:
        logger.error(f"Transcription failed for {video_id}: {e}", extra={"trace_id": trace_id})
        db_manager.update_video_status(video_id, source, transcription_status=TranscriptionStatus.FAILED)

@app.task(name="src.workers.tasks.requeue_failed_tasks", queue="transcription")
def requeue_failed_tasks():
    """Find failed tasks and re-queue them if files exist, otherwise restart from download"""
    db_manager = get_db_manager()
    session = db_manager.get_session()
    from ..database.db_manager import VideoRecord
    from ..models.processing_status import DownloadStatus, TranscriptionStatus
    
    # 1. Find failed transcriptions
    failed_transcripts = session.query(VideoRecord).filter(VideoRecord.transcription_status == "failed").all()
    requeued_count = 0
    restarted_count = 0
    
    for record in failed_transcripts:
        if record.audio_path and os.path.exists(record.audio_path):
            logger.info(f"Re-queueing transcription for {record.id} (audio exists)")
            transcribe_audio_task.delay(record.id, record.source)
            requeued_count += 1
        else:
            logger.info(f"Restarting download for {record.id} (audio/video missing)")
            db_manager.update_video_status(
                record.id, record.source, 
                download_status=DownloadStatus.PENDING,
                transcription_status=TranscriptionStatus.PENDING
            )
            download_video_task.delay(record.id, record.source)
            restarted_count += 1

    # 2. Find failed downloads
    failed_downloads = session.query(VideoRecord).filter(VideoRecord.download_status == "failed").all()
    for record in failed_downloads:
        logger.info(f"Retrying download for {record.id}")
        db_manager.update_video_status(record.id, record.source, download_status=DownloadStatus.PENDING)
        download_video_task.delay(record.id, record.source)
        restarted_count += 1
    
    session.close()
    return {"requeued": requeued_count, "restarted": restarted_count}

