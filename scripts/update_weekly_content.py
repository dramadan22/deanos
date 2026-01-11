#!/usr/bin/env python3
import json
import os
import random
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import ssl
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

try:
    import certifi
except Exception:  # pragma: no cover - optional dependency
    certifi = None

RECIPE_FEEDS = [
    {
        "name": "Serious Eats",
        "url": "https://feeds.feedburner.com/seriouseats/recipes",
        "type": "rss",
    },
    {
        "name": "Bon Appetit",
        "url": "https://www.bonappetit.com/feed/rss",
        "type": "rss",
    },
    {
        "name": "The Kitchn",
        "url": "https://www.thekitchn.com/main.rss",
        "type": "rss",
    },
    {
        "name": "Skinnytaste",
        "url": "https://www.skinnytaste.com/feed/",
        "type": "rss",
    },
    {
        "name": "Love and Lemons",
        "url": "https://www.loveandlemons.com/feed/",
        "type": "rss",
    },
]

LONGEVITY_FEEDS = [
    {
        "name": "Huberman Lab",
        "url": "https://feeds.megaphone.fm/hubermanlab",
        "type": "rss",
    },
    {
        "name": "Peter Attia",
        "url": "https://peterattiamd.com/feed/",
        "type": "rss",
    },
]

YOUTUBE_QUERIES = [
    {
        "query": "seated strength workouts",
        "type": "Strength",
        "location": "YouTube",
    },
    {
        "query": "machine workouts at gym for longevity",
        "type": "Strength",
        "location": "YouTube",
    },
    {
        "query": "POTS friendly seated workout",
        "type": "Cardio + Mobility",
        "location": "YouTube",
    },
]

WORKOUT_TEMPLATE = [
    {
        "day": "Monday",
        "type": "Upper Body Strength",
        "location": "LA Fitness",
        "exercises": [
            {"name": "Seated Chest Press Machine", "sets": "3x10-12", "video": "https://www.youtube.com/watch?v=xUm0BiZCWlQ"},
            {"name": "Lat Pulldown", "sets": "3x10-12", "video": "https://www.youtube.com/watch?v=CAwf7n6Luuc"},
            {"name": "Seated Shoulder Press Machine", "sets": "3x10-12", "video": "https://www.youtube.com/watch?v=Wqq43dKW1TU"},
            {"name": "Seated Cable Row", "sets": "3x10-12", "video": "https://www.youtube.com/watch?v=GZbfZ033f74"},
            {"name": "Tricep Pushdown", "sets": "3x12-15", "video": "https://www.youtube.com/watch?v=2-LAMcpzODU"},
        ],
    },
    {
        "day": "Wednesday",
        "type": "Lower Body Strength",
        "location": "LA Fitness",
        "exercises": [
            {"name": "Leg Press", "sets": "4x10-12", "video": "https://www.youtube.com/watch?v=IZxyjW7MPJQ"},
            {"name": "Leg Curl Machine", "sets": "3x12-15", "video": "https://www.youtube.com/watch?v=1Tq3QdYUuHs"},
            {"name": "Leg Extension", "sets": "3x12-15", "video": "https://www.youtube.com/watch?v=YyvSfVjQeL0"},
            {"name": "Seated Calf Raise", "sets": "3x15-20", "video": "https://www.youtube.com/watch?v=-M4-G8p8fmc"},
            {"name": "Hip Adductor Machine", "sets": "3x12-15", "video": "https://www.youtube.com/watch?v=2cPwLG3MOLs"},
        ],
    },
    {
        "day": "Friday",
        "type": "PT Session with Josh",
        "location": "Full Body",
        "exercises": [
            {"name": "Personal Training Session", "sets": "Full body, guided by Josh"},
        ],
    },
    {
        "day": "Saturday",
        "type": "Cardio + Mobility",
        "location": "LA Fitness",
        "exercises": [
            {"name": "Upright Bike", "sets": "30 min, 90+ RPM, Level 12", "video": "https://www.youtube.com/watch?v=oBFhn-2BrEw"},
            {"name": "Seated Stretch Flow", "sets": "10-12 min, easy pace"},
        ],
    },
]


