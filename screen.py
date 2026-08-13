"""Timeframe & pair screening: find profitable combinations.

Fetches several years of OANDA data per timeframe/pair and runs the Donchian
strategy on each, printing a ranked table and saving screen_results.csv.

IMPORTANT: this is a *screening* step only. Any positive result is a candidate
that still needs out-of-sample (walk-forward) confirmation before real use -
running many tests and cherry-picking the best is selection bias.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "C:/cline_forex_hibryd")

import pandas as pd

from config import load_config
from broker.oanda import OandaClient
from strategies.donchian import DonchianTrend
from backtest.engine import BacktestEngine
from backtest.metrics import compute_metrics

PAIRS = ["EUR_USD", "GBP_USD", "AUD_USD", "NZD_USD", "USD_CAD", "EUR_GBP"]
TIMEFRAMES = ["H1", "H4", "H8", "H12", "D"]
BARS_PER_DAY = {"H1": 24, "H4": 6, "H8": 3, "H12": 2, "D": 1}
YEARS = 5
CONFIGS = [(20, 10, "20/10d"), (55, 20, "55/20d")]  # (entry_days, exit_days, label)


def fetch_history(client, instrument, granularity, years):
    end = datetime.now(timezone.utc)
    target_start = end - timedelta(days=365.25 * years)
    to = None
    batches = []
    guard = 0
    while guard < 200:
        guard += 1
        params = {"granularity": granularity, "count": 5000, "price": "M"}
        if to:
            params["to"] = to
        data = client._get(f"/v3/instruments/{instrument}/candles", params)
        batch = data.get("candles", [])
        if not batch:
            break
        batches.append(batch)
        if len(batch) < 5000:
            break
        earliest = batch[0]["time"]
        if to and earliest >= to:
            break
        to = earliest
        if pd.to_datetime(earliest) < target_start:
            break
    by_time = {}
    for b in batches:
        for c in b:
            by_time[c["time"]] = c
    times = sorted(by_time)
    rows = []
    for t in times:
        mid = by_time[t]["mid"]
        rows.append({
            "Open": float(mid["o"]), "High": float(mid["h"]),
            "Low": float(mid["l"]), "Close": float(mid["c"]),
            "Volume": int(by_time[t].get("volume", 0)),
        })
    if not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    df = pd.DataFrame(rows, index=pd.to_datetime(times))
    df = df[df.index >= target_start]
    return df[["Open", "High", "Low", "Close", "Volume"]]


def pf_str(pf):
    if pf is None:
        return "n/a"
    if pf == float("inf"):
        return "inf"
    return f"{pf:.2f}"


def main():
    cfg = load_config()
    client = OandaClient(cfg.oanda)
    results = []

    print(f"Screening {len(PAIRS)} pairs x {len(TIMEFRAMES)} timeframes x {len(CONFIGS)} configs "
          f"(~{YEARS}y history each)...")
    print()

    for tf in TIMEFRAMES:
        bpd = BARS_PER_DAY[tf]
        for pair in PAIRS:
            try:
                df = fetch_history(client, pair, tf, YEARS)
            except Exception as e:
                print(f"  [skip] {pair} {tf}: fetch failed ({e})")
                continue
            if len(df) < 1000:
                print(f"  [skip] {pair} {tf}: only {len(df)} bars")
                continue
            for entry_days, exit_days, label in CONFIGS:
                cfg.donchian.entry_window = entry_days * bpd
                cfg.donchian.exit_window = exit_days * bpd
                cfg.strategy.trail_enabled = False
                sig = DonchianTrend(cfg).generate_signals(df)
                eng = BacktestEngine(cfg)
                eq = eng.run(sig)
                m = compute_metrics(eq["equity"], eng.trades)
                results.append({
                    "pair": pair, "tf": tf, "cfg": label,
                    "bars": len(df),
                    "ret_pct": round(m["total_return_pct"], 2),
                    "dd_pct": round(m["max_drawdown_pct"], 2),
                    "sharpe": round(m["sharpe"], 2),
                    "trades": m["num_trades"],
                    "pf": m["profit_factor"],
                })
                print(f"  {pair:8s} {tf:4s} {label:6s}  ret {m['total_return_pct']:7.2f}%  "
                      f"dd {m['max_drawdown_pct']:7.2f}%  sharpe {m['sharpe']:5.2f}  "
                      f"trades {m['num_trades']:4d}  PF {pf_str(m['profit_factor'])}")

    res = pd.DataFrame(results)
    res.to_csv("reports/screen_results.csv", index=False)
    print(f"\nSaved reports/screen_results.csv ({len(res)} results)")

    res = res.sort_values("ret_pct", ascending=False)
    print("\n===== TOP 15 BY RETURN =====")
    top = res.head(15).copy()
    top["pf"] = top["pf"].apply(pf_str)
    print(top.to_string(index=False))

    profitable = res[res["ret_pct"] > 0]
    print(f"\nProfitable combos found: {len(profitable)} / {len(res)}")


if __name__ == "__main__":
    main()