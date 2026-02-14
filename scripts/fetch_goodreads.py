#!/usr/bin/env python3
"""Fetch Goodreads 'to-read' shelf via RSS and save as JSON."""

import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
import ssl
from datetime import datetime, timezone

try:
    import certifi
except Exception:
    certifi = None


def fetch_url(url):
    context = ssl.create_default_context(
        cafile=certifi.where() if certifi else None
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DeanOS Goodreads Feed/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        return response.read()


def parse_goodreads_rss(xml_data):
    """Parse Goodreads RSS feed and extract book information."""
    root = ET.fromstring(xml_data)
    channel = root.find("channel")
    if channel is None:
        return []

    books = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        author = (item.findtext("author_name") or "").strip()
        image_url = (item.findtext("book_image_url") or "").strip()
        average_rating = (item.findtext("average_rating") or "").strip()
        date_added = (item.findtext("user_date_added") or "").strip()

        if not title:
            continue

        books.append({
            "title": title,
            "author": author,
            "link": link,
            "image_url": image_url,
            "average_rating": average_rating,
            "date_added": date_added,
        })

    return books


def main():
    user_id = os.environ.get("GOODREADS_USER_ID", "")
    rss_key = os.environ.get("GOODREADS_RSS_KEY", "")

    if not user_id or not rss_key:
        print("Error: GOODREADS_USER_ID and GOODREADS_RSS_KEY must be set", file=sys.stderr)
        sys.exit(1)

    url = f"https://www.goodreads.com/review/list_rss/{user_id}?key={rss_key}&shelf=to-read"

    print(f"Fetching Goodreads to-read shelf for user {user_id}...")

    try:
        xml_data = fetch_url(url)
    except Exception as exc:
        print(f"Failed to fetch Goodreads RSS: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        books = parse_goodreads_rss(xml_data)
    except Exception as exc:
        print(f"Failed to parse Goodreads RSS: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(books)} books on to-read shelf")

    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "books": books,
    }

    with open("goodreads-feed.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=True, indent=2)
        f.write("\n")

    print("Saved to goodreads-feed.json")


if __name__ == "__main__":
    main()
