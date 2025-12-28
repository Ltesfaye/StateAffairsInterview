"""Main CLI entry point for video archive service"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import click

from .utils import load_config, setup_logger
from .database import get_db_manager
from .services import StateService, DiscoveryService, DownloadService


@click.command()
@click.option(
    "--cutoff-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Only process videos after this date (YYYY-MM-DD)",
)
@click.option(
    "--cutoff-days",
    type=int,
    default=60,
    help="Number of days to look back (default: 60)",
)
@click.option(
    "--config",
    type=click.Path(exists=True),
    help="Path to config.yaml file",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    help="Output directory for downloaded videos",
)
@click.option(
    "--discover-only",
    is_flag=True,
    help="Only discover videos, don't download",
)
@click.option(
    "--download-only",
    is_flag=True,
    help="Only download already discovered videos",
)
@click.option(
    "--limit",
    type=int,
    help="Limit number of videos per source",
)
@click.option(
    "--source",
    type=click.Choice(["house", "senate"], case_sensitive=False),
    help="Filter by source (house or senate)",
)
@click.option(
    "--resolve-streams",
    is_flag=True,
    default=True,
    help="Resolve final stream URLs during discovery (required for House)",
)
def main(
    cutoff_date,
    cutoff_days,
    config,
    output_dir,
    discover_only,
    download_only,
    limit,
    source,
    resolve_streams,
):
    """Discover and download videos from Michigan House and Senate archives"""
    
    # Load configuration
    try:
        config_path = Path(config) if config else None
        cfg = load_config(config_path)
    except Exception as e:
        click.echo(f"Error loading config: {e}", err=True)
        sys.exit(1)
    
    # Setup logging
    log_config = cfg.logging
    logger = setup_logger(
        level=log_config.get("level", "INFO"),
        log_file=Path(log_config.get("file", "./logs/video_service.log")) if log_config.get("file") else None,
    )
    
    logger.info("Starting video archive service")
    
    # Determine cutoff date
    if cutoff_date:
        cutoff = cutoff_date
    else:
        cutoff = datetime.now() - timedelta(days=cutoff_days)
    
    logger.info(f"Cutoff date: {cutoff.date()}")
    
    # Initialize database
    db_path = cfg.database.get("path", "./data/database/videos.db")
    db_manager = get_db_manager(db_path)
    
    # Initialize services
    state_service = StateService(db_manager)
    discovery_service = DiscoveryService(
        house_archive_url=cfg.discovery.get("house_archive_url"),
        senate_api_url=cfg.discovery.get("senate_api_url"),
    )
    
    # Discover videos
    if not download_only:
        logger.info("Discovering videos...")
        discovered_videos = discovery_service.discover_videos(
            cutoff_date=cutoff,
            cutoff_days=cutoff_days,
            limit=limit,
            source=source,
            resolve_streams=resolve_streams,
        )
        
        # Mark videos as discovered
        for video in discovered_videos:
            state_service.mark_video_discovered(video)
        
        logger.info(f"Discovered {len(discovered_videos)} videos")
        
        if discover_only:
            click.echo(f"Discovered {len(discovered_videos)} videos")
            return
    
    # Download videos
    if not discover_only:
        # Get unprocessed videos
        unprocessed = state_service.get_unprocessed_videos(cutoff_date=cutoff, source=source)
        logger.info(f"Found {len(unprocessed)} unprocessed videos")
        
        if not unprocessed:
            click.echo("No unprocessed videos found")
            return
        
        # Apply limit to downloads if specified
        if limit:
            unprocessed = unprocessed[:limit]
            logger.info(f"Limiting downloads to {limit} videos")
        
        # Initialize download service
        output_directory = Path(output_dir or cfg.download.get("output_directory", "./data/videos"))
        download_service = DownloadService(
            state_service=state_service,
            output_directory=output_directory,
            max_retries=cfg.download.get("max_retries", 3),
            timeout=cfg.download.get("timeout_seconds", 300),
            use_blob_handler=False,  # Set to True if blob URLs are encountered
        )
        
        # Download videos
        logger.info(f"Downloading {len(unprocessed)} videos...")
        results = download_service.download_videos(unprocessed)
        
        # Report results
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        click.echo(f"\nDownload complete:")
        click.echo(f"  Successful: {successful}")
        click.echo(f"  Failed: {failed}")
        
        logger.info(f"Download complete: {successful} successful, {failed} failed")


if __name__ == "__main__":
    main()

