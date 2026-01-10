#!/usr/bin/env python3
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

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
        "name": "EatingWell",
        "url": "https://www.eatingwell.com/rss/recipes/",
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
        "url": "https://peterattiamd.com/feed/podcast/",
        "type": "rss",
    },
    {
        "name": "Bryan Johnson",
        "url": "https://www.bryanjohnson.com/blogs/rss.xml",
        "type": "rss",
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
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DeanOS Weekly Feed/1.0"},
    )
    with urllib.request.urlopen(request, timeout=25) as response:
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


def fetch_feed_items(feeds):
    all_items = []
    for feed in feeds:
        try:
            xml_data = fetch_url(feed["url"])
        except Exception as exc:
            print(f"Failed to fetch {feed['name']}: {exc}", file=sys.stderr)
            continue
        try:
            items = parse_rss(xml_data, feed["name"])
            all_items.extend(items)
        except Exception as exc:
            print(f"Failed to parse {feed['name']}: {exc}", file=sys.stderr)
    deduped = dedupe_items(all_items)
    deduped.sort(key=lambda item: item["published"] or "", reverse=True)
    return deduped


def build_meal_plan(recipes):
    def pick(count, offset=0):
        selection = recipes[offset : offset + count]
        return [
            {
                "title": item["title"],
                "url": item["url"],
                "source": item["source"],
                "tags": ["rss", "new"],
            }
            for item in selection
        ]

    lunches = pick(5, 0)
    dinners = pick(3, 5)
    weekend = pick(1, 8)

    return [
        {
            "type": "Lunch Prep",
            "description": "Prep on Sunday for 5 weekday lunches",
            "items": lunches,
        },
        {
            "type": "Weeknight Dinners",
            "description": "Quick & easy (<45 min)",
            "items": dinners,
        },
        {
            "type": "Weekend Challenge",
            "description": "One ambitious cook!",
            "items": weekend,
        },
    ]


def main():
    recipe_items = fetch_feed_items(RECIPE_FEEDS)
    longevity_items = fetch_feed_items(LONGEVITY_FEEDS)

    meal_plan = build_meal_plan(recipe_items) if recipe_items else []

    weekly_recipes = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "meals": meal_plan,
    }

    weekly_workouts = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "workouts": WORKOUT_TEMPLATE,
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
