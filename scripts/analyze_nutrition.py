#!/usr/bin/env python3
"""
Weekly Nutrition Analysis Script

Fetches meal logs from a GitHub Gist and uses Claude AI to analyze
nutritional patterns, identifying strengths and gaps based on
longevity research recommendations.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

try:
    import anthropic
except ImportError:
    anthropic = None


def fetch_gist_meals(gist_id, github_token):
    """Fetch meal logs from the specified GitHub Gist."""
    if not gist_id:
        print("No GIST_ID configured, skipping nutrition analysis.", file=sys.stderr)
        return None

    url = f"https://api.github.com/gists/{gist_id}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "DeanOS-Nutrition-Analysis/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            gist_data = json.loads(response.read().decode("utf-8"))

        # Get the meal-logs.json file content
        files = gist_data.get("files", {})
        meal_file = files.get("meal-logs.json", {})
        content = meal_file.get("content", "")

        if not content:
            print("No meal-logs.json found in gist", file=sys.stderr)
            return None

        return json.loads(content)

    except Exception as e:
        print(f"Error fetching gist: {e}", file=sys.stderr)
        return None


def analyze_with_claude(meal_data):
    """Use Claude to analyze the meal logs and provide nutrition insights."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Missing ANTHROPIC_API_KEY", file=sys.stderr)
        return None

    if anthropic is None:
        print("anthropic package not installed", file=sys.stderr)
        return None

    meals = meal_data.get("meals", [])
    if not meals:
        print("No meal data to analyze", file=sys.stderr)
        return None

    # Format meals for analysis
    meal_summary = []
    for day in meals:
        day_meals = day.get("meals", {})
        meal_summary.append(f"""
{day.get('day', 'Unknown')} ({day.get('date', '')}):
- Breakfast: {day_meals.get('breakfast', 'Not logged')}
- Lunch: {day_meals.get('lunch', 'Not logged')}
- Dinner: {day_meals.get('dinner', 'Not logged')}
- Snacks: {day_meals.get('snacks', 'None')}
""")

    meals_text = "\n".join(meal_summary)

    prompt = f"""Analyze the following week of meal logs for nutritional patterns. Focus on longevity and health optimization based on research from experts like Peter Attia and Andrew Huberman.

MEAL LOGS:
{meals_text}

Based on these meals, provide analysis in the following areas:

1. STRENGTHS (2-4 points): What did this person do well nutritionally this week? Consider:
   - Protein intake and variety of sources
   - Vegetable and fiber intake
   - Omega-3 sources (fish, etc.)
   - Whole foods vs processed foods
   - Meal timing and consistency

2. GAPS (2-4 points): What nutrients or food groups are likely missing or insufficient? Consider longevity-focused targets:
   - Protein: ~1g per pound of body weight for muscle preservation
   - Fiber: 30g+ daily for gut health
   - Omega-3s: 2-3 servings of fatty fish per week
   - Micronutrients: magnesium, vitamin D, B12, potassium
   - Colorful vegetables for polyphenols

3. SUGGESTIONS (2-3 points): Specific, actionable meal prep suggestions for next week to address the gaps.

Return ONLY valid JSON in this exact format, no markdown or explanation:
{{
  "strengths": [
    "Brief strength point 1",
    "Brief strength point 2"
  ],
  "gaps": [
    "Brief gap point 1 with specific nutrient/food mentioned",
    "Brief gap point 2 with specific nutrient/food mentioned"
  ],
  "suggestions": [
    "Specific actionable suggestion 1",
    "Specific actionable suggestion 2"
  ]
}}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text.strip()
        return json.loads(response_text)

    except json.JSONDecodeError as e:
        print(f"Failed to parse Claude response as JSON: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error calling Claude API: {e}", file=sys.stderr)
        return None


def main():
    gist_id = os.getenv("GIST_ID", "").strip()
    github_token = os.getenv("GITHUB_TOKEN", "").strip()

    if not gist_id:
        print("GIST_ID not configured. Add it as a repository secret.", file=sys.stderr)
        # Create empty report so the workflow doesn't fail
        report = {
            "updated": datetime.now(timezone.utc).isoformat(),
            "weekOf": datetime.now(timezone.utc).isoformat()[:10],
            "analysis": None,
            "error": "No GIST_ID configured. Set up sync in DeanOS Settings first.",
        }
        with open("nutrition-report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            f.write("\n")
        return

    # Fetch meal data from gist
    meal_data = fetch_gist_meals(gist_id, github_token)
    if not meal_data:
        print("Could not fetch meal data from gist", file=sys.stderr)
        return

    # Analyze with Claude
    analysis = analyze_with_claude(meal_data)

    # Create report
    report = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "weekOf": meal_data.get("weekOf", datetime.now(timezone.utc).isoformat()[:10]),
        "analysis": analysis,
        "mealsAnalyzed": len(meal_data.get("meals", [])),
    }

    # Write report
    with open("nutrition-report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    print(f"Nutrition report generated for week of {report['weekOf']}")
    if analysis:
        print(f"  Strengths: {len(analysis.get('strengths', []))}")
        print(f"  Gaps: {len(analysis.get('gaps', []))}")
        print(f"  Suggestions: {len(analysis.get('suggestions', []))}")


if __name__ == "__main__":
    main()
