"""Rule-based EMA trend-following strategy (alternative core).

Signals (computed on each bar's close, filled next bar by the engine):
  long  -> EMA(fast) crosses above EMA(slow), ADX > threshold, close > EMA(trend)
  short -> EMA(fast) crosses below EMA(slow), ADX > threshold, close < EMA(trend)
Exits  -> opposite EMA crossover, plus an ATR trailing stop handled by the engine.
"""
from __future__ import annotations

import pandas as pd

from .base import Strategy
from .signals import adx, atr, ema


class TrendFollowing(Strategy):
    name = "trend_following"

    def __init__(self, cfg):
        self.cfg = cfg

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        cfg = self.cfg
        out = df.copy()
        close = out["Close"]

        out["ema_fast"] = ema(close, cfg.ema_fast)
        out["ema_slow"] = ema(close, cfg.ema_slow)
        out["ema_trend"] = ema(close, cfg.ema_trend)
        out["atr"] = atr(out, cfg.atr_period)
        out["adx"], out["plus_di"], out["minus_di"] = adx(out, cfg.adx_period)

        cross_up = (out["ema_fast"] > out["ema_slow"]) & (out["ema_fast"].shift(1) <= out["ema_slow"].shift(1))
        cross_down = (out["ema_fast"] < out["ema_slow"]) & (out["ema_fast"].shift(1) >= out["ema_slow"].shift(1))

        trend_up = close > out["ema_trend"]
        trend_down = close < out["ema_trend"]
        strong = out["adx"] > cfg.adx_threshold

        out["signal"] = 0
        out.loc[cross_up & trend_up & strong, "signal"] = 1
        out.loc[cross_down & trend_down & strong, "signal"] = -1

        out["exit_long"] = cross_down.astype(int)
        out["exit_short"] = cross_up.astype(int)
        return out