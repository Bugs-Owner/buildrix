"""
General-Purpose Time Series Forecaster for Building Science
Uses a lightweight LSTM model (PyTorch) for multi-step ahead prediction.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Optional

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


# ---------------------------------------------------------------------------
# LSTM Model
# ---------------------------------------------------------------------------
class LSTMForecaster(nn.Module):
    """Simple LSTM for multi-step time series forecasting."""

    def __init__(self, input_size: int, hidden_size: int, output_size: int, horizon: int):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers=2,
                            batch_first=True, dropout=0.1)
        self.fc = nn.Linear(hidden_size, output_size * horizon)
        self.output_size = output_size
        self.horizon = horizon

    def forward(self, x):
        out, _ = self.lstm(x)
        out = self.fc(out[:, -1, :])  # Use last time step
        return out.view(-1, self.horizon, self.output_size)


# ---------------------------------------------------------------------------
# Main Forecaster Class
# ---------------------------------------------------------------------------
class TimeSeriesForecaster:
    """
    Train and predict time series using LSTM.

    Parameters
    ----------
    target_columns : list[str]
        Column(s) to forecast.
    lookback_hours : float
        Hours of history to use as input window.
    horizon_hours : float
        Hours ahead to forecast.
    hidden_size : int
        LSTM hidden layer size (default 64).
    """

    def __init__(
        self,
        target_columns: list[str],
        lookback_hours: float = 48,
        horizon_hours: float = 24,
        hidden_size: int = 64,
    ):
        if not HAS_TORCH:
            raise ImportError(
                "PyTorch is required. Install with: pip install torch"
            )

        self.target_columns = target_columns
        self.lookback_hours = lookback_hours
        self.horizon_hours = horizon_hours
        self.hidden_size = hidden_size

        self.model = None
        self.scaler_mean = None
        self.scaler_std = None
        self.resolution_minutes = None
        self.lookback_steps = None
        self.horizon_steps = None

    def fit(
        self,
        df: pd.DataFrame,
        epochs: int = 50,
        batch_size: int = 32,
        val_split: float = 0.2,
        lr: float = 0.001,
        verbose: bool = True,
    ):
        """
        Train the LSTM model on historical data.

        Parameters
        ----------
        df : pd.DataFrame with DatetimeIndex
        epochs : int
        batch_size : int
        val_split : float — fraction of data for validation
        lr : float — learning rate
        verbose : bool — print training progress
        """
        # Auto-detect resolution
        self.resolution_minutes = _detect_resolution(df)
        steps_per_hour = 60 / self.resolution_minutes
        self.lookback_steps = int(self.lookback_hours * steps_per_hour)
        self.horizon_steps = int(self.horizon_hours * steps_per_hour)

        if verbose:
            print(f"  Resolution: {self.resolution_minutes} min")
            print(f"  Lookback: {self.lookback_steps} steps ({self.lookback_hours}h)")
            print(f"  Horizon: {self.horizon_steps} steps ({self.horizon_hours}h)")

        # Validate columns exist
        missing = [c for c in self.target_columns if c not in df.columns]
        if missing:
            # Try auto-detecting
            available = list(df.select_dtypes(include=[np.number]).columns)
            raise ValueError(
                f"Columns not found: {missing}. Available numeric columns: {available}"
            )

        # Extract and normalize data
        data = df[self.target_columns].values.astype(np.float32)

        # Handle NaN by forward-fill then backward-fill
        data_df = pd.DataFrame(data)
        data_df = data_df.ffill().bfill()
        data = data_df.values

        self.scaler_mean = data.mean(axis=0)
        self.scaler_std = data.std(axis=0) + 1e-8
        data_norm = (data - self.scaler_mean) / self.scaler_std

        # Create sequences
        X, Y = _create_sequences(data_norm, self.lookback_steps, self.horizon_steps)
        if len(X) < 10:
            raise ValueError(
                f"Not enough data. Need at least {self.lookback_steps + self.horizon_steps + 10} "
                f"rows, got {len(data)}."
            )

        # Train/val split (keep temporal order)
        split_idx = int(len(X) * (1 - val_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        Y_train, Y_val = Y[:split_idx], Y[split_idx:]

        train_ds = TensorDataset(torch.tensor(X_train), torch.tensor(Y_train))
        train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

        # Build model
        n_features = len(self.target_columns)
        self.model = LSTMForecaster(n_features, self.hidden_size, n_features, self.horizon_steps)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.MSELoss()

        # Training loop
        if verbose:
            print(f"  Training on {len(X_train)} samples, validating on {len(X_val)}...")

        best_val_loss = float("inf")
        for epoch in range(epochs):
            self.model.train()
            train_loss = 0
            for xb, yb in train_dl:
                pred = self.model(xb)
                loss = criterion(pred, yb)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                train_loss += loss.item() * len(xb)
            train_loss /= len(X_train)

            # Validation
            self.model.eval()
            with torch.no_grad():
                val_pred = self.model(torch.tensor(X_val))
                val_loss = criterion(val_pred, torch.tensor(Y_val)).item()

            if val_loss < best_val_loss:
                best_val_loss = val_loss

            if verbose and (epoch + 1) % 10 == 0:
                print(f"    Epoch {epoch+1}/{epochs} — train: {train_loss:.4f}, val: {val_loss:.4f}")

        if verbose:
            # Report validation metrics in original units
            val_pred_np = val_pred.numpy() * self.scaler_std + self.scaler_mean
            val_true_np = Y_val * self.scaler_std + self.scaler_mean
            rmse = np.sqrt(np.mean((val_pred_np - val_true_np) ** 2, axis=(0, 1)))
            mae = np.mean(np.abs(val_pred_np - val_true_np), axis=(0, 1))
            print(f"\n  Validation metrics (original units):")
            for i, col in enumerate(self.target_columns):
                print(f"    {col}: RMSE={rmse[i]:.2f}, MAE={mae[i]:.2f}")

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate forecast from the end of the provided data.

        Returns DataFrame with predicted values and future timestamps.
        """
        if self.model is None:
            raise RuntimeError("Model not trained. Call fit() first.")

        data = df[self.target_columns].values.astype(np.float32)
        data_df = pd.DataFrame(data).ffill().bfill()
        data = data_df.values

        data_norm = (data - self.scaler_mean) / self.scaler_std

        # Use the last lookback_steps as input
        input_seq = data_norm[-self.lookback_steps:]
        input_tensor = torch.tensor(input_seq).unsqueeze(0)

        self.model.eval()
        with torch.no_grad():
            pred_norm = self.model(input_tensor).squeeze(0).numpy()

        pred = pred_norm * self.scaler_std + self.scaler_mean

        # Build future timestamps
        last_time = df.index[-1]
        freq = pd.Timedelta(minutes=self.resolution_minutes)
        future_times = pd.date_range(
            start=last_time + freq,
            periods=self.horizon_steps,
            freq=freq,
        )

        pred_df = pd.DataFrame(pred, index=future_times, columns=self.target_columns)
        pred_df.index.name = "datetime"
        return pred_df

    def save_results(
        self,
        predictions: pd.DataFrame,
        df_history: Optional[pd.DataFrame] = None,
        output_dir: str = ".",
        plot: bool = True,
    ):
        """Save forecast CSV and plot."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # Save CSV
        csv_path = out / "forecast_results.csv"
        predictions.to_csv(csv_path)
        print(f"  Forecast saved to {csv_path}")

        # Plot
        if plot and df_history is not None:
            fig, axes = plt.subplots(
                len(self.target_columns), 1,
                figsize=(14, 3.5 * len(self.target_columns)),
                sharex=True,
            )
            if len(self.target_columns) == 1:
                axes = [axes]

            # Show last N hours of history for context
            context_hours = min(self.lookback_hours * 2, len(df_history) * self.resolution_minutes / 60)
            context_steps = int(context_hours * 60 / self.resolution_minutes)
            history_tail = df_history[self.target_columns].iloc[-context_steps:]

            for i, col in enumerate(self.target_columns):
                ax = axes[i]
                ax.plot(history_tail.index, history_tail[col],
                        color="#3498db", linewidth=1, label="History")
                ax.plot(predictions.index, predictions[col],
                        color="#e74c3c", linewidth=1.5, label="Forecast", linestyle="--")
                ax.axvline(df_history.index[-1], color="gray", linestyle=":",
                           alpha=0.5, label="Now")
                ax.set_ylabel(col)
                ax.legend(fontsize=8)
                ax.grid(True, alpha=0.3)

            axes[-1].set_xlabel("Time")
            plt.suptitle("Time Series Forecast", fontsize=14, fontweight="bold")
            plt.tight_layout()

            plot_path = out / "forecast_plot.png"
            fig.savefig(plot_path, dpi=150, bbox_inches="tight")
            print(f"  Plot saved to {plot_path}")
            plt.close(fig)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _detect_resolution(df: pd.DataFrame) -> float:
    """Detect time series resolution in minutes."""
    if len(df) < 2:
        return 60.0
    gaps = df.index.to_series().diff().dropna()
    median_gap = gaps.median()
    minutes = median_gap.total_seconds() / 60
    # Round to nearest standard resolution
    standards = [1, 5, 10, 15, 30, 60, 180, 360, 1440]
    closest = min(standards, key=lambda x: abs(x - minutes))
    return float(closest)


def _create_sequences(data: np.ndarray, lookback: int, horizon: int):
    """Create sliding window sequences for training."""
    X, Y = [], []
    for i in range(len(data) - lookback - horizon + 1):
        X.append(data[i : i + lookback])
        Y.append(data[i + lookback : i + lookback + horizon])
    return np.array(X), np.array(Y)


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("TimeSeriesForecaster — run via a skill or import in Python.")
    print()
    print("Quick example:")
    print("  from forecaster import TimeSeriesForecaster")
    print("  f = TimeSeriesForecaster(['Temperature [°C]'], lookback_hours=48, horizon_hours=24)")
    print("  f.fit(df, epochs=50)")
    print("  predictions = f.predict(df)")
    print("  f.save_results(predictions, df, output_dir='outputs')")
