"""Date parsing utilities for different archive formats"""

import re
from datetime import datetime
from typing import Optional
from dateutil import parser as date_parser


def parse_date(date_string: str, default: Optional[datetime] = None) -> Optional[datetime]:
    """Generic date parser that tries multiple formats"""
    if not date_string:
        return default
    
    try:
        return date_parser.parse(date_string)
    except (ValueError, TypeError):
        return default


def parse_house_date(date_string: str) -> Optional[datetime]:
    """
    Parse date from House archive format.
    Examples: 
    - "Thursday, February 20, 2025"
    - "Wednesday, April 16, 2025 - Part 2"
    """
    if not date_string:
        return None
    
    try:
        # Remove day of week prefix if present
        date_string = date_string.strip()
        
        # Remove suffixes like " - Part 2", " - Part 1", etc.
        date_string = re.sub(r'\s*-\s*Part\s+\d+', '', date_string, flags=re.IGNORECASE)
        
        if "," in date_string:
            # Format: "Thursday, February 20, 2025"
            parts = date_string.split(",", 1)
            if len(parts) == 2:
                date_string = parts[1].strip()
        
        return date_parser.parse(date_string)
    except (ValueError, TypeError):
        return None


def parse_senate_date(date_string: str) -> Optional[datetime]:
    """
    Parse date from Senate archive format.
    Example: "25-12-23" (YY-MM-DD) or "Senate Session 25-12-23"
    """
    if not date_string:
        return None
    
    try:
        # Extract date pattern YY-MM-DD from string
        import re
        pattern = r'(\d{2})-(\d{2})-(\d{2})'
        match = re.search(pattern, date_string)
        
        if match:
            year, month, day = match.groups()
            # Convert YY to YYYY (assuming 20XX)
            year = f"20{year}"
            date_string = f"{year}-{month}-{day}"
            return datetime.strptime(date_string, "%Y-%m-%d")
        
        # Fallback to generic parser
        return parse_date(date_string)
    except (ValueError, TypeError):
        return None

