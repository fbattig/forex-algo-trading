"""Synthetic FX data generator (offline fallback). Clearly labeled as synthetic."""
from __future__ import annotations

import numpy as np
import pandas as pd


def generate_synthetic(symbol: str = "EURUSD=X", n: int = 3000, start: str = "2016-01-01",
                       seed: int = 42, base: float = 1.10, daily_vol: float = 0.006) -> pd.DataFrame:
    """Generate regime-switching OHLC data so the full pipeline runs offline."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0, daily_vol, n)
    # regime: 0 = ranging, 1 = uptrend, 2 = downtrend
    regime = rng.choice([0, 1, 2], size=n, p=[0.55, 0.22, 0.23])
    drift = np.zeros(n)
    for i in range(1, n):
        if regime[i] == 1:
            drift[i] = drift[i - 1] + rng.normal(0.00035, 0.0002)
        elif regime[i] == 2:
            drift[i] = drift[i - 1] - rng.normal(0.00035, 0.0002)
        else:
            drift[i] = drift[i - 1] * 0.98
    log_price = np.log(base) + np.cumsum(returns) + np.cumsum(drift)
    close = np.exp(log_price)
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0.0, daily_vol / 2, n)))
    low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0.0, daily_vol / 2, n)))
    idx = pd.date_range(start=start, periods=n, freq="D")
    df = pd.DataFrame({
        "Open": open_, "High": high, "Low": low, "Close": close,
        "Volume": rng.integers(1000, 50000, n),
    }, index=idx)
    return df