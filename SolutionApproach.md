# Video Archive Microservice Framework

## Architecture Overview

This is a microservice-based system designed to:
1. **Current Phase**: Discover and download videos from past 1-2 months
2. **Future Phase**: Scheduled detection of new uploads (cron/scheduler)
3. **Future Phase**: Video transcription service
4. **Future Phase**: Horizontal scaling for multiple uploads

The system is built with clear service boundaries, making it easy to extend with additional capabilities.

## Research Findings

### Michigan House Archive
- **URL**: `https://house.mi.gov/VideoArchive`
- **Format**: HTML page with expandable committee lists
- **Video URL Pattern**: `/VideoArchivePlayer?video={FILENAME}.mp4`
- **Filename Format**: `{COMMITTEE_CODE}-{MMDDYY}.mp4` (e.g., `HAGRI-022025.mp4`)
- **Video Source**: Direct MP4 files served from `house.mi.gov`
- **Scraping Method**: Parse HTML, expand committee sections, extract video links with dates

### Michigan Senate Archive  
- **URL**: `https://cloud.castus.tv/vod/misenate/?page=ALL`
- **Format**: React SPA using AWS Lambda APIs
- **API Endpoint**: `POST https://tf4pr3wftk.execute-api.us-west-2.amazonaws.com/default/api/all`
- **Video Storage**: CloudFront CDN at `https://dlttx48mxf9m3.cloudfront.net/outputs/{ID}/...`
- **Date Format**: Videos have dates like "25-12-23" (YY-MM-DD format)
- **Scraping Method**: Use API calls to fetch video metadata, extract video URLs from responses

## Microservice Architecture

### Core Services

#### 1. Video Discovery Service (`src/services/discovery_service.py`)
**Purpose**: Discover videos from both archives within a date range

- **Interface**: `discover_videos(cutoff_date: datetime, limit: Optional[int] = None) -> List[VideoMetadata]`
- **Responsibilities**:
  - Orchestrate scraping from House and Senate archives
  - Filter by cutoff date (past 1-2 months)
  - Return standardized video metadata
  - Handle errors gracefully with retries
- **Future Extension**: Can be called by scheduler service to detect new uploads

#### 2. Video Download Service (`src/services/download_service.py`)
**Purpose**: Download videos to local storage

- **Interface**: `download_video(video_metadata: VideoMetadata, output_dir: Path) -> DownloadResult`
- **Responsibilities**:
  - Check if video already downloaded (idempotent)
  - Handle blob URLs if needed
  - Stream large files with progress tracking
  - Retry on failures
  - Return download status and file path
- **Future Extension**: Can be triggered by discovery service or scheduler

#### 3. State Management Service (`src/services/state_service.py`)
**Purpose**: Track processed videos and system state

- **Interface**: 
  - `is_video_processed(video_id: str, source: str) -> bool`
  - `mark_video_processed(video: VideoMetadata, status: ProcessingStatus) -> None`
  - `get_unprocessed_videos(cutoff_date: datetime) -> List[VideoMetadata]`
- **Responsibilities**:
  - Maintain database of processed videos
  - Track download status, transcription status
  - Prevent duplicate processing
  - Support idempotent operations
- **Database Schema** (SQLite for now, extensible to PostgreSQL):
  ```sql
  videos (
    id TEXT PRIMARY KEY,
    source TEXT,  -- 'house' or 'senate'
    filename TEXT,
    url TEXT,
    date_recorded DATE,
    committee TEXT,
    date_discovered TIMESTAMP,
    download_status TEXT,  -- 'pending', 'downloaded', 'failed'
    download_path TEXT,
    transcription_status TEXT,  -- 'pending', 'completed', 'failed' (future)
    transcription_path TEXT,  -- (future)
    created_at TIMESTAMP,
    updated_at TIMESTAMP
  )
  ```

### Supporting Modules

#### 4. Archive Scrapers (`src/scrapers/`)
- **House Scraper** (`house_scraper.py`): HTML parsing, date extraction
- **Senate Scraper** (`senate_scraper.py`): API calls, JSON parsing
- **Base Scraper Interface** (`base_scraper.py`): Abstract interface for extensibility

#### 5. Download Handlers (`src/downloaders/`)
- **Video Downloader** (`video_downloader.py`): Direct MP4 downloads
- **Blob Handler** (`blob_handler.py`): Extract URLs from blob sources (if needed)

#### 6. Data Models (`src/models/`)
- **VideoMetadata**: Standardized video information
- **ProcessingStatus**: Enum for tracking states
- **DownloadResult**: Download operation results

## Current Implementation Scope

### Phase 1: Core Discovery & Download (Current)

#### 1.1 Discovery Service Implementation
- Implement House and Senate scrapers
- Create unified discovery service
- Add date filtering (past 1-2 months)
- Error handling and retries

#### 1.2 Download Service Implementation  
- Implement video downloader with streaming
- Add blob URL handling (if needed)
- Progress tracking
- Idempotent downloads (check state service first)

#### 1.3 State Service Implementation
- SQLite database setup
- Video tracking schema
- Query methods for processed videos
- Transaction support for atomic operations

