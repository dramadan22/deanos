#!/usr/bin/env python3
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
import ssl
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

try:
    import certifi
except Exception:  # pragma: no cover - optional dependency
    certifi = None

FEEDS = [
    {
        "name": "Google News",
        "url": "https://news.google.com/rss/search?q=POTS%20OR%20dysautonomia&hl=en-US&gl=US&ceid=US:en",
        "type": "rss",
    },
    {
        "name": "arXiv",
        "url": "http://export.arxiv.org/api/query?search_query=all:POTS+OR+dysautonomia&start=0&max_results=10",
        "type": "atom",
    },
    {
        "name": "Dysautonomia International",
        "url": "https://www.dysautonomiainternational.org/blog/wordpress/?feed=rss2",
        "type": "rss",
    },
]


def fetch_url(url):
    context = ssl.create_default_context(
        cafile=certifi.where() if certifi else None
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DeanOS Research Feed/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20, context=context) as response:
        return response.read()


def parse_date(value):
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
        if dt:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def sanitize_xml(xml_data):
    if isinstance(xml_data, bytes):
        text = xml_data.decode("utf-8", errors="ignore")
    else:
        text = str(xml_data)
    cleaned = "".join(
        ch for ch in text if ch == "\t" or ch == "\n" or ch == "\r" or ord(ch) >= 32
    )
    return cleaned.encode("utf-8")


def parse_rss(xml_data, source):
    root = ET.fromstring(sanitize_xml(xml_data))
    channel = root.find("channel")
    if channel is None:
        return []
    items = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = parse_date(item.findtext("pubDate") or item.findtext("dc:date"))
        if not title or not link:
            continue
        items.append(
            {
                "title": title,
                "url": link,
                "source": source,
                "published": pub_date.isoformat() if pub_date else None,
            }
        )
    return items


def parse_atom(xml_data, source):
    root = ET.fromstring(xml_data)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []
    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        link_elem = entry.find("atom:link[@rel='alternate']", ns)
        if link_elem is None:
            link_elem = entry.find("atom:link", ns)
        link = (link_elem.attrib.get("href") if link_elem is not None else "").strip()
        pub_text = entry.findtext("atom:published", default="", namespaces=ns) or entry.findtext(
            "atom:updated", default="", namespaces=ns
        )
        pub_date = parse_date(pub_text)
        if not title or not link:
            continue
        items.append(
            {
                "title": title,
                "url": link,
                "source": source,
                "published": pub_date.isoformat() if pub_date else None,
            }
        )
    return items


def dedupe_items(items):
    seen = set()
    deduped = []
    for item in items:
        key = (item["url"] or item["title"]).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def load_existing_feed():
    """Load the existing feed to compare for new items."""
    try:
        with open("research-feed.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"items": [], "updated": None}


def main():
    # Load existing feed to determine what's new
    existing = load_existing_feed()
    existing_urls = {item.get("url", "").lower() for item in existing.get("items", [])}
    last_updated = existing.get("updated")

    all_items = []
    for feed in FEEDS:
        try:
            xml_data = fetch_url(feed["url"])
        except Exception as exc:
            print(f"Failed to fetch {feed['name']}: {exc}", file=sys.stderr)
            continue
        try:
            if feed["type"] == "atom":
                items = parse_atom(xml_data, feed["name"])
            else:
                items = parse_rss(xml_data, feed["name"])
            all_items.extend(items)
        except Exception as exc:
            print(f"Failed to parse {feed['name']}: {exc}", file=sys.stderr)

    deduped = dedupe_items(all_items)
    deduped.sort(
        key=lambda item: item["published"] or "",
        reverse=True,
    )

    # Mark items as new if they weren't in the previous feed
    for item in deduped:
        item["isNew"] = item.get("url", "").lower() not in existing_urls

    new_count = sum(1 for item in deduped if item.get("isNew"))
    print(f"Found {new_count} new items since last update")

    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "lastUpdated": last_updated,
        "items": deduped[:50],
    }

    with open("research-feed.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=True, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
