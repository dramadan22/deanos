#!/usr/bin/env python3
"""
Oura Ring Data Sync Script

Fetches all available data from the Oura API for the past 90 days
and outputs JSON for DeanOS to consume.

Requires:
- OURA_PAT environment variable (Personal Access Token)
- Generate at: https://cloud.ouraring.com/personal-access-tokens
"""

import json
import os
import ssl
import sys
import urllib.request
from datetime import datetime, timedelta, timezone


OURA_API_BASE = "https://api.ouraring.com/v2/usercollection"
DAYS_TO_FETCH = 90

# Create SSL context that doesn't verify certificates (for macOS Python installs)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


def fetch_oura_data(endpoint, pat, start_date, end_date):
    """Fetch data from Oura API endpoint."""
    url = f"{OURA_API_BASE}/{endpoint}?start_date={start_date}&end_date={end_date}"

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept": "application/json",
            "User-Agent": "DeanOS-Oura-Sync/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30, context=ssl_context) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error fetching {endpoint}: {e.code} {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error fetching {endpoint}: {e}", file=sys.stderr)
        return None


def get_daily_sleep(pat, start_date, end_date):
    """Get daily sleep scores and data."""
    data = fetch_oura_data("daily_sleep", pat, start_date, end_date)
    if not data:
        return []

    results = []
    for item in data.get("data", []):
        results.append({
            "date": item.get("day"),
            "score": item.get("score"),
            "contributors": item.get("contributors", {}),
        })
    return results


def get_sleep_periods(pat, start_date, end_date):
    """Get detailed sleep period data including HR and HRV."""
    data = fetch_oura_data("sleep", pat, start_date, end_date)
    if not data:
        return []

    results = []
    for item in data.get("data", []):
        results.append({
            "date": item.get("day"),
            "bedtime_start": item.get("bedtime_start"),
            "bedtime_end": item.get("bedtime_end"),
            "total_sleep_duration": item.get("total_sleep_duration"),
            "deep_sleep_duration": item.get("deep_sleep_duration"),
            "rem_sleep_duration": item.get("rem_sleep_duration"),
            "light_sleep_duration": item.get("light_sleep_duration"),
            "awake_time": item.get("awake_time"),
            "efficiency": item.get("efficiency"),
            "average_heart_rate": item.get("average_heart_rate"),
            "lowest_heart_rate": item.get("lowest_heart_rate"),
            "average_hrv": item.get("average_hrv"),
            "average_breath": item.get("average_breath"),
            "restless_periods": item.get("restless_periods"),
        })
    return results


def get_daily_readiness(pat, start_date, end_date):
    """Get daily readiness scores."""
    data = fetch_oura_data("daily_readiness", pat, start_date, end_date)
    if not data:
        return []

    results = []
    for item in data.get("data", []):
        results.append({
            "date": item.get("day"),
            "score": item.get("score"),
            "temperature_deviation": item.get("temperature_deviation"),
            "temperature_trend_deviation": item.get("temperature_trend_deviation"),
            "contributors": item.get("contributors", {}),
        })
    return results


def get_daily_activity(pat, start_date, end_date):
    """Get daily activity scores and data."""
    data = fetch_oura_data("daily_activity", pat, start_date, end_date)
    if not data:
        return []

    results = []
    for item in data.get("data", []):
        results.append({
            "date": item.get("day"),
            "score": item.get("score"),
            "active_calories": item.get("active_calories"),
            "total_calories": item.get("total_calories"),
            "steps": item.get("steps"),
            "equivalent_walking_distance": item.get("equivalent_walking_distance"),
            "high_activity_time": item.get("high_activity_time"),
            "medium_activity_time": item.get("medium_activity_time"),
            "low_activity_time": item.get("low_activity_time"),
            "sedentary_time": item.get("sedentary_time"),
            "resting_time": item.get("resting_time"),
            "inactivity_alerts": item.get("inactivity_alerts"),
            "met_minutes": item.get("met", {}).get("minutes") if item.get("met") else None,
            "contributors": item.get("contributors", {}),
        })
    return results


