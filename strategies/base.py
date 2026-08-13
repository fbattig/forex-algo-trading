"""Base strategy interface."""
from __future__ import annotations

import pandas as pd


class Strategy:
    name = "base"
    uses_ml = True

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of df augmented with 'signal', 'cross_up', 'cross_down'
        and any indicator columns the engine needs (e.g. 'atr')."""
        raise NotImplementedError