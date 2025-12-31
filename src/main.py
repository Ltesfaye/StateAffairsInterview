"""Main CLI entry point for video archive service"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
import click
from dotenv import load_dotenv

# Load .env
load_dotenv()

from .utils import load_config
from .database import get_db_manager
from .services import StateService, DiscoveryService, DownloadService
from .utils.logger import get_logger

logger = get_logger(__name__, service_name="cli")

@click.group()
def cli():
    """Video Archive Microservice CLI"""
    pass

@cli.command()
@click.option("--source", type=click.Choice(["house", "senate"]), help="Filter by source")
@click.option("--days", type=int, default=2, help="Days to look back")
@click.option("--async-mode", is_flag=True, help="Run via Celery workers")
def discover(source, days, async_mode):
    """Discover new videos from archives"""
    if async_mode:
        from .workers.tasks import discover_videos_task
        discover_videos_task.delay(source=source, days=days)
        click.echo(f"Dispatched discovery task to Celery for {source or 'all'} sources.")
        return

    # Synchronous mode
    db_manager = get_db_manager()
    discovery_service = DiscoveryService()
    state_service = StateService(db_manager)
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    videos = discovery_service.discover_videos(cutoff_date=cutoff_date, source=source)
    
    for video in videos:
        state_service.mark_video_discovered(video)
    
    click.echo(f"Discovered {len(videos)} videos.")

@cli.command()
@click.option("--video-id", required=True, help="ID of video to process")
@click.option("--source", required=True, help="Source of video")
def process(video_id, source):
    """Manually trigger processing for a specific video"""
    from .workers.tasks import download_video_task
    download_video_task.delay(video_id, source)
    click.echo(f"Dispatched processing task for {video_id} ({source})")

@cli.command()
def test_infra():
    """Test connection to DB and Redis"""
    try:
        db = get_db_manager()
        db.get_session().execute(click.echo("Testing DB connection...") or "SELECT 1")
        click.echo("Postgres: OK")
        
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        r.ping()
        click.echo("Redis: OK")
    except Exception as e:
        click.echo(f"Infra test failed: {e}")

if __name__ == "__main__":
    cli()
