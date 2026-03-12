# 🌤 Weather Calendar

A self-hosted, subscribable weather calendar for Hamburg (or any city),
powered by **Open-Meteo** (free, no API key needed) and **GitHub Actions**.

## Features

- ☀️ Daily min/max temperature + weather emoji
- 📅 Future 10-day forecast updated every day at 00:05 UTC
- 🕰 Past days show real historical temperatures (never overwritten)
- 📡 Subscribable `.ics` link for Google Calendar, Apple Calendar, Outlook

## Setup (one-time, ~5 minutes)

### 1. Fork or create this repo

Push all these files to a **public** GitHub repository.

### 2. Enable GitHub Pages

Go to your repo → **Settings** → **Pages**  
Set source to: **Deploy from a branch** → branch `main` → folder `/docs`  
Click Save.

Your calendar URL will be:
```
https://<your-username>.github.io/<repo-name>/weather.ics
```

### 3. Run the action for the first time

Go to **Actions** → **Generate Weather Calendar** → **Run workflow**

This generates the initial `docs/weather.ics` and commits it.

### 4. Subscribe in Google Calendar

1. Open Google Calendar → left sidebar → **"Other calendars"** → `+` → **"From URL"**
2. Paste your URL:
   ```
   https://<your-username>.github.io/<repo-name>/weather.ics
   ```
3. Done! ✅

> Google Calendar refreshes external subscriptions roughly every 12–24 hours.

## Customization

Edit `generate_weather_ics.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `LATITUDE` | `53.5753` | Your city latitude |
| `LONGITUDE` | `10.0153` | Your city longitude |
| `CITY_NAME` | `"Hamburg"` | Display name |
| `TIMEZONE` | `"Europe/Berlin"` | [IANA timezone](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) |
| `DAYS_BACK` | `30` | How many past days to keep |

## Data source

[Open-Meteo](https://open-meteo.com/) — free, no API key, data from ECMWF & DWD.
