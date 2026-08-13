"""Mean-reversion screening on the daily timeframe (the least-bad timeframe).

FX majors often mean-revert in ranging regimes. This tests a Bollinger-band
mean-reversion strategy (fade extreme deviations, exit at the mean) across
pairs on the daily timeframe.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "C:/cline_forex_hibryd")

from config import load_config
from broker.oanda import OandaClient
from backtest.engine import BacktestEngine
from backtest.metrics import compute_metrics
from strategies.signals import atr
from screen import PAIRS, fetch_history


class MeanReversion:
    name = "mean_reversion"

    def __init__(self, lookback=20, num_std=2.0):
        self.lookback = lookback
        self.num_std = num_std

    def generate_signals(self, df):
        out = df.copy()
        close = out["Close"]
        ma = close.rolling(self.lookback).mean()
        std = close.rolling(self.lookback).std()
        upper = ma + self.num_std * std
        lower = ma - self.num_std * std

        out["atr"] = atr(out, 14)
        out["signal"] = 0
        out.loc[close < lower, "signal"] = 1    # oversold -> buy
        out.loc[close > upper, "signal"] = -1   # overbought -> sell

        out["exit_long"] = (close >= ma).astype(int)   # reverted to mean -> exit
        out["exit_short"] = (close <= ma).astype(int)
        return out


def pf_str(pf):
    if pf is None:
        return "n/a"
    if pf == float("inf"):
        return "inf"
    return f"{pf:.2f}"


def main():
    cfg = load_config()
    cfg.strategy.trail_enabled = False
    client = OandaClient(cfg.oanda)
    results = []

    for pair in PAIRS:
        df = fetch_history(client, pair, "D", 5)
        for lb, ns in [(20, 2.0), (20, 2.5), (50, 2.0)]:
            sig = MeanReversion(lb, ns).generate_signals(df)
            eng = BacktestEngine(cfg)
            eq = eng.run(sig)
            m = compute_metrics(eq["equity"], eng.trades)
            results.append((pair, lb, ns, m))
            print(f"{pair:8s} MR lb={lb:2d} sd={ns:3.1f}  ret {m['total_return_pct']:7.2f}%  "
                  f"dd {m['max_drawdown_pct']:7.2f}%  sharpe {m['sharpe']:5.2f}  "
                  f"trades {m['num_trades']:4d}  PF {pf_str(m['profit_factor'])}")

    results.sort(key=lambda r: -r[3]["total_return_pct"])
    print("\n===== MEAN REVERSION TOP 10 (daily) =====")
    for pair, lb, ns, m in results[:10]:
        print(f"{pair:8s} MR lb={lb:2d} sd={ns:3.1f}  ret {m['total_return_pct']:7.2f}%  "
              f"dd {m['max_drawdown_pct']:7.2f}%  trades {m['num_trades']:4d}  PF {pf_str(m['profit_factor'])}")
    npos = sum(1 for r in results if r[3]["total_return_pct"] > 0)
    print(f"\nProfitable mean-reversion combos: {npos} / {len(results)}")


if __name__ == "__main__":
    main()