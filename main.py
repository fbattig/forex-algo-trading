"""Forex hybrid algorithmic trading system - CLI entry point.

Examples:
    python main.py                              # Donchian breakout, rule-based + ML
    python main.py --strategy ema               # EMA crossover strategy
    python main.py --pairs EURUSD=X             # single pair
    python main.py --no-ml                      # rule-based only
    python main.py --capital 50000 --risk-pct 2 # 2% risk per trade

For a simple double-click launcher, use run.bat.

OANDA (broker of choice) - credentials are read automatically from a .env file
(OANDA_API_KEY / OANDA_API_TOKEN, OANDA_ACCOUNT_ID, OANDA_API_URL, OANDA_ENV).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from config import load_config
from data.fetcher import fetch_yahoo
from data.sample_data import generate_synthetic
from strategies.trend_following import TrendFollowing
from strategies.donchian import DonchianTrend
from strategies.mean_reversion import MeanReversion
from ml.regime_filter import RegimeFilter, apply_filter
from ml.fade_filter import FadeFilter, apply_fade_filter
from backtest.engine import BacktestEngine
from backtest.metrics import compute_metrics
from analysis.walk_forward import walk_forward
from analysis.monte_carlo import monte_carlo, mc_summary
from analysis.report import print_metrics, plot_equity
from broker.oanda import OandaClient


def parse_args():
    p = argparse.ArgumentParser(description="Forex hybrid algorithmic trading system")
    p.add_argument("--pairs", nargs="+", default=["EURUSD=X", "GBPUSD=X"],
                   help="Yahoo symbols; OANDA instruments are derived automatically")
    p.add_argument("--strategy", choices=["donchian", "ema", "meanreversion", "meanreversion-ml"], default="donchian",
                   help="core strategy (default: donchian breakout)")
    p.add_argument("--start", default="2016-01-01")
    p.add_argument("--no-ml", action="store_true", help="disable the ML regime filter")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--risk", type=float, default=None, help="risk per trade as a fraction (e.g. 0.01)")
    p.add_argument("--risk-pct", type=float, default=None, help="risk per trade as a percent (e.g. 1 = 1%%)")
    p.add_argument("--out", default="reports", help="output directory for charts")
    return p.parse_args()


def to_oanda_symbol(symbol: str) -> str:
    s = symbol.replace("=X", "")
    if len(s) == 6:
        return f"{s[:3]}_{s[3:]}"
    return s


def make_strategy(cfg, name: str):
    if name == "ema":
        cfg.strategy.trail_enabled = True
        return TrendFollowing(cfg.strategy)
    if name in ("meanreversion", "meanreversion-ml"):
        cfg.strategy.trail_enabled = False
        strat = MeanReversion(cfg)
        if name == "meanreversion-ml":
            strat.uses_ml = True
        return strat
    cfg.strategy.trail_enabled = False
    return DonchianTrend(cfg)


def load_data(symbol: str, oanda_symbol: str, cfg):
    """Try OANDA -> yfinance -> synthetic, in that order."""
    if cfg.oanda.api_token:
        try:
            client = OandaClient(cfg.oanda)
            df = client.fetch_candles(oanda_symbol, granularity=cfg.data.oanda_granularity,
                                      count=5000, start=cfg.data.start)
            if df is not None and len(df) > 300:
                return df, "oanda"
        except Exception as e:
            print(f"  [data] OANDA failed for {oanda_symbol}: {e}")
    try:
        df = fetch_yahoo(symbol, interval=cfg.data.interval, start=cfg.data.start, end=cfg.data.end)
        if len(df) > 300:
            return df, "yahoo"
    except Exception as e:
        print(f"  [data] yahoo failed for {symbol}: {e}")
    print(f"  [data] using SYNTHETIC data for {symbol}")
    return generate_synthetic(symbol, n=3000, start=cfg.data.start), "synthetic"


def build_signals(df, strat, cfg, use_ml):
    sig = strat.generate_signals(df)
    if use_ml:
        if strat.name == "mean_reversion":
            proba = FadeFilter(cfg).generate_probabilities(df)
            sig["signal"] = apply_fade_filter(sig["signal"], proba, cfg.fade_ml.prob_threshold)
        else:
            proba = RegimeFilter(cfg).generate_probabilities(df)
            sig["signal"] = apply_filter(sig["signal"], proba, cfg.ml.prob_threshold)
    return sig


def _summarize(label, m):
    pf = m.get("profit_factor")
    pf_s = "inf" if pf == float("inf") else (f"{pf:.2f}" if pf is not None else "n/a")
    wr = m.get("win_rate_pct")
    wr_s = f"{wr:.1f}" if wr is not None else "n/a"
    return (f"{label}: return {m['total_return_pct']:.2f}% | maxDD {m['max_drawdown_pct']:.2f}% | "
            f"trades {m['num_trades']} | winRate {wr_s}% | PF {pf_s}")


def main():
    args = parse_args()
    cfg = load_config()
    cfg.data.pairs = args.pairs
    cfg.data.start = args.start
    cfg.risk.initial_capital = args.capital
    if args.risk_pct is not None:
        cfg.risk.risk_per_trade = args.risk_pct / 100.0
    elif args.risk is not None:
        cfg.risk.risk_per_trade = args.risk
    cfg.ml.enabled = not args.no_ml

    os.makedirs(args.out, exist_ok=True)
    summary = [
        "Forex Hybrid Trading System - Backtest Results",
        "=" * 62,
        f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Strategy  : {args.strategy}",
        f"ML filter : {'on' if (cfg.ml.enabled and args.strategy in ('donchian', 'ema', 'meanreversion-ml')) else 'off'}",
        f"Capital   : ${cfg.risk.initial_capital:,.0f}",
        f"Risk/trade: {cfg.risk.risk_per_trade * 100:.2f}%",
        "",
    ]

    for symbol in cfg.data.pairs:
        oanda_symbol = to_oanda_symbol(symbol)
        print(f"\n{'=' * 70}\n{symbol}   (OANDA: {oanda_symbol})   strategy: {args.strategy}\n{'=' * 70}")

        df, source = load_data(symbol, oanda_symbol, cfg)
        print(f"  data source : {source}")
        print(f"  bars        : {len(df)}")
        print(f"  period      : {df.index[0].date()} -> {df.index[-1].date()}")

        strat = make_strategy(cfg, args.strategy)

        sig_base = build_signals(df, strat, cfg, use_ml=False)
        eng = BacktestEngine(cfg)
        eq_base = eng.run(sig_base)
        trades_base = eng.trades
        m_base = compute_metrics(eq_base["equity"], trades_base)
        print_metrics(m_base, "RULE-BASED (no ML)")
        summary.append(_summarize(f"{symbol} [rule-based]", m_base))
        base_png = os.path.join(args.out, f"{symbol.replace('=', '_')}_{args.strategy}_rule.png")
        plot_equity(eq_base["equity"], f"{symbol} - {args.strategy} rule-based", base_png)

        if cfg.ml.enabled and strat.uses_ml:
            sig_hyb = build_signals(df, strat, cfg, use_ml=True)
            eng2 = BacktestEngine(cfg)
            eq_hyb = eng2.run(sig_hyb)
            trades_hyb = eng2.trades
            m_hyb = compute_metrics(eq_hyb["equity"], trades_hyb)
            print_metrics(m_hyb, "HYBRID (rule-based + ML filter)")
            summary.append(_summarize(f"{symbol} [hybrid]", m_hyb))
            hyb_png = os.path.join(args.out, f"{symbol.replace('=', '_')}_{args.strategy}_hybrid.png")
            plot_equity(eq_hyb["equity"], f"{symbol} - {args.strategy} hybrid", hyb_png, benchmark=eq_base["equity"])

            if len(trades_hyb):
                mc = monte_carlo(trades_hyb["pnl"])
                s = mc_summary(mc, cfg.risk.initial_capital)
                print(f"\n  ---- MONTE CARLO ({len(trades_hyb)} trades, 2000 sims) ----")
                print(f"  P(final P&L < 0)   : {s['prob_negative']:.1f}%")
                print(f"  Median final P&L   : ${s['median_final_pnl']:,.0f}")
                print(f"  5th/95th pct P&L   : ${s['p5_final_pnl']:,.0f} / ${s['p95_final_pnl']:,.0f}")
                print(f"  Median max DD      : {s['median_max_dd_pct']:.2f}%")
                print(f"  Worst-5% max DD    : {s['p95_max_dd_pct']:.2f}%")

                print("\n  ---- WALK-FORWARD (out-of-sample) ----")
                for (t0, t1, m) in walk_forward(sig_hyb, cfg, n_splits=4):
                    print(f"  {t0.date()} -> {t1.date()}:  ret {m['total_return_pct']:.2f}%,  "
                          f"dd {m['max_drawdown_pct']:.2f}%,  trades {m['num_trades']}")

    summary_path = os.path.join(args.out, "summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary) + "\n")
    print(f"\nDone. Charts + summary written to {os.path.abspath(args.out)}")
    print(f"Summary file: {summary_path}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(130)
    except Exception as exc:
        print("\n" + "=" * 62)
        print("  Something went wrong (don't panic):")
        print(f"  {type(exc).__name__}: {exc}")
        print()
        print("  Most common fixes:")
        print("   - Check your internet connection (data download).")
        print("   - Re-run; the system falls back to built-in data")
        print("     automatically if downloads fail.")
        print("=" * 62)
        sys.exit(1)