#### 1.4 Main Entry Point (`src/main.py`)
- CLI interface for manual execution
- Accept cutoff date parameter
- Discover videos from both sources
- Download unprocessed videos
- Update state service
- Logging and error reporting

## Future Extension Points

### Phase 2: Scheduled Detection (Future)
- **Scheduler Service** (`src/services/scheduler_service.py`)
  - Cron job integration
  - Periodic discovery runs
  - Detect new uploads since last run
  - Trigger download service for new videos
  - Can be deployed as separate service or same process

### Phase 3: Transcription Service (Future)
- **Transcription Service** (`src/services/transcription_service.py`)
  - Accept video file path
  - Use local (Whisper) or cloud (OpenAI, AssemblyAI) transcription
  - Store transcription results
  - Update state service with transcription status
  - Can be separate microservice or integrated

### Phase 4: API Layer (Future)
- REST API or message queue interface
- Allow external systems to trigger discovery/download
- Webhook support for notifications
- Health check endpoints

## File Structure

```
StateAffair-Interview/
├── src/
│   ├── services/           # Core microservices
│   │   ├── __init__.py
│   │   ├── discovery_service.py
│   │   ├── download_service.py
│   │   └── state_service.py
│   ├── scrapers/           # Archive-specific scrapers
│   │   ├── __init__.py
│   │   ├── base_scraper.py
│   │   ├── house_scraper.py
│   │   └── senate_scraper.py
│   ├── downloaders/        # Download handlers
│   │   ├── __init__.py
│   │   ├── video_downloader.py
│   │   └── blob_handler.py
│   ├── models/             # Data models
│   │   ├── __init__.py
│   │   ├── video_metadata.py
│   │   └── processing_status.py
│   ├── database/           # Database layer
│   │   ├── __init__.py
│   │   ├── db_manager.py
│   │   └── migrations/
│   ├── utils/              # Utilities
│   │   ├── __init__.py
│   │   ├── date_parser.py
│   │   ├── logger.py
│   │   └── config.py
│   └── main.py             # CLI entry point
├── config/
│   ├── config.yaml         # Configuration file
│   └── logging.yaml        # Logging configuration
├── data/                   # Data storage
│   ├── videos/             # Downloaded videos
│   └── database/           # SQLite database
├── tests/                  # Unit and integration tests
├── requirements.txt
├── README.md
├── .env.example
└── .gitignore
```

## Key Design Principles

1. **Idempotency**: All operations safe to run multiple times
2. **Modularity**: Clear service boundaries, easy to extend
3. **State Management**: Centralized tracking prevents duplicates
4. **Error Handling**: Graceful failures, retry logic, logging
5. **Extensibility**: Future services can be added without modifying core
6. **Production-Ready**: Proper logging, configuration management, error handling

## Configuration

```yaml
# config/config.yaml
discovery:
  cutoff_days: 60  # Past 1-2 months
  house_archive_url: "https://house.mi.gov/VideoArchive"
  senate_archive_url: "https://cloud.castus.tv/vod/misenate/"
  senate_api_url: "https://tf4pr3wftk.execute-api.us-west-2.amazonaws.com/default/api/all"

download:
  output_directory: "./data/videos"
  max_retries: 3
  timeout_seconds: 300
  chunk_size: 8192

database:
  path: "./data/database/videos.db"
  connection_pool_size: 5

logging:
  level: "INFO"
  file: "./logs/video_service.log"
```

## Dependencies

- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing  
- `playwright` or `selenium` - For blob URL extraction (if needed)
- `python-dateutil` - Date parsing
- `tqdm` - Progress bars
- `pyyaml` - Configuration management
- `sqlalchemy` - Database ORM (for future PostgreSQL migration)
- `click` - CLI interface

## Testing Strategy

- Unit tests for each service
- Integration tests for scraper + download flow
- Mock external APIs/HTML for testing
- Test idempotency (running multiple times)
- Test error scenarios and retries

## Implementation Todos

1. **Data Models**: Create data models (VideoMetadata, ProcessingStatus) for standardized video information
2. **Database Schema**: Design and implement database schema with SQLite for tracking processed videos
3. **State Service**: Implement state service for tracking processed videos and preventing duplicates
4. **House Scraper**: Implement House archive scraper to parse HTML and extract video links with dates
5. **Senate Scraper**: Implement Senate archive scraper to call API and extract video metadata from JSON
6. **Discovery Service**: Build discovery service that orchestrates both scrapers and filters by date
7. **Video Downloader**: Implement video downloader with streaming, progress tracking, and retry logic
8. **Blob Handler**: Implement blob URL handler for extracting direct video URLs when needed
9. **Download Service**: Build download service that checks state, downloads videos, and updates state
10. **Config Management**: Create configuration management system with YAML config and environment variables
11. **Main CLI**: Build CLI entry point that orchestrates discovery and download services
12. **Error Handling**: Add comprehensive error handling, retries, logging, and graceful failure recovery
13. **Idempotency Tests**: Test that system is safe to run multiple times without duplicate processing

