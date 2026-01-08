"""Database manager for PostgreSQL and SQLite"""

import os
from pathlib import Path
from sqlalchemy import create_engine, Column, String, DateTime, Text, ForeignKey, JSON, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime
from typing import Optional, List

Base = declarative_base()


class VideoRecord(Base):
    """Database model for video records"""
    __tablename__ = "videos"
    
    id = Column(String, primary_key=True)  # video_id
    source = Column(String, nullable=False)  # 'house' or 'senate'
    filename = Column(String, nullable=False)
    url = Column(Text, nullable=False)
    stream_url = Column(Text, nullable=True)
    date_recorded = Column(DateTime, nullable=False)
    committee = Column(String, nullable=True)
    title = Column(String, nullable=True)
    date_discovered = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Statuses
    download_status = Column(String, default="pending")
    audio_status = Column(String, default="pending")
    transcription_status = Column(String, default="pending")
    
    # Paths
    download_path = Column(Text, nullable=True)
    audio_path = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transcripts = relationship("TranscriptRecord", back_populates="video", cascade="all, delete-orphan")


class TranscriptRecord(Base):
    """Database model for transcription records (Searchable Registry)"""
    __tablename__ = "transcripts"
    
    id = Column(String, primary_key=True)  # UUID or unique ID
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    provider = Column(String, nullable=False)  # 'local', 'openai', 'gemini'
    content = Column(Text, nullable=False)  # Full searchable text
    raw_data = Column(JSON, nullable=True)  # Word-level timestamps, confidence, etc.
    vtt_path = Column(String, nullable=True)  # Path to subtitle file
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    video = relationship("VideoRecord", back_populates="transcripts")


