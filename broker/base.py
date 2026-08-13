"""Abstract broker interface."""
from __future__ import annotations


class Broker:
    """Minimal interface every broker adapter must implement."""

    def fetch_candles(self, instrument: str, granularity: str = "D", count: int = 5000):
        raise NotImplementedError

    def place_market_order(self, instrument: str, units: int):
        raise NotImplementedError

    def get_open_positions(self):
        raise NotImplementedError

    def close_position(self, instrument: str):
        raise NotImplementedError