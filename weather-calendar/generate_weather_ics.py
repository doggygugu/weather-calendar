#!/usr/bin/env python3
"""
Weather Calendar Generator
- Fetches forecast (next 10 days) from Open-Meteo forecast API
- Fetches past weather from Open-Meteo historical API
- Merges with existing ICS to preserve historical entries
- Outputs a subscribable weather.ics file
"""

import json
import os
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone

# ── Configuration ────────────────────────────────────────────────────────────
LATITUDE  = 53.5753  # Hamburg
LONGITUDE = 10.0153
CITY_NAME = "Hamburg"
TIMEZONE  = "Europe/Berlin"
ICS_PATH  = "docs/weather.ics"   # published via GitHub Pages
DAYS_BACK = 30                   # how many past days to include / preserve

# Weather code → emoji mapping (WMO codes)
WMO_EMOJI = {
    0: "☀️", 1: "🌤", 2: "⛅️", 3: "☁️",
    45: "🌫", 48: "🌫",
    51: "🌦", 53: "🌦", 55: "🌧",
    61: "🌦", 63: "🌧", 65: "🌧",
    71: "🌨", 73: "🌨", 75: "❄️",
    77: "🌨",
    80: "🌦", 81: "🌧", 82: "⛈",
    85: "🌨", 86: "❄️",
    95: "⛈", 96: "⛈", 99: "⛈",
}

WMO_DESC = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Heavy showers",
    85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm + hail", 99: "Thunderstorm + heavy hail",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode())

def uid_for_date(d: date) -> str:
    return f"weather-{d.isoformat()}@{CITY_NAME.lower()}-calendar"

def make_event(d: date, t_min: float, t_max: float, wmo: int, is_past: bool) -> str:
    emoji = WMO_EMOJI.get(wmo, "🌡")
    desc  = WMO_DESC.get(wmo, "Unknown")

    # Title: emoji + temp range
    summary = f"{emoji} {round(t_min)}°–{round(t_max)}°C  {desc}"

    # All-day event: just DATE
    dt_str = d.strftime("%Y%m%d")

    # For past days we stamp at 23:59:00 local → store as UTC offset string
    # For future days we use the all-day format
    if is_past:
        dtstart = f"DTSTART;TZID={TIMEZONE}:{d.strftime('%Y%m%d')}T235900"
        dtend   = f"DTEND;TZID={TIMEZONE}:{(d + timedelta(days=1)).strftime('%Y%m%d')}T000000"
    else:
        dtstart = f"DTSTART;VALUE=DATE:{dt_str}"
        dtend   = f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}"

    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    uid     = uid_for_date(d)

    return "\n".join([
        "BEGIN:VEVENT",
        uid_for_date(d) and f"UID:{uid}",
        f"DTSTAMP:{now_utc}",
        dtstart,
        dtend,
        f"SUMMARY:{summary}",
        f"DESCRIPTION:Low: {round(t_min)}°C / High: {round(t_max)}°C\\nCondition: {desc}\\nSource: Open-Meteo",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ])

def load_existing_uids(path: str) -> set:
    """Return set of UIDs already in the ICS file (to detect past events)."""
    uids = set()
    if not os.path.exists(path):
        return uids
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^UID:(.+)$", line.strip())
            if m:
                uids.add(m.group(1))
    return uids

def load_existing_events(path: str) -> dict:
    """Parse existing ICS and return dict of {uid: event_block_str}."""
    events = {}
    if not os.path.exists(path):
        return events
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # Split on VEVENT boundaries
    blocks = re.findall(r"(BEGIN:VEVENT.*?END:VEVENT)", content, re.DOTALL)
    for block in blocks:
        m = re.search(r"UID:(.+)", block)
        if m:
            events[m.group(1).strip()] = block.strip()
    return events

# ── Fetch weather data ────────────────────────────────────────────────────────

def fetch_forecast() -> dict:
    """Returns {date_str: (t_min, t_max, wmo_code)} for next 10 days."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        f"&daily=temperature_2m_max,temperature_2m_min,weathercode"
        f"&timezone={TIMEZONE}&forecast_days=10"
    )
    data = fetch_json(url)["daily"]
    result = {}
    for i, d in enumerate(data["time"]):
        result[d] = (
            data["temperature_2m_min"][i],
            data["temperature_2m_max"][i],
            data["weathercode"][i],
        )
    return result

def fetch_historical(start: date, end: date) -> dict:
    """Returns {date_str: (t_min, t_max, wmo_code)} for past days."""
    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        f"&start_date={start.isoformat()}&end_date={end.isoformat()}"
        f"&daily=temperature_2m_max,temperature_2m_min,weathercode"
        f"&timezone={TIMEZONE}"
    )
    data = fetch_json(url)["daily"]
    result = {}
    for i, d in enumerate(data["time"]):
        result[d] = (
            data["temperature_2m_min"][i],
            data["temperature_2m_max"][i],
            data["weathercode"][i],
        )
    return result

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    today      = date.today()
    yesterday  = today - timedelta(days=1)
    hist_start = today - timedelta(days=DAYS_BACK)

    print(f"Generating weather calendar for {CITY_NAME} ({today})...")

    # Load existing events so we can preserve truly old history
    existing_events = load_existing_events(ICS_PATH)

    # Fetch new data
    print("Fetching forecast...")
    forecast = fetch_forecast()

    print(f"Fetching historical data ({hist_start} → {yesterday})...")
    try:
        historical = fetch_historical(hist_start, yesterday)
    except Exception as e:
        print(f"Warning: historical fetch failed: {e}")
        historical = {}

    # Build event dict: uid → event_text
    # Priority: fresh API data > existing stored data
    new_events: dict[str, str] = {}

    # 1. Past days: use historical API (authoritative real values)
    d = hist_start
    while d <= yesterday:
        uid = uid_for_date(d)
        ds  = d.isoformat()
        if ds in historical:
            t_min, t_max, wmo = historical[ds]
            new_events[uid] = make_event(d, t_min, t_max, wmo, is_past=True)
        elif uid in existing_events:
            # Keep old stored value — don't overwrite with nothing
            new_events[uid] = existing_events[uid]
        d += timedelta(days=1)

    # 2. Future days (today + 9 more): use forecast
    for ds, (t_min, t_max, wmo) in forecast.items():
        fd  = date.fromisoformat(ds)
        uid = uid_for_date(fd)
        new_events[uid] = make_event(fd, t_min, t_max, wmo, is_past=False)

    # Write ICS
    os.makedirs(os.path.dirname(ICS_PATH), exist_ok=True)
    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Weather Calendar//Hamburg//EN",
        f"X-WR-CALNAME:🌤 {CITY_NAME} Weather",
        "X-WR-CALDESC:Daily weather forecast and history for Hamburg",
        "X-WR-TIMEZONE:Europe/Berlin",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]
    for event_text in sorted(new_events.values()):
        lines.append(event_text)
    lines.append("END:VCALENDAR")

    with open(ICS_PATH, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines) + "\r\n")

    print(f"✅ Written {len(new_events)} events to {ICS_PATH}")

if __name__ == "__main__":
    main()