class DatabaseManager:
    """Manages database connections and operations for Postgres and SQLite"""
    
    def __init__(self, db_url: Optional[str] = None):
        """Initialize database manager"""
        if not db_url:
            # Default to SQLite if no URL provided
            db_path = Path("./data/database/videos.db")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{db_path}"
        
        # Create engine
        # For Postgres, we might want to add pool_size etc.
        self.engine = create_engine(db_url, echo=False)
        
        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Create tables
        Base.metadata.create_all(self.engine)
    
    def get_session(self) -> Session:
        """Get a database session"""
        return self.SessionLocal()
    
    def create_video_record(
        self,
        video_id: str,
        source: str,
        filename: str,
        url: str,
        date_recorded: datetime,
        committee: Optional[str] = None,
        title: Optional[str] = None,
        stream_url: Optional[str] = None,
    ) -> VideoRecord:
        """Create a new video record"""
        session = self.get_session()
        try:
            record = VideoRecord(
                id=video_id,
                source=source,
                filename=filename,
                url=url,
                stream_url=stream_url,
                date_recorded=date_recorded,
                committee=committee,
                title=title,
                date_discovered=datetime.utcnow(),
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    def update_video_status(
        self,
        video_id: str,
        source: str,
        download_status: Optional[str] = None,
        audio_status: Optional[str] = None,
        transcription_status: Optional[str] = None,
        download_path: Optional[str] = None,
        audio_path: Optional[str] = None,
    ):
        """Update various statuses and paths for a video"""
        session = self.get_session()
        try:
            record = session.query(VideoRecord).filter_by(id=video_id, source=source).first()
            if record:
                if download_status: record.download_status = download_status
                if audio_status: record.audio_status = audio_status
                if transcription_status: record.transcription_status = transcription_status
                if download_path: record.download_path = download_path
                if audio_path: record.audio_path = audio_path
                session.commit()
        finally:
            session.close()

    def add_transcript(
        self,
        video_id: str,
        provider: str,
        content: str,
        raw_data: Optional[dict] = None,
        vtt_path: Optional[str] = None,
    ) -> TranscriptRecord:
        """Add a transcription record to the registry"""
        import uuid
        session = self.get_session()
        try:
            record = TranscriptRecord(
                id=str(uuid.uuid4()),
                video_id=video_id,
                provider=provider,
                content=content,
                raw_data=raw_data,
                vtt_path=vtt_path,
                created_at=datetime.utcnow()
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
        finally:
            session.close()

    def get_video_record(self, video_id: str, source: str) -> Optional[VideoRecord]:
        """Get video record by ID and source"""
        session = self.get_session()
        try:
            return session.query(VideoRecord).filter_by(id=video_id, source=source).first()
        finally:
            session.close()

    def video_exists(self, video_id: str, source: str) -> bool:
        """Check if video record exists"""
        session = self.get_session()
        try:
            return session.query(VideoRecord).filter_by(id=video_id, source=source).count() > 0
        finally:
            session.close()

    def update_stream_url(self, video_id: str, source: str, stream_url: str):
        """Update stream URL for a video"""
        self.update_video_status(video_id, source, transcription_status=None) # Just trigger session
        session = self.get_session()
        try:
            record = session.query(VideoRecord).filter_by(id=video_id, source=source).first()
            if record:
                record.stream_url = stream_url
                session.commit()
        finally:
            session.close()

    def get_all_videos(self, cutoff_date: Optional[datetime] = None) -> List[VideoRecord]:
        """Get all videos, optionally filtered by date"""
        session = self.get_session()
        try:
            query = session.query(VideoRecord)
            if cutoff_date:
                query = query.filter(VideoRecord.date_recorded >= cutoff_date)
            return query.order_by(VideoRecord.date_recorded.desc()).all()
        finally:
            session.close()

    def get_unprocessed_videos(
        self,
        cutoff_date: Optional[datetime] = None,
        download_status: str = "pending",
        source: Optional[str] = None,
    ) -> List[VideoRecord]:
        """Get videos that haven't been processed"""
        session = self.get_session()
        try:
            query = session.query(VideoRecord).filter_by(download_status=download_status)
            if cutoff_date:
                query = query.filter(VideoRecord.date_recorded >= cutoff_date)
            if source:
                query = query.filter_by(source=source.lower())
            return query.all()
        finally:
            session.close()

    def search_transcripts(self, query: str) -> List[dict]:
        """Search across all transcript records"""
        session = self.get_session()
        try:
            # Simple ILIKE search for both Postgres and SQLite
            results = session.query(TranscriptRecord, VideoRecord).join(
                VideoRecord, TranscriptRecord.video_id == VideoRecord.id
            ).filter(TranscriptRecord.content.ilike(f"%{query}%")).all()
            
            output = []
            for transcript, video in results:
                output.append({
                    "video_id": video.id,
                    "title": video.title,
                    "source": video.source,
                    "date": video.date_recorded,
                    "content": transcript.content,
                    "provider": transcript.provider
                })
            return output
        finally:
            session.close()

    def get_stats(self) -> dict:
        """Get high-level pipeline stats"""
        session = self.get_session()
        try:
            total = session.query(VideoRecord).count()
            downloaded = session.query(VideoRecord).filter_by(download_status="downloaded").count()
            transcribed = session.query(VideoRecord).filter_by(transcription_status="completed").count()
            failed = session.query(VideoRecord).filter(
                (VideoRecord.download_status == "failed") | 
                (VideoRecord.transcription_status == "failed")
            ).count()
            
            return {
                "total": total,
                "downloaded": downloaded,
                "transcribed": transcribed,
                "failed": failed
            }
        finally:
            session.close()

    def get_last_downloaded_date(self, source: str) -> Optional[datetime]:
        """Get the date_recorded of the most recently downloaded video for a source"""
        session = self.get_session()
        try:
            record = session.query(VideoRecord).filter(
                VideoRecord.source == source.lower(),
                VideoRecord.download_status == "downloaded"
            ).order_by(VideoRecord.date_recorded.desc()).first()
            
            if record:
                return record.date_recorded
            return None
        finally:
            session.close()


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(db_url: Optional[str] = None) -> DatabaseManager:
    """Get or create database manager instance"""
    global _db_manager
    if _db_manager is None:
        # Priority: 1. Argument, 2. Env Var, 3. Default (SQLite)
        url = db_url or os.getenv("DATABASE_URL")
        _db_manager = DatabaseManager(url)
    return _db_manager
