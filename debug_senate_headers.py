
import requests
import sys

url = "https://dlttx48mxf9m3.cloudfront.net/outputs/694acaf0e912f70002990711/Default/HLS/694acaf0e912f70002990711.m3u8"

headers_sets = [
    {
        "name": "No Headers",
        "headers": {}
    },
    {
        "name": "Referer: cloud.castus.tv",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://cloud.castus.tv/vod/misenate/",
            "Origin": "https://cloud.castus.tv"
        }
    },
    {
        "name": "Referer: misenate.castus.tv",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://misenate.castus.tv/",
            "Origin": "https://misenate.castus.tv"
        }
    },
    {
        "name": "Referer: castus.tv (generic)",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://castus.tv/",
        }
    }
]

print(f"Testing URL: {url}")

for h_set in headers_sets:
    print(f"\nTesting {h_set['name']}...")
    try:
        response = requests.head(url, headers=h_set['headers'], timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 403:
            # Try GET to see body
            response = requests.get(url, headers=h_set['headers'], timeout=10)
            print(f"Body: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

