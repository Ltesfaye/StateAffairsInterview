"""Video downloader with streaming and progress tracking"""

import re
import time
import urllib3
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urljoin, parse_qs

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False

from ..models import DownloadResult
from ..utils import get_logger

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = get_logger(__name__)


class VideoDownloader:
    """Downloads videos with streaming, progress tracking, and retry logic"""
    
    def __init__(
        self,
        max_retries: int = 3,
        timeout: int = 300,
        chunk_size: int = 1024 * 1024,  # 1MB Chunks
    ):
        """Initialize video downloader"""
        self.max_retries = max_retries
        self.timeout = timeout
        self.chunk_size = chunk_size
    
    def download(
        self,
        url: str,
        output_path: Path,
        video_id: str = "",
    ) -> DownloadResult:
        """
        Download video from URL to output path
        
        Args:
            url: Video URL to download
            output_path: Path where video should be saved
            video_id: Video ID for logging
        
        Returns:
            DownloadResult with success status and details
        """
        logger.debug(f"[VIDEO_DOWNLOADER] download() called - video_id={video_id}, url={url}")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if file already exists
        if output_path.exists():
            logger.debug(f"[VIDEO_DOWNLOADER] File already exists: {output_path}")
            return DownloadResult(
                success=True,
                video_id=video_id,
                file_path=output_path,
                bytes_downloaded=output_path.stat().st_size,
            )
        
        # Use yt-dlp for:
        # 1. HLS streams (.m3u8)
        # 2. House player pages (VideoArchivePlayer) - Brightcove HLS
        # 3. Senate player pages (cloud.castus.tv)
        # 4. Any URL from House or Senate domains (to enable multi-threaded aria2c)
        use_ytdlp = (
            url.endswith('.m3u8') or 
            '.m3u8' in url or 
            'VideoArchivePlayer' in url or
            'cloud.castus.tv' in url or
            'house.mi.gov' in url or
            'cloudfront.net' in url
        )
        
        # #region agent log
        try:
            import json
            from datetime import datetime
            with open("/Users/leultesfaye/Desktop/StateAffair-Interview/.cursor/debug.log", "a") as log_f:
                log_f.write(json.dumps({
                    "sessionId": "speed-debug",
                    "runId": "speed-test-1",
                    "hypothesisId": "SYSTEM",
                    "location": "video_downloader.py:88",
                    "message": "Download method selected",
                    "data": {
                        "url": url,
                        "use_ytdlp": use_ytdlp,
                        "YT_DLP_AVAILABLE": YT_DLP_AVAILABLE
                    },
                    "timestamp": int(datetime.now().timestamp() * 1000)
                }) + "\n")
        except: pass
        # #endregion
        
        logger.debug(f"[VIDEO_DOWNLOADER] use_ytdlp={use_ytdlp} (url ends with .m3u8: {url.endswith('.m3u8')}, contains .m3u8: {'.m3u8' in url}, contains VideoArchivePlayer: {'VideoArchivePlayer' in url}, contains cloud.castus.tv: {'cloud.castus.tv' in url})")
        
        if use_ytdlp:
            if not YT_DLP_AVAILABLE:
                logger.error(f"[VIDEO_DOWNLOADER] yt-dlp not available")
                return DownloadResult(
                    success=False,
                    video_id=video_id,
                    error_message="yt-dlp is required but not installed. Install with: pip install yt-dlp",
                )
            logger.debug(f"[VIDEO_DOWNLOADER] Calling _download_with_ytdlp()")
            return self._download_with_ytdlp(url, output_path, video_id)
        
        # For direct MP4 files, use requests with retries
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = self._download_with_progress(url, output_path, video_id)
                if result.success:
                    return result
                last_error = result.error_message
                
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
        
        # All retries failed
        return DownloadResult(
            success=False,
            video_id=video_id,
            error_message=f"Failed after {self.max_retries} attempts: {last_error}",
        )
    
    def _download_with_progress(
        self,
        url: str,
        output_path: Path,
        video_id: str,
    ) -> DownloadResult:
        """Download with progress bar"""
        try:
            # Start request with streaming
            # Note: verify=False is used here due to SSL certificate issues on some systems
            response = requests.get(
                url,
                stream=True,
                timeout=self.timeout,
                verify=False,  # Disable SSL verification (fix certificates in production)
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            response.raise_for_status()
            
            # Get file size if available
            total_size = int(response.headers.get("content-length", 0))
            
            # Download with progress bar
            bytes_downloaded = 0
            first_chunk = None
            start_time = time.time()
            chunk_times = []
            
            with open(output_path, "wb") as f:
                if total_size > 0:
                    # Known size - use progress bar
                    with tqdm(
                        total=total_size,
                        unit="B",
                        unit_scale=True,
                        desc=f"Downloading {video_id[:20]}",
                    ) as pbar:
                        for chunk in response.iter_content(chunk_size=self.chunk_size):
                            if chunk:
                                # #region agent log
                                c_start = time.time()
                                # #endregion
                                if first_chunk is None:
                                    first_chunk = chunk[:1024]  # Save first 1KB for validation
                                f.write(chunk)
                                bytes_downloaded += len(chunk)
                                pbar.update(len(chunk))
                                # #region agent log
                                c_end = time.time()
                                chunk_times.append(c_end - c_start)
                                if len(chunk_times) % 50 == 0:
                                    try:
                                        import json
                                        from datetime import datetime
                                        with open("/Users/leultesfaye/Desktop/StateAffair-Interview/.cursor/debug.log", "a") as log_f:
                                            log_f.write(json.dumps({
                                                "sessionId": "speed-debug",
                                                "runId": "speed-test-1",
                                                "hypothesisId": "B",
                                                "location": "video_downloader.py:165",
                                                "message": "Requests Chunk Performance",
                                                "data": {
                                                    "chunk_size": self.chunk_size,
                                                    "avg_chunk_time": sum(chunk_times[-50:]) / 50,
                                                    "bytes_downloaded": bytes_downloaded,
                                                    "total_size": total_size
                                                },
                                                "timestamp": int(datetime.now().timestamp() * 1000)
                                            }) + "\n")
                                    except: pass
                                # #endregion
                else:
                    # Unknown size - just show activity
                    with tqdm(unit="B", unit_scale=True, desc=f"Downloading {video_id[:20]}") as pbar:
                        for chunk in response.iter_content(chunk_size=self.chunk_size):
                            if chunk:
                                f.write(chunk)
                                bytes_downloaded += len(chunk)
                                pbar.update(len(chunk))
            
            # Validate that we downloaded a video file, not HTML
            if first_chunk:
                first_chunk_lower = first_chunk.lower()
                # Check for HTML indicators
                if b"<!doctype" in first_chunk_lower or b"<html" in first_chunk_lower or b"<html" in first_chunk:
                    # This is HTML, not a video file
                    output_path.unlink()  # Delete the invalid file
                    return DownloadResult(
                        success=False,
                        video_id=video_id,
                        error_message=f"Downloaded HTML instead of video file. URL may be incorrect: {url}",
                    )
                # Check for MP4 file signature (should start with ftyp box)
                # MP4 files typically start with bytes that indicate ftyp box
                if bytes_downloaded < 1000:  # Very small file is suspicious
                    output_path.unlink()  # Delete the invalid file
                    return DownloadResult(
                        success=False,
                        video_id=video_id,
                        error_message=f"Downloaded file is too small ({bytes_downloaded} bytes). Expected video file.",
                    )
            
            return DownloadResult(
                success=True,
                video_id=video_id,
                file_path=output_path,
                bytes_downloaded=bytes_downloaded,
            )
            
        except requests.exceptions.RequestException as e:
            return DownloadResult(
                success=False,
                video_id=video_id,
                error_message=f"Request error: {str(e)}",
            )
        except Exception as e:
            return DownloadResult(
                success=False,
                video_id=video_id,
                error_message=f"Unexpected error: {str(e)}",
            )
    
    def _download_with_ytdlp(
        self,
        url: str,
        output_path: Path,
        video_id: str,
    ) -> DownloadResult:
        """Download HLS stream (m3u8) or direct URL using yt-dlp with speed optimizations"""
        logger.debug(f"[VIDEO_DOWNLOADER] _download_with_ytdlp() called - video_id={video_id}, url={url}")
        try:
            # Determine referer based on URL source
            if 'house.mi.gov' in url or 'VideoArchivePlayer' in url:
                referer = 'https://house.mi.gov/'
                origin = 'https://house.mi.gov'
            elif 'cloudfront.net' in url or 'castus.tv' in url:
                referer = 'https://cloud.castus.tv/vod/misenate/'
                origin = 'https://cloud.castus.tv'
            else:
                referer = url.split('/outputs')[0] if '/outputs' in url else url
                origin = referer
            
            # Create progress bar
            pbar = tqdm(total=100, unit='%', desc=f"Downloading {video_id[:20]}", leave=False)
            
            def progress_hook(d):
                if d['status'] == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    if total > 0:
                        percent = min(100, (downloaded / total) * 100)
                        pbar.n = int(percent)
                        pbar.refresh()
                elif d['status'] == 'finished':
                    pbar.n = 100
                    pbar.refresh()
            
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': str(output_path.with_suffix('')),  # Remove extension, yt-dlp adds it
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,  # Disable SSL certificate verification
                'progress_hooks': [progress_hook],
                
                # --- TURBO SPEED OPTIMIZATIONS ---
                'external_downloader': 'aria2c',
                'external_downloader_args': [
                    '--min-split-size=1M',
                    '--max-connection-per-server=16',
                    '--split=16',
                    '--retry-wait=2',
                    '--max-tries=5',
                    '--uri-selector=feedback'
                ],
                'concurrent_fragments': 16,  # Parallel segment downloads for HLS
                'buffersize': 1024 * 1024,    # 1MB buffer
                'http_chunk_size': 1024 * 1024, # 1MB chunks for better throughput
                # ---------------------------
                
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': referer,
                    'Origin': origin,
                },
            }
            
            # #region agent log
            try:
                import json
                from datetime import datetime
                with open("/Users/leultesfaye/Desktop/StateAffair-Interview/.cursor/debug.log", "a") as log_f:
                    log_f.write(json.dumps({
                        "sessionId": "speed-debug",
                        "runId": "speed-test-1",
                        "hypothesisId": "A,C",
                        "location": "video_downloader.py:281",
                        "message": "Starting yt-dlp download",
                        "data": {
                            "url": url,
                            "ydl_opts_fragment_concurrency": ydl_opts.get('concurrent_fragments'),
                            "aria2c_args": ydl_opts.get('external_downloader_args')
                        },
                        "timestamp": int(datetime.now().timestamp() * 1000)
                    }) + "\n")
            except: pass
            # #endregion

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # #region agent log
            try:
                with open("/Users/leultesfaye/Desktop/StateAffair-Interview/.cursor/debug.log", "a") as log_f:
                    log_f.write(json.dumps({
                        "sessionId": "speed-debug",
                        "runId": "speed-test-1",
                        "hypothesisId": "A,C",
                        "location": "video_downloader.py:295",
                        "message": "Finished yt-dlp download",
                        "data": {"video_id": video_id},
                        "timestamp": int(datetime.now().timestamp() * 1000)
                    }) + "\n")
            except: pass
            # #endregion
            
            pbar.close()
            
            # yt-dlp may add extension or save as-is
            # 1. Check if the exact requested path exists
            if output_path.exists():
                file_size = output_path.stat().st_size
            else:
                # 2. Check if it saved without extension (as requested in outtmpl)
                base_path = output_path.with_suffix('')
                if base_path.exists():
                    base_path.rename(output_path)
                    file_size = output_path.stat().st_size
                else:
                    # 3. Try with common extensions yt-dlp might have added
                    found = False
                    for ext in ['.mp4', '.mkv', '.webm']:
                        alt_path = base_path.with_suffix(ext)
                        if alt_path.exists() and alt_path != output_path:
                            alt_path.rename(output_path)
                            file_size = output_path.stat().st_size
                            found = True
                            break
                    
                    if not found:
                        return DownloadResult(
                            success=False,
                            video_id=video_id,
                            error_message="yt-dlp download completed but output file not found",
                        )
            
            return DownloadResult(
                success=True,
                video_id=video_id,
                file_path=output_path,
                bytes_downloaded=file_size,
            )
            
        except Exception as e:
            if 'pbar' in locals():
                pbar.close()
            return DownloadResult(
                success=False,
                video_id=video_id,
                error_message=f"yt-dlp failed: {str(e)}",
            )
    
    def get_direct_video_url(self, url: str) -> Optional[str]:
        """Check if URL is a direct video URL"""
        logger.debug(f"[VIDEO_DOWNLOADER] get_direct_video_url() called with: {url}")
        parsed = urlparse(url)
        
        # Check if it's already a direct video URL (path ends with extension, not query string)
        path = parsed.path
        if path.endswith((".mp4", ".m3u8", ".m4v", ".mov")):
            return url
        
        # For m3u8 URLs, return as-is
        if ".m3u8" in url:
            return url
        
        return url

    # Playwright extraction moved to Scrapers layer for architectural decoupling