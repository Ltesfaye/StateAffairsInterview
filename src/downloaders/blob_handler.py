"""Blob URL handler for extracting direct video URLs"""

from typing import Optional
from urllib.parse import urlparse

from ..utils import get_logger

logger = get_logger(__name__)


class BlobHandler:
    """Handles blob URLs and extracts direct video URLs"""
    
    def __init__(self, use_browser: bool = False):
        """
        Initialize blob handler
        
        Args:
            use_browser: Whether to use browser automation (playwright/selenium)
                        for extracting blob URLs. Set to True if videos use blob URLs.
        """
        self.use_browser = use_browser
        self._browser = None
    
    def is_blob_url(self, url: str) -> bool:
        """Check if URL is a blob URL"""
        return url.startswith("blob:")
    
    def extract_video_url(self, url: str) -> Optional[str]:
        """
        Extract direct video URL from blob URL or player page
        
        Args:
            url: Blob URL or player page URL
        
        Returns:
            Direct video URL if extraction successful, None otherwise
        """
        # Check if it's a player page that might need browser automation
        if "VideoArchivePlayer" in url:
            if self.use_browser:
                logger.info(f"Using browser automation to extract video URL from player page: {url}")
                return self._extract_with_browser(url)
            else:
                # Return as-is, let video_downloader handle it
                return url
        
        if not self.is_blob_url(url):
            # Not a blob URL, return as-is
            return url
        
        if not self.use_browser:
            logger.warning(
                "Blob URL detected but browser automation not enabled. "
                "Set use_browser=True to extract blob URLs."
            )
            return None
        
        # Use browser automation to extract blob URL
        try:
            return self._extract_with_browser(url)
        except Exception as e:
            logger.error(f"Error extracting blob URL: {e}", exc_info=True)
            return None
    
    def _extract_with_browser(self, url: str) -> Optional[str]:
        """Extract video URL using browser automation"""
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Navigate to page
                page.goto(url, wait_until="networkidle")
                
                # Find video element
                video_element = page.query_selector("video")
                if video_element:
                    # Get video source
                    video_src = video_element.get_attribute("src")
                    if video_src:
                        browser.close()
                        return video_src
                    
                    # Try source elements
                    source_elements = page.query_selector_all("video > source")
                    for source in source_elements:
                        src = source.get_attribute("src")
                        if src and not src.startswith("blob:"):
                            browser.close()
                            return src
                
                browser.close()
                return None
                
        except ImportError:
            logger.error(
                "playwright not installed. Install with: pip install playwright && playwright install"
            )
            return None
        except Exception as e:
            logger.error(f"Browser automation error: {e}", exc_info=True)
            return None
    
    def cleanup(self):
        """Cleanup browser resources if needed"""
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None

