---
name: heat-wave-identification
description: >-
  Identify and analyze heat wave periods from temperature data for building
  performance assessment. Use when the user asks about extreme heat events,
  heat waves, hot spells, or cooling load during peak periods. Supports
  multiple definitions (WMO, NWS, percentile-based, absolute threshold).
  Input is any pandas DataFrame or CSV with a temperature column.
license: Apache-2.0
metadata:
  author: buildrix-community
  version: "0.1.0"
  domain: energy
  tags: [heat-wave, extreme-weather, cooling, climate, thermal-comfort]
---

# Heat Wave Identification

Detects heat wave events from temperature time series and produces structured
analysis for building energy and comfort assessment.

## When to Use This Skill

- User asks about heat waves, extreme heat, or hot spells for a location
- Cooling system sizing under extreme conditions
- Climate risk assessment for buildings
- Identifying peak cooling periods for energy analysis
- Any question about consecutive hot days or heat stress

## What This Skill Needs

A pandas DataFrame (or CSV file) with:
- A datetime index (or datetime column)
- A temperature column in °C

If the user doesn't have temperature data yet, obtain it first — the agent
should determine the best way to get weather data for the requested location
and time period before running this analysis.

## Heat Wave Definitions Supported

| Method | Definition | Source |
|--------|-----------|--------|
| `percentile` | Tmax exceeds Nth percentile for ≥N days | Default: 90th, 3 days |
| `absolute` | Tmax exceeds fixed threshold for ≥N days | Default: 35°C, 3 days |
| `wmo` | ≥5 days with Tmax >5°C above dataset mean | World Meteorological Org |
| `nws` | Heat index ≥40.6°C for ≥2 days | US National Weather Service |

## Instructions

### Step 1: Ensure Temperature Data is Available

The user needs hourly or daily temperature data. If they don't have it,
help them get it first (from a file, API, or any available data source).

### Step 2: Run the Analysis

```python
import sys
sys.path.insert(0, "<skill_directory>/scripts")
from heat_wave import identify_heat_waves, generate_heat_wave_report

# df is a DataFrame with temperature data
events = identify_heat_waves(
    df,
    temp_column="Temperature [°C]",  # adjust to match actual column name
    method="percentile",              # or "absolute", "wmo", "nws"
    percentile=90,
    min_duration=3,
)

report = generate_heat_wave_report(events, df, location="City Name", output_dir="outputs")
```

### Step 3: Present Results

Show the user:
- Number of heat wave events found
- Table with each event's dates, duration, peak temp, mean temp, and CDH
- Building impact notes (cooling degree-hours during events)
- Saved files: `heat_wave_events.csv` and `heat_wave_report.md`

## Examples

**Example 1:**
> "Were there any heat waves in Phoenix last summer?"

→ Get Phoenix summer 2024 temperature data, then run percentile-based detection

**Example 2:**
> "I need extreme heat periods for Syracuse 2024 for cooling system sizing"

→ Get Syracuse 2024 data, run analysis, highlight peak temps and CDH values

**Example 3:**
> "Find days above 35°C for at least 3 consecutive days in this weather file"

→ Run absolute threshold method on the provided data

## Dependencies

- Python 3.11+
- pandas
- numpy
