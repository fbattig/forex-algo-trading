"""Live paper-trading for the daily mean-reversion strategy (OANDA practice).

Runs the mean-reversion strategy on EUR_GBP, AUD_USD, EUR_USD, GBP_USD, placing
real market orders with attached stop-losses on your OANDA PRACTICE account.
Paper trading = demo money, no real risk.

Usage:
    python paper_trade.py              # one check-and-act cycle, then exit
    python paper_trade.py --loop       # run continuously, acting after each daily close
    python paper_trade.py --dry-run    # print what WOULD happen, place no orders
    python paper_trade.py --live       # ALLOW trading a live account (DANGER)
    python paper_trade.py --risk-pct 2 # risk 2%% of equity per trade
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

sys.path.insert(0, "C:/cline_forex_hibryd")

from config import load_config
from broker.oanda import OandaClient
from strategies.mean_reversion import MeanReversion
from ml.fade_filter import FadeFilter, apply_fade_filter, ml_applies
from notify import make_trade_chart, send_email

INSTRUMENTS = ["EUR_GBP", "AUD_USD", "EUR_USD", "GBP_USD"]
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_trade.log")

log = logging.getLogger("paper_trade")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
    )


def parse_args():
    p = argparse.ArgumentParser(description="OANDA paper trading (mean reversion)")
    p.add_argument("--loop", action="store_true", help="run continuously, act after each daily close")
    p.add_argument("--dry-run", action="store_true", help="print actions without placing orders")
    p.add_argument("--live", action="store_true", help="ALLOW trading a live account (danger)")
    p.add_argument("--pairs", nargs="+", default=None, help="OANDA instruments (e.g. EUR_GBP AUD_USD)")
    p.add_argument("--risk-pct", type=float, default=1.0, help="risk per trade in percent")
    p.add_argument("--lookback", type=int, default=None, help="mean-reversion lookback window")
    p.add_argument("--num-std", type=float, default=None, help="entry threshold in standard deviations")
    p.add_argument("--no-ml", action="store_true", help="disable the ML fade filter")
    p.add_argument("--ml-pairs", nargs="+", default=None, help="OANDA instruments to apply ML to (default: EUR_GBP EUR_USD)")
    return p.parse_args()


def fetch_complete_daily(client, instrument, count=400):
    """Fetch only COMPLETE daily candles (skip the in-progress one)."""
    data = client._get(f"/v3/instruments/{instrument}/candles",
                       {"granularity": "D", "count": count, "price": "M"})
    rows, times = [], []
    for c in data.get("candles", []):
        if not c.get("complete", True):
            continue
        mid = c["mid"]
        rows.append({"Open": float(mid["o"]), "High": float(mid["h"]),
                     "Low": float(mid["l"]), "Close": float(mid["c"]),
                     "Volume": int(c.get("volume", 0))})
        times.append(c["time"])
    if not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    df = pd.DataFrame(rows, index=pd.to_datetime(times))
    return df[["Open", "High", "Low", "Close", "Volume"]]


def get_open_positions_map(client):
    """Return {instrument: {'side': 1|-1, 'units': float, 'avg': float}}."""
    data = client.get_open_positions()
    out = {}
    for p in data.get("positions", []):
        long_units = float(p.get("long", {}).get("units", 0) or 0)
        short_units = float(p.get("short", {}).get("units", 0) or 0)
        if long_units > 0:
            avg = float(p.get("long", {}).get("averagePrice", 0) or 0)
            out[p["instrument"]] = {"side": 1, "units": long_units, "avg": avg}
        elif short_units > 0:
            avg = float(p.get("short", {}).get("averagePrice", 0) or 0)
            out[p["instrument"]] = {"side": -1, "units": short_units, "avg": avg}
    return out


def quote_to_account_rate(client, instrument, account_currency):
    """Rate to convert the instrument's quote currency into the account currency."""
    quote = instrument.split("_")[1]
    if quote == account_currency:
        return 1.0
    pricing = client.get_pricing(f"{quote}_{account_currency}")
    for pr in pricing.get("prices", []):
        mid = (float(pr["bids"][0]["price"]) + float(pr["asks"][0]["price"])) / 2.0
        return mid
    raise RuntimeError(f"could not price {quote}_{account_currency}")


def tail_log(path, n=20):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except Exception:
        return "(no log available)"


def send_trade_alert(cfg, inst, df, subject, body, entry_idx=None, entry_price=None,
                     entry_side=None, exit_idx=None, exit_price=None):
    """Generate a chart and email the trade notification (non-fatal on failure)."""
    try:
        chart = make_trade_chart(inst, df, cfg.mean_reversion.lookback, cfg.mean_reversion.num_std,
                                 path="reports/last_trade.png",
                                 entry_idx=entry_idx, entry_price=entry_price, entry_side=entry_side,
                                 exit_idx=exit_idx, exit_price=exit_price)
        body += "\n\nRecent log:\n" + tail_log(LOG_FILE, 20)
        ok, msg = send_email(cfg, subject, body, attachments=[chart])
        log.info("%s: email '%s' -> %s", inst, subject, "sent" if ok else "FAILED: " + msg)
    except Exception as e:
        log.error("%s: email error: %s", inst, e)


