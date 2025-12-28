# Video Archive Microservice Framework

A microservice-based system for discovering and downloading videos from Michigan House and Senate archives.

## Features

- **Video Discovery**: Automatically discovers videos from both House and Senate archives
- **Date Filtering**: Filters videos by date (default: past 1-2 months)
- **State Management**: Tracks processed videos to prevent duplicates
- **Idempotent Operations**: Safe to run multiple times
- **Progress Tracking**: Shows download progress with progress bars
- **Error Handling**: Retry logic and graceful error recovery

## Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. (Optional) Install Playwright for blob URL extraction:

```bash
playwright install
```

## Configuration

Edit `config/config.yaml` to customize settings:

- `discovery.cutoff_days`: Number of days to look back (default: 60)
- `download.output_directory`: Where to save downloaded videos
- `database.path`: SQLite database location

## Usage

### Basic Usage

Discover and download videos from the past 60 days:

```bash
python -m src.main
```

### Custom Cutoff Date

Only process videos after a specific date:

```bash
python -m src.main --cutoff-date 2024-11-01
```

### Custom Days

Look back a different number of days:

```bash
python -m src.main --cutoff-days 30
```

### Discover Only

Only discover videos without downloading:

```bash
python -m src.main --discover-only
```

### Download Only

Only download already discovered videos:

```bash
python -m src.main --download-only
```

### Limit Results

Limit number of videos per source:

```bash
python -m src.main --limit 10
```

## Project Structure

```
StateAffair-Interview/
├── src/
│   ├── services/       # Core microservices
│   ├── scrapers/       # Archive scrapers
│   ├── downloaders/    # Download handlers
│   ├── models/         # Data models
│   ├── database/       # Database layer
│   └── utils/          # Utilities
├── config/             # Configuration files
├── data/               # Data storage (created at runtime)
└── logs/               # Log files (created at runtime)
```

## Architecture

The system is built with a microservice architecture:

- **Discovery Service**: Orchestrates video discovery from multiple archives
- **Download Service**: Manages video downloads with state tracking
- **State Service**: Tracks processed videos in SQLite database

## Future Extensions

- Scheduled detection (cron jobs)
- Video transcription service
- REST API layer
- Horizontal scaling support

## License

See LICENSE file for details.

