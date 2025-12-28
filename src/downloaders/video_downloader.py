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
        chunk_size: int = 8192,
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
        # 4. Any URL that needs special handling
        use_ytdlp = (
            url.endswith('.m3u8') or 
            '.m3u8' in url or 
            'VideoArchivePlayer' in url or
            'cloud.castus.tv' in url
        )
        
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
                                if first_chunk is None:
                                    first_chunk = chunk[:1024]  # Save first 1KB for validation
                                f.write(chunk)
                                bytes_downloaded += len(chunk)
                                pbar.update(len(chunk))
                else:
                    # Unknown size - just show activity
                    with tqdm(unit="B", unit_scale=True, desc=f"Downloading {video_id[:20]}") as pbar:
                        for chunk in response.iter_content(chunk_size=self.chunk_size):
                            if chunk:
                                if first_chunk is None:
                                    first_chunk = chunk[:1024]  # Save first 1KB for validation
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
        """Download HLS stream (m3u8) or extract from player page using yt-dlp"""
        logger.debug(f"[VIDEO_DOWNLOADER] _download_with_ytdlp() called - video_id={video_id}, url={url}")
        try:
            # If this is a player page, extract the m3u8 URL first
            if 'VideoArchivePlayer' in url or 'cloud.castus.tv' in url:
                logger.debug(f"[VIDEO_DOWNLOADER] Detected player page URL, calling _extract_m3u8_from_player_page()")
                m3u8_url = self._extract_m3u8_from_player_page(url)
                if m3u8_url:
                    logger.debug(f"[VIDEO_DOWNLOADER] Successfully extracted m3u8 URL: {m3u8_url}")
                    url = m3u8_url
                else:
                    logger.error(f"[VIDEO_DOWNLOADER] Failed to extract m3u8 URL from player page")
                    return DownloadResult(
                        success=False,
                        video_id=video_id,
                        error_message="Could not extract m3u8 URL from player page",
                    )
            
            # Determine referer based on URL source
            if 'house.mi.gov' in url or 'VideoArchivePlayer' in url:
                referer = 'https://house.mi.gov/'
                origin = 'https://house.mi.gov'
            elif 'cloudfront.net' in url:
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
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': referer,
                    'Origin': origin,
                },
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
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
        """Extract direct video URL (for blob URLs or player pages)"""
        logger.debug(f"[VIDEO_DOWNLOADER] get_direct_video_url() called with: {url}")
        parsed = urlparse(url)
        
        # Check if it's already a direct video URL (path ends with extension, not query string)
        path = parsed.path
        if path.endswith((".mp4", ".m3u8", ".m4v", ".mov")):
            return url
        
        # Check if it's a House player page
        if "VideoArchivePlayer" in url:
            # Try to resolve to direct MP4 first (faster, no Playwright needed)
            params = parse_qs(parsed.query)
            video_file = params.get('video', [None])[0]
            
            if video_file:
                # Construct direct MP4 URL based on discovered pattern
                # Pattern: https://www.house.mi.gov/ArchiveVideoFiles/{video_file}
                direct_url = f"https://www.house.mi.gov/ArchiveVideoFiles/{video_file}"
                logger.info(f"Resolved House player URL to direct MP4: {direct_url}")
                return direct_url
                
            logger.debug(f"[VIDEO_DOWNLOADER] Detected VideoArchivePlayer, returning as-is for yt-dlp extraction")
            return url
        
        # Check if it's a Senate player page
        if "cloud.castus.tv" in url:
            logger.debug(f"[VIDEO_DOWNLOADER] Detected Senate player page, returning as-is for yt-dlp extraction")
            return url
        
        # For m3u8 URLs, return as-is
        if ".m3u8" in url:
            return url
        
        return url
    
    def _extract_m3u8_from_player_page(self, player_url: str) -> Optional[str]:
        """Enhanced extraction for Michigan House Archive"""
        try:
            from playwright.sync_api import sync_playwright
            
            # HOUSE SPECIFIC CHEAT: 
            # Often, if the URL is ?video=NAME.mp4, the manifest is at /Videos/NAME.mp4/index.m3u8
            # We try this if extraction fails.
            parsed_query = parse_qs(urlparse(player_url).query)
            video_param = parsed_query.get('video', [None])[0]
            
            # SENATE SPECIFIC CHEAT:
            # If it's a Castus URL, we can often just return the guessed CloudFront URL 
            # because yt-dlp can handle it if the URL is correct.
            # But the scraper now provides the correct URL, so this shouldn't be needed.
            
            logger.info(f"Extracting m3u8 URL from player page: {player_url}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
                page = context.new_page()
                
                m3u8_urls = []
                
                # Listen to ALL requests, including those in iframes
                def handle_request(request):
                    url = request.url
                    # Log all requests to debug what is happening - using INFO to ensure visibility
                    # logger.info(f"Request: {url[:150]}") 
                    
                    if ".m3u8" in url or ".mpd" in url:
                        logger.info(f"Captured manifest URL: {url}")
                        m3u8_urls.append(url)
                    elif "master" in url or "manifest" in url or ".mp4" in url:
                        logger.info(f"Potential video request: {url}")
                    elif "brightcove" in url or "boltdns" in url:
                        logger.info(f"Brightcove/BoltDNS request: {url}")
                        
                page.on("request", handle_request)

                try:
                    # Use domcontentloaded which is faster and less prone to timeouts from tracking scripts
                    logger.info("Navigating to page...")
                    page.goto(player_url, wait_until="domcontentloaded", timeout=30000)
                    
                    # Wait a bit for initial scripts
                    time.sleep(2)
                    
                    # 1. Handle Iframes: Search for the play button in EVERY frame
                    logger.info("Searching for play buttons in frames...")
                    frames = page.frames
                    logger.info(f"Found {len(frames)} frames")
                    
                    for frame in frames:
                        try:
                            # Common Brightcove/HTML5 play button selectors
                            play_btn = frame.wait_for_selector("button.vjs-big-play-button, .play-button, video", timeout=2000)
                            if play_btn:
                                logger.info(f"Clicked play button inside frame: {frame.url}")
                                play_btn.click(timeout=1000, force=True)
                                # Give it a moment to trigger requests
                                time.sleep(1)
                        except Exception as e:
                            # Expected for frames without play buttons
                            pass

                    # 2. Wait loop for the stream to actually start
                    logger.info("Waiting for m3u8 requests...")
                    for _ in range(10):  # Wait up to 10 seconds checking for urls
                        if m3u8_urls:
                            logger.info(f"Found {len(m3u8_urls)} m3u8 URLs")
                            break
                        time.sleep(1)
                    
                except Exception as e:
                    logger.warning(f"Navigation/Click issue: {e}")
 
                browser.close()
                
                if m3u8_urls:
                    # Prioritize the "master" or "index" manifest
                    master = next((u for u in m3u8_urls if "master" in u or "index" in u), m3u8_urls[0])
                    logger.info(f"Selected manifest: {master}")
                    return master

            # 3. FALLBACK: Michigan House usually follows a predictable pattern
            # If the param is HAGRI-121125.mp4, the stream is likely at:
            if video_param:
                # Try constructed fallback
                fallback_url = f"https://house.mi.gov/Videos/{video_param}/index.m3u8"
                # But verify it first? No, let yt-dlp try it.
                logger.info(f"Manual extraction failed. Trying constructed fallback: {fallback_url}")
                return fallback_url
                
            return None
                    
        except Exception as e:
            logger.error(f"Error in extraction: {e}")
            return None