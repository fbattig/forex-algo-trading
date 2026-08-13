"""Yahoo Finance data fetcher (pure Python fallback when OANDA is unavailable)."""
from __future__ import annotations

import pandas as pd
import yfinance as yf


def fetch_yahoo(symbol: str, interval: str = "1d", start: str = "2016-01-01",
                end: str | None = None) -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    df = ticker.history(interval=interval, start=start, end=end,
                        auto_adjust=False, actions=False)
    if df is None or df.empty:
        raise RuntimeError(f"no data returned for {symbol}")
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df