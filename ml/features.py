"""Feature engineering for the ML filters."""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.signals import adx, atr, ema, rsi

FEATURES = [
    "ret_1", "ret_5", "ret_10", "ret_20",
    "vol_20", "atr_ratio", "adx", "rsi_14",
    "ema_dist_200", "ema_spread", "mom_10", "zscore",
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
    out["zscore"] = (close - close.rolling(20).mean()) / close.rolling(20).std()
    return out


def build_target(df: pd.DataFrame, horizon: int = 1) -> pd.Series:
    """1 if the close `horizon` bars ahead is higher than today's close, else 0."""
    fwd = df["Close"].shift(-horizon)
    return (fwd > df["Close"]).astype(int)


def build_fade_target(df: pd.DataFrame, lookback: int = 20, horizon: int = 10) -> pd.Series:
    """Label each bar: would fading toward the mean revert within `horizon` bars?

    Fade direction: long if close < rolling mean, short if close > rolling mean.
    y = 1 if the fade reverts (price touches the mean) within `horizon` bars,
        0 if it does not, NaN where it cannot be determined.
    """
    close = df["Close"]
    ma = close.rolling(lookback).mean()
    fwd_high = df["High"].shift(-1).rolling(horizon).max()
    fwd_low = df["Low"].shift(-1).rolling(horizon).min()

    y = pd.Series(np.nan, index=df.index, dtype=float)
    long_mask = close < ma
    short_mask = close > ma
    y[long_mask & (fwd_high >= ma)] = 1.0
    y[short_mask & (fwd_low <= ma)] = 1.0
    y[long_mask & (fwd_high < ma)] = 0.0
    y[short_mask & (fwd_low > ma)] = 0.0
    return y