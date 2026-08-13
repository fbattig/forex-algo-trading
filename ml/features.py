"""Feature engineering for the ML regime filter."""
from __future__ import annotations

import pandas as pd

from strategies.signals import adx, atr, ema, rsi

FEATURES = [
    "ret_1", "ret_5", "ret_10", "ret_20",
    "vol_20", "atr_ratio", "adx", "rsi_14",
    "ema_dist_200", "ema_spread", "mom_10",
]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"]
    out = pd.DataFrame(index=df.index)
    out["ret_1"] = close.pct_change(1)
    out["ret_5"] = close.pct_change(5)
    out["ret_10"] = close.pct_change(10)
    out["ret_20"] = close.pct_change(20)
    out["vol_20"] = close.pct_change().rolling(20).std()
    out["atr_ratio"] = atr(df, 14) / close
    out["adx"] = adx(df, 14)[0]
    out["rsi_14"] = rsi(close, 14)
    out["ema_dist_200"] = (close - ema(close, 200)) / close
    out["ema_spread"] = (ema(close, 20) - ema(close, 50)) / close
    out["mom_10"] = close.pct_change(10)
    return out


def build_target(df: pd.DataFrame, horizon: int = 1) -> pd.Series:
    """1 if the close `horizon` bars ahead is higher than today's close, else 0."""
    fwd = df["Close"].shift(-horizon)
    return (fwd > df["Close"]).astype(int)