#!/usr/bin/env python3
"""Test URL extraction from player page"""

import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, urljoin

urllib3.disable_warnings()

player_url = 'https://house.mi.gov/VideoArchivePlayer?video=HAGRI-103025.mp4'
print(f"Testing player page: {player_url}\n")

# Fetch the player page
print("1. Fetching player page HTML...")
response = requests.get(player_url, verify=False, timeout=10, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})
print(f"   Status: {response.status_code}")
print(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")
print(f"   Content length: {len(response.content)} bytes\n")

# Parse HTML
print("2. Parsing HTML for video source...")
soup = BeautifulSoup(response.content, 'html.parser')

# Look for video tag
video_tag = soup.find('video')
if video_tag:
    print(f"   Found <video> tag")
    src = video_tag.get('src')
    print(f"   Video src attribute: {src}")
    
    # Check source elements
    source_tags = video_tag.find_all('source')
    for i, source in enumerate(source_tags):
        print(f"   Source {i+1}: {source.get('src')} (type: {source.get('type', 'N/A')})")
    
    # Try to find video URL in JavaScript
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'mp4' in script.string.lower():
            print(f"   Found script with 'mp4' reference")
            # Look for URL patterns
            import re
            urls = re.findall(r'https?://[^\s"\'<>]+\.mp4', script.string)
            if urls:
                print(f"   Found MP4 URLs in script: {urls[:3]}")
else:
    print("   No <video> tag found")
    
    # Check for iframe or embed
    iframe = soup.find('iframe')
    if iframe:
        print(f"   Found <iframe> with src: {iframe.get('src')}")
    
    # Print first 1000 chars of HTML to see structure
    print(f"\n   First 1000 chars of HTML:")
    print(f"   {response.text[:1000]}")

# Try common direct URL patterns
print("\n3. Testing common direct URL patterns...")
parsed = urlparse(player_url)
params = parse_qs(parsed.query)
video_filename = params.get('video', [None])[0]

if video_filename:
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    test_urls = [
        f"{base_url}/VideoArchive/{video_filename}",
        f"{base_url}/videos/{video_filename}",
        f"{base_url}/video/{video_filename}",
        f"{base_url}/{video_filename}",
    ]
    
    for test_url in test_urls:
        try:
            r = requests.head(test_url, verify=False, timeout=5, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            content_type = r.headers.get('Content-Type', '')
            content_length = r.headers.get('Content-Length', 'N/A')
            print(f"   {test_url}")
            print(f"      Status: {r.status_code}, Type: {content_type}, Size: {content_length}")
            if r.status_code == 200 and 'video' in content_type.lower():
                print(f"      ✓ THIS LOOKS LIKE A VALID VIDEO URL!")
                break
        except Exception as e:
            print(f"   {test_url}: Error - {e}")