def fetch_url(url):
    context = ssl.create_default_context(
        cafile=certifi.where() if certifi else None
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DeanOS Weekly Feed/1.0"},
    )
    with urllib.request.urlopen(request, timeout=25, context=context) as response:
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
    root = ET.fromstring(sanitize_xml(xml_data))
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


def fetch_youtube_videos(query, max_results=8):
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("Missing YOUTUBE_API_KEY, skipping YouTube fetch.", file=sys.stderr)
        return []

    params = urllib.parse.urlencode(
        {
            "part": "snippet",
            "type": "video",
            "maxResults": max_results,
            "q": query,
            "key": api_key,
        }
    )
    url = f"https://www.googleapis.com/youtube/v3/search?{params}"
    data = json.loads(fetch_url(url))
    videos = []
    for item in data.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        title = snippet.get("title", "").strip()
        published = snippet.get("publishedAt")
        if not video_id or not title:
            continue
        videos.append(
            {
                "title": title,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "source": "YouTube",
                "published": published,
            }
        )
    return videos


def build_weekly_workouts():
    videos_by_type = {"Strength": [], "Cardio + Mobility": []}
    for item in YOUTUBE_QUERIES:
        videos = fetch_youtube_videos(item["query"])
        if not videos:
            continue
        videos_by_type[item["type"]].extend(videos)

    workouts = []
    random.shuffle(videos_by_type["Strength"])
    random.shuffle(videos_by_type["Cardio + Mobility"])

    def pick_videos(pool, count):
        if not pool:
            return []
        selection = pool[:count]
        del pool[:count]
        return selection

    def make_workout(day, workout_type, pool, count):
        selected = pick_videos(pool, count)
        if not selected:
            return None
        return {
            "day": day,
            "type": workout_type,
            "location": "YouTube",
            "exercises": [
                {"name": v["title"], "sets": "Follow along", "video": v["url"]}
                for v in selected
            ],
        }

    strength_pool = videos_by_type["Strength"]
    cardio_pool = videos_by_type["Cardio + Mobility"]

    workout_plan = [
        make_workout("Monday", "Strength", strength_pool, 2),
        make_workout("Wednesday", "Strength", strength_pool, 2),
        make_workout("Friday", "Strength", strength_pool, 2),
        make_workout("Saturday", "Cardio + Mobility", cardio_pool, 2),
    ]

    return [w for w in workout_plan if w]


def is_recipe_item(item):
    title = (item.get("title") or "").lower()
    url = (item.get("url") or "").lower()
    keywords = ["recipe", "recipes", "meal", "dinner", "lunch", "breakfast"]
    return any(word in title or f"/{word}" in url for word in keywords)


def fetch_feed_items(feeds):
    all_items = []
    for feed in feeds:
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
    deduped.sort(key=lambda item: item["published"] or "", reverse=True)
    return deduped


def main():
    recipe_items = [item for item in fetch_feed_items(RECIPE_FEEDS) if is_recipe_item(item)]
    longevity_items = fetch_feed_items(LONGEVITY_FEEDS)
    workout_items = build_weekly_workouts()

    weekly_recipes = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "meals": [],
        "items": recipe_items,
    }

    weekly_workouts = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "workouts": workout_items or WORKOUT_TEMPLATE,
        "sources": longevity_items[:5],
    }

    with open("weekly-recipes.json", "w", encoding="utf-8") as f:
        json.dump(weekly_recipes, f, ensure_ascii=True, indent=2)
        f.write("\n")

    with open("weekly-workouts.json", "w", encoding="utf-8") as f:
        json.dump(weekly_workouts, f, ensure_ascii=True, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
