---
name: weather-data-extraction
description: >-
  Extract, transform, and analyze historical weather data for building science
  applications. Use when the user needs weather data for energy simulation,
  HVAC sizing, solar assessment, climate analysis, or any building-performance
  task that requires site-specific meteorological variables. Supports any
  location worldwide via geocoding. No API key required.
license: Apache-2.0
metadata:
  author: buildrix-community
  version: "0.1.0"
  domain: energy
  tags: [weather, climate, solar, TMY, building-science, open-meteo]
---

# Weather Data Extraction

Fetches historical hourly weather data from the Open-Meteo Archive API and
produces analysis-ready outputs for building science workflows.

## When to Use This Skill

- User asks for weather data for a specific location and date range
- Energy simulation pre-processing (EnergyPlus, eQuest, IES-VE inputs)
- Solar resource assessment (GHI, DNI, DHI analysis)
- HVAC load estimation requiring outdoor conditions
- Degree-day calculations or climate classification
- Any task mentioning "TMY", "weather file", or "climate data"

## Capabilities

The helper script at `scripts/weather_helper.py` provides:

1. **Geocoding** — convert city names or lat/lon to coordinates
2. **Data fetching** — hourly historical data from Open-Meteo (free, no key)
3. **Summary statistics** — per-variable stats, daily solar totals
4. **Visualization** — multi-panel time-series plots
5. **Export** — CSV, markdown summary, PNG plots

## Default Variables (Building Science Core Set)

| Variable | Unit | Use Case |
|----------|------|----------|
| Temperature (2m) | °C | Load calcs, degree-days |
| Relative Humidity (2m) | % | Psychrometrics, comfort |
| GHI (shortwave) | W/m² | Solar gains, PV sizing |
| Direct Radiation | W/m² | Shading analysis |
| DHI (diffuse) | W/m² | Daylighting |
| DNI | W/m² | Concentrating solar |
| Wind Speed (10m) | m/s | Infiltration, ventilation |
| Wind Direction (10m) | ° | Wind analysis |
| Precipitation | mm | Stormwater, moisture |
| Cloud Cover | % | Sky condition |
| Surface Pressure | hPa | Altitude corrections |

## Instructions

### Step 1: Determine Location and Date Range

Ask the user for:
- **Location**: city name (e.g., "Syracuse, NY") or coordinates ("43.05, -76.15")
- **Date range**: explicit dates or "last N days" (data available up to ~5 days ago)
- **Variables**: use the default building-science set unless they specify otherwise

### Step 2: Run the Script

```python
import sys
sys.path.insert(0, "<skill_directory>/scripts")
from weather_helper import get_weather

df = get_weather(
    location="Syracuse, NY",
    start_date="2025-04-01",
    end_date="2025-04-30",
    output_dir="outputs"
)
```

Or for quick recent data:

```python
df = get_weather("Syracuse, NY", days=30, output_dir="outputs")
```

### Step 3: Deliver Outputs

The function saves three files to `output_dir`:
- `weather_data.csv` — full hourly dataset
- `weather_summary.md` — statistics and solar analysis
- `weather_plots.png` — multi-panel visualization

Present the summary to the user and note where files are saved.

### Step 4: Follow-Up Analysis (if requested)

Common next steps users may ask for:
- Degree-day calculations (base temperature)
- Monthly/seasonal aggregation
- Comparison between locations or years
- Format conversion for simulation tools (EPW, TMY3)
- Solar potential estimates

Use the returned DataFrame for these — it's a standard pandas object.

## Examples

**Example 1 — Basic extraction:**
> "Get me April 2025 weather data for Syracuse, NY"

→ Run `get_weather("Syracuse, NY", start_date="2025-04-01", end_date="2025-04-30")`

**Example 2 — Custom location with coordinates:**
> "I need solar radiation data for 40.7128, -74.0060 for the last 2 weeks"

→ Run `get_weather("40.7128, -74.0060", days=14)`

**Example 3 — Specific variables:**
> "Just temperature and humidity for Boston, March 2024"

→ Run with `variables=["temperature_2m", "relative_humidity_2m"]`

## Data Source

[Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api)
— free, open-source, no API key required. Data derived from ERA5 reanalysis
and national weather services. Hourly resolution, global coverage, data
available from 1940 to ~5 days ago.

## Dependencies

- Python 3.11+
- requests
- pandas
- matplotlib
