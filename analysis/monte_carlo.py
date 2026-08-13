"""Monte Carlo simulation of trade sequences."""
from __future__ import annotations

import numpy as np
import pandas as pd


def monte_carlo(pnl: pd.Series, n_sims: int = 2000, seed: int = 42) -> pd.DataFrame:
    """Shuffle trade P&L order to estimate the distribution of final P&L and
    max drawdown under path uncertainty."""
    rng = np.random.default_rng(seed)
    vals = pnl.to_numpy(dtype=float)
    finals = np.empty(n_sims)
    max_dds = np.empty(n_sims)
    for s in range(n_sims):
        shuffled = rng.permutation(vals)
        eq = np.concatenate(([0.0], np.cumsum(shuffled)))
        finals[s] = eq[-1]
        max_dds[s] = (eq - np.maximum.accumulate(eq)).min()
    return pd.DataFrame({"final_pnl": finals, "max_dd": max_dds})


def mc_summary(mc: pd.DataFrame, capital: float) -> dict:
    """Summarize a Monte Carlo result."""
    return {
        "prob_negative": float((mc["final_pnl"] < 0).mean() * 100.0),
        "median_final_pnl": float(mc["final_pnl"].median()),
        "p5_final_pnl": float(mc["final_pnl"].quantile(0.05)),
        "p95_final_pnl": float(mc["final_pnl"].quantile(0.95)),
        "median_max_dd_pct": float((mc["max_dd"] / capital).median() * 100.0),
        "p95_max_dd_pct": float((mc["max_dd"] / capital).quantile(0.05) * 100.0),
    }