def get_heart_rate(pat, start_date, end_date):
    """Get heart rate time series data."""
    data = fetch_oura_data("heartrate", pat, start_date, end_date)
    if not data:
        return []

    # Group by date and calculate daily stats
    daily_hr = {}
    for item in data.get("data", []):
        timestamp = item.get("timestamp", "")
        date = timestamp[:10] if timestamp else None
        bpm = item.get("bpm")
        source = item.get("source")  # awake, sleep, rest, etc.

        if date and bpm:
            if date not in daily_hr:
                daily_hr[date] = {"readings": [], "resting": [], "awake": []}

            daily_hr[date]["readings"].append(bpm)
            if source in ("rest", "sleep"):
                daily_hr[date]["resting"].append(bpm)
            if source == "awake":
                daily_hr[date]["awake"].append(bpm)

    results = []
    for date, hr_data in sorted(daily_hr.items()):
        readings = hr_data["readings"]
        resting = hr_data["resting"]
        awake = hr_data["awake"]

        results.append({
            "date": date,
            "average_hr": round(sum(readings) / len(readings)) if readings else None,
            "min_hr": min(readings) if readings else None,
            "max_hr": max(readings) if readings else None,
            "resting_hr": round(sum(resting) / len(resting)) if resting else None,
            "awake_hr": round(sum(awake) / len(awake)) if awake else None,
        })

    return results


def get_workouts(pat, start_date, end_date):
    """Get workout/exercise sessions."""
    data = fetch_oura_data("workout", pat, start_date, end_date)
    if not data:
        return []

    results = []
    for item in data.get("data", []):
        results.append({
            "date": item.get("day"),
            "activity": item.get("activity"),
            "calories": item.get("calories"),
            "distance": item.get("distance"),
            "start_datetime": item.get("start_datetime"),
            "end_datetime": item.get("end_datetime"),
            "intensity": item.get("intensity"),
            "label": item.get("label"),
            "source": item.get("source"),
        })
    return results


def get_daily_spo2(pat, start_date, end_date):
    """Get daily SpO2 (blood oxygen) data."""
    data = fetch_oura_data("daily_spo2", pat, start_date, end_date)
    if not data:
        return []

    results = []
    for item in data.get("data", []):
        results.append({
            "date": item.get("day"),
            "spo2_average": item.get("spo2_percentage", {}).get("average") if item.get("spo2_percentage") else None,
        })
    return results


