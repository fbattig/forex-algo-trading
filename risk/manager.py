"""Position sizing helpers."""
from __future__ import annotations


def position_units(equity: float, risk_per_trade: float, stop_distance: float) -> float:
    """Risk-based sizing: risk `risk_per_trade` fraction of equity over
    `stop_distance` price units. Returns position size in units."""
    if stop_distance <= 0:
        return 0.0
    return (equity * risk_per_trade) / stop_distance