"""Transparent event-driven backtesting engine (no lookahead bias).

Execution model:
  - Entry signals from bar i's close are filled at bar i+1's OPEN.
  - ATR trailing stops are updated each bar and checked intra-bar against
    High/Low, filling at the stop price (optional, see trail_enabled).
  - Strategy exit signals (exit_long / exit_short) fill at bar i's CLOSE.
  - A round-trip cost of (spread + 2 * slippage) pips is deducted per trade.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class Position:
    def __init__(self, side, entry_price, units, entry_time, stop_price):
        self.side = side            # 1 = long, -1 = short
        self.entry_price = entry_price
        self.units = units
        self.entry_time = entry_time
        self.stop_price = stop_price
        self.high_water = entry_price
        self.low_water = entry_price
        self.bars_held = 0


class BacktestEngine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.initial_capital = float(cfg.risk.initial_capital)
        self.equity_curve = None
        self.trades = None

    def _round_trip_cost(self) -> float:
        c = self.cfg.risk
        return (c.spread_pips + 2.0 * c.slippage_pips) * 0.0001

    def _position_units(self, equity: float, stop_distance: float) -> float:
        if stop_distance <= 0:
            return 0.0
        return (equity * self.cfg.risk.risk_per_trade) / stop_distance

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        cfg = self.cfg
        opens = df["Open"].to_numpy()
        highs = df["High"].to_numpy()
        lows = df["Low"].to_numpy()
        closes = df["Close"].to_numpy()
        atr = df["atr"].to_numpy()
        signal = df["signal"].to_numpy()
        exit_long = df["exit_long"].to_numpy()
        exit_short = df["exit_short"].to_numpy()
        dates = df.index

        equity = self.initial_capital
        pos = None
        pending_entry = 0
        trades = []
        curve = []
        rtc = self._round_trip_cost()
        n = len(df)

        for i in range(n):
            # 1) fill a pending entry at this bar's open
            if pos is None and pending_entry != 0:
                a_prev = atr[i - 1] if i > 0 else np.nan
                if not np.isnan(a_prev):
                    entry_price = opens[i]
                    stop_distance = cfg.strategy.atr_stop_mult * a_prev
                    stop_price = (entry_price - stop_distance) if pending_entry == 1 else (entry_price + stop_distance)
                    units = self._position_units(equity, stop_distance)
                    if units > 0:
                        pos = Position(pending_entry, entry_price, units, dates[i], stop_price)
                pending_entry = 0

            # 2) manage the open position on this bar
            if pos is not None:
                pos.bars_held += 1
                a = atr[i]
                if pos.side == 1:
                    pos.high_water = max(pos.high_water, highs[i])
                    if cfg.strategy.trail_enabled and not np.isnan(a):
                        pos.stop_price = max(pos.stop_price, pos.high_water - cfg.strategy.atr_stop_mult * a)
                    stop_hit = lows[i] <= pos.stop_price
                    exit_signal = bool(exit_long[i])
                else:
                    pos.low_water = min(pos.low_water, lows[i])
                    if cfg.strategy.trail_enabled and not np.isnan(a):
                        pos.stop_price = min(pos.stop_price, pos.low_water + cfg.strategy.atr_stop_mult * a)
                    stop_hit = highs[i] >= pos.stop_price
                    exit_signal = bool(exit_short[i])

                if stop_hit or exit_signal:
                    if stop_hit:
                        exit_price = pos.stop_price
                        reason = "stop"
                    else:
                        exit_price = closes[i]
                        reason = "signal"
                    gross = pos.side * (exit_price - pos.entry_price) * pos.units
                    pnl = gross - pos.units * rtc
                    equity += pnl
                    trades.append({
                        "entry_time": pos.entry_time,
                        "exit_time": dates[i],
                        "side": pos.side,
                        "entry_price": pos.entry_price,
                        "exit_price": exit_price,
                        "units": pos.units,
                        "bars_held": pos.bars_held,
                        "exit_reason": reason,
                        "pnl": pnl,
                    })
                    pos = None

            # 3) queue a new entry from this bar's close (filled next bar)
            if pos is None and signal[i] != 0:
                pending_entry = int(signal[i])

            # 4) mark-to-market equity at this bar's close
            mtm = equity
            if pos is not None:
                mtm += pos.side * (closes[i] - pos.entry_price) * pos.units
            curve.append({"date": dates[i], "equity": mtm})

        self.equity_curve = pd.DataFrame(curve).set_index("date")
        self.trades = pd.DataFrame(trades)
        return self.equity_curve