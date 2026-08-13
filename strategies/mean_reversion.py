"""Bollinger-band mean reversion strategy.

FX majors mean-revert in ranging regimes. Enter by fading extreme deviations
from the rolling mean (close below the lower band -> buy, above the upper band
-> sell) and exit when price reverts to the mean. An initial ATR stop caps
losses when a genuine trend does develop.

This is intentionally NOT paired with the ML direction filter (which is built
for trend-following); mean reversion is the strategy that proved profitable on
the 2021-2026 daily data.
"""
from __future__ import annotations

import pandas as pd

from .base import Strategy
from .signals import atr


class MeanReversion(Strategy):
    name = "mean_reversion"
    uses_ml = False

    def __init__(self, cfg):
        self.cfg = cfg

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        mr = self.cfg.mean_reversion
        out = df.copy()
        close = out["Close"]

        ma = close.rolling(mr.lookback).mean()
        std = close.rolling(mr.lookback).std()
        upper = ma + mr.num_std * std
        lower = ma - mr.num_std * std

        out["atr"] = atr(out, self.cfg.strategy.atr_period)

        out["signal"] = 0
        out.loc[close < lower, "signal"] = 1    # oversold -> buy
        out.loc[close > upper, "signal"] = -1   # overbought -> sell

        out["exit_long"] = (close >= ma).astype(int)   # reverted to mean -> exit long
        out["exit_short"] = (close <= ma).astype(int)  # reverted to mean -> exit short
        return out