def main():
    pat = os.getenv("OURA_PAT", "").strip()

    if not pat:
        print("OURA_PAT not configured.", file=sys.stderr)
        print("Generate a Personal Access Token at:", file=sys.stderr)
        print("https://cloud.ouraring.com/personal-access-tokens", file=sys.stderr)

        # Create empty report
        report = {
            "updated": datetime.now(timezone.utc).isoformat(),
            "error": "No OURA_PAT configured",
            "data": None,
        }
        with open("oura-data.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            f.write("\n")
        return

    # Fetch last 90 days of data
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=DAYS_TO_FETCH)).strftime("%Y-%m-%d")

    print(f"Fetching Oura data from {start_date} to {end_date} ({DAYS_TO_FETCH} days)...")

    # Fetch all data types
    print("  Fetching sleep scores...")
    daily_sleep = get_daily_sleep(pat, start_date, end_date)

    print("  Fetching sleep details...")
    sleep_periods = get_sleep_periods(pat, start_date, end_date)

    print("  Fetching readiness scores...")
    readiness = get_daily_readiness(pat, start_date, end_date)

    print("  Fetching activity data...")
    activity = get_daily_activity(pat, start_date, end_date)

    print("  Fetching heart rate data...")
    heart_rate = get_heart_rate(pat, start_date, end_date)

    print("  Fetching workouts...")
    workouts = get_workouts(pat, start_date, end_date)

    print("  Fetching SpO2 data...")
    spo2 = get_daily_spo2(pat, start_date, end_date)

    # Combine into daily summaries
    daily_data = {}

    # Add sleep scores
    for item in daily_sleep:
        date = item["date"]
        if not date:
            continue
        if date not in daily_data:
            daily_data[date] = {"date": date}
        daily_data[date]["sleep_score"] = item["score"]
        daily_data[date]["sleep_contributors"] = item["contributors"]

    # Add sleep period details - keep the longest sleep period per day (main sleep, not naps)
    # First, group sleep periods by date and find the longest one
    sleep_by_date = {}
    for item in sleep_periods:
        date = item["date"]
        if not date:
            continue
        duration = item["total_sleep_duration"] or 0
        # Keep the longest sleep period for each date
        if date not in sleep_by_date or duration > (sleep_by_date[date]["total_sleep_duration"] or 0):
            sleep_by_date[date] = item

    # Now add the main sleep period for each date
    for date, item in sleep_by_date.items():
        if date not in daily_data:
            daily_data[date] = {"date": date}
        daily_data[date]["bedtime_start"] = item["bedtime_start"]
        daily_data[date]["bedtime_end"] = item["bedtime_end"]
        daily_data[date]["total_sleep_seconds"] = item["total_sleep_duration"]
        daily_data[date]["deep_sleep_seconds"] = item["deep_sleep_duration"]
        daily_data[date]["rem_sleep_seconds"] = item["rem_sleep_duration"]
        daily_data[date]["light_sleep_seconds"] = item["light_sleep_duration"]
        daily_data[date]["awake_seconds"] = item["awake_time"]
        daily_data[date]["sleep_efficiency"] = item["efficiency"]
        daily_data[date]["average_hrv"] = item["average_hrv"]
        daily_data[date]["lowest_hr"] = item["lowest_heart_rate"]
        daily_data[date]["average_hr_sleep"] = item["average_heart_rate"]
        daily_data[date]["average_breath"] = item["average_breath"]
        daily_data[date]["restless_periods"] = item["restless_periods"]

    # Add readiness
    for item in readiness:
        date = item["date"]
        if not date:
            continue
        if date not in daily_data:
            daily_data[date] = {"date": date}
        daily_data[date]["readiness_score"] = item["score"]
        daily_data[date]["temperature_deviation"] = item["temperature_deviation"]
        daily_data[date]["temperature_trend_deviation"] = item["temperature_trend_deviation"]
        daily_data[date]["readiness_contributors"] = item["contributors"]

    # Add activity
    for item in activity:
        date = item["date"]
        if not date:
            continue
        if date not in daily_data:
            daily_data[date] = {"date": date}
        daily_data[date]["activity_score"] = item["score"]
        daily_data[date]["steps"] = item["steps"]
        daily_data[date]["active_calories"] = item["active_calories"]
        daily_data[date]["total_calories"] = item["total_calories"]
        daily_data[date]["distance_meters"] = item["equivalent_walking_distance"]
        daily_data[date]["high_activity_seconds"] = item["high_activity_time"]
        daily_data[date]["medium_activity_seconds"] = item["medium_activity_time"]
        daily_data[date]["low_activity_seconds"] = item["low_activity_time"]
        daily_data[date]["sedentary_seconds"] = item["sedentary_time"]
        daily_data[date]["inactivity_alerts"] = item["inactivity_alerts"]
        daily_data[date]["activity_contributors"] = item["contributors"]

    # Add heart rate stats
    for item in heart_rate:
        date = item["date"]
        if not date:
            continue
        if date not in daily_data:
            daily_data[date] = {"date": date}
        daily_data[date]["resting_hr"] = item["resting_hr"]
        daily_data[date]["average_hr"] = item["average_hr"]
        daily_data[date]["min_hr"] = item["min_hr"]
        daily_data[date]["max_hr"] = item["max_hr"]
        daily_data[date]["awake_hr"] = item["awake_hr"]

    # Add SpO2
    for item in spo2:
        date = item["date"]
        if not date:
            continue
        if date not in daily_data:
            daily_data[date] = {"date": date}
        daily_data[date]["spo2_average"] = item["spo2_average"]

    # Sort by date
    sorted_data = [daily_data[d] for d in sorted(daily_data.keys(), reverse=True)]

    # Create report
    report = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "start_date": start_date,
        "end_date": end_date,
        "days_requested": DAYS_TO_FETCH,
        "days_returned": len(sorted_data),
        "workouts": workouts,
        "days": sorted_data,
    }

    # Write report
    with open("oura-data.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    print(f"\nOura data synced: {len(sorted_data)} days")
    print(f"Workouts found: {len(workouts)}")

    if sorted_data:
        print("\nMost recent 3 days:")
        for day in sorted_data[:3]:
            sleep = day.get('sleep_score', '--')
            readiness = day.get('readiness_score', '--')
            activity = day.get('activity_score', '--')
            hrv = day.get('average_hrv', '--')
            steps = day.get('steps', '--')
            print(f"  {day['date']}: Sleep {sleep}, Readiness {readiness}, Activity {activity}, HRV {hrv}, Steps {steps}")


if __name__ == "__main__":
    main()
