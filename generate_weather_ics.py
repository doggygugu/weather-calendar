#!/usr/bin/env python3
"""
Weather Calendar Generator
- Fetches forecast (next 10 days) from Open-Meteo forecast API
- Fetches past weather from Open-Meteo historical API
- Merges with existing ICS to preserve historical entries
- Outputs one subscribable weather.ics file per city
"""

import json
import os
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone

# ── Configuration ────────────────────────────────────────────────────────────
# Add or remove cities here. Each entry:
#   "City Name": (latitude, longitude, "IANA/Timezone")
# File will be saved as docs/<city-name-lowercase>.ics
CITIES = {
    "Hamburg":   (53.5753, 10.0153, "Europe/Berlin"),
    "Groningen": (53.2194,  6.5665, "Europe/Amsterdam"),
    "Burdaard":  (53.3000,  5.9833, "Europe/Amsterdam"),
    "Berlin":    (52.5200, 13.4050, "Europe/Berlin"),
}

DAYS_BACK = 30   # how many past days to include / preserve

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

def uid_for_date(d: date, city_name: str) -> str:
    return f"weather-{d.isoformat()}@{city_name.lower().replace(' ', '-')}-calendar"

def make_event(d: date, t_min: float, t_max: float, wmo: int, is_past: bool,
               city_name: str, tz: str) -> str:
    emoji = WMO_EMOJI.get(wmo, "🌡")
    desc  = WMO_DESC.get(wmo, "Unknown")

    summary = f"{emoji} {round(t_min)}°–{round(t_max)}°C  {desc}"
    dt_str  = d.strftime("%Y%m%d")

    if is_past:
        dtstart = f"DTSTART;TZID={tz}:{dt_str}T235900"
        dtend   = f"DTEND;TZID={tz}:{(d + timedelta(days=1)).strftime('%Y%m%d')}T000000"
    else:
        dtstart = f"DTSTART;VALUE=DATE:{dt_str}"
        dtend   = f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}"

    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    uid     = uid_for_date(d, city_name)

    return "\n".join([
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now_utc}",
        dtstart,
        dtend,
        f"SUMMARY:{summary}",
        f"DESCRIPTION:Low: {round(t_min)}°C / High: {round(t_max)}°C\\nCondition: {desc}\\nSource: Open-Meteo",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ])

def load_existing_events(path: str) -> dict:
    """Parse existing ICS and return dict of {uid: event_block_str}."""
    events = {}
    if not os.path.exists(path):
        return events
    with open(path, encoding="utf-8") as f:
        content = f.read()
    blocks = re.findall(r"(BEGIN:VEVENT.*?END:VEVENT)", content, re.DOTALL)
    for block in blocks:
        m = re.search(r"UID:(.+)", block)
        if m:
            events[m.group(1).strip()] = block.strip()
    return events

# ── Fetch weather data ────────────────────────────────────────────────────────

def fetch_forecast(lat: float, lon: float, tz: str) -> dict:
    """Returns {date_str: (t_min, t_max, wmo_code)} for next 10 days."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,weathercode"
        f"&timezone={tz}&forecast_days=10"
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

def fetch_historical(lat: float, lon: float, tz: str, start: date, end: date) -> dict:
    """Returns {date_str: (t_min, t_max, wmo_code)} for past days."""
    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start.isoformat()}&end_date={end.isoformat()}"
        f"&daily=temperature_2m_max,temperature_2m_min,weathercode"
        f"&timezone={tz}"
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

# ── Generate one city ─────────────────────────────────────────────────────────

def generate_city(city_name: str, lat: float, lon: float, tz: str):
    ics_path   = f"docs/{city_name.lower().replace(' ', '-')}.ics"
    today      = date.today()
    yesterday  = today - timedelta(days=1)
    hist_start = today - timedelta(days=DAYS_BACK)

    print(f"\n📍 {city_name} ({today})")

    existing_events = load_existing_events(ics_path)

    print("  Fetching forecast...")
    forecast = fetch_forecast(lat, lon, tz)

    print(f"  Fetching historical ({hist_start} → {yesterday})...")
    try:
        historical = fetch_historical(lat, lon, tz, hist_start, yesterday)
    except Exception as e:
        print(f"  ⚠️  Historical fetch failed: {e}")
        historical = {}

    new_events: dict[str, str] = {}

    # Past days
    d = hist_start
    while d <= yesterday:
        uid = uid_for_date(d, city_name)
        ds  = d.isoformat()
        if ds in historical:
            t_min, t_max, wmo = historical[ds]
            new_events[uid] = make_event(d, t_min, t_max, wmo, True, city_name, tz)
        elif uid in existing_events:
            new_events[uid] = existing_events[uid]
        d += timedelta(days=1)

    # Future days
    for ds, (t_min, t_max, wmo) in forecast.items():
        fd  = date.fromisoformat(ds)
        uid = uid_for_date(fd, city_name)
        new_events[uid] = make_event(fd, t_min, t_max, wmo, False, city_name, tz)

    os.makedirs("docs", exist_ok=True)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//Weather Calendar//{city_name}//EN",
        f"X-WR-CALNAME:🌤 {city_name} Weather",
        f"X-WR-CALDESC:Daily weather forecast and history for {city_name}",
        f"X-WR-TIMEZONE:{tz}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]
    for event_text in sorted(new_events.values()):
        lines.append(event_text)
    lines.append("END:VCALENDAR")

    with open(ics_path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines) + "\r\n")

    print(f"  ✅ {len(new_events)} events → {ics_path}")

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    for city_name, (lat, lon, tz) in CITIES.items():
        generate_city(city_name, lat, lon, tz)
    print("\n🎉 All cities done.")

if __name__ == "__main__":
    main()