def run_once(client, cfg, instruments, risk_pct, dry_run, use_ml=True):
    account = client.get_account_summary()["account"]
    equity = float(account.get("NAV", account.get("balance", 100000)))
    currency = account.get("currency", "USD")
    log.info("Account %s | equity=%.2f %s | dry_run=%s | ml=%s", account.get("id"), equity, currency, dry_run, use_ml)

    positions = get_open_positions_map(client)
    log.info("Open positions: %s", positions if positions else "(none)")

    strat = MeanReversion(cfg)
    fade = FadeFilter(cfg)
    for inst in instruments:
        use_ml_pair = use_ml and ml_applies(cfg, inst)
        log.info("%s: ML fade filter %s", inst, "ON" if use_ml_pair else "off")
        try:
            df = fetch_complete_daily(client, inst, count=1500)
            if len(df) < 300:
                log.warning("%s: only %d bars, skipping", inst, len(df))
                continue
            sig = strat.generate_signals(df)
            if use_ml_pair:
                proba = fade.generate_probabilities(df)
                sig["signal"] = apply_fade_filter(sig["signal"], proba, cfg.fade_ml.prob_threshold)
            signal = int(sig["signal"].iloc[-1])
            exit_long = bool(sig["exit_long"].iloc[-1])
            exit_short = bool(sig["exit_short"].iloc[-1])
            atr_val = float(sig["atr"].iloc[-1])
            close = float(df["Close"].iloc[-1])
            pos = positions.get(inst, {}).get("side", 0)

            if pos == 0 and signal != 0:
                stop_distance = cfg.strategy.atr_stop_mult * atr_val
                stop_price = close - stop_distance if signal == 1 else close + stop_distance
                rate = quote_to_account_rate(client, inst, currency)
                risk_usd = equity * risk_pct / 100.0
                units = int(risk_usd / (stop_distance * rate))
                if units == 0:
                    log.info("%s: signal=%d but units=0 (risk too small), skip", inst, signal)
                    continue
                side = "LONG" if signal == 1 else "SHORT"
                if dry_run:
                    log.info("%s: [DRY] would ENTER %s %d units, stop=%.5f", inst, side, units, stop_price)
                else:
                    client.place_market_order_with_sl(inst, signal * units, stop_price)
                    log.info("%s: ENTERED %s %d units, stop=%.5f", inst, side, signal * units, stop_price)
                    send_trade_alert(cfg, inst, df,
                                     f"TRADE OPENED: {inst} {side}",
                                     f"{side} {inst} @ {close:.5f}  (stop {stop_price:.5f}, {units} units)",
                                     entry_idx=len(df) - 1, entry_price=close, entry_side=signal)
            elif pos == 1 and exit_long:
                if dry_run:
                    log.info("%s: [DRY] would CLOSE long (reverted to mean)", inst)
                else:
                    entry_info = positions.get(inst, {})
                    entry_avg = entry_info.get("avg", 0.0) or close
                    entry_units = entry_info.get("units", 0.0)
                    rate = quote_to_account_rate(client, inst, currency)
                    pnl = (close - entry_avg) * entry_units * rate
                    client.close_position(inst)
                    log.info("%s: CLOSED long (reverted to mean)", inst)
                    send_trade_alert(cfg, inst, df,
                                     f"TRADE CLOSED: {inst} LONG",
                                     f"Closed LONG {inst} @ {close:.5f}  (approx P&L {pnl:+.2f} {currency})",
                                     exit_idx=len(df) - 1, exit_price=close)
            elif pos == -1 and exit_short:
                if dry_run:
                    log.info("%s: [DRY] would CLOSE short (reverted to mean)", inst)
                else:
                    entry_info = positions.get(inst, {})
                    entry_avg = entry_info.get("avg", 0.0) or close
                    entry_units = entry_info.get("units", 0.0)
                    rate = quote_to_account_rate(client, inst, currency)
                    pnl = (entry_avg - close) * entry_units * rate
                    client.close_position(inst)
                    log.info("%s: CLOSED short (reverted to mean)", inst)
                    send_trade_alert(cfg, inst, df,
                                     f"TRADE CLOSED: {inst} SHORT",
                                     f"Closed SHORT {inst} @ {close:.5f}  (approx P&L {pnl:+.2f} {currency})",
                                     exit_idx=len(df) - 1, exit_price=close)
            else:
                state = "LONG" if pos == 1 else ("SHORT" if pos == -1 else "flat")
                log.info("%s: %s - no action (signal=%d, close=%.5f)", inst, state, signal, close)
        except Exception as e:
            log.error("%s: error - %s", inst, e)


def seconds_until_next_close():
    now = datetime.now(timezone.utc)
    target = now.replace(hour=21, minute=5, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def main():
    args = parse_args()
    setup_logging()
    cfg = load_config()

    if cfg.oanda.environment == "live" and not args.live:
        log.error("Refusing to trade a LIVE account without --live. Use the practice account.")
        sys.exit(1)
    if args.live:
        log.warning("!!! TRADING A LIVE ACCOUNT - REAL MONEY AT RISK !!!")

    if args.lookback is not None:
        cfg.mean_reversion.lookback = args.lookback
    if args.num_std is not None:
        cfg.mean_reversion.num_std = args.num_std
    cfg.strategy.trail_enabled = False
    if args.ml_pairs is not None:
        cfg.fade_ml.ml_pairs = args.ml_pairs

    instruments = args.pairs or INSTRUMENTS
    client = OandaClient(cfg.oanda)

    if args.loop:
        log.info("Loop mode ON: acting after each daily close (~21:05 UTC). Ctrl+C to stop.")
        while True:
            try:
                run_once(client, cfg, instruments, args.risk_pct, args.dry_run, use_ml=not args.no_ml)
            except Exception as e:
                log.error("cycle error: %s", e)
            while True:
                secs = seconds_until_next_close()
                if secs <= 0:
                    break
                time.sleep(min(secs, 3600))
    else:
        run_once(client, cfg, instruments, args.risk_pct, args.dry_run, use_ml=not args.no_ml)
        log.info("Done. Log written to %s", LOG_FILE)


if __name__ == "__main__":
    main()