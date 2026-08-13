"""Out-of-sample walk-forward validation."""
from __future__ import annotations

import numpy as np

from backtest.engine import BacktestEngine
from backtest.metrics import compute_metrics


def walk_forward(sig, cfg, n_splits: int = 4):
    """Split the prepared signal frame into n sequential out-of-sample chunks and
    run the backtest on each. Indicators are already warmed up (computed on the
    full series), so each chunk starts with valid signals. Returns a list of
    (start, end, metrics) tuples."""
    n = len(sig)
    edges = np.linspace(0, n, n_splits + 1).astype(int)
    results = []
    for k in range(n_splits):
        test = sig.iloc[edges[k]:edges[k + 1]]
        if len(test) < 100:
            continue
        eng = BacktestEngine(cfg)
        eq = eng.run(test)
        m = compute_metrics(eq["equity"], eng.trades)
        results.append((test.index[0], test.index[-1], m))
    return results