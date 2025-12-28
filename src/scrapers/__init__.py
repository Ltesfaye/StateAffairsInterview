"""Archive scrapers"""

from .base_scraper import BaseScraper
from .house_scraper import HouseScraper
from .senate_scraper import SenateScraper

__all__ = [
    "BaseScraper",
    "HouseScraper",
    "SenateScraper",
]

