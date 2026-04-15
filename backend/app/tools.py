import pandas as pd
import numpy as np
from langchain_core.tools import tool
from app.config import CSV_PATH, THRESHOLDS, ENERGY_RATES

# Load DataFrame into memory once
df = pd.read_csv(CSV_PATH, parse_dates=["timestamp"])

@tool
def query_sensor_data(metric: str, limit: int = 20) -> str:
    """
    Query a sensor metric. Returns stats and recent values. 
    Use this to get raw numbers for pump vibration, hot water temp, or energy.
    """
    matches = [c for c in df.columns if metric.lower() in c.lower()]
    if not matches: return f"Column '{metric}' not found."
    metric = matches[0]

    subset = df[["timestamp", metric]].dropna().tail(limit)
    vals = subset[metric].values
    return (
        f"Metric: {metric} | Current: {vals[-1]:.2f} | Mean: {np.mean(vals):.2f}\n"
        f"Last 5: {', '.join(f'{v:.2f}' for v in vals[-5:])}"
    )

@tool
def get_trend_analysis(metric: str, window_days: int = 7) -> str:
    """Analyse trend and predict future values for a metric."""
    matches = [c for c in df.columns if metric.lower() in c.lower()]
    if not matches: return f"Column '{metric}' not found."
    metric = matches[0]

    subset = df[["timestamp", metric]].dropna().tail(window_days * 96)
    vals = subset[metric].values
    if len(vals) < 10: return "Not enough data."

    x = np.arange(len(vals))
    slope, _ = np.polyfit(x, vals, 1)
    daily_change = slope * 96

    return (
        f"Trend for {metric} (last {window_days} days):\n"
        f"Current: {vals[-1]:.2f} | Daily change: {daily_change:+.3f}/day\n"
        f"Predicted 7 days: {vals[-1] + daily_change * 7:.2f}\n"
        f"Predicted 30 days: {vals[-1] + daily_change * 30:.2f}"
    )

@tool
def get_energy_rates() -> str:
    """Get energy pricing for cost calculations and optimisation."""
    return "\n".join(f"{k}: {v}" for k, v in ENERGY_RATES.items())