#!/usr/bin/env python3
import json
import os
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

try:
    import anthropic
except Exception:  # pragma: no cover - optional dependency
    anthropic = None

RECIPE_FEEDS = [
    {
        "name": "Skinnytaste",
        "url": "https://www.skinnytaste.com/feed/",
        "type": "rss",
    },
    {
        "name": "Serious Eats",
        "url": "https://feeds.feedburner.com/seriouseats/recipes",
        "type": "rss",
    },
    {
        "name": "Allrecipes",
        "url": "https://www.simplyrecipes.com/feed/",
        "type": "rss",
    },
    {
        "name": "EatingWell",
        "url": "https://www.budgetbytes.com/feed/",
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

WORKOUT_PROFILE = """
- Location: LA Fitness (commercial gym with full machine selection)
- Schedule: Monday (Upper), Wednesday (Lower), Friday (PT with trainer Josh), Saturday (Cardio + Mobility)
- Goals: Hypertrophy, general strength, longevity/joint health
- Preferences: Machine-based and cable exercises preferred (joint-friendly, consistent resistance)
- No current injuries or limitations
"""

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


def generate_workouts_with_claude():
    """Generate a weekly workout plan using Claude API."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Missing ANTHROPIC_API_KEY, skipping Claude workout generation.", file=sys.stderr)
        return []

    if anthropic is None:
        print("anthropic package not installed, skipping Claude workout generation.", file=sys.stderr)
        return []

    try:
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Generate a weekly workout plan based on this profile:
{WORKOUT_PROFILE}

Create workouts for Monday (Upper Body), Wednesday (Lower Body), and Saturday (Cardio + Mobility).
Friday is reserved for personal training - do not generate exercises for Friday.

Requirements:
- 4-5 exercises per strength day
- Use machine and cable exercises primarily (available at LA Fitness)
- Include sets/reps in hypertrophy range (3-4 sets, 8-12 reps for compounds, 10-15 for isolation)
- Vary exercises week to week for muscle confusion and engagement
- Saturday should include 20-30 min cardio and mobility/stretching work

Return ONLY valid JSON in this exact format, no markdown or explanation:
{{
  "workouts": [
    {{
      "day": "Monday",
      "type": "Upper Body Strength",
      "location": "LA Fitness",
      "exercises": [
        {{"name": "Exercise Name", "sets": "3x10-12"}},
        {{"name": "Exercise Name", "sets": "3x10-12"}}
      ]
    }},
    {{
      "day": "Wednesday",
      "type": "Lower Body Strength",
      "location": "LA Fitness",
      "exercises": [
        {{"name": "Exercise Name", "sets": "4x8-10"}},
        {{"name": "Exercise Name", "sets": "3x12-15"}}
      ]
    }},
    {{
      "day": "Friday",
      "type": "PT Session with Josh",
      "location": "LA Fitness",
      "exercises": [
        {{"name": "Personal Training Session", "sets": "Full body, guided by Josh"}}
      ]
    }},
    {{
      "day": "Saturday",
      "type": "Cardio + Mobility",
      "location": "LA Fitness",
      "exercises": [
        {{"name": "Cardio exercise", "sets": "duration/intensity"}},
        {{"name": "Mobility work", "sets": "duration"}}
      ]
    }}
  ]
}}"""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = message.content[0].text.strip()
        workout_data = json.loads(response_text)
        return workout_data.get("workouts", [])

    except json.JSONDecodeError as e:
        print(f"Failed to parse Claude workout response as JSON: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error generating workout plan with Claude: {e}", file=sys.stderr)
        return []


def generate_meal_plan_with_claude():
    """Generate a 5-day meal plan using Claude API."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Missing ANTHROPIC_API_KEY, skipping Claude meal generation.", file=sys.stderr)
        return []

    if anthropic is None:
        print("anthropic package not installed, skipping Claude meal generation.", file=sys.stderr)
        return []

    try:
        client = anthropic.Anthropic(api_key=api_key)

        prompt = """Generate a 5-day weekday meal plan (Monday through Friday) with breakfast, lunch, and dinner for each day.

Requirements:
- High protein focus: Each meal should have 25-40g of protein
- Quick preparation: All meals must be under 30 minutes to prepare
- Practical ingredients: Use common grocery store items
- Variety: Mix different protein sources (chicken, fish, eggs, beef, legumes, dairy)
- Balanced: Include vegetables and whole grains where appropriate

Return ONLY valid JSON in this exact format, no markdown or explanation:
{
  "days": [
    {
      "day": "Monday",
      "breakfast": {
        "title": "Meal name",
        "description": "Brief 1-sentence description of the meal",
        "time": "X min",
        "protein": "XXg"
      },
      "lunch": {
        "title": "Meal name",
        "description": "Brief description",
        "time": "X min",
        "protein": "XXg"
      },
      "dinner": {
        "title": "Meal name",
        "description": "Brief description",
        "time": "X min",
        "protein": "XXg"
      }
    }
  ]
}

Generate for Monday, Tuesday, Wednesday, Thursday, and Friday."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = message.content[0].text.strip()
        meal_data = json.loads(response_text)
        return meal_data.get("days", [])

    except json.JSONDecodeError as e:
        print(f"Failed to parse Claude response as JSON: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error generating meal plan with Claude: {e}", file=sys.stderr)
        return []


def is_recipe_item(item):
    title = (item.get("title") or "").lower()
    url = (item.get("url") or "").lower()
    recipe_sources = {"skinnytaste", "serious eats", "simply recipes", "budget bytes"}
    source = (item.get("source") or "").lower()
    has_recipe_url = "/recipe" in url or "/recipes/" in url
    listicle_markers = [
        "best", "favorite", "roundup", "list", "collection", "guide", "review", "ideas",
        "meal plan", "meal prep", "top", "week", "gallery"
    ]
    has_listicle = any(marker in title for marker in listicle_markers)
    has_list_number = any(char.isdigit() for char in title)
    if has_listicle or has_list_number:
        return False
    return has_recipe_url or source in recipe_sources


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
    workout_items = generate_workouts_with_claude()
    meal_plan = generate_meal_plan_with_claude()

    weekly_recipes = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "meals": meal_plan,
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
