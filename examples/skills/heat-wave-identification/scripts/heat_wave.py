"""
Heat Wave Identification for Building Science
Detects and analyzes heat wave events from temperature time series.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class HeatWaveEvent:
    """A single identified heat wave event."""
    start: pd.Timestamp
    end: pd.Timestamp
    duration_days: int
    peak_temp: float
    mean_temp: float
    cooling_degree_hours: float  # CDH above base temp during event


def identify_heat_waves(
    df: pd.DataFrame,
    temp_column: str = "Temperature [°C]",
    method: str = "percentile",
    percentile: float = 90,
    threshold: float = 35.0,
    min_duration: int = 3,
    base_temp: float = 18.0,
) -> list[HeatWaveEvent]:
    """
    Identify heat wave periods from temperature data.

    Parameters
    ----------
    df : pd.DataFrame
        Data with DatetimeIndex. Can be hourly or daily.
    temp_column : str
        Column name containing temperature in °C.
    method : str
        "percentile", "absolute", "wmo", or "nws"
    percentile : float
        For percentile method: threshold percentile (default 90).
    threshold : float
        For absolute method: temperature threshold in °C (default 35).
    min_duration : int
        Minimum consecutive days to qualify (default 3).
    base_temp : float
        Base temperature for CDH calculation (default 18°C).

    Returns
    -------
    List of HeatWaveEvent objects, sorted by start date.
    """
    if temp_column not in df.columns:
        # Try to find a temperature column automatically
        temp_cols = [c for c in df.columns if "temp" in c.lower() or "°c" in c.lower() or "°f" in c.lower()]
        if temp_cols:
            temp_column = temp_cols[0]
            print(f"  Auto-detected temperature column: '{temp_column}'")
        else:
            raise ValueError(
                f"Column '{temp_column}' not found. Available: {list(df.columns)}"
            )

    temp = df[temp_column].copy()

    # Resample to daily max if hourly data
    if _is_hourly(temp):
        daily_max = temp.resample("D").max()
        hourly = temp
    else:
        daily_max = temp
        hourly = None

    # Determine threshold based on method
    if method == "percentile":
        thresh = daily_max.quantile(percentile / 100)
        print(f"  Percentile method: {percentile}th = {thresh:.1f}°C")
    elif method == "absolute":
        thresh = threshold
    elif method == "wmo":
        thresh = daily_max.mean() + 5.0
        min_duration = max(min_duration, 5)
        print(f"  WMO method: mean + 5°C = {thresh:.1f}°C")
    elif method == "nws":
        thresh = 40.6
        min_duration = max(min_duration, 2)
    else:
        raise ValueError(f"Unknown method: {method}. Use: percentile, absolute, wmo, nws")

    # Find consecutive hot days
    exceed = daily_max > thresh
    events = []
    in_event = False
    event_start = None

    for date, is_hot in exceed.items():
        if is_hot and not in_event:
            event_start = date
            in_event = True
        elif not is_hot and in_event:
            duration = (date - event_start).days
            if duration >= min_duration:
                events.append(_build_event(
                    event_start, date - pd.Timedelta(days=1),
                    duration, daily_max, hourly, base_temp
                ))
            in_event = False

    # Handle event still open at end of data
    if in_event:
        end_date = daily_max.index[-1]
        duration = (end_date - event_start).days + 1
        if duration >= min_duration:
            events.append(_build_event(
                event_start, end_date, duration, daily_max, hourly, base_temp
            ))

    print(f"  Found {len(events)} heat wave event(s) "
          f"(method={method}, threshold={thresh:.1f}°C, min {min_duration} days)")

    return events


def _build_event(start, end, duration, daily_max, hourly, base_temp):
    mask = (daily_max.index >= start) & (daily_max.index <= end)
    temps = daily_max[mask]

    cdh = 0.0
    if hourly is not None:
        hmask = (hourly.index >= start) & (hourly.index <= end + pd.Timedelta(days=1))
        h_temps = hourly[hmask]
        cdh = h_temps[h_temps > base_temp].sub(base_temp).sum()
    else:
        cdh = temps[temps > base_temp].sub(base_temp).sum() * 24

    return HeatWaveEvent(
        start=start, end=end, duration_days=duration,
        peak_temp=temps.max(), mean_temp=temps.mean(),
        cooling_degree_hours=round(cdh, 1),
    )


def _is_hourly(series):
    if len(series) < 2:
        return False
    gaps = series.index.to_series().diff().dropna()
    return gaps.median() < pd.Timedelta(hours=2)


def generate_heat_wave_report(
    events: list[HeatWaveEvent],
    df: pd.DataFrame,
    location: str = "Unknown",
    output_dir: str = ".",
) -> str:
    """Generate markdown report and CSV of heat wave events."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Heat Wave Analysis: {location}",
        "",
        f"- **Data period:** {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}",
        f"- **Events found:** {len(events)}",
        "",
    ]

    if not events:
        lines.append("No heat wave events detected in this period.")
    else:
        lines.append("## Events")
        lines.append("")
        lines.append("| # | Start | End | Days | Peak °C | Mean °C | CDH |")
        lines.append("|---|-------|-----|------|---------|---------|-----|")
        total_cdh = 0
        for i, e in enumerate(events, 1):
            lines.append(
                f"| {i} | {e.start.strftime('%Y-%m-%d')} | {e.end.strftime('%Y-%m-%d')} "
                f"| {e.duration_days} | {e.peak_temp:.1f} | {e.mean_temp:.1f} "
                f"| {e.cooling_degree_hours:.0f} |"
            )
            total_cdh += e.cooling_degree_hours

        lines.extend([
            "",
            "## Summary",
            "",
            f"- **Total heat wave days:** {sum(e.duration_days for e in events)}",
            f"- **Hottest event peak:** {max(e.peak_temp for e in events):.1f}°C",
            f"- **Longest event:** {max(e.duration_days for e in events)} days",
            f"- **Total CDH during events:** {total_cdh:.0f} (base 18°C)",
            "",
            "## Building Impact Notes",
            "",
            "- CDH = cumulative cooling load above 18°C base during heat wave periods",
            "- Peak temperatures indicate design conditions for cooling system sizing",
            "- Duration affects thermal mass response and occupant comfort strategies",
            "",
        ])

        # Save CSV
        rows = [{
            "event": i + 1,
            "start": e.start.strftime("%Y-%m-%d"),
            "end": e.end.strftime("%Y-%m-%d"),
            "duration_days": e.duration_days,
            "peak_temp_C": round(e.peak_temp, 1),
            "mean_temp_C": round(e.mean_temp, 1),
            "cooling_degree_hours": round(e.cooling_degree_hours, 1),
        } for i, e in enumerate(events)]
        pd.DataFrame(rows).to_csv(out / "heat_wave_events.csv", index=False)
        print(f"  Events saved to {out / 'heat_wave_events.csv'}")

    report = "\n".join(lines)
    (out / "heat_wave_report.md").write_text(report)
    print(f"  Report saved to {out / 'heat_wave_report.md'}")
    return report
