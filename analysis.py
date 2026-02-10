from __future__ import annotations

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression


def calc_rolling_average(df: pd.DataFrame, window: int) -> pd.Series:
    return df["weight_lbs"].rolling(window=window, min_periods=1).mean()


def calc_weekly_weight_change(df: pd.DataFrame) -> float | None:
    """Average weekly weight delta using recent data (last 4 weeks or all if less)."""
    if len(df) < 2:
        return None
    df = df.sort_values("date").copy()
    df["date"] = pd.to_datetime(df["date"])
    total_days = (df["date"].iloc[-1] - df["date"].iloc[0]).days
    if total_days == 0:
        return 0.0
    total_change = df["weight_lbs"].iloc[-1] - df["weight_lbs"].iloc[0]
    weekly_change = total_change / (total_days / 7)
    return round(weekly_change, 2)


def estimate_maintenance_calories(df: pd.DataFrame) -> float | None:
    """
    Estimate maintenance calories:
    maintenance = avg_daily_calories - (weekly_weight_change * 3500 / 7)
    """
    df_cal = df.dropna(subset=["calories"])
    if len(df_cal) < 2:
        return None
    avg_calories = df_cal["calories"].mean()
    weekly_change = calc_weekly_weight_change(df)
    if weekly_change is None:
        return None
    adjustment = weekly_change * 3500 / 7
    maintenance = avg_calories - adjustment
    return round(maintenance)


def get_trend_direction(weekly_change: float | None) -> str:
    if weekly_change is None:
        return "Insufficient Data"
    if weekly_change < -0.1:
        return "Losing"
    elif weekly_change > 0.1:
        return "Gaining"
    return "Maintaining"


def calc_calorie_vs_weight_data(df: pd.DataFrame) -> pd.DataFrame | None:
    """Aggregate weekly avg calories vs weekly weight change for scatter plot."""
    df = df.dropna(subset=["calories"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    if len(df) < 14:
        return None
    df = df.set_index("date")
    weekly = df.resample("W").agg({"calories": "mean", "weight_lbs": "mean"})
    weekly = weekly.dropna()
    if len(weekly) < 2:
        return None
    weekly["weight_change"] = weekly["weight_lbs"].diff()
    weekly = weekly.dropna()
    if len(weekly) < 2:
        return None
    return weekly.reset_index()


def linear_regression_line(
    x: np.ndarray, y: np.ndarray
) -> tuple[float, float] | None:
    """Returns (slope, intercept) for trend line."""
    if len(x) < 2:
        return None
    x = np.array(x).reshape(-1, 1)
    y = np.array(y)
    model = LinearRegression().fit(x, y)
    return float(model.coef_[0]), float(model.intercept_)
