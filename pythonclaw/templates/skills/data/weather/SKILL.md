---
name: weather
description: >
  Get current weather and forecasts for any city or location worldwide.
  Use when the user asks about weather, temperature, rain, wind, or
  forecasts for any place.
---

## Instructions

Fetch weather data using the **Open-Meteo API** — completely free,
no API key required, and supports any location on Earth.

### Usage

```bash
python {skill_path}/weather.py "City Name" [options]
```

Options:
- `--forecast 3` — include N-day forecast (default: current only)
- `--format json` — output as JSON (default: human-readable text)
- `--units imperial` — use Fahrenheit/mph (default: metric)

### Examples

- "What's the weather in Tokyo?" → `python {skill_path}/weather.py "Tokyo"`
- "5-day forecast for New York" → `python {skill_path}/weather.py "New York" --forecast 5`
- "Is it raining in London?" → `python {skill_path}/weather.py "London"`
- "Weather in Paris in Fahrenheit" → `python {skill_path}/weather.py "Paris" --units imperial`

### How It Works

1. Geocodes the city name to latitude/longitude via Open-Meteo's geocoding API
2. Fetches current weather + optional forecast from Open-Meteo's weather API
3. Returns temperature, humidity, wind speed, weather condition, and precipitation

## Resources

| File | Description |
|------|-------------|
| `weather.py` | Weather data fetcher via Open-Meteo |
