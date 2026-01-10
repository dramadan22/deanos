#!/usr/bin/env python3
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

FEEDS = [
    {
        "name": "Google News",
        "url": "https://news.google.com/rss/search?q=POTS%20OR%20dysautonomia&hl=en-US&gl=US&ceid=US:en",
        "type": "rss",
    },
    {
        "name": "PubMed",
        "url": "https://pubmed.ncbi.nlm.nih.gov/?term=postural+orthostatic+tachycardia+syndrome+OR+dysautonomia&format=rss",
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
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DeanOS Research Feed/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
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


def parse_rss(xml_data, source):
    root = ET.fromstring(xml_data)
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


def main():
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
    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "items": deduped[:50],
    }

    with open("research-feed.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=True, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
