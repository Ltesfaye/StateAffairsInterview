"""Database manager for SQLite"""

from pathlib import Path
from sqlalchemy import create_engine, Column, String, DateTime, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
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
    date_discovered = Column(DateTime, nullable=False, default=datetime.now)
    download_status = Column(String, default="pending")  # pending, downloaded, failed, in_progress
    download_path = Column(Text, nullable=True)
    transcription_status = Column(String, default="pending")  # pending, completed, failed (future)
    transcription_path = Column(Text, nullable=True)  # (future)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class DatabaseManager:
    """Manages database connections and operations"""
    
    def __init__(self, db_path: str):
        """Initialize database manager"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create engine
        db_url = f"sqlite:///{self.db_path}"
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
                date_discovered=datetime.now(),
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

    def update_stream_url(
        self,
        video_id: str,
        source: str,
        stream_url: str,
    ):
        """Update stream URL for a video"""
        session = self.get_session()
        try:
            record = session.query(VideoRecord).filter_by(
                id=video_id,
                source=source
            ).first()
            
            if record:
                record.stream_url = stream_url
                record.updated_at = datetime.now()
                session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_video_record(self, video_id: str, source: str) -> Optional[VideoRecord]:
        """Get video record by ID and source"""
        session = self.get_session()
        try:
            return session.query(VideoRecord).filter_by(
                id=video_id,
                source=source
            ).first()
        finally:
            session.close()
    
    def video_exists(self, video_id: str, source: str) -> bool:
        """Check if video record exists"""
        return self.get_video_record(video_id, source) is not None
    
    def update_download_status(
        self,
        video_id: str,
        source: str,
        status: str,
        download_path: Optional[str] = None,
    ):
        """Update download status for a video"""
        session = self.get_session()
        try:
            record = session.query(VideoRecord).filter_by(
                id=video_id,
                source=source
            ).first()
            
            if record:
                record.download_status = status
                if download_path:
                    record.download_path = download_path
                record.updated_at = datetime.now()
                session.commit()
        except Exception as e:
            session.rollback()
            raise
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
    
    def get_all_videos(
        self,
        cutoff_date: Optional[datetime] = None,
    ) -> List[VideoRecord]:
        """Get all videos, optionally filtered by date"""
        session = self.get_session()
        try:
            query = session.query(VideoRecord)
            
            if cutoff_date:
                query = query.filter(VideoRecord.date_recorded >= cutoff_date)
            
            return query.order_by(VideoRecord.date_recorded.desc()).all()
        finally:
            session.close()


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(db_path: Optional[str] = None) -> DatabaseManager:
    """Get or create database manager instance"""
    global _db_manager
    
    if _db_manager is None:
        if db_path is None:
            raise ValueError("Database path must be provided on first call")
        _db_manager = DatabaseManager(db_path)
    
    return _db_manager

