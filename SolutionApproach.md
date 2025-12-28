# Video Archive Microservice Framework (Turbo Edition)

## Architecture Overview

The system is a high-performance, microservice-based framework designed for automated discovery and high-speed downloading of legislative video archives.

1. **Current Phase**: Discover and download videos from past 1-2 months (Optimized with Turbo Speed)
2. **Future Phase**: Scheduled detection of new uploads (cron/scheduler)
3. **Future Phase**: Video transcription service (Whisper integration)
4. **Future Phase**: Horizontal scaling and PostgreSQL migration

**Key Architectural Shift**: The system uses a **Decoupled Extraction Pipeline**. Extraction (CPU/RAM-heavy browser work) is done during Discovery to resolve the direct `stream_url`, while Download (Network-heavy IO) is done by a lightweight worker using `yt-dlp` + `aria2c`.

## Research Findings

### Michigan House Archive
- **URL**: `https://house.mi.gov/VideoArchive`
- **Format**: HTML page with expandable committee lists
- **Video Source**: Direct MP4 files or HLS manifests
- **Turbo Resolution**: Uses Playwright to intercept the `.m3u8` manifest from the player page, with a fallback to direct MP4 links at `house.mi.gov/ArchiveVideoFiles/`.
- **Scraping Method**: Parse HTML, expand committee sections, extract video metadata.

### Michigan Senate Archive  
- **URL**: `https://cloud.castus.tv/vod/misenate/?page=ALL`
- **Format**: React SPA using AWS Lambda APIs
- **Video Source**: Amazon CloudFront CDN (Castus.tv)
- **Turbo Resolution**: Uses the dedicated Castus Resolution API (`/upload/get`) to obtain signed/direct HLS manifests, bypassing 403 Forbidden errors.
- **Scraping Method**: Use API calls to fetch video metadata, resolve stream URLs via Resolution API.

## Microservice Architecture

### Core Services

#### 1. Video Discovery Service (`src/services/discovery_service.py`)
**Purpose**: Discover videos from archives within a date range and resolve their high-speed download links.

- **Interface**: `discover_videos(cutoff_date: datetime, limit: Optional[int] = None) -> List[VideoMetadata]`
- **Responsibilities**:
  - Orchestrate scraping from House and Senate archives
  - **Resolution Phase (Turbo)**: Execute Playwright or API calls to find the `stream_url`
  - Filter by cutoff date (past 1-2 months)
  - Return standardized video metadata with pre-resolved stream links
- **Future Extension**: Can be called by scheduler service to detect new uploads

#### 2. Video Download Service (`src/services/download_service.py`)
**Purpose**: High-speed video downloading to local storage.

- **Interface**: `download_video(video_metadata: VideoMetadata, output_dir: Path) -> DownloadResult`
- **Responsibilities**:
  - **Turbo Download**: Force `yt-dlp` + `aria2c` for 16x parallel connection downloading
  - Check if video already downloaded (idempotent)
  - Handle blob URLs if needed via earlier resolution
  - Stream large files with progress tracking
  - Retry on failures
  - Return download status and file path
- **Future Extension**: Can be triggered by discovery service or scheduler

#### 3. State Management Service (`src/services/state_service.py`)
**Purpose**: Track processed videos and system state. Designed for future migration to PostgreSQL.

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
    url TEXT,     -- Original player page URL
    stream_url TEXT, -- Resolved direct stream URL (Turbo Addition)
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
4. **Bandwidth Saturation**: Multi-connection `aria2c` logic ensures 100% network utilization
5. **Decoupling**: Extraction (CPU/RAM/Browser) is separated from Downloading (Network/IO)
6. **Error Handling**: Graceful failures, retry logic, logging
7. **Production-Ready**: Proper logging, configuration management, error handling

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
  chunk_size: 1048576 # 1MB for Turbo performance
  aria2c_connections: 16

database:
  path: "./data/database/videos.db"
  connection_pool_size: 5
  # Future PostgreSQL config
  # url: "postgresql://user:pass@localhost:5432/videos"
```

## Dependencies

- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing  
- `playwright` - Headless browser for manifest resolution
- `yt-dlp` - Stream orchestration and metadata handling
- `aria2` - External downloader for multi-threaded fragmentation
- `python-dateutil` - Date parsing
- `tqdm` - Progress bars
- `pyyaml` - Configuration management
- `sqlalchemy` - Database ORM (Supports SQLite/PostgreSQL)
- `click` - CLI interface

## Testing Strategy

- Unit tests for each service
- Integration tests for scraper + download flow
- Mock external APIs/HTML for testing
- Test idempotency (running multiple times)
- Test error scenarios and retries

## Implementation Todos (Phase 1 Status)

1. [x] **Data Models**: Create data models (VideoMetadata, ProcessingStatus) for standardized video information
2. [x] **Database Schema**: Design and implement database schema with SQLite (including `stream_url`)
3. [x] **State Service**: Implement state service for tracking processed videos and preventing duplicates
4. [x] **House Scraper**: Implement House archive scraper with Playwright stream resolution
5. [x] **Senate Scraper**: Implement Senate archive scraper with official resolution API
6. [x] **Discovery Service**: Build discovery service with decoupled resolution phase
7. [x] **Video Downloader**: Implement Turbo downloader with `yt-dlp` and `aria2c` multi-threading
8. [ ] **Blob Handler**: Deprecated (handled by resolution phase)
9. [x] **Download Service**: Build download service that checks state, downloads videos, and updates state
10. [x] **Config Management**: Create configuration management system with YAML config
11. [x] **Main CLI**: Build CLI entry point that orchestrates discovery and download services
12. [x] **Error Handling**: Add comprehensive error handling, retries, logging, and graceful failure recovery
13. [x] **Idempotency Tests**: Test that system is safe to run multiple times without duplicate processing

