"""Performance metrics for a backtest."""
from __future__ import annotations

import numpy as np
import pandas as pd


def drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def sharpe_ratio(returns: pd.Series, periods_per_year: int = 252, rf: float = 0.0) -> float:
    if len(returns) == 0 or returns.std() == 0:
        return 0.0
    return (returns.mean() - rf) / returns.std() * np.sqrt(periods_per_year)


def compute_metrics(equity: pd.Series, trades: pd.DataFrame) -> dict:
    eq = equity.dropna()
    returns = eq.pct_change().dropna()
    dd = drawdown(eq)
    total_return = eq.iloc[-1] / eq.iloc[0] - 1.0
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    cagr = (1.0 + total_return) ** (1.0 / years) - 1.0

    m = {
        "initial_capital": float(eq.iloc[0]),
        "final_equity": float(eq.iloc[-1]),
        "total_return_pct": total_return * 100.0,
        "cagr_pct": cagr * 100.0,
        "sharpe": sharpe_ratio(returns),
        "max_drawdown_pct": dd.min() * 100.0,
        "num_trades": int(len(trades)),
    }

    if len(trades):
        wins = trades[trades["pnl"] > 0]
        losses = trades[trades["pnl"] <= 0]
        gross_win = float(wins["pnl"].sum()) if len(wins) else 0.0
        gross_loss = abs(float(losses["pnl"].sum())) if len(losses) else 0.0
        m["profit_factor"] = gross_win / gross_loss if gross_loss > 0 else float("inf")
        m["win_rate_pct"] = len(wins) / len(trades) * 100.0
        m["avg_win"] = float(wins["pnl"].mean()) if len(wins) else 0.0
        m["avg_loss"] = float(losses["pnl"].mean()) if len(losses) else 0.0
        m["expectancy"] = float(trades["pnl"].mean())
        m["total_pnl"] = float(trades["pnl"].sum())
    else:
        m["profit_factor"] = None
        m["win_rate_pct"] = None
        m["avg_win"] = None
        m["avg_loss"] = None
        m["expectancy"] = None
        m["total_pnl"] = 0.0
    return m