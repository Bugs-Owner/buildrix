---
name: timeseries-forecast
description: >-
  General-purpose time series forecasting for building science data using
  deep learning (LSTM). Use when the user wants to predict future values
  of any time-dependent variable: outdoor temperature, solar radiation,
  energy consumption, occupancy, electricity price, indoor conditions, etc.
  Supports configurable forecast horizon, resolution, and target variable.
license: Apache-2.0
metadata:
  author: buildrix-community
  version: "0.1.0"
  domain: energy
  tags: [forecast, prediction, LSTM, deep-learning, time-series, MPC, disturbance]
---

# Time Series Forecast

Train a lightweight LSTM model on historical data and produce multi-step
ahead forecasts. Designed for building science disturbance prediction
(weather, occupancy, price) to support model predictive control and
operational planning.

## When to Use This Skill

- User wants to forecast/predict future values of a time series
- Disturbance prediction for MPC (outdoor temp, solar, occupancy, price)
- Short-term weather forecast from local station data
- Energy load forecasting
- Any question involving "predict", "forecast", "what will X be tomorrow"

## Capabilities

- **Any variable**: temperature, solar, humidity, occupancy, price, load, etc.
- **Any resolution**: 5-min, 15-min, 30-min, hourly, daily — auto-detected
- **Configurable horizon**: forecast 1 hour ahead or 7 days ahead
- **Multiple targets**: forecast several variables simultaneously
- **Uncertainty**: optional Monte Carlo dropout for prediction intervals

## Instructions

### Step 1: Prepare Data

The user needs historical time series data as a pandas DataFrame or CSV
with a datetime index. If they don't have data yet, help them obtain it
from available sources.

### Step 2: Run Forecast

```python
import sys
sys.path.insert(0, "<skill_directory>/scripts")
from forecaster import TimeSeriesForecaster

forecaster = TimeSeriesForecaster(
    target_columns=["Temperature [°C]"],   # what to predict
    lookback_hours=48,                      # how much history to use
    horizon_hours=24,                       # how far ahead to predict
    hidden_size=64,                         # model capacity
)

# Train on historical data
forecaster.fit(df, epochs=50)

# Predict
predictions = forecaster.predict(df)

# Save results
forecaster.save_results(predictions, output_dir="outputs")
```

### Step 3: Deliver Results

- `forecast_results.csv` — predicted values with timestamps
- `forecast_plot.png` — visualization showing history + prediction
- Console summary with error metrics on validation set

## Examples

**Example 1 — Weather forecast:**
> "Predict tomorrow's outdoor temperature for Syracuse based on the last week"

→ Use available temperature data, train LSTM, forecast 24 hours ahead

**Example 2 — Multi-variable:**
> "Forecast solar radiation and temperature for the next 3 days"

→ Set `target_columns=["GHI [W/m²]", "Temperature [°C]"]`, `horizon_hours=72`

**Example 3 — High-resolution:**
> "I have 15-minute occupancy data. Predict the next 4 hours"

→ Auto-detects 15-min resolution, sets `horizon_hours=4`

**Example 4 — Price forecast:**
> "Predict electricity prices for tomorrow using this historical data"

→ Works on any numeric column — price, load, demand, etc.

## Dependencies

- Python 3.11+
- torch (PyTorch)
- pandas
- numpy
- matplotlib
