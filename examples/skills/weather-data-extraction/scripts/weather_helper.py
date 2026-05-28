"""
Weather Data Extraction Helper
Uses the Open-Meteo API (free, no key required) to fetch historical weather data.
"""

import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Default variable set for building science applications
# ---------------------------------------------------------------------------
DEFAULT_HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "direct_normal_irradiance",
    "wind_speed_10m",
    "wind_direction_10m",
    "precipitation",
    "cloud_cover",
    "surface_pressure",
]

COLUMN_NAMES = {
    "temperature_2m": "Temperature [°C]",
    "relative_humidity_2m": "Relative Humidity [%]",
    "shortwave_radiation": "GHI [W/m²]",
    "direct_radiation": "Direct Radiation [W/m²]",
    "diffuse_radiation": "DHI [W/m²]",
    "direct_normal_irradiance": "DNI [W/m²]",
    "wind_speed_10m": "Wind Speed [m/s]",
    "wind_direction_10m": "Wind Direction [°]",
    "precipitation": "Precipitation [mm]",
    "cloud_cover": "Cloud Cover [%]",
    "surface_pressure": "Surface Pressure [hPa]",
}

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------
def geocode(location: str) -> dict:
    """
    Convert a city/address string to coordinates using Open-Meteo Geocoding API.

    Returns dict with keys: name, latitude, longitude, timezone, elevation,
    country, admin1 (state/province).
    """
    # Try multiple query formats for robustness
    queries = [location]
    # If it looks like "City, ST" or "City, State", also try just the city name
    parts = [p.strip() for p in location.split(",")]
    if len(parts) >= 2:
        queries.append(parts[0])  # Just city name
        # Try "City State" without comma
        queries.append(" ".join(parts))

    for query in queries:
        try:
            resp = requests.get(
                GEOCODING_URL,
                params={"name": query, "count": 5, "language": "en", "format": "json"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if "results" in data and len(data["results"]) > 0:
                r = data["results"][0]
                return {
                    "name": r.get("name", location),
                    "latitude": r["latitude"],
                    "longitude": r["longitude"],
                    "timezone": r.get("timezone", "UTC"),
                    "elevation": r.get("elevation"),
                    "country": r.get("country", ""),
                    "admin1": r.get("admin1", ""),
                }
        except requests.RequestException:
            continue

    # Last resort: check common city lookup table
    hit = _COMMON_CITIES.get(location.lower().strip())
    if not hit:
        # Try just the city part
        city_part = location.split(",")[0].strip().lower()
        hit = _COMMON_CITIES.get(city_part)

    if hit:
        return hit

    raise ValueError(
        f"Could not geocode '{location}'. Try coordinates instead, e.g. '43.05, -76.15'"
    )


# Common building-science cities as fallback when geocoding API fails
_COMMON_CITIES = {
    "syracuse": {"name": "Syracuse", "latitude": 43.0481, "longitude": -76.1474, "timezone": "America/New_York", "elevation": 126, "country": "United States", "admin1": "New York"},
    "new york": {"name": "New York", "latitude": 40.7128, "longitude": -74.0060, "timezone": "America/New_York", "elevation": 10, "country": "United States", "admin1": "New York"},
    "boston": {"name": "Boston", "latitude": 42.3601, "longitude": -71.0589, "timezone": "America/New_York", "elevation": 43, "country": "United States", "admin1": "Massachusetts"},
    "chicago": {"name": "Chicago", "latitude": 41.8781, "longitude": -87.6298, "timezone": "America/Chicago", "elevation": 181, "country": "United States", "admin1": "Illinois"},
    "phoenix": {"name": "Phoenix", "latitude": 33.4484, "longitude": -112.0740, "timezone": "America/Phoenix", "elevation": 331, "country": "United States", "admin1": "Arizona"},
    "los angeles": {"name": "Los Angeles", "latitude": 34.0522, "longitude": -118.2437, "timezone": "America/Los_Angeles", "elevation": 71, "country": "United States", "admin1": "California"},
    "miami": {"name": "Miami", "latitude": 25.7617, "longitude": -80.1918, "timezone": "America/New_York", "elevation": 2, "country": "United States", "admin1": "Florida"},
    "denver": {"name": "Denver", "latitude": 39.7392, "longitude": -104.9903, "timezone": "America/Denver", "elevation": 1609, "country": "United States", "admin1": "Colorado"},
    "seattle": {"name": "Seattle", "latitude": 47.6062, "longitude": -122.3321, "timezone": "America/Los_Angeles", "elevation": 56, "country": "United States", "admin1": "Washington"},
    "houston": {"name": "Houston", "latitude": 29.7604, "longitude": -95.3698, "timezone": "America/Chicago", "elevation": 15, "country": "United States", "admin1": "Texas"},
    "atlanta": {"name": "Atlanta", "latitude": 33.7490, "longitude": -84.3880, "timezone": "America/New_York", "elevation": 320, "country": "United States", "admin1": "Georgia"},
    "san francisco": {"name": "San Francisco", "latitude": 37.7749, "longitude": -122.4194, "timezone": "America/Los_Angeles", "elevation": 16, "country": "United States", "admin1": "California"},
}


def parse_location(location: str) -> dict:
    """
    Accept either a city name OR a 'lat, lon' string.
    Returns geocoded dict in both cases.
    """
    parts = [p.strip() for p in location.replace(";", ",").split(",")]
    if len(parts) == 2:
        try:
            lat, lon = float(parts[0]), float(parts[1])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return {
                    "name": f"{lat:.4f}, {lon:.4f}",
                    "latitude": lat,
                    "longitude": lon,
                    "timezone": "auto",
                    "elevation": None,
                    "country": "",
                    "admin1": "",
                }
        except ValueError:
            pass

    return geocode(location)


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------
def fetch_weather(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    timezone: str = "auto",
    variables: Optional[list[str]] = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Fetch hourly historical weather data from Open-Meteo Archive API.

    Parameters
    ----------
    latitude, longitude : float
    start_date, end_date : str in YYYY-MM-DD format
    timezone : str (IANA timezone or "auto")
    variables : list of Open-Meteo variable names (defaults to DEFAULT_HOURLY_VARS)

    Returns
    -------
    df : pd.DataFrame with DatetimeIndex and one column per variable
    meta : dict with API metadata (elevation, utc_offset, etc.)
    """
    if variables is None:
        variables = DEFAULT_HOURLY_VARS

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(variables),
        "timezone": timezone,
    }

    resp = requests.get(ARCHIVE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if "hourly" not in data:
        raise ValueError(f"No hourly data returned. API response: {data}")

    hourly = data["hourly"]
    times = pd.to_datetime(hourly["time"])

    df = pd.DataFrame(
        {var: hourly.get(var) for var in variables if var in hourly},
        index=times,
    )
    df.index.name = "datetime"

    # Rename columns to human-readable
    df.rename(columns={k: v for k, v in COLUMN_NAMES.items() if k in df.columns}, inplace=True)

    meta = {
        "elevation": data.get("elevation"),
        "utc_offset_seconds": data.get("utc_offset_seconds"),
        "timezone": data.get("timezone"),
        "timezone_abbreviation": data.get("timezone_abbreviation"),
    }

    return df, meta


# ---------------------------------------------------------------------------
# Date range helpers
# ---------------------------------------------------------------------------
def resolve_date_range(
    days: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> tuple[str, str]:
    """
    Resolve user inputs into (start_date, end_date) strings.

    Open-Meteo historical data is available up to ~5 days ago.
    """
    safe_end = datetime.now() - timedelta(days=5)

    if start_date and end_date:
        ed = datetime.strptime(end_date, "%Y-%m-%d")
        if ed > safe_end:
            end_date = safe_end.strftime("%Y-%m-%d")
            print(f"⚠️  Adjusted end_date to {end_date} (data available up to ~5 days ago)")
        return start_date, end_date

    if days is None:
        days = 7

    ed = safe_end
    sd = ed - timedelta(days=days - 1)
    return sd.strftime("%Y-%m-%d"), ed.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------
def generate_summary(df: pd.DataFrame, location_info: dict, meta: dict) -> str:
    """Generate a markdown summary of the weather data."""
    lines = []
    name = location_info.get("name", "Unknown")
    admin = location_info.get("admin1", "")
    country = location_info.get("country", "")
    label = ", ".join(filter(None, [name, admin, country]))

    lines.append(f"# Weather Data Summary: {label}")
    lines.append("")
    lines.append(f"- **Coordinates:** {location_info['latitude']:.4f}°N, {location_info['longitude']:.4f}°W")
    lines.append(f"- **Elevation:** {meta.get('elevation', 'N/A')} m")
    lines.append(f"- **Timezone:** {meta.get('timezone', 'N/A')} ({meta.get('timezone_abbreviation', '')})")
    lines.append(f"- **Period:** {df.index[0].strftime('%Y-%m-%d %H:%M')} to {df.index[-1].strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"- **Hours:** {len(df)}")
    lines.append("")

    lines.append("## Variable Statistics")
    lines.append("")
    lines.append("| Variable | Min | Max | Mean | Std Dev | Missing |")
    lines.append("|----------|-----|-----|------|---------|---------|")
    for col in df.columns:
        s = df[col]
        nan_count = s.isna().sum()
        if s.dtype in ["float64", "int64", "float32"]:
            lines.append(
                f"| {col} | {s.min():.1f} | {s.max():.1f} | {s.mean():.1f} | {s.std():.1f} | {nan_count} |"
            )
    lines.append("")

    if "GHI [W/m²]" in df.columns:
        daily_ghi = df["GHI [W/m²]"].resample("D").sum() / 1000
        lines.append("## Daily Solar Radiation (GHI)")
        lines.append("")
        lines.append(f"- **Average:** {daily_ghi.mean():.2f} kWh/m²/day")
        lines.append(f"- **Peak day:** {daily_ghi.idxmax().strftime('%Y-%m-%d')} ({daily_ghi.max():.2f} kWh/m²)")
        lines.append(f"- **Lowest day:** {daily_ghi.idxmin().strftime('%Y-%m-%d')} ({daily_ghi.min():.2f} kWh/m²)")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def plot_weather(df: pd.DataFrame, location_label: str, save_path: Optional[str] = None):
    """
    Create a multi-panel time-series plot of key weather variables.

    Returns the matplotlib Figure object.
    """
    fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)
    fig.suptitle(f"Weather Data — {location_label}", fontsize=14, fontweight="bold")

    # Panel 1: Temperature
    ax = axes[0]
    if "Temperature [°C]" in df.columns:
        ax.plot(df.index, df["Temperature [°C]"], color="#e74c3c", linewidth=0.8)
        ax.set_ylabel("Temperature [°C]")
        ax.grid(True, alpha=0.3)

    # Panel 2: Solar Radiation
    ax = axes[1]
    solar_cols = {
        "GHI [W/m²]": ("#f39c12", "GHI"),
        "DNI [W/m²]": ("#e67e22", "DNI"),
        "DHI [W/m²]": ("#3498db", "DHI"),
    }
    for col, (color, label) in solar_cols.items():
        if col in df.columns:
            ax.plot(df.index, df[col], color=color, linewidth=0.6, label=label, alpha=0.85)
    ax.set_ylabel("Radiation [W/m²]")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)

    # Panel 3: Wind Speed
    ax = axes[2]
    if "Wind Speed [m/s]" in df.columns:
        ax.plot(df.index, df["Wind Speed [m/s]"], color="#2ecc71", linewidth=0.8)
        ax.set_ylabel("Wind Speed [m/s]")
        ax.grid(True, alpha=0.3)

    # Panel 4: Humidity + Cloud Cover
    ax = axes[3]
    if "Relative Humidity [%]" in df.columns:
        ax.plot(df.index, df["Relative Humidity [%]"], color="#9b59b6", linewidth=0.7, label="RH")
    if "Cloud Cover [%]" in df.columns:
        ax.plot(df.index, df["Cloud Cover [%]"], color="#95a5a6", linewidth=0.7, label="Cloud", alpha=0.7)
    ax.set_ylabel("Percent [%]")
    ax.set_ylim(0, 105)
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    axes[-1].xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=30)
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f" Plot saved to {save_path}")

    return fig


# ---------------------------------------------------------------------------
# Main convenience function
# ---------------------------------------------------------------------------
def get_weather(
    location: str,
    days: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    variables: Optional[list[str]] = None,
    output_dir: str = ".",
    plot: bool = True,
) -> pd.DataFrame:
    """
    One-call convenience function: geocode → fetch → summarize → plot → save.

    Parameters
    ----------
    location : str
        City name or "lat, lon" string.
    days : int, optional
        Number of past days (default 7).
    start_date, end_date : str, optional
        Explicit date range in YYYY-MM-DD format (overrides days).
    variables : list, optional
        Open-Meteo variable names (defaults to building-science core set).
    output_dir : str
        Where to save CSV, summary, and plot files.
    plot : bool
        Whether to generate and save the plot.

    Returns
    -------
    pd.DataFrame with hourly weather data.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Geocode
    loc = parse_location(location)
    label = ", ".join(filter(None, [loc["name"], loc["admin1"], loc["country"]]))
    print(f" Location: {label} ({loc['latitude']:.4f}, {loc['longitude']:.4f})")

    # 2. Date range
    sd, ed = resolve_date_range(days, start_date, end_date)
    print(f" Date range: {sd} to {ed}")

    # 3. Fetch
    print("  Fetching weather data from Open-Meteo...")
    df, meta = fetch_weather(
        loc["latitude"], loc["longitude"], sd, ed, loc["timezone"], variables
    )
    print(f"✅ Retrieved {len(df)} hourly records, {len(df.columns)} variables")

    # 4. Summary
    summary = generate_summary(df, loc, meta)
    summary_path = out / "weather_summary.md"
    summary_path.write_text(summary)
    print(f" Summary saved to {summary_path}")
    print()
    print(summary)

    # 5. Plot
    if plot:
        plot_path = out / "weather_plots.png"
        plot_weather(df, f"{label} ({sd} to {ed})", str(plot_path))
        plt.show()

    # 6. Save CSV
    csv_path = out / "weather_data.csv"
    df.to_csv(csv_path)
    print(f" Data saved to {csv_path}")

    return df


# ---------------------------------------------------------------------------
# Script entry point (for standalone use)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    location = sys.argv[1] if len(sys.argv) > 1 else "Syracuse, NY"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 7

    df = get_weather(location, days=days)
