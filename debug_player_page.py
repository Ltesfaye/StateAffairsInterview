#!/usr/bin/env python3
"""Debug script to understand House player page structure"""

import requests
import urllib3
from bs4 import BeautifulSoup
import re

urllib3.disable_warnings()

player_url = 'https://house.mi.gov/VideoArchivePlayer?video=HAGRI-103025.mp4'
print(f"Analyzing player page: {player_url}\n")

# Fetch the page
r = requests.get(player_url, verify=False, timeout=10, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

print(f"Status: {r.status_code}")
print(f"Content-Type: {r.headers.get('Content-Type')}")
print(f"Content-Length: {len(r.content)} bytes\n")

# Save HTML for inspection
with open('/tmp/player_page.html', 'w') as f:
    f.write(r.text)
print("Saved HTML to /tmp/player_page.html for inspection\n")

# Parse HTML
soup = BeautifulSoup(r.content, 'html.parser')

# Look for video elements
print("=== Searching for video elements ===")
video_tags = soup.find_all('video')
print(f"Found {len(video_tags)} <video> tags")
for i, video in enumerate(video_tags):
    print(f"\nVideo {i+1}:")
    print(f"  src: {video.get('src')}")
    print(f"  poster: {video.get('poster')}")
    sources = video.find_all('source')
    for j, source in enumerate(sources):
        print(f"  Source {j+1}: src={source.get('src')}, type={source.get('type')}")

# Look for iframes
iframes = soup.find_all('iframe')
print(f"\nFound {len(iframes)} <iframe> tags")
for iframe in iframes:
    print(f"  src: {iframe.get('src')}")

# Search for MP4 URLs in JavaScript
print("\n=== Searching for MP4 URLs in JavaScript ===")
scripts = soup.find_all('script')
mp4_urls = []
for script in scripts:
    if script.string:
        # Look for various URL patterns
        patterns = [
            r'["\']([^"\']+\.mp4[^"\']*)["\']',
            r'url["\']?\s*[:=]\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'src["\']?\s*[:=]\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'https?://[^\s"\'<>]+\.mp4',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, script.string, re.IGNORECASE)
            mp4_urls.extend(matches)

if mp4_urls:
    print(f"Found {len(mp4_urls)} potential MP4 URLs in JavaScript:")
    for url in set(mp4_urls[:10]):  # Show first 10 unique
        print(f"  {url}")
else:
    print("No MP4 URLs found in JavaScript")

# Search for video-related data attributes
print("\n=== Searching for data attributes ===")
elements_with_data = soup.find_all(attrs=lambda x: x and any(k.startswith('data-') for k in x.keys()))
video_data_elements = [e for e in elements_with_data if 'video' in str(e).lower() or 'mp4' in str(e).lower()]
print(f"Found {len(video_data_elements)} elements with video-related data attributes")
for elem in video_data_elements[:5]:
    print(f"  {elem.name}: {dict((k, v) for k, v in elem.attrs.items() if k.startswith('data-'))}")

# Check page title and meta tags
print("\n=== Page metadata ===")
print(f"Title: {soup.title.string if soup.title else 'N/A'}")
meta_tags = soup.find_all('meta')
for meta in meta_tags:
    if meta.get('property') or meta.get('name'):
        print(f"  {meta.get('property') or meta.get('name')}: {meta.get('content')}")

