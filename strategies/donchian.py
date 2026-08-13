"""Donchian channel breakout trend-following strategy (Turtle-style).

Long entry  : close breaks above the highest high of the last entry_window bars.
Short entry : close breaks below the lowest low of the last entry_window bars.
Exit        : opposite breakout (close breaks the exit_window-bar low/high),
              plus an initial ATR risk stop managed by the engine (no trailing).

This is the canonical robust trend-following system: it lets winners run and
cuts losers quickly, and works across many markets and regimes.
"""
from __future__ import annotations

import pandas as pd

from .base import Strategy
from .signals import atr


class DonchianTrend(Strategy):
    name = "donchian"

    def __init__(self, cfg):
        self.cfg = cfg

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        cfg = self.cfg
        out = df.copy()
        close = out["Close"]

        out["atr"] = atr(out, cfg.strategy.atr_period)

        entry_high = out["High"].rolling(cfg.donchian.entry_window).max().shift(1)
        entry_low = out["Low"].rolling(cfg.donchian.entry_window).min().shift(1)
        exit_high = out["High"].rolling(cfg.donchian.exit_window).max().shift(1)
        exit_low = out["Low"].rolling(cfg.donchian.exit_window).min().shift(1)

        out["signal"] = 0
        out.loc[close > entry_high, "signal"] = 1
        out.loc[close < entry_low, "signal"] = -1

        out["exit_long"] = (close < exit_low).astype(int)
        out["exit_short"] = (close > exit_high).astype(int)
        return out