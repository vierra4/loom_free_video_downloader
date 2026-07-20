#!/usr/bin/env python3
"""
Loom Video Downloader
----------------------
Downloads a Loom video given its PUBLIC share URL, e.g.:
    https://www.loom.com/share/abcdef1234567890abcdef1234567890

This only works for videos that are publicly shared/viewable without
requiring a login. It will not work on private/restricted videos.

Usage:
    python loom_downloader.py <loom_share_url> [-o output.mp4]

Requirements:
    pip install requests

How it works:
Loom exposes an internal endpoint that, given a video's ID, returns a
direct link to the transcoded MP4 file:
    https://www.loom.com/api/campaigns/sessions/{video_id}/transcoded-url
This script extracts the video ID from the share URL, calls that
endpoint, and streams the resulting MP4 to disk.
"""

import argparse
import os
import re
import sys
from urllib.parse import urlparse

import requests

TRANSCODE_API = "https://www.loom.com/api/campaigns/sessions/{video_id}/transcoded-url"


def extract_video_id(url: str) -> str:
    """Pull the 32-character video ID out of a Loom share URL."""
    # Common forms:
    #   https://www.loom.com/share/<id>
    #   https://www.loom.com/share/<id>?sid=...
    #   https://www.loom.com/embed/<id>
    match = re.search(r"(?:share|embed)/([a-zA-Z0-9]+)", url)
    if match:
        return match.group(1)

    # Fallback: last path segment
    path = urlparse(url).path
    segment = path.rstrip("/").split("/")[-1]
    if segment:
        return segment

    raise ValueError(f"Could not extract a video ID from URL: {url}")


def get_download_url(video_id: str) -> str:
    """Ask Loom's API for the direct, downloadable MP4 URL."""
    api_url = TRANSCODE_API.format(video_id=video_id)
    resp = requests.post(api_url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    download_url = data.get("url")
    if not download_url:
        raise RuntimeError(
            "No download URL returned. The video may be private, "
            "restricted, or Loom may have changed its API."
        )
    return download_url


def download_file(url: str, output_path: str) -> None:
    """Stream the MP4 to disk with a simple progress indicator."""
    with requests.get(url, stream=True, timeout=30) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"\rDownloading... {pct:5.1f}%", end="", flush=True)
                else:
                    mb = downloaded / (1024 * 1024)
                    print(f"\rDownloading... {mb:6.1f} MB", end="", flush=True)
    print()  # newline after progress bar


def main():
    parser = argparse.ArgumentParser(description="Download a public Loom video.")
    parser.add_argument("url", help="Public Loom share URL, e.g. https://www.loom.com/share/<id>")
    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: <video_id>.mp4)",
        default=None,
    )
    args = parser.parse_args()

    try:
        video_id = extract_video_id(args.url)
        print(f"Video ID: {video_id}")

        print("Fetching download link...")
        download_url = get_download_url(video_id)

        output_path = args.output or f"{video_id}.mp4"
        print(f"Saving to: {output_path}")
        download_file(download_url, output_path)

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"Done. Saved {size_mb:.1f} MB to {output_path}")